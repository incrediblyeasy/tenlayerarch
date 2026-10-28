"""Round 2 arms (configs/round2_plan.json): old primary, baseline recipe, flag gate, explained-cue features.

    python -m ten_layer_detector.r2_run val     # choice on validation data
    python -m ten_layer_detector.r2_run test    # fresh test sets, once, after the lock
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from .config import ProjectConfig
from .features import reset_flags
from .layers.base import is_clean_session, persistent_alarm
from .metrics import session_outcome, summarize_outcomes
from .splits import session_type, split_three_way
from .v4_a2 import load_splits as load_v4_splits
from .v4_a3a4 import build, chosen_cols, rule_kw
from .v4_study import Data, Rule, Split, calibrate_rule, fa_ci, session_scores
from .v4_test import platform

PLATFORMS = ("multirotor_hover", "multirotor_maneuver", "fixed_wing", "large_slow")
RESET_COLS = ["since_reset_s", "reset_recent_5s"]
K = 5


def hold_mask(session, hold_s: float) -> np.ndarray:
    """True in the hold_s seconds after (and including) each flagged lock reset."""
    n = len(session)
    if hold_s <= 0:
        return np.zeros(n, dtype=bool)
    t = session["t_gnss_s"].to_numpy(float)
    flag = np.flatnonzero(reset_flags(session))
    m = np.zeros(n, dtype=bool)
    for k in flag:
        m |= (t >= t[k]) & (t < t[k] + hold_s)
    return m


def evaluate(scores, split: Split, thr: float, hold_s: float, reset_ids: set):
    clean, attacked, per_plat = [], {}, {p: {"events": 0, "hours": 0.0, "det": []} for p in PLATFORMS}
    det_reset, det_other, ct = [], [], []
    for sc, (s, _), act in zip(scores, split.items, split.active):
        sid = str(s["session_id"].iloc[0])
        p = platform(sid)
        alarm = persistent_alarm(sc, thr, K) & ~hold_mask(s, hold_s)
        t = s["t_gnss_s"].to_numpy(float)
        if is_clean_session(s):
            o = session_outcome(alarm, t, None, act)
            clean.append(o)
            per_plat[p]["events"] += o["fa_events"]
            per_plat[p]["hours"] += o["clean_s"] / 3600.0
        else:
            o = session_outcome(alarm, t, float(s["attack_onset_s"].iloc[0]), act)
            attacked.setdefault(session_type(s), []).append(o)
            per_plat[p]["det"].append(o["detected"])
            (det_reset if sid in reset_ids else det_other).append(o["detected"])
            if session_type(s) == "consistent_takeover":
                ct.append(o["detected"])
    out = {"fa_per_platform": {p: {"events": v["events"], "hours": v["hours"], "rate": v["events"] / v["hours"] if v["hours"] else float("nan"),
                                    "upper95": fa_ci(v["events"], v["hours"]) if v["hours"] else float("nan")} for p, v in per_plat.items()}}
    if clean:
        m = summarize_outcomes(clean, attacked) if attacked else {"fa_events": sum(o["fa_events"] for o in clean), "clean_hours": sum(o["clean_s"] for o in clean) / 3600.0}
        out["fa_events"], out["clean_hours"] = m["fa_events"], m["clean_hours"]
        out["fa_per_hour"] = m["fa_events"] / m["clean_hours"]
        out["fa_upper95"] = fa_ci(m["fa_events"], m["clean_hours"])
    if attacked:
        m = summarize_outcomes(clean or [{"fa_events": 0, "clean_s": 1.0, "alarmed": False}], attacked)
        out.update(detection=m["all_attacks"]["rate"], detection_ci95=m["all_attacks"]["ci95"], delay_median_s=m["delay_median_s"], delay_p90_s=m["delay_p90_s"],
                   consistent_takeover=float(np.mean(ct)) if ct else float("nan"), per_type={a: r["rate"] for a, r in m["per_type"].items()},
                   detection_reset_attackers=float(np.mean(det_reset)) if det_reset else float("nan"), n_reset_attackers=len(det_reset),
                   detection_other_attackers=float(np.mean(det_other)) if det_other else float("nan"),
                   detection_by_platform={p: float(np.mean(v["det"])) if v["det"] else float("nan") for p, v in per_plat.items()})
    return out


def reset_ids_of(data: Data) -> set:
    return {str(m["session_id"]) for m in data.meta if m.get("lock_reset")}


def load_split(path, cfg):
    d = Data(path, cfg)
    return d, Split(list(zip(d.sessions, d.feats)), cfg)


def three_way(path, cfg):
    d = Data(path, cfg)
    tr, ca, va = split_three_way(d.sessions, cfg.train_fraction, cfg.calibration_fraction, seed=cfg.split_seed)
    pick = lambda ss: Split([(s, d.feats[d.by_id[id(s)]]) for s in ss], cfg)
    return d, pick(tr), pick(ca), pick(va)


def fit_arm(cols, tr, ca, cfg):
    scorer = build("M2_ensemble_0.25", cols, (tr, ca), cfg)
    rule = calibrate_rule(scorer, Rule(cfg=cfg, **rule_kw("persistence_k5")), ca)
    return scorer, rule


def main():
    stage = sys.argv[1]
    cfg4 = ProjectConfig.load("configs/sim_v4.json").detector
    cfg = ProjectConfig.load("configs/sim_v5.json").detector
    _, v4splits, _ = load_v4_splits(cfg4)
    cols = chosen_cols(v4splits)
    # R0: the locked v4 primary, unchanged
    r0_scorer = build("M2_ensemble_0.25", cols, v4splits, cfg4)
    r0_rule = calibrate_rule(r0_scorer, Rule(cfg=cfg4, **rule_kw("persistence_k5")), v4splits[1])
    # fits in the v5 world
    d, tr, ca, va = three_way("datasets/sim_r2_val", cfg)
    r1_scorer, r1_rule = fit_arm(cols, tr, ca, cfg)
    r3_scorer, r3_rule = fit_arm(cols + RESET_COLS, tr, ca, cfg)
    arms = {"R0_old_primary": (r0_scorer, r0_rule.thr, 0.0), "R1_baseline": (r1_scorer, r1_rule.thr, 0.0), "R3_explained_cue": (r3_scorer, r3_rule.thr, 0.0)}
    for n in (2.0, 5.0, 10.0):
        arms[f"R2_flag_gate_{int(n)}s"] = (r1_scorer, r1_rule.thr, n)
    out = {"thresholds": {k: v[1] for k, v in arms.items()}}
    if stage == "val":
        dw, weak = load_split("datasets/sim_r2_weakval", cfg)
        dh, fah = load_split("datasets/sim_r2_fahold", cfg)
        sets = {"val": (va, reset_ids_of(d)), "weak": (weak, reset_ids_of(dw)), "fahold": (fah, set())}
        cache = {}
        out["arms"] = {}
        for name, (sc, thr, hold) in arms.items():
            res = {}
            for sname, (sp, rid) in sets.items():
                key = (id(sc), sname)
                if key not in cache:
                    cache[key] = session_scores(sc, sp)
                res[sname] = evaluate(cache[key], sp, thr, hold, rid)
            out["arms"][name] = res
            f = res["fahold"]["fa_per_platform"]
            print(name, f"det {res['val']['detection']:.3f} p90 {res['val']['delay_p90_s']:.1f} resetdet {res['val']['detection_reset_attackers']:.3f}(n{res['val']['n_reset_attackers']}) weak {res['weak']['detection']:.3f}",
                  "FA/type", {p[:9] + p[-2:]: round(v["rate"], 2) for p, v in f.items()}, "overall", round(res["fahold"]["fa_per_hour"], 2), flush=True)
        # choice rule
        base = out["arms"]["R1_baseline"]
        elig = {}
        for name, res in out["arms"].items():
            if name in ("R0_old_primary", "R1_baseline"):
                continue
            mx = max(v["rate"] for v in res["fahold"]["fa_per_platform"].values())
            v = res["val"]
            ok = (mx <= 0.8 and v["detection"] >= base["val"]["detection"] - 0.02 and v["delay_p90_s"] <= base["val"]["delay_p90_s"] + 1.0
                  and v["detection_reset_attackers"] >= base["val"]["detection_reset_attackers"] - 0.05)
            res["rule"] = {"max_per_type_fa": mx, "eligible": bool(ok)}
            if ok:
                elig[name] = mx
        base_max = max(v["rate"] for v in base["fahold"]["fa_per_platform"].values())
        out["baseline_max_per_type_fa"] = base_max
        chosen = "R1_baseline"
        if elig:
            best = min(elig, key=elig.get)
            if base_max > 0.8 or elig[best] <= base_max - 0.1:
                chosen = best
        out["chosen"] = chosen
        out["needs_step4"] = bool(max(v["rate"] for v in out["arms"][chosen]["fahold"]["fa_per_platform"].values()) > 0.8)
        print("eligible:", elig, "baseline max per-type FA:", round(base_max, 2), "chosen:", chosen, "needs step 4:", out["needs_step4"])
        Path("results/r2_val.json").write_text(json.dumps(out, indent=2, default=float))
    else:
        val = json.loads(Path("results/r2_val.json").read_text())
        chosen = val["chosen"]
        thr_c, hold_c = (arms[chosen][1], arms[chosen][2])
        for name, path in (("main", "datasets/sim_r2_test"), ("weak", "datasets/sim_r2_weaktest"), ("reset", "datasets/sim_r2_resettest")):
            dd, sp = load_split(path, cfg)
            rid = reset_ids_of(dd)
            out[name] = {}
            for arm in dict.fromkeys(["R0_old_primary", "R1_baseline", chosen, "R2_flag_gate_5s"]):
                sc, thr, hold = arms[arm]
                out[name][arm] = evaluate(session_scores(sc, sp), sp, thr, hold, rid)
                r = out[name][arm]
                print(name, arm, f"det {r.get('detection', float('nan')):.3f}", f"FA {r.get('fa_per_hour', float('nan')):.2f}", {p[:9] + p[-2:]: (v["events"], round(v["upper95"], 2)) for p, v in r["fa_per_platform"].items()} if "fa_per_hour" in r else "", f"p90 {r.get('delay_p90_s', float('nan')):.1f}", flush=True)
        out["chosen"] = chosen
        Path("results/r2_test.json").write_text(json.dumps(out, indent=2, default=float))


if __name__ == "__main__":
    main()
