"""A2: which features enter the model (configs/feature_rule_v4.json). Validation data only."""
from __future__ import annotations

import json
from pathlib import Path

from .config import ProjectConfig
from .v4_study import Split, feature_sets, make_splits, run, Data

OUT = Path("results/v4_a2_features.json")


def load_splits(cfg):
    d, tr, ca, va = make_splits("datasets/sim_v4_val", cfg)
    dw, dh = Data("datasets/sim_v4_weakval", cfg), Data("datasets/sim_v4_fahold", cfg)
    weak = Split(list(zip(dw.sessions, dw.feats)), cfg)
    fah = Split(list(zip(dh.sessions, dh.feats)), cfg)
    return d, (tr, ca, va, weak, fah), dw


def main():
    cfg = ProjectConfig.load("configs/sim_v4.json").detector
    d, splits, dw = load_splits(cfg)
    sets = feature_sets(list(splits[0].items[0][1].columns))
    rule_kw = {"kind": "persistence", "k": cfg.persistence_k}
    res = {"sets": {}, "ablation": {}}
    for name, cols in sets.items():
        _, _, m = run("lightgbm", cols, cfg, rule_kw, splits)
        res["sets"][name] = {"n_features": len(cols), **m}
        print(name, {k: round(v, 3) for k, v in m.items() if not isinstance(v, dict)}, flush=True)
    base = res["sets"]["S_v3"]
    qual = {}
    for name, m in res["sets"].items():
        if name == "S_v3":
            continue
        g1, g2 = m["ct_val"] - base["ct_val"], m["ct_weak"] - base["ct_weak"]
        ok = g1 >= 0.03 and g2 >= 0.03 and m["dr_weak"] >= base["dr_weak"] and m["far_hold"] <= 1.0
        res["sets"][name]["rule"] = {"gain_ct_val": g1, "gain_ct_weak": g2, "qualifies": bool(ok)}
        if ok:
            qual[name] = (g1 + g2) / 2
    chosen = max(qual, key=qual.get) if qual else "S_v3"
    res["chosen_set"] = chosen
    print("chosen:", chosen, flush=True)
    for drop in ("code_carrier_m", "allan_dev_nsps", "const_diff_m", "dead_reckoning_m", "baro_resid_m", "imu_resid_long_mps2"):
        cols = [c for c in sets[chosen] if c != drop]
        if len(cols) == len(sets[chosen]):
            continue
        _, _, m = run("lightgbm", cols, cfg, rule_kw, splits)
        res["ablation"][drop] = {k: m[k] for k in ("dr_val", "ct_val", "dr_weak", "ct_weak", "far_hold", "delay_p90_s")}
        print("drop", drop, res["ablation"][drop], flush=True)
    OUT.write_text(json.dumps(res, indent=2, default=float))
    return res


if __name__ == "__main__":
    main()
