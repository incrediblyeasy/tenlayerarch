"""Write protocol results to disk (IMPLEMENTATION_GUIDE.md section 10)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

import numpy as np
import pandas as pd

from .layers import LayerResult
from .pipeline import EQUAL_VOTE, VOTE, VOTE_FA

WEAK_LAYER_DETECTION = 0.2
NOISY_LAYER_FA_PER_HOUR = 10.0


def summary_table(result: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for name, d in result["detectors"].items():
        base = {
            "detector": name,
            "threshold": d["threshold"],
            "false_alarms_per_hour": d["false_alarms_per_hour"],
            "fa_events": d["fa_events"],
            "clean_hours": d["clean_hours"],
            "clean_sessions_alarmed": d["clean_sessions_alarmed"]["rate"],
            "delay_median_s": d["delay_median_s"],
            "delay_p90_s": d["delay_p90_s"],
        }
        for attack, r in [("all_attacks", d["all_attacks"])] + list(d["per_type"].items()):
            rows.append({**base, "attack_type": attack, "detection_rate": r["rate"], "k": r["k"], "n": r["n"], "ci95_low": r["ci95"][0], "ci95_high": r["ci95"][1]})
    return pd.DataFrame(rows)


def overview_table(result: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for name, d in result["detectors"].items():
        r = d["all_attacks"]
        rows.append({
            "detector": name,
            "detect": r["rate"],
            "ci95": f"{r['ci95'][0]:.2f}-{r['ci95'][1]:.2f}",
            "fa_per_hour": d["false_alarms_per_hour"],
            "clean_alarmed": d["clean_sessions_alarmed"]["rate"],
            "delay_med_s": d["delay_median_s"],
            "delay_p90_s": d["delay_p90_s"],
            **{a: v["rate"] for a, v in d["per_type"].items()},
        })
    return pd.DataFrame(rows)


def shortcut_table(full: Dict[str, Any], no_cn0: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    for name in full["detectors"]:
        a = full["detectors"][name]
        b = no_cn0["detectors"].get(name)
        rows.append({
            "detector": name,
            "detect_all": a["all_attacks"]["rate"],
            "fa_per_hour_all": a["false_alarms_per_hour"],
            "detect_no_cn0": b["all_attacks"]["rate"] if b else np.nan,
            "fa_per_hour_no_cn0": b["false_alarms_per_hour"] if b else np.nan,
            "note": "" if b else no_cn0["not_evaluated"].get(name, "not run"),
        })
    return pd.DataFrame(rows)


def negative_findings(full: Dict[str, Any], no_cn0: Dict[str, Any] | None = None) -> List[str]:
    out = []
    for name, reason in full["not_evaluated"].items():
        out.append(f"Layer {name} was not evaluated: {reason}.")
    layers = [n for n in full["detectors"] if n not in (VOTE, EQUAL_VOTE)]
    for name in layers:
        d = full["detectors"][name]
        det, fa = d["all_attacks"]["rate"], d["false_alarms_per_hour"]
        if det < WEAK_LAYER_DETECTION:
            out.append(f"Layer {name} detects only {det:.2f} of attacks on its own.")
        if fa > NOISY_LAYER_FA_PER_HOUR:
            out.append(f"Layer {name} raises {fa:.1f} false alarms per hour on clean sessions at the frozen threshold.")
    v = full["vote_vs_best_layer"]
    if not v["vote_beats_best_layer"]:
        out.append(
            f"The vote does not beat the best single layer ({v['best_layer']}: detect {v['best_layer_detect']:.2f} at "
            f"{v['best_layer_fa_per_hour']:.1f} FA/h; vote: {v['vote_detect']:.2f} at {v['vote_fa_per_hour']:.1f} FA/h)."
        )
    vd = full["detectors"][VOTE]
    for a, r in vd["per_type"].items():
        if r["rate"] < 0.9:
            out.append(f"The vote detects {r['rate']:.2f} of {a} attacks (95% CI {r['ci95'][0]:.2f}-{r['ci95'][1]:.2f}).")
    if vd["false_alarms_per_hour"] > 1.0:
        out.append(f"At the {full['config']['threshold_percentile']}th-percentile threshold the vote raises {vd['false_alarms_per_hour']:.2f} false alarms/h, above the 1/h target.")
    vf = full["detectors"].get(VOTE_FA)
    if vf is not None:
        target = full["config"].get("fa_per_hour_target", 1.0)
        line = (
            f"At the threshold set for {target:g} FA/h on calibration sessions, the vote detects {vf['all_attacks']['rate']:.2f} "
            f"at {vf['false_alarms_per_hour']:.2f} FA/h on held-out clean sessions ({vf['fa_events']} events in {vf['clean_hours']:.2f} h)."
        )
        if vf["false_alarms_per_hour"] > target:
            line += " The target is not met on the test set."
        out.append(line)
        for a, r in vf["per_type"].items():
            if r["rate"] < 0.9:
                out.append(f"At the false-alarm target the vote detects {r['rate']:.2f} of {a} attacks (95% CI {r['ci95'][0]:.2f}-{r['ci95'][1]:.2f}).")
    for row in full.get("by_power", []):
        if row["n"] and np.isfinite(row[VOTE]) and row[VOTE] < 0.9:
            out.append(f"At spoofer power {row['power_db']} dB the vote detects {row[VOTE]:.2f} (n={row['n']}).")
    acc = full["naming"]["accuracy"]
    if acc["n"]:
        out.append(f"Attack naming is correct for {acc['rate']:.2f} of detected attacks (n={acc['n']}); see the confusion matrix.")
    if no_cn0 is not None:
        n = no_cn0["detectors"][VOTE]
        out.append(
            f"Without C/N0 features the vote detects {n['all_attacks']['rate']:.2f} at {n['false_alarms_per_hour']:.2f} FA/h "
            f"(with C/N0: {vd['all_attacks']['rate']:.2f} at {vd['false_alarms_per_hour']:.2f} FA/h)."
        )
    out.append("All results are on simulated data. Clock, sensor and spoofer parameters are assumptions until calibrated on the bench.")
    return out


def write_protocol_results(
    out_dir: str | Path,
    full: Dict[str, Any],
    no_cn0: Dict[str, Any] | None = None,
    project_config: Dict[str, Any] | None = None,
) -> Dict[str, str]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {}
    summary_table(full).to_csv(out / "summary.csv", index=False)
    paths["summary"] = str(out / "summary.csv")
    pd.DataFrame(full["ablation"]).to_csv(out / "ablation.csv", index=False)
    paths["ablation"] = str(out / "ablation.csv")
    if full.get("by_power"):
        pd.DataFrame(full["by_power"]).to_csv(out / "by_power.csv", index=False)
        paths["by_power"] = str(out / "by_power.csv")
    if no_cn0 is not None:
        shortcut_table(full, no_cn0).to_csv(out / "shortcut.csv", index=False)
        paths["shortcut"] = str(out / "shortcut.csv")
    (out / "negative.md").write_text(
        "# Negative results and limits\n\n" + "\n".join(f"- {line}" for line in negative_findings(full, no_cn0)) + "\n",
        encoding="utf-8",
    )
    paths["negative"] = str(out / "negative.md")
    frozen = {
        "project_config": project_config,
        "protocol_config": full["config"],
        "thresholds": {k: v["threshold"] for k, v in full["detectors"].items()},
        "vote_weights": full["vote_weights"],
        "counts": full["counts"],
        "not_evaluated": full["not_evaluated"],
    }
    (out / "config_frozen.json").write_text(json.dumps(frozen, indent=2, default=float), encoding="utf-8")
    paths["config_frozen"] = str(out / "config_frozen.json")
    serialisable = {k: v for k, v in full.items() if k != "detector"}
    (out / "protocol.json").write_text(json.dumps(serialisable, indent=1, default=float), encoding="utf-8")
    paths["protocol"] = str(out / "protocol.json")
    return paths


def build_summary_report(results: Iterable[LayerResult]) -> str:
    lines = ["# Layer Summary", ""]
    for r in results:
        lines.append(f"- {r.name}: score {r.score:.4f} ({'ALARM' if r.alarmed else 'no alarm'}, threshold={r.threshold:.3f})")
    return "\n".join(lines)
