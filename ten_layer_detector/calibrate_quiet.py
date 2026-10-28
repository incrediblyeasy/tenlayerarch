"""Round 2 Step 2: grid-calibrate the quiet-nuisance options against the real rates.

    python -m ten_layer_detector.calibrate_quiet --out results/quiet_calibration.json
The grid, target rates and selection rule are in configs/sim_v5_calibration_plan.json."""
from __future__ import annotations

import argparse
import itertools
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from .nuisance import episodes, pooled_rate
from .sim import generate_session
from .sim.realism import PLATFORMS

KEYS = ("sat_drop>=1", "sat_rise>=1", "hdop_jump>=0.2", "position_jump>=3.0", "sat_drop>=2", "sat_rise>=2", "hdop_jump>=0.1", "hdop_jump>=0.5")


def _point(args):
    quiet, n_per_platform = args
    recs = []
    for k, plat in enumerate(PLATFORMS):
        for i in range(n_per_platform):
            s = generate_session(attack_type="clean", seed=61000 + 1000 * k + i, session_id=f"cal_{k}_{i}",
                                 realism={"imu": "realistic", "ionosphere": True, "multipath": True, "platform": plat, "quiet": quiet})
            recs.append(episodes(s["t_gnss_s"].to_numpy(float), s["num_sv"], s["hdop"], s["lat_deg"], s["lon_deg"], s["vel_n_mps"], s["vel_e_mps"]))
    return quiet, {k: pooled_rate(recs, k, n_boot=2000) for k in KEYS}


def _resid(args):
    scale, n_per_platform = args
    from .sim.realism import PLATFORMS as P

    out = []
    for k, plat in enumerate(P):
        for i in range(n_per_platform):
            s = generate_session(attack_type="clean", seed=61000 + 1000 * k + i, session_id=f"cal_{k}_{i}",
                                 realism={"imu": "realistic", "ionosphere": True, "multipath": True, "platform": plat, "quiet": {"position_white_scale": scale}})
            out.append(residual_1s(s))
    r = np.concatenate(out)
    return scale, [float(x) for x in np.percentile(r, [50, 90, 99])]


def residual_1s(s):
    from .nuisance import EARTH_R

    t = s["t_gnss_s"].to_numpy(float)
    lat, lon = np.deg2rad(s["lat_deg"].to_numpy(float)), np.deg2rad(s["lon_deg"].to_numpy(float))
    vn, ve = s["vel_n_mps"].to_numpy(float), s["vel_e_mps"].to_numpy(float)
    north, east = lat * EARTH_R, lon * EARTH_R * np.cos(lat[0])
    cn = np.cumsum(np.r_[0.0, 0.5 * (vn[1:] + vn[:-1]) * np.diff(t)])
    ce = np.cumsum(np.r_[0.0, 0.5 * (ve[1:] + ve[:-1]) * np.diff(t)])
    idx = np.searchsorted(t, t - 1.0, side="right") - 1
    ok = idx >= 0
    return np.hypot((north[ok] - north[idx[ok]]) - (cn[ok] - cn[idx[ok]]), (east[ok] - east[idx[ok]]) - (ce[ok] - ce[idx[ok]]))


def stage_a(args):
    plan = json.loads(Path("configs/sim_v5_calibration_plan2.json").read_text())["stage_a"]
    tgt = plan["real_targets_m"]
    with ProcessPoolExecutor(args.workers) as ex:
        rows = list(ex.map(_resid, [(sc, 30) for sc in plan["grid"]]))
    res = []
    for sc, (m, p90, p99) in rows:
        res.append({"position_white_scale": sc, "median": m, "p90": p90, "p99": p99,
                    "score": float(abs(np.log(m / tgt["median"])) + abs(np.log(p90 / tgt["p90"])) + abs(np.log(p99 / tgt["p99"])))})
    best = min(res, key=lambda r: r["score"])
    Path("results/quiet_calibration_a.json").write_text(json.dumps({"points": res, "best": best, "targets": tgt}, indent=2))
    for r in res:
        print(r)
    print("best scale:", best["position_white_scale"])


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out", default="results/quiet_calibration.json")
    a.add_argument("--workers", type=int, default=24)
    a.add_argument("--stage", default="0", help="0 first grid, a position-noise scale, b grid with the chosen scale")
    args = a.parse_args()
    if args.stage == "a":
        return stage_a(args)
    scale = 1.0
    if args.stage == "b":
        scale = json.loads(Path("results/quiet_calibration_a.json").read_text())["best"]["position_white_scale"]
    plan = json.loads(Path("configs/sim_v5_calibration_plan.json").read_text())
    g = plan["grid"]
    points = [dict(tracking_s=t, hysteresis_db=h, occlusion_prob=o, multipath_jump_prob=m, position_white_scale=scale)
              for t, h, o, m in itertools.product(g["tracking_s"], g["hysteresis_db"], g["occlusion_prob"], g["multipath_jump_prob"])]
    with ProcessPoolExecutor(args.workers) as ex:
        rows = list(ex.map(_point, [(p, 30) for p in points]))
    tgt = plan["targets_real_rates_per_min"]
    out = []
    for quiet, rates in rows:
        score = sum(abs(np.log(max(rates[k][0], 1e-3) / tgt[k])) for k in ("sat_drop>=1", "sat_rise>=1", "hdop_jump>=0.2"))
        out.append({"quiet": quiet, "rates": {k: {"rate": v[0], "lo": v[1], "hi": v[2]} for k, v in rates.items()}, "score": float(score), "position_ok": bool(rates["position_jump>=3.0"][0] <= 0.15)})
    ok = [r for r in out if r["position_ok"]]
    best = min(ok or out, key=lambda r: r["score"])
    Path(args.out).write_text(json.dumps({"points": out, "best": best, "targets": tgt}, indent=2, default=float))
    for r in sorted(out, key=lambda r: r["score"])[:8]:
        print(r["quiet"], round(r["score"], 2), r["position_ok"], {k.split(">=")[0][:8] + k[-3:]: round(v["rate"], 2) for k, v in r["rates"].items() if k in KEYS[:4]})
    print("best:", best["quiet"])


if __name__ == "__main__":
    main()
