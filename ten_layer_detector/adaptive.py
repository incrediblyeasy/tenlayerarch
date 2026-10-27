"""White-box adaptive attacker (SIMULATOR_IMPROVEMENTS.md, C2).

For each simulated world the attacker tries every value of one attack parameter on a grid and
keeps the largest value the trained detector does not alarm on after onset.

    python -m ten_layer_detector.adaptive --config configs/sim_v3.json --select-data datasets/sim_fa2 --out results/c2_adaptive.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .config import ProjectConfig
from .dataset import load_sessions
from .features import available_features, compute_features
from .layers.base import persistent_alarm
from .model_selection import _fit, _Rows, _score, _threshold
from .sim import generate_session
from .splits import split_three_way

ONSET_S, DURATION_S = 20.0, 60.0
FAMILIES = {
    "ramp": ("rate_mps", [0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 1.5, 2.0]),
    "consistent_takeover": ("accel_mps2", [0.01, 0.02, 0.05, 0.1, 0.15, 0.2, 0.3]),
}


def final_offset_m(family: str, value: float, meta: dict) -> float:
    tau = DURATION_S - ONSET_S
    if family == "ramp":
        return value * tau
    t_acc = meta["accel_s"]
    ta = min(tau, t_acc)
    return 0.5 * value * ta**2 + value * t_acc * max(tau - t_acc, 0.0)


def build(cfg, select_data: str, model: str = "lightgbm"):
    sessions, _ = load_sessions(select_data)
    train, cal, _ = split_three_way(sessions, cfg.train_fraction, cfg.calibration_fraction, seed=cfg.split_seed)
    cols = [c for c in available_features(train[0]) if c not in cfg.exclude_features]
    rows = lambda ss: _Rows(ss, [compute_features(s, None, cfg) for s in ss], cols, cfg)
    mdl = _fit(model, rows(train), cfg)
    thr = _threshold(mdl, model, rows(cal), cfg)
    return mdl, thr, cols, model


def detected(mdl, model, thr, cols, cfg, session) -> bool:
    r = _Rows([session], [compute_features(session, None, cfg)], cols, cfg)
    sc = _score(mdl, model, r.X[0])
    sc[~r.active[0]] = -np.inf
    alarm = persistent_alarm(sc, thr, cfg.persistence_k)
    return bool(alarm[session["t_gnss_s"].to_numpy() >= ONSET_S].any())


def run(config: str, select_data: str, n_worlds: int, matched: bool, model: str = "lightgbm") -> dict:
    cfg = ProjectConfig.load(config).detector
    mdl, thr, cols, model = build(cfg, select_data, model)
    seeds = np.random.SeedSequence(777).generate_state(n_worlds)
    out = {}
    for family, (param, grid) in FAMILIES.items():
        det = np.zeros((n_worlds, len(grid)), dtype=bool)
        offs = np.zeros((n_worlds, len(grid)))
        for w, seed in enumerate(seeds):
            for g, value in enumerate(grid):
                attacker = {param: value}
                if matched:
                    attacker.update(matched_power=True, match_tolerance_db=1.0)
                s, meta = generate_session(DURATION_S, 10.0, family, ONSET_S, f"{family}_{w}_{g}", int(seed), attacker=attacker, return_metadata=True)
                det[w, g] = detected(mdl, model, thr, cols, cfg, s)
                offs[w, g] = final_offset_m(family, value, meta)
        best = np.where(~det, offs, 0.0).max(axis=1)  # largest undetected final offset per world
        out[family] = {
            "parameter": param, "grid": grid,
            "detection_by_value": det.mean(axis=0).round(3).tolist(),
            "attacker_finds_undetected": float((best > 0).mean()),
            "undetected_offset_ge_25m": float((best >= 25).mean()),
            "undetected_offset_ge_50m": float((best >= 50).mean()),
            "undetected_offset_ge_100m": float((best >= 100).mean()),
            "undetected_offset_median_m": float(np.median(best)),
            "undetected_offset_p90_m": float(np.percentile(best, 90)),
            "max_offset_on_grid_m": float(offs.max()),
        }
    return {"matched_power": matched, "n_worlds": n_worlds, "threshold": thr, "families": out}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--select-data", required=True)
    p.add_argument("--worlds", type=int, default=150)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    res = {v: run(a.config, a.select_data, a.worlds, matched=(v == "matched")) for v in ("default", "matched")}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
