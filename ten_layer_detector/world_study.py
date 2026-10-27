"""Train a detector in one simulated world and score it in others (SIMULATOR_IMPROVEMENTS.md).

A plan file lists arms. Each arm trains LightGBM (all features, and without signal-strength
features) on a training world, calibrates the alarm threshold on clean calibration sessions of
that world, then scores fresh test worlds with identical measures. Datasets are generated in
memory from seeds, so every number can be rebuilt from the plan file.

    python -m ten_layer_detector.world_study --plan configs/simplan_c3.json --out results/ws_c3.json
"""
from __future__ import annotations

import argparse
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.stats import chi2

from .config import ProjectConfig
from .features import available_features, compute_features
from .model_selection import STRENGTH_FEATURES, _fit, _Rows, _threshold, _validate
from .sim import generate_mixed_dataset
from .splits import split_three_way

LEVEL_IMU = ["imu_resid_mps2", "imu_resid_long_mps2"]
ATT_IMU = ["imu_att_resid_mps2", "imu_att_resid_long_mps2"]


def make(spec: dict, n_clean: int, n_per_attack: int):
    sessions, _ = generate_mixed_dataset(
        n_clean, n_per_attack, seed=spec["seed"], realism=spec.get("realism"),
        attacker_overrides=spec.get("attacker"), matched_power=spec.get("matched_power", False),
    )
    return sessions


def fa_range(events: int, hours: float):
    lo = chi2.ppf(0.025, 2 * events) / 2 / hours if events else 0.0
    return float(lo), float(chi2.ppf(0.975, 2 * (events + 1)) / 2 / hours)


def run_arm(arm: dict, cfg0, sizes: dict) -> dict:
    cfg = replace(cfg0, exclude_features=tuple(arm.get("features_exclude", ())))
    sizes = {**sizes, **arm.get("sizes", {})}
    train_sessions = []
    specs = arm["train"] if isinstance(arm["train"], list) else [arm["train"]]
    for spec in specs:
        part = make(spec, sizes["train_clean"], sizes["train_per_attack"])
        if len(specs) > 1:  # worlds share session ids; keep them unique when pooled
            for s in part:
                s["session_id"] = f"w{spec['seed']}_" + s["session_id"].astype(str)
        train_sessions += part
    tr, ca, _ = split_three_way(train_sessions, cfg.train_fraction, cfg.calibration_fraction, seed=cfg.split_seed)
    feats = {}

    def rows(ss, cols):
        for s in ss:
            if id(s) not in feats:
                feats[id(s)] = compute_features(s, None, cfg)
        return _Rows(ss, [feats[id(s)] for s in ss], cols, cfg)

    cols_full = [c for c in available_features(tr[0]) if c not in cfg.exclude_features]
    if arm.get("features_only"):  # a single group of cues on its own
        cols_full = [c for c in cols_full if c in arm["features_only"]]
    cols_ns = [c for c in cols_full if c not in STRENGTH_FEATURES]
    models = {}
    for label, cols in (("full", cols_full), ("no_strength", cols_ns)) if cols_ns else (("full", cols_full),):
        mdl = _fit("lightgbm", rows(tr, cols), cfg)
        models[label] = (mdl, cols, _threshold(mdl, "lightgbm", rows(ca, cols), cfg))
    out = {"arm": arm["name"], "n_features_full": len(cols_full), "features_excluded": list(cfg.exclude_features), "tests": {}}
    for test in arm["tests"]:
        sessions = make(test, sizes["test_clean"], sizes["test_per_attack"])
        res = {}
        for label, (mdl, cols, thr) in models.items():
            m, _, _, _ = _validate(mdl, "lightgbm", thr, rows(sessions, cols), cfg)
            lo, hi = fa_range(m["fa_events"], m["clean_hours"])
            res[label] = {
                "detection": m["all_attacks"]["rate"], "detection_ci95": m["all_attacks"]["ci95"],
                "fa_per_hour": m["false_alarms_per_hour"], "fa_events": m["fa_events"], "clean_hours": m["clean_hours"], "fa_range": [lo, hi],
                "delay_median_s": m["delay_median_s"], "delay_p90_s": m["delay_p90_s"],
                "per_type": {k: v["rate"] for k, v in m["per_type"].items()},
            }
        out["tests"][test["name"]] = res
        print(f"[{arm['name']}] {test['name']}: " + "; ".join(f"{k} DR {v['detection']:.3f} FA {v['fa_per_hour']:.2f}/h" for k, v in res.items()), flush=True)
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--plan", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--only", default=None, help="comma-separated arm names")
    a = p.parse_args()
    plan = json.loads(Path(a.plan).read_text())
    cfg0 = ProjectConfig.load(plan.get("config", "configs/sim_v3.json")).detector
    sizes = plan["sizes"]
    out_path = Path(a.out)
    results = json.loads(out_path.read_text()) if out_path.exists() else {}
    for arm in plan["arms"]:
        if a.only and arm["name"] not in a.only.split(","):
            continue
        if arm["name"] in results:
            continue  # resumable: saved arms are kept
        results[arm["name"]] = run_arm(arm, cfg0, sizes)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2, default=float), encoding="utf-8")


if __name__ == "__main__":
    main()
