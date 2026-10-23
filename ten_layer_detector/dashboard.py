"""Model-comparison report: charts, JSON summary and an HTML page.

Usage:
    ten-layer-dashboard --data datasets/sim_dev --out reports
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .config import DEFAULT_DETECTOR_CONFIG, ProjectConfig
from .dataset import load_sessions
from .model_selection import MODEL_CANDIDATES, evaluate_model_candidates, is_eligible, select_model
from .splits import split_three_way

SLOW_FIRST = ("one_class_svm", "rbf_svm", "knn", "mlp", "random_forest", "extra_trees")

COLUMNS = [
    ("dr_validation", "DR (T1)"),
    ("far_per_hour", "FA/h (T2)"),
    ("dr_no_strength", "DR no C/N0, DOP (T3)"),
    ("dr_weak", "DR weak <1 dB (T4)"),
    ("dr_unseen", "DR unseen type (T5)"),
    ("delay_median_s", "Delay median s (T6)"),
    ("ms_per_decision", "ms/decision (T7)"),
    ("t8_dr_mean", "DR mean, 5 seeds (T8)"),
    ("t8_dr_std", "DR std (T8)"),
    ("t8_far_mean", "FA/h mean (T8)"),
    ("t8_far_std", "FA/h std (T8)"),
]


def _fmt(v: Any) -> str:
    if isinstance(v, (bool, np.bool_)):
        return "yes" if v else "no"
    if isinstance(v, (float, np.floating)):
        return "n/a" if not np.isfinite(v) else f"{v:.3f}"
    return html_lib.escape(str(v))


def write_report(results: Sequence[dict], winner: str | None, dataset_meta: dict, out_dir: str | Path) -> dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results).sort_values("dr_validation", ascending=False)
    colors = ["#2e7d32" if m == winner else "#5c7cfa" for m in df["model_name"]]

    paths = {}
    for col, label, fname in (
        ("dr_validation", "Detection rate (validation sessions)", "model_detection_rate.png"),
        ("far_per_hour", "False alarms per hour (clean validation sessions)", "model_false_alarm_rate.png"),
    ):
        fig, ax = plt.subplots(figsize=(10, 4.5))
        ax.bar(df["model_name"], df[col], color=colors)
        ax.set_title(label)
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        fig.savefig(out / fname, dpi=150)
        plt.close(fig)
        paths[col] = str(out / fname)

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(df["far_per_hour"], df["dr_validation"], s=80, c=colors)
    for _, r in df.iterrows():
        ax.annotate(r["model_name"], (r["far_per_hour"], r["dr_validation"]), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.axvline(1.0, color="grey", ls="--", lw=1)
    ax.set_xlabel("False alarms per hour")
    ax.set_ylabel("Detection rate")
    ax.set_title("Detection vs false alarms (dashed: eligibility limit 1/h)")
    fig.tight_layout()
    fig.savefig(out / "model_tradeoff.png", dpi=150)
    plt.close(fig)
    paths["tradeoff"] = str(out / "model_tradeoff.png")

    summary = {"dataset": dataset_meta, "winner_model": winner, "results": results}
    (out / "model_summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    paths["summary_json"] = str(out / "model_summary.json")

    header = "".join(f"<th>{h}</th>" for _, h in COLUMNS)
    body = "".join(
        f"<tr{' class=win' if r['model_name'] == winner else ''}><td>{r['model_name']}</td>"
        + "".join(f"<td>{_fmt(r[c])}</td>" for c, _ in COLUMNS)
        + f"<td>{_fmt(r['eligible'])}</td></tr>"
        for r in df.to_dict("records")
    )
    meta_rows = "".join(f"<tr><td>{html_lib.escape(str(k))}</td><td>{_fmt(v)}</td></tr>" for k, v in dataset_meta.items())
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Model comparison</title>
<style>body{{font-family:system-ui,sans-serif;margin:2rem;max-width:1100px}}table{{border-collapse:collapse;margin:1rem 0}}
td,th{{border:1px solid #ccc;padding:4px 8px;text-align:right}}td:first-child,th:first-child{{text-align:left}}
tr.win{{background:#e8f5e9}}img{{max-width:100%}}</style></head><body>
<h1>Model comparison (simulated data)</h1>
<p>Winner by the rule in MODEL_SELECTION.md section 6: <b>{winner or "none eligible"}</b>. Simulation only; not a bench or flight result.</p>
<h2>Dataset</h2><table>{meta_rows}</table>
<h2>Results (validation sessions)</h2><table><tr><th>Model</th>{header}<th>Eligible</th></tr>{body}</table>
<img src="model_detection_rate.png" alt="Detection rate"><img src="model_false_alarm_rate.png" alt="False alarms per hour"><img src="model_tradeoff.png" alt="Trade-off">
</body></html>"""
    (out / "model_dashboard.html").write_text(page, encoding="utf-8")
    paths["html"] = str(out / "model_dashboard.html")
    return paths


