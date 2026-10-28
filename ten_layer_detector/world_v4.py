"""The v4 simulated world (MODEL_IMPROVEMENT_PLAN.md A1): a mix of four platform classes with
realistic IMU, ionosphere and multipath, and attackers that are half ordinary and half
matched-power (C1) with a preserved clock (C5) and a reproduced ionosphere (C4).
Session ids carry the platform and attacker kind, e.g. fixed_wing_m_ramp_0003 (m = matched).

    python -m ten_layer_detector.world_v4 --out datasets/sim_v4_val --seed 41000 --n-clean 1000 --n-per-attack 15
    python -m ten_layer_detector.world_v4 --out datasets/sim_v4_weakval --seed 42000 --n-clean 25 --n-per-attack 15 --weak
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from .dataset import save_sessions
from .sim import generate_mixed_dataset
from .sim.realism import PLATFORMS

REALISM = {"imu": "realistic", "ionosphere": True, "multipath": True}
CAREFUL = {"iono_matched": True, "clock_coupled": False}


def _job(args):
    platform, kind, seed, n_clean, n_per_attack, weak, quiet, force_reset = args
    realism = {**REALISM, "platform": platform, **({"quiet": quiet} if quiet else {})}
    matched = kind == "m"
    sessions, meta = generate_mixed_dataset(
        n_clean, n_per_attack, seed=seed, realism=realism, matched_power=matched,
        attacker_overrides={**(CAREFUL if matched else {}), **({"lock_reset": True} if force_reset else {})} or None, power_range_db=(0.0, 1.0) if weak else None,
    )
    for s, m in zip(sessions, meta):
        sid = f"{platform}_{kind}_{s['session_id'].iloc[0]}"
        s["session_id"] = sid
        m["session_id"] = sid
        m["platform"] = platform
        m["matched_attacker"] = matched
    return sessions, meta


def build(out: str, seed: int, n_clean: int, n_per_attack: int, weak: bool = False, workers: int = 8, quiet: dict | None = None, force_reset: bool = False):
    """Per platform: ordinary attackers (all clean sessions plus half the attacks) and matched-power
    attackers (the other half, no clean sessions). Weak sets use power 0-1 dB and no matched attacker."""
    jobs = []
    for k, p in enumerate(PLATFORMS):
        if weak:
            jobs.append((p, "o", seed + 10 * k, n_clean, n_per_attack, True, quiet, force_reset))
        else:
            half = n_per_attack // 2
            jobs.append((p, "o", seed + 10 * k, n_clean, n_per_attack - half, False, quiet, force_reset))
            if half:
                jobs.append((p, "m", seed + 10 * k + 1, 0, half, False, quiet, force_reset))
    with ProcessPoolExecutor(workers) as ex:
        parts = list(ex.map(_job, jobs))
    sessions = [s for p, _ in parts for s in p]
    meta = [m for _, mm in parts for m in mm]
    save_sessions(out, sessions, meta)
    return len(sessions)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--n-clean", type=int, required=True)
    p.add_argument("--n-per-attack", type=int, required=True)
    p.add_argument("--weak", action="store_true")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--quiet-json", default=None, help="config file whose 'quiet' block sets the clean-flight nuisances (configs/sim_v5.json)")
    p.add_argument("--force-reset", action="store_true", help="every attacker resets the receiver lock at onset")
    a = p.parse_args()
    import json

    quiet = json.loads(open(a.quiet_json).read())["quiet"] if a.quiet_json else None
    n = build(a.out, a.seed, a.n_clean, a.n_per_attack, a.weak, a.workers, quiet, a.force_reset)
    print(f"wrote {n} sessions to {a.out}")


if __name__ == "__main__":
    main()
