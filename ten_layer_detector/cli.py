"""Command line: generate datasets, run the evaluation protocol, compare models.

    python -m ten_layer_detector.cli generate --out datasets/sim_v1
    python -m ten_layer_detector.cli evaluate --data datasets/sim_v1 --out results/sim_v1
    python -m ten_layer_detector.cli compare  --data datasets/sim_dev --out reports
    python -m ten_layer_detector.cli demo     # one clean and one attacked session, end to end
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

from .config import DEFAULT_CONFIG, ProjectConfig


def _load_config(path: str | None) -> ProjectConfig:
    return ProjectConfig.load(path) if path else DEFAULT_CONFIG


def cmd_generate(args) -> None:
    from .dataset import save_sessions
    from .sim import generate_mixed_dataset

    cfg = _load_config(args.config)
    ds = cfg.dataset
    ds = replace(
        ds,
        **{k: v for k, v in {"n_clean": args.n_clean, "n_per_attack": args.n_per_attack, "seed": args.seed}.items() if v is not None},
    )
    sessions, meta = generate_mixed_dataset(ds.n_clean, ds.n_per_attack, duration_s=ds.duration_s, sample_rate_hz=ds.sample_rate_hz, seed=ds.seed, power_range_db=tuple(args.power_range) if args.power_range else None)
    out = save_sessions(args.out, sessions, meta)
    ProjectConfig(cfg.version, ds, cfg.detector).save(out / "config.json")
    print(f"wrote {len(sessions)} sessions ({sum(len(s) for s in sessions)} rows) to {out}")


def cmd_evaluate(args) -> None:
    from .dataset import load_sessions
    from .evaluate import evaluate_protocol
    from .features import CN0_FEATURES
    from .reporting import overview_table, write_protocol_results

    cfg = _load_config(args.config)
    sessions, meta = load_sessions(args.data)
    full = evaluate_protocol(sessions, meta, config=cfg.detector)
    no_cn0 = None
    if not args.skip_shortcut:
        no_cn0 = evaluate_protocol(sessions, meta, config=replace(cfg.detector, exclude_features=CN0_FEATURES), ablation=False)
    data_cfg = Path(args.data) / "config.json"
    project = json.loads(data_cfg.read_text()) if data_cfg.exists() else None
    paths = write_protocol_results(args.out, full, no_cn0, {"dataset": project, "detector": cfg.to_dict()["detector"], "version": cfg.version})
    print(overview_table(full).round(3).to_string(index=False))
    print(json.dumps(full["vote_vs_best_layer"], indent=1, default=float))
    print("\n".join(f"{k}: {v}" for k, v in paths.items()))


def cmd_compare(args) -> None:
    from .dashboard import build_model_comparison_report

    cfg = _load_config(args.config)
    summary = build_model_comparison_report(args.data, args.out, cfg.detector, workers=args.workers)
    print(json.dumps({"winner": summary["winner"], "paths": summary["paths"]}, indent=1))


def cmd_demo(args) -> None:
    from .pipeline import TenLayerDetector
    from .sim import generate_mixed_dataset, generate_session
    from .splits import split_sessions

    sessions, _ = generate_mixed_dataset(60, 12, seed=args.seed)
    train, cal = split_sessions(sessions, test_fraction=0.3, seed=args.seed)
    det = TenLayerDetector(DEFAULT_CONFIG.detector).fit(train, cal)
    for kind in ("clean", args.attack_type):
        s = generate_session(attack_type=kind, seed=args.seed + 999, session_id=f"demo_{kind}")
        r = det.detect(s)
        onset = s["attack_onset_s"].iloc[0] if kind != "clean" else None
        print(f"{kind:20s} onset={onset} first_alarm={r['first_alarm_s']} named={r['attack_type']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ten-layer GNSS spoofing detector (simulation phase)")
    parser.add_argument("--config", default=None, help="project config JSON (default: built-in config)")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="generate a simulated dataset")
    g.add_argument("--out", default="datasets/sim_v1")
    g.add_argument("--n-clean", type=int, default=None)
    g.add_argument("--n-per-attack", type=int, default=None)
    g.add_argument("--seed", type=int, default=None)
    g.add_argument("--power-range", type=float, nargs=2, metavar=("LO", "HI"), default=None, help="spoofer power range in dB for attacked sessions")
    g.set_defaults(func=cmd_generate)

    e = sub.add_parser("evaluate", help="run the evaluation protocol on a saved dataset")
    e.add_argument("--data", default="datasets/sim_v1")
    e.add_argument("--out", default="results/sim_v1")
    e.add_argument("--skip-shortcut", action="store_true", help="skip the second run without C/N0")
    e.set_defaults(func=cmd_evaluate)

    c = sub.add_parser("compare", help="model comparison report (MODEL_SELECTION.md)")
    c.add_argument("--data", default="datasets/sim_dev")
    c.add_argument("--out", default="reports")
    c.add_argument("--workers", type=int, default=1, help="candidates evaluated in parallel processes")
    c.set_defaults(func=cmd_compare)

    d = sub.add_parser("demo", help="fit on a small dataset and run one clean and one attacked session")
    d.add_argument("--attack-type", default="ramp")
    d.add_argument("--seed", type=int, default=3)
    d.set_defaults(func=cmd_demo)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
