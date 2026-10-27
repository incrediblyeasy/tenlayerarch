"""A5: score the locked v4 configuration and the reported variants once on the fresh test sets.

    python -m ten_layer_detector.v4_test --out results/v4_test.json
Variants are listed in configs/locked_model_v4.json. Fits use sim_v4_val only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .config import ProjectConfig
from .v4_a2 import load_splits
from .v4_a3a4 import build, chosen_cols, rule_kw, temporal_columns
from .v4_study import Data, Rule, Split, calibrate_rule, fa_ci, measure, session_scores


def platform(sid: str) -> str:
    for p in ("multirotor_hover", "multirotor_maneuver", "fixed_wing", "large_slow"):
        if sid.startswith(p):
            return p
    return "?"


def metrics(scorer, rule, split: Split) -> dict:
    summ, per = measure(session_scores(scorer, split), split, rule)
    ct = [o["detected"] for o in per.values() if o["type"] == "consistent_takeover"]
    delays = lambda sel: [o["delay_s"] for k, o in per.items() if o["detected"] and sel(k)]
    out = {
        "detection": summ["all_attacks"]["rate"], "detection_ci95": summ["all_attacks"]["ci95"],
        "n_attacked": summ["all_attacks"]["n"],
        "consistent_takeover": float(np.mean(ct)) if ct else float("nan"), "n_consistent_takeover": len(ct),
        "fa_events": summ["fa_events"], "clean_hours": summ["clean_hours"], "fa_per_hour": summ["false_alarms_per_hour"],
        "fa_upper95": fa_ci(summ["fa_events"], summ["clean_hours"]) if summ["clean_hours"] else float("nan"),
        "delay_median_s": summ["delay_median_s"], "delay_p90_s": summ["delay_p90_s"],
        "per_type": {a: r["rate"] for a, r in summ["per_type"].items()},
        "detection_ordinary": float(np.mean([o["detected"] for k, o in per.items() if "_o_" in k])) if any("_o_" in k for k in per) else float("nan"),
        "detection_matched": float(np.mean([o["detected"] for k, o in per.items() if "_m_" in k])) if any("_m_" in k for k in per) else float("nan"),
        "per_platform": {},
    }
    scores = session_scores(scorer, split)
    for p in ("multirotor_hover", "multirotor_maneuver", "fixed_wing", "large_slow"):
        det = [o["detected"] for k, o in per.items() if platform(k) == p]
        ev = hrs = 0
        for sc, (s, _), act in zip(scores, split.items, split.active):
            if platform(str(s["session_id"].iloc[0])) == p and "label" in s and not s["label"].any():
                from .metrics import rising_edges

                ev += rising_edges(rule.alarm(sc))
                hrs += act.sum() * 0.1 / 3600.0
        out["per_platform"][p] = {"detection": float(np.mean(det)) if det else float("nan"), "fa_per_hour": ev / hrs if hrs else float("nan"), "fa_events": int(ev), "clean_hours": float(hrs)}
    return out


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--out", default="results/v4_test.json")
    args = a.parse_args()
    cfg = ProjectConfig.load("configs/sim_v4.json").detector
    _, splits, _ = load_splits(cfg)
    cols = chosen_cols(splits)
    tr, ca = splits[0], splits[1]
    test = Data("datasets/sim_v4_test", cfg)
    weak = Data("datasets/sim_v4_weaktest", cfg)
    t_split = Split(list(zip(test.sessions, test.feats)), cfg)
    w_split = Split(list(zip(weak.sessions, weak.feats)), cfg)
    from .v4_study import feature_sets

    all_cols = feature_sets(list(tr.items[0][1].columns))["S_all"]
    out = {}

    def score_both(name, scorer, rule, ts=t_split, ws=w_split):
        out[name] = {"main": metrics(scorer, rule, ts), "weak": metrics(scorer, rule, ws)}
        m, w = out[name]["main"], out[name]["weak"]
        print(name, f"det {m['detection']:.3f} FA {m['fa_per_hour']:.2f} (<= {m['fa_upper95']:.2f}) ct {m['consistent_takeover']:.2f} p90 {m['delay_p90_s']:.1f} | weak det {w['detection']:.3f} ct {w['consistent_takeover']:.2f}", flush=True)
        Path(args.out).write_text(json.dumps(out, indent=2, default=float))

    k5 = Rule(cfg=cfg, **rule_kw("persistence_k5"))
    sc = build("M2_ensemble_0.25", cols, splits, cfg)
    score_both("primary_M2_ensemble_0.25", sc, calibrate_rule(sc, Rule(cfg=cfg, **rule_kw("persistence_k5")), ca))
    sc = build("M1_lightgbm", cols, splits, cfg)
    score_both("V1_lightgbm_cusum_p99", sc, calibrate_rule(sc, Rule(cfg=cfg, **rule_kw("cusum_p99.0")), ca))
    sp3, cols3, _ = temporal_columns(splits, cols, cfg)
    sc = build("M1_lightgbm", cols3, sp3, cfg)
    # the test sets get the same trailing-window expansion as the training data

    def expand(sp):
        import pandas as pd

        top = [c for c in cols3 if c.endswith("_m30")]
        top = [c[:-4] for c in top]
        n = 300
        items = []
        for s, f in sp.items:
            g = f.copy()
            for c in top:
                r = pd.Series(f[c].to_numpy(dtype=float)).rolling(n, min_periods=1)
                g[c + "_m30"], g[c + "_x30"] = r.mean().to_numpy(), r.max().to_numpy()
                g[c + "_s30"] = (f[c].to_numpy(dtype=float) - r.apply(lambda v: v[0], raw=True).to_numpy()) / 30.0
            items.append((s, g))
        return Split(items, cfg)

    score_both("V2_temporal", sc, calibrate_rule(sc, Rule(cfg=cfg, **rule_kw("persistence_k5")), sp3[1]), expand(t_split), expand(w_split))
    sc = build("M1_lightgbm", all_cols, splits, cfg)
    score_both("V3_lightgbm_all_features", sc, calibrate_rule(sc, Rule(cfg=cfg, **rule_kw("persistence_k5")), ca))


if __name__ == "__main__":
    main()
