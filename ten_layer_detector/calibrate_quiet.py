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


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--out", default="results/quiet_calibration.json")
    a.add_argument("--workers", type=int, default=24)
    args = a.parse_args()
    plan = json.loads(Path("configs/sim_v5_calibration_plan.json").read_text())
    g = plan["grid"]
    points = [dict(tracking_s=t, hysteresis_db=h, occlusion_prob=o, multipath_jump_prob=m)
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
