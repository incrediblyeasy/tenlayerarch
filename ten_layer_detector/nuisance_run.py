"""Round 2 Step 1: nuisance rates in real clean recordings and in simulated clean sessions.

    python -m ten_layer_detector.nuisance_run --real-dir <dir of CSVs from Clean.xlsx> --out results/nuisance_v5.json
Metrics, windows and the decision rule are in configs/nuisance_measure_v5.json (committed before
this ran). Implementation detail not in that file: a Nayfeh sheet joins several flights, so it is cut
wherever the time step is above 1 s or not positive and no episode is counted across a cut; minutes
are the summed length of the pieces. Simulated sessions are used whole (60 s each).
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .dataset import load_sessions
from .layers.base import is_clean_session
from .nuisance import ALSO, FAMILIES, PRIMARY, episodes, pooled_rate, verdict

NAYFEH_COLS = ["timestamp", "time_utc_usec", "lat", "lon", "alt", "alt_ellipsoid", "s_variance_m_s", "c_variance_rad", "eph", "epv", "hdop", "vdop",
               "noise_per_ms", "jamming_indicator", "vel_m_s", "vel_n_m_s", "vel_e_m_s", "vel_d_m_s", "cog_rad", "timestamp_time_relative", "heading",
               "heading_offset", "fix_type", "jamming_state", "vel_ned_valid", "satellites_used", "selected"]


def read_real(path: str) -> pd.DataFrame:
    d = pd.read_csv(path)
    if "timestamp" not in d.columns:  # one sheet has no header row: the first data row was read as the header
        d = pd.read_csv(path, header=None, names=NAYFEH_COLS)
    return d


def real_record(path: str) -> dict:
    d = read_real(path)
    t = pd.to_timedelta(d["timestamp"]).dt.total_seconds().to_numpy()
    cuts = np.flatnonzero((np.diff(t) > 1.0) | (np.diff(t) <= 0)) + 1
    total = {"minutes": 0.0, "counts": {}, "pieces": 0}
    for lo, hi in zip(np.r_[0, cuts], np.r_[cuts, len(d)]):
        if hi - lo < 10:
            continue
        p = d.iloc[lo:hi]
        r = episodes(t[lo:hi], p["satellites_used"], p["hdop"], p["lat"] * 1e-7, p["lon"] * 1e-7, p["vel_n_m_s"], p["vel_e_m_s"])
        total["minutes"] += r["minutes"]
        total["pieces"] += 1
        for k, v in r["counts"].items():
            total["counts"][k] = total["counts"].get(k, 0) + v
    total["name"] = Path(path).stem
    return total


def sim_records(path: str) -> list[dict]:
    sessions, _ = load_sessions(path)
    out = []
    for s in sessions:
        if not is_clean_session(s):
            continue
        out.append(episodes(s["t_gnss_s"].to_numpy(float), s["num_sv"], s["hdop"], s["lat_deg"], s["lon_deg"], s["vel_n_mps"], s["vel_e_mps"]))
    return out


def summarize(records):
    keys = list(records[0]["counts"])
    return {k: dict(zip(("rate_per_min", "lo", "hi"), pooled_rate(records, k))) for k in keys}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--real-dir", required=True)
    a.add_argument("--out", default="results/nuisance_v5.json")
    args = a.parse_args()
    real = [real_record(p) for p in sorted(glob.glob(f"{args.real_dir}/*.csv"))]
    res = {"real": {"recordings": [{"name": r["name"], "minutes": r["minutes"], "pieces": r["pieces"], "counts": r["counts"]} for r in real],
                    "total_minutes": sum(r["minutes"] for r in real), "rates": summarize(real)}}
    for tag, path in (("sim_v4_fahold", "datasets/sim_v4_fahold"), ("sim_fa2_clean", "datasets/sim_fa2")):
        recs = sim_records(path)
        res[tag] = {"sessions": len(recs), "total_minutes": sum(r["minutes"] for r in recs), "rates": summarize(recs)}
    verdicts = {}
    for fam in FAMILIES:
        key = f"{fam}>={PRIMARY[fam]}"
        for tag in ("sim_v4_fahold", "sim_fa2_clean"):
            s, r = res[tag]["rates"][key], res["real"]["rates"][key]
            verdicts.setdefault(tag, {})[fam] = {"key": key, "sim": s["rate_per_min"], "real": r["rate_per_min"], "real_ci": [r["lo"], r["hi"]],
                                                 "verdict": verdict((s["rate_per_min"], s["lo"], s["hi"]), (r["rate_per_min"], r["lo"], r["hi"]))}
    res["verdicts"] = verdicts
    n_more = sum(v["verdict"] == "much_more_active" for v in verdicts["sim_v4_fahold"].values())
    res["H1_holds_primary"] = bool(n_more >= 2)
    res["n_much_more_active_primary"] = int(n_more)
    Path(args.out).write_text(json.dumps(res, indent=2, default=float))
    for tag, v in verdicts.items():
        print(tag)
        for fam, x in v.items():
            print(f"  {fam:14} sim {x['sim']:.3f}/min  real {x['real']:.3f} ({x['real_ci'][0]:.3f}-{x['real_ci'][1]:.3f})  {x['verdict']}")
    print("real minutes", round(res["real"]["total_minutes"], 1), "H1 holds (primary data):", res["H1_holds_primary"])


if __name__ == "__main__":
    main()
