"""A3 decision logic and A4 model candidates on validation data (configs/model_grid_v4.json,
selection_rule_v4.json). Reads the feature set chosen in A2 from results/v4_a2_features.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ProjectConfig
from .model_selection import STRENGTH_FEATURES, UNSUPERVISED
from .splits import session_type
from .v4_a2 import load_splits
from .v4_study import Ensemble, Rule, Scorer, Split, calibrate_rule, evaluate, run

A2 = Path("results/v4_a2_features.json")
A3 = Path("results/v4_a3_decision.json")
A4 = Path("results/v4_a4_models.json")


def chosen_cols(splits):
    from .v4_study import feature_sets

    res = json.loads(A2.read_text())
    return feature_sets(list(splits[0].items[0][1].columns))[res["chosen_set"]]


def a3(cfg, splits, cols):
    tr, ca, va, weak, fah = splits
    scorer = Scorer("lightgbm", cols, cfg).fit(tr)
    kws = [{"kind": "persistence", "k": 3}, {"kind": "persistence", "k": 5}, {"kind": "persistence", "k": 10},
           {"kind": "cusum", "ref_pct": 90.0}, {"kind": "cusum", "ref_pct": 99.0}, {"kind": "conformal", "k": 5, "alpha": 0.01}]
    out = {}
    for kw in kws:
        rule = calibrate_rule(scorer, Rule(cfg=cfg, **kw), ca)
        m = evaluate(scorer, rule, ca, va, weak, fah)
        out[rule.label] = {**m, "threshold": rule.thr}
        print(rule.label, {k: round(v, 3) for k, v in m.items() if not isinstance(v, dict)}, flush=True)
    base = out["persistence_k5"]
    cand = {k: v for k, v in out.items() if v["far_hold"] <= 0.7 and v["dr_val"] >= base["dr_val"] - 0.01}
    best = min(cand, key=lambda k: out[k]["delay_p90_s"]) if cand else "persistence_k5"
    chosen = best if out[best]["delay_p90_s"] <= base["delay_p90_s"] - 0.5 else "persistence_k5"
    out["_chosen"] = chosen
    print("decision rule chosen:", chosen)
    A3.write_text(json.dumps(out, indent=2, default=float))
    return chosen


def rule_kw(label):
    if label.startswith("persistence_k"):
        return {"kind": "persistence", "k": int(label.split("k")[-1])}
    if label.startswith("cusum_p"):
        return {"kind": "cusum", "ref_pct": float(label.split("p")[-1])}
    return {"kind": "conformal", "k": 5, "alpha": 0.01}


def temporal_columns(splits, cols, cfg):
    """M3: add trailing 30 s mean, max and slope of the six most important features (by LightGBM gain)."""
    tr = splits[0]
    sc = Scorer("lightgbm", cols, cfg).fit(tr)
    gain = sc.model.booster_.feature_importance("gain")
    top = [cols[i] for i in np.argsort(gain)[::-1][:6]]
    n = int(30 / 0.1)
    new_splits = []
    for sp in splits:
        items = []
        for s, f in sp.items:
            g = f.copy()
            for c in top:
                r = pd.Series(f[c].to_numpy(dtype=float)).rolling(n, min_periods=1)
                g[c + "_m30"] = r.mean().to_numpy()
                g[c + "_x30"] = r.max().to_numpy()
                g[c + "_s30"] = (f[c].to_numpy(dtype=float) - r.apply(lambda v: v[0], raw=True).to_numpy()) / 30.0
            items.append((s, g))
        new_splits.append(Split(items, sp.cfg))
    cols2 = list(cols) + [c + suf for c in top for suf in ("_m30", "_x30", "_s30")]
    return new_splits, cols2, top


def build(name, cols, splits, cfg, seed=None):
    tr, ca = splits[0], splits[1]
    if name.startswith("M1_"):
        return Scorer(name[3:], cols, cfg, seed).fit(tr)
    if name.startswith("M2_"):
        w = float(name.split("_")[-1])
        a = Scorer("lightgbm", cols, cfg, seed).fit(tr)
        b = Scorer("one_class_svm", cols, cfg, seed).fit(tr)
        return Ensemble(a, b, w).calibrate(ca)
    raise ValueError(name)


def a4(cfg, splits0, cols0, label):
    kw = rule_kw(label)
    res = {}
    cands = ["M1_one_class_svm", "M1_lightgbm", "M1_xgboost", "M2_ensemble_0.25", "M2_ensemble_0.5", "M2_ensemble_0.75", "M3_temporal"]
    for cand in cands:
        splits, cols = splits0, cols0
        if cand == "M3_temporal":
            splits, cols, top = temporal_columns(splits0, cols0, cfg)
        tr, ca, va, weak, fah = splits
        scorer = build("M1_lightgbm" if cand == "M3_temporal" else cand, cols, splits, cfg)
        rule = calibrate_rule(scorer, Rule(cfg=cfg, **kw), ca)
        m = evaluate(scorer, rule, ca, va, weak, fah)
        # no-strength: refit without C/N0, HDOP and satellite-count cues
        cols_ns = [c for c in cols if not any(c.startswith(x) for x in STRENGTH_FEATURES)]
        sc_ns = build("M1_lightgbm" if cand == "M3_temporal" else cand, cols_ns, splits, cfg)
        rule_ns = calibrate_rule(sc_ns, Rule(cfg=cfg, **kw), ca)
        m_ns = evaluate(sc_ns, rule_ns, ca, va, weak, fah)
        # unseen attacks: leave each type out of training (supervised only)
        types = sorted({session_type(s) for s, _ in tr.items if session_type(s) != "clean"})
        unseen = []
        if cand.startswith("M1_") and cand[3:] in UNSUPERVISED:
            unseen_dr = m["dr_val"]
        else:
            for t in types:
                if cand.startswith("M2_"):
                    w = float(cand.split("_")[-1])
                    a_ = Scorer("lightgbm", cols, cfg).fit(tr, keep=lambda s, t=t: session_type(s) != t)
                    b_ = Scorer("one_class_svm", cols, cfg).fit(tr)
                    sc_u = Ensemble(a_, b_, w).calibrate(ca)
                else:
                    sc_u = Scorer("lightgbm" if cand == "M3_temporal" else cand[3:], cols, cfg).fit(tr, keep=lambda s, t=t: session_type(s) != t)
                r_u = calibrate_rule(sc_u, Rule(cfg=cfg, **kw), ca)
                m_u = evaluate(sc_u, r_u, ca, va, weak, fah)
                unseen.append(m_u["per_type_val"].get(t, float("nan")))
            unseen_dr = float(np.nanmean(unseen))
        res[cand] = {**m, "dr_no_strength": m_ns["dr_val"], "far_hold_no_strength": m_ns["far_hold"], "dr_unseen": unseen_dr,
                     "robustness": (m["dr_weak"] + unseen_dr + m["ct_weak"]) / 3, "n_features": len(cols), "rule": label}
        print(cand, {k: round(v, 3) for k, v in res[cand].items() if isinstance(v, float)}, flush=True)
        A4.write_text(json.dumps(res, indent=2, default=float))
    return res


def select(res, tie=0.05):
    el = {k: r for k, r in res.items() if r["far_hold"] <= 1.0 and r["dr_no_strength"] > 0 and r["dr_val"] >= 0.5}
    if not el:
        return None
    best_dr = max(r["dr_val"] for r in el.values())
    best_rob = max(r["robustness"] for r in el.values())
    tied = {k: r for k, r in el.items() if best_dr - r["dr_val"] <= tie and best_rob - r["robustness"] <= tie}
    if tied:
        return min(tied, key=lambda k: (tied[k]["delay_median_s"], k))
    return max(el, key=lambda k: (el[k]["robustness"], el[k]["dr_val"]))


def main():
    stage = sys.argv[1]
    cfg = ProjectConfig.load("configs/sim_v4.json").detector
    d, splits, dw = load_splits(cfg)
    cols = chosen_cols(splits)
    if stage == "a3":
        a3(cfg, splits, cols)
    else:
        label = json.loads(A3.read_text())["_chosen"]
        res = a4(cfg, splits, cols, label)
        res_sel = select(res)
        print("selected by rule:", res_sel)
        Path("results/v4_selected.json").write_text(json.dumps({"selected": res_sel, "decision_rule": label}, indent=2))


if __name__ == "__main__":
    main()
