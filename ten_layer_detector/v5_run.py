"""v5 false-alarm fix (configs/v5_plan.json): threshold arms for the locked v4 primary scorer.

    python -m ten_layer_detector.v5_run val     # choose between A4 and A1 on sim_v5_val
    python -m ten_layer_detector.v5_run test    # open sim_v5_test and sim_v5_weaktest once
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from .config import ProjectConfig
from .layers.base import is_clean_session, persistent_alarm
from .metrics import fa_target_threshold, rising_edges, session_outcome, summarize_outcomes
from .splits import session_type
from .v4_a2 import load_splits
from .v4_a3a4 import build, chosen_cols, rule_kw
from .v4_study import Data, Rule, Split, calibrate_rule, fa_ci, session_scores
from .v4_test import platform

PLATFORMS = ("multirotor_hover", "multirotor_maneuver", "fixed_wing", "large_slow")
K = 5


def fit_threshold(cfg, scores, hours):
    pooled = np.concatenate([v[np.isfinite(v)] for v in scores])
    start = float(np.percentile(pooled, cfg.threshold_percentile))
    return fa_target_threshold(scores, hours, start, cfg.fa_per_hour_target, K)


def arm_thresholds(cfg, scorer, a0_rule, cal_split):
    """Thresholds per platform for the three arms."""
    sc = session_scores(scorer, cal_split)
    clean = [(v, platform(str(s["session_id"].iloc[0])), a) for v, (s, _), a in zip(sc, cal_split.items, cal_split.active) if is_clean_session(s)]
    hours = lambda sel: sum(a.sum() * 0.1 / 3600.0 for _, _, a in sel)
    pooled = fit_threshold(cfg, [v for v, _, _ in clean], hours(clean))
    out = {"A0_baseline": {p: a0_rule.thr for p in PLATFORMS}, "A4_larger_calibration": {p: pooled for p in PLATFORMS}, "A1_per_type_threshold": {}}
    calib_hours = {"pooled": hours(clean)}
    for p in PLATFORMS:
        sel = [x for x in clean if x[1] == p]
        out["A1_per_type_threshold"][p] = fit_threshold(cfg, [v for v, _, _ in sel], hours(sel))
        calib_hours[p] = hours(sel)
    return out, calib_hours


def evaluate_arm(scores, split: Split, thr: dict):
    clean, attacked, per_plat = [], {}, {p: {"events": 0, "hours": 0.0, "det": []} for p in PLATFORMS}
    ct = []
    for sc, (s, _), act in zip(scores, split.items, split.active):
        p = platform(str(s["session_id"].iloc[0]))
        alarm = persistent_alarm(sc, thr[p], K)
        t = s["t_gnss_s"].to_numpy(dtype=float)
        if is_clean_session(s):
            o = session_outcome(alarm, t, None, act)
            clean.append(o)
            per_plat[p]["events"] += o["fa_events"]
            per_plat[p]["hours"] += o["clean_s"] / 3600.0
        else:
            o = session_outcome(alarm, t, float(s["attack_onset_s"].iloc[0]), act)
            attacked.setdefault(session_type(s), []).append(o)
            per_plat[p]["det"].append(o["detected"])
            if session_type(s) == "consistent_takeover":
                ct.append(o["detected"])
    m = summarize_outcomes(clean, attacked)
    return {
        "detection": m["all_attacks"]["rate"], "detection_ci95": m["all_attacks"]["ci95"], "consistent_takeover": float(np.mean(ct)) if ct else float("nan"),
        "fa_events": m["fa_events"], "clean_hours": m["clean_hours"], "fa_per_hour": m["false_alarms_per_hour"],
        "fa_upper95": fa_ci(m["fa_events"], m["clean_hours"]), "delay_median_s": m["delay_median_s"], "delay_p90_s": m["delay_p90_s"],
        "per_type": {a: r["rate"] for a, r in m["per_type"].items()},
        "per_platform": {p: {"fa_events": v["events"], "clean_hours": v["hours"], "fa_per_hour": v["events"] / v["hours"] if v["hours"] else float("nan"),
                             "fa_upper95": fa_ci(v["events"], v["hours"]) if v["hours"] else float("nan"),
                             "detection": float(np.mean(v["det"])) if v["det"] else float("nan")} for p, v in per_plat.items()},
    }


def setup():
    cfg = ProjectConfig.load("configs/sim_v4.json").detector
    _, splits, _ = load_splits(cfg)
    cols = chosen_cols(splits)
    scorer = build("M2_ensemble_0.25", cols, splits, cfg)
    a0 = calibrate_rule(scorer, Rule(cfg=cfg, **rule_kw("persistence_k5")), splits[1])
    cal = Data("datasets/sim_v5_cal", cfg)
    thr, hours = arm_thresholds(cfg, scorer, a0, Split(list(zip(cal.sessions, cal.feats)), cfg))
    return cfg, scorer, thr, hours


def load(path, cfg):
    d = Data(path, cfg)
    return Split(list(zip(d.sessions, d.feats)), cfg)


def main():
    stage = sys.argv[1]
    cfg, scorer, thr, hours = setup()
    out = {"thresholds": thr, "calibration_hours": hours}
    if stage == "val":
        sp = load("datasets/sim_v5_val", cfg)
        sc = session_scores(scorer, sp)
        out["val"] = {arm: evaluate_arm(sc, sp, t) for arm, t in thr.items()}
        base = out["val"]["A0_baseline"]
        elig = {}
        for arm in ("A4_larger_calibration", "A1_per_type_threshold"):
            r = out["val"][arm]
            mx = max(v["fa_per_hour"] for v in r["per_platform"].values())
            ok = mx <= 0.8 and r["detection"] >= base["detection"] - 0.02 and r["delay_p90_s"] <= base["delay_p90_s"] + 1.0
            out["val"][arm]["rule"] = {"max_per_type_fa": mx, "eligible": bool(ok)}
            if ok:
                elig[arm] = mx
        out["chosen"] = min(elig, key=lambda a: (elig[a], a != "A4_larger_calibration")) if elig else None
        Path("results/v5_val.json").write_text(json.dumps(out, indent=2, default=float))
        for arm, r in out["val"].items():
            print(arm, f"det {r['detection']:.3f} FA {r['fa_per_hour']:.2f}", {p[:6]: round(v['fa_per_hour'], 2) for p, v in r["per_platform"].items()}, "p90", round(r["delay_p90_s"], 1), r.get("rule"))
        print("chosen:", out["chosen"])
    else:
        chosen = json.loads(Path("results/v5_val.json").read_text())["chosen"]
        out["chosen"] = chosen
        for name, path in (("main", "datasets/sim_v5_test"), ("weak", "datasets/sim_v5_weaktest")):
            sp = load(path, cfg)
            sc = session_scores(scorer, sp)
            out[name] = {arm: evaluate_arm(sc, sp, thr[arm]) for arm in ("A0_baseline", chosen) if arm}
            for arm, r in out[name].items():
                print(name, arm, f"det {r['detection']:.3f} FA {r['fa_per_hour']:.2f} (<= {r['fa_upper95']:.2f})", {p[:6]: (v['fa_events'], round(v['fa_upper95'], 2)) for p, v in r["per_platform"].items()}, "p90", round(r["delay_p90_s"], 1), "ct", round(r["consistent_takeover"], 2))
        Path("results/v5_test.json").write_text(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
