"""FALSE_ALARM_FIX_PLAN.md section 3: read-only diagnosis of the v4 primary model's false alarms.

    python -m ten_layer_detector.v5_diag --out results/v5_diagnosis.json
Refits the locked primary configuration on sim_v4_val (same splits as v4_test.py), checks that it
reproduces the 55 test false alarms, then does D1 (mix), D2 (event analysis), D3 (per-type
thresholds, not used for any alarm), D4 (intervals). Changes nothing in the locked model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .config import ProjectConfig
from .layers.base import is_clean_session
from .metrics import rising_edges
from .v4_a2 import load_splits
from .v4_a3a4 import build, chosen_cols, rule_kw
from .v4_study import Data, Rule, Split, calibrate_rule, session_scores
from .v4_test import platform

PLATFORMS = ("multirotor_hover", "multirotor_maneuver", "fixed_wing", "large_slow")


def split_mix(split: Split):
    out = {p: {"clean_sessions": 0, "clean_hours": 0.0, "attacked_sessions": 0} for p in PLATFORMS}
    for (s, _), act in zip(split.items, split.active):
        p = platform(str(s["session_id"].iloc[0]))
        if is_clean_session(s):
            out[p]["clean_sessions"] += 1
            out[p]["clean_hours"] += float(act.sum() * 0.1 / 3600.0)
        else:
            out[p]["attacked_sessions"] += 1
    return out


def poisson_ci(k, h):
    from scipy.stats import chi2

    lo = chi2.ppf(0.025, 2 * k) / 2 / h if k else 0.0
    return float(lo), float(chi2.ppf(0.975, 2 * (k + 1)) / 2 / h)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out", default="results/v5_diagnosis.json")
    args = a.parse_args()
    cfg = ProjectConfig.load("configs/sim_v4.json").detector
    _, splits, _ = load_splits(cfg)
    tr, ca, va, weak, fah = splits
    cols = chosen_cols(splits)
    scorer = build("M2_ensemble_0.25", cols, splits, cfg)
    rule = calibrate_rule(scorer, Rule(cfg=cfg, **rule_kw("persistence_k5")), ca)
    test = Data("datasets/sim_v4_test", cfg)
    t_split = Split(list(zip(test.sessions, test.feats)), cfg)
    res = {"pooled_threshold": rule.thr}

    # D1
    res["D1_mix"] = {"train": split_mix(tr), "calibration": split_mix(ca), "validation": split_mix(va), "fahold": split_mix(fah), "test": split_mix(t_split)}

    # reproduce the test false alarms and collect events
    scores = session_scores(scorer, t_split)
    events, per_plat = [], {p: {"events": 0, "hours": 0.0} for p in PLATFORMS}
    non_alarm = {p: [] for p in PLATFORMS}
    rng = np.random.default_rng(0)
    for sc, (s, f), act in zip(scores, t_split.items, t_split.active):
        if not is_clean_session(s):
            continue
        p = platform(str(s["session_id"].iloc[0]))
        alarm = rule.alarm(sc)
        per_plat[p]["hours"] += act.sum() * 0.1 / 3600.0
        per_plat[p]["events"] += rising_edges(alarm)
        vn, ve = s["vel_n_mps"].to_numpy(float), s["vel_e_mps"].to_numpy(float)
        speed = np.hypot(vn, ve)
        acc = np.r_[0.0, np.diff(speed)] / 0.1
        yaw = np.unwrap(s["yaw_rad"].to_numpy(float))
        turn = np.abs(np.r_[0.0, np.diff(yaw)]) / 0.1
        F = f[cols].to_numpy(float)
        idx = np.flatnonzero(alarm[1:] & ~alarm[:-1]) + 1
        if alarm.size and alarm[0]:
            idx = np.r_[0, idx]
        for i in idx:
            events.append({"platform": p, "session": str(s["session_id"].iloc[0]), "row": int(i), "t_s": float(s["t_gnss_s"].iloc[i]),
                           "speed": float(speed[i]), "acc": float(acc[i]), "turn": float(turn[i]), "score": float(sc[i]),
                           "features": {c: float(F[i, j]) for j, c in enumerate(cols)}})
        ok = np.flatnonzero(act & ~alarm)
        pick = rng.choice(ok, size=min(30, len(ok)), replace=False)
        for i in pick:
            non_alarm[p].append({"speed": float(speed[i]), "acc": float(acc[i]), "turn": float(turn[i]), "features": {c: float(F[i, j]) for j, c in enumerate(cols)}})
    res["reproduced_events"] = {"total": int(sum(v["events"] for v in per_plat.values())), "per_platform": per_plat}

    # D2: where does each event sit among non-alarm rows of the same platform?
    d2 = {}
    for p in PLATFORMS:
        ev = [e for e in events if e["platform"] == p]
        ref = non_alarm[p]
        row = {"n_events": len(ev)}
        for key in ("speed", "acc", "turn"):
            r = np.array([x[key] for x in ref])
            row[f"{key}_event_median"] = float(np.median([e[key] for e in ev])) if ev else float("nan")
            row[f"{key}_nonalarm_median"] = float(np.median(r))
            row[f"{key}_event_pctile_in_nonalarm"] = float(np.mean([np.mean(r <= e[key]) for e in ev])) if ev else float("nan")
        # features: median percentile of event values among non-alarm rows, per feature
        pct = {}
        for c in cols:
            r = np.array([x["features"][c] for x in ref])
            pct[c] = float(np.median([np.mean(r <= e["features"][c]) for e in ev])) if ev else float("nan")
        row["feature_pctile_median"] = dict(sorted(pct.items(), key=lambda kv: -(kv[1] if kv[1] == kv[1] else 0))[:6])
        d2[p] = row
    res["D2_events"] = d2
    res["D2_session_spread"] = {"sessions_with_events": len({e["session"] for e in events}), "events": len(events),
                                "events_per_session_max": int(max([sum(1 for x in events if x["session"] == s) for s in {e["session"] for e in events}] or [0]))}

    # D3: threshold each platform would get from its own clean calibration sessions (diagnosis only)
    d3 = {}
    sc_ca = session_scores(scorer, ca)
    for p in PLATFORMS:
        sel = [(v, (s, f), a_) for v, (s, f), a_ in zip(sc_ca, ca.items, ca.active) if is_clean_session(s) and platform(str(s["session_id"].iloc[0])) == p]
        r = Rule(cfg=cfg, **rule_kw("persistence_k5"))
        hours = sum(a_.sum() * 0.1 / 3600.0 for _, _, a_ in sel)
        r.fit([v for v, _, _ in sel], hours)
        pooled_events = sum(rising_edges(rule.alarm(v)) for v, _, _ in sel)
        d3[p] = {"clean_sessions": len(sel), "clean_hours": float(hours), "own_threshold": r.thr, "pooled_threshold": rule.thr,
                 "allowed_events_at_target": float(cfg.fa_per_hour_target * hours), "calibration_events_at_pooled_threshold": int(pooled_events)}
    res["D3_thresholds"] = d3

    # D4: intervals and a test of fixed wing against the rest
    from scipy.stats import binomtest

    d4 = {}
    for p in PLATFORMS:
        k, h = per_plat[p]["events"], per_plat[p]["hours"]
        d4[p] = {"events": k, "hours": float(h), "rate": k / h, "ci95": poisson_ci(k, h)}
    fw = per_plat["fixed_wing"]
    rest_k = sum(v["events"] for p, v in per_plat.items() if p != "fixed_wing")
    rest_h = sum(v["hours"] for p, v in per_plat.items() if p != "fixed_wing")
    pr = fw["hours"] / (fw["hours"] + rest_h)
    d4["fixed_wing_vs_rest_binomial_p"] = float(binomtest(fw["events"], fw["events"] + rest_k, pr, alternative="greater").pvalue)
    res["D4_intervals"] = d4
    Path(args.out).write_text(json.dumps(res, indent=2, default=float))
    print(json.dumps({k: v for k, v in res.items() if k in ("pooled_threshold", "reproduced_events", "D3_thresholds", "D4_intervals")}, indent=1, default=float))


if __name__ == "__main__":
    main()