def _run_one(args):
    """Worker: evaluate one candidate and save its result (skipped when already saved)."""
    name, data_dir, partial_dir, cfg = args
    out = Path(partial_dir) / f"{name}.json"
    if out.exists():
        return name, json.loads(out.read_text(encoding="utf-8"))
    sessions, metadata = load_sessions(data_dir)
    train, cal, val = split_three_way(sessions, cfg.train_fraction, cfg.calibration_fraction, seed=cfg.split_seed)
    t0 = time.time()
    result = evaluate_model_candidates(train, cal, val, metadata, cfg=cfg, candidates=[name])[0]
    result["wall_s"] = time.time() - t0
    out.write_text(json.dumps(result, default=float), encoding="utf-8")
    print(f"done {name} in {result['wall_s'] / 60:.1f} min", flush=True)
    return name, result


def build_model_comparison_report(data_dir: str | Path, output_dir: str | Path, cfg=DEFAULT_DETECTOR_CONFIG, workers: int = 1) -> dict[str, Any]:
    """Each candidate's result is saved to <output_dir>/partial/<name>.json as soon as it
    finishes; a rerun reuses saved results, so an interrupted run loses at most the models in flight."""
    sessions, _ = load_sessions(data_dir)
    train, cal, val = split_three_way(sessions, cfg.train_fraction, cfg.calibration_fraction, seed=cfg.split_seed)
    partial = Path(output_dir) / "partial"
    partial.mkdir(parents=True, exist_ok=True)
    # Slowest first so the long models start immediately.
    order = sorted(MODEL_CANDIDATES, key=lambda n: n not in SLOW_FIRST)
    jobs = [(n, str(data_dir), str(partial), cfg) for n in order]
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            done = dict(pool.map(_run_one, jobs))
    else:
        done = dict(map(_run_one, jobs))
    results = [done[n] for n in MODEL_CANDIDATES]
    for r in results:
        r["eligible"] = is_eligible(r)  # re-derived, so saved results follow the current rule
    winner = select_model(results)
    meta = {
        "data": str(data_dir),
        "sessions_train": len(train),
        "sessions_calibration": len(cal),
        "sessions_validation": len(val),
        "threshold_percentile": cfg.threshold_percentile,
        "persistence_k": cfg.persistence_k,
    }
    paths = write_report(results, winner, meta, output_dir)
    return {"winner": winner, "results": results, "paths": paths, "dataset": meta}


def main() -> None:
    parser = argparse.ArgumentParser(description="Model-comparison report on a saved dataset")
    parser.add_argument("--data", default="datasets/sim_dev")
    parser.add_argument("--out", default="reports")
    parser.add_argument("--config", default=None)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    cfg = ProjectConfig.load(args.config).detector if args.config else DEFAULT_DETECTOR_CONFIG
    summary = build_model_comparison_report(args.data, args.out, cfg, workers=args.workers)
    print(json.dumps({"winner": summary["winner"], "paths": summary["paths"]}, indent=2))


if __name__ == "__main__":
    main()
