"""Canonical simulated session generator (the only generator in the package).

Physics per session: smooth 3D trajectory, 10-satellite geometry with DOP from geometry,
two-state receiver clock, IMU and barometer with bias and drift, Gauss-Markov GNSS error,
and a second-constellation (Galileo) solution.

Nuisances present in every class: C/N0 occlusion dips that drop satellites, multipath
position jumps, a per-session C/N0 gain offset.

Two random streams are used: one for the world (trajectory, sky, clock, sensors, noise)
and one for the attacker. A clean and an attacked session with the same seed are therefore
identical before the attack onset, which gives a within-session control.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

import numpy as np
import pandas as pd

from .attacks import ATTACK_TYPES, attack_offset, normalize_attack_type, sample_attacker
from .clock_model import clock_state
from .gnss_model import (
    C,
    CN0_LOST_DBHZ,
    L1_LAMBDA,
    N_SAT,
    dop_from_geometry,
    ned_to_geodetic,
    sat_elevation_azimuth,
    solution_error,
    unit_ned,
)
from .realism import PLATFORMS, iono_delay, multipath, realistic_imu
from .sensors import baro_signal, imu_signal
from .trajectory import sample_trajectory

__all__ = ["ATTACK_TYPES", "generate_session", "generate_dataset", "generate_mixed_dataset"]


def _default_onset(rng: np.random.Generator, duration_s: float) -> float:
    lo = min(15.0, 0.25 * duration_s)
    hi = max(lo, min(35.0, 0.6 * duration_s))
    return float(rng.uniform(lo, hi))


def generate_session(
    duration_s: float = 60.0,
    sample_rate_hz: float = 10.0,
    attack_type: str = "clean",
    attack_onset_s: float | None = None,
    session_id: str = "sim_clean_0000",
    seed: int = 0,
    *,
    attacker: Mapping[str, Any] | None = None,
    realism: Mapping[str, Any] | None = None,
    return_metadata: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, Dict[str, Any]]:
    """Generate one labelled session in the canonical schema.

    attack_onset_s: None draws an onset in [0.25, 0.6] x duration (15-35 s for 60 s).
    attacker: optional overrides for the sampled attacker parameters (see
    sim.attacks.sample_attacker), e.g. {"power_db": 0.5}.
    """
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    if sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")
    attack_type = normalize_attack_type(attack_type)
    attacked = attack_type != "clean"
    R = dict(realism or {})  # opt-in realism options (sim/realism.py); empty means the original simulator
    orng = np.random.default_rng([int(seed), 11])

    rng = np.random.default_rng(seed)
    arng = np.random.default_rng([int(seed), 1])
    if attacked:
        onset_s = _default_onset(arng, duration_s) if attack_onset_s is None else float(attack_onset_s)
        if onset_s < 0:
            raise ValueError("attack_onset_s must be non-negative")
        if onset_s >= duration_s:
            raise ValueError("attack_onset_s must be strictly before the end of the session")
    else:
        onset_s = 0.0

    n = max(2, int(round(duration_s * sample_rate_hz)))
    dt = 1.0 / sample_rate_hz
    t = np.arange(n) * dt

    traj = sample_trajectory(rng, t, PLATFORMS[R["platform"]] if R.get("platform") else None)
    true_pos, true_vel = traj["pos"], traj["vel"]
    el, az = sat_elevation_azimuth(rng, t)
    clk_bias, clk_drift = clock_state(rng, n, dt)

    gain = rng.normal(0.0, 2.0)
    cn0 = 33.0 + 12.0 * (el / 90.0) + rng.normal(0.0, 2.0, N_SAT) + gain + rng.normal(0.0, 1.0, (n, N_SAT))
    mp_pos, mp_pr0 = np.zeros((n, 3)), np.zeros(n)
    if R.get("multipath"):  # C6
        mp_pos, mp_cn0, mp_pr0 = multipath(orng, n, dt, el)
        cn0 = cn0 + mp_cn0

    meta: Dict[str, Any] = {
        "session_id": str(session_id),
        "kind": "attack" if attacked else "clean",
        "source": "sim",
        "attack_type": attack_type,
        "attack_start_t_gnss_s": onset_s if attacked else None,
        "attack_end_t_gnss_s": float(t[-1]) if attacked else None,
        "seed": int(seed),
        "rates": {"all_hz": sample_rate_hz},
        "nuisances": [],
    }

    # Nuisance: occlusion dips (several satellites lose 4-12 dB for 3-15 s).
    n_occ = int(rng.integers(1, 3)) if rng.random() < 0.3 else 0
    for _ in range(n_occ):
        sats = rng.choice(N_SAT, size=int(rng.integers(2, 6)), replace=False)
        start = rng.uniform(0.0, max(0.0, duration_s - 5.0))
        length = rng.uniform(3.0, 15.0)
        window = (t >= start) & (t < start + length)
        cn0[np.ix_(window, sats)] -= rng.uniform(4.0, 12.0)
        meta["nuisances"].append({"kind": "occlusion", "start_s": float(start), "length_s": float(length)})

    # Nuisance: multipath jump in horizontal position (velocity unaffected).
    mp = np.zeros((n, 3))
    if rng.random() < 0.15:
        start = rng.uniform(0.0, max(0.0, duration_s - 5.0))
        length = rng.uniform(1.0, 4.0)
        ang = rng.uniform(0.0, 2 * np.pi)
        mag = rng.uniform(3.0, 10.0)
        window = (t >= start) & (t < start + length)
        mp[window, 0] = mag * np.cos(ang)
        mp[window, 1] = mag * np.sin(ang)
        meta["nuisances"].append({"kind": "multipath", "start_s": float(start), "length_s": float(length), "m": float(mag)})

    # World noise, drawn in the same order for every class.
    err_gps_noise = rng.integers(0, 2**31)
    err_gal_noise = rng.integers(0, 2**31)
    lat0 = rng.uniform(-50.0, 50.0)
    lon0 = rng.uniform(-180.0, 180.0)
    alt_msl0 = rng.uniform(100.0, 800.0)
    sat_range = rng.uniform(2.0e7, 2.5e7) + rng.uniform(-600.0, 600.0) * t
    imu_acc, imu_gyr = imu_signal(rng, traj["acc"], traj["yaw"], traj["yaw_rate"])
    att_est = None
    if R.get("imu") == "realistic":  # C3
        imu_acc, imu_gyr, roll_est, pitch_est = realistic_imu(orng, traj["acc"], traj["yaw"], dt)
        att_est = (roll_est, pitch_est)
    baro = baro_signal(rng, alt_msl0 - true_pos[:, 2], dt)
    vel_noise = rng.normal(0.0, 0.08, (n, 3))
    meas_noise = {
        "bias": rng.normal(0.0, 2.0, n),
        "drift": rng.normal(0.0, 0.3, n),
        "pr": rng.normal(0.0, 0.5, n),
        "dop": rng.normal(0.0, 0.2, n),
        "cp": rng.normal(0.0, 0.01, n),
        "att": rng.normal(0.0, 0.005, (n, 2)),
        "host": rng.normal(0.0, 2e5, n),
    }
    host_offset = rng.uniform(0, 1e9)
    lock_start = rng.uniform(5e3, 6e4)
    ambiguity0 = float(rng.integers(-1_000_000, 1_000_000))

    offset = np.zeros((n, 3))
    offset_dot = np.zeros((n, 3))
    gal_offset = np.zeros((n, 3))
    lock_reset_idx: list[int] = []
    if attacked:
        on = t >= onset_s
        k0 = int(np.argmax(on))
        offset, offset_dot, shape = attack_offset(arng, attack_type, t, onset_s, true_pos, true_vel, overrides=attacker)
        params = sample_attacker(arng, attack_type)
        if attacker:
            params.update(attacker)
        power_db = float(params["power_db"])
        matched = bool(params.get("matched_power", False))

        if matched:
            # Careful attacker (SIMULATOR_IMPROVEMENTS.md, C1): per-satellite C/N0 matches the
            # authentic signal up to a Gaussian error, and the satellite geometry is reproduced too,
            # so neither the strength cue nor the geometry cue is available to the detector.
            tol = float(params.get("match_tolerance_db", 1.0))
            cn0[on] = cn0[on] + arng.normal(0.0, tol, cn0[on].shape)
            params["geometry_changed"] = False
        else:
            # Spoofed signals arrive at a common power: C/N0 rises and its spread across
            # satellites shrinks, both scaled by spoofer power.
            squeeze = 1.0 - 0.6 * min(power_db, 10.0) / 10.0
            auth = cn0[on]
            row_mean = auth.mean(axis=1, keepdims=True)
            cn0[on] = row_mean + (auth - row_mean) * squeeze + power_db * arng.uniform(0.7, 1.0)

        if params["clock_coupled"]:
            jump_ns = arng.uniform(-1000.0, 1000.0) if attack_type not in {"ramp", "consistent_takeover"} else 0.0
            d_drift = arng.normal(0.0, 20.0)
            tau = t[on] - onset_s
            clk_bias[on] += jump_ns + d_drift * tau
            clk_drift[on] += d_drift
            shape.update(clock_jump_ns=float(jump_ns), clock_drift_change_nsps=float(d_drift))

        if params["geometry_changed"]:
            n_spoof = int(np.clip(N_SAT + arng.integers(-3, 4), 6, N_SAT))
            s_el, s_az = sat_elevation_azimuth(arng, t)
            el[on] = s_el[on]
            az[on] = s_az[on]
            cn0[np.ix_(on, np.arange(n_spoof, N_SAT))] = 0.0  # satellites the spoofer does not simulate
            shape["spoofed_sat_count"] = n_spoof

        if params["lock_reset"]:
            lock_reset_idx.append(k0)
        if params["spoofs_galileo"]:
            gal_offset = offset

        meta.update(params)
        meta.update(shape)
        meta["attack_onset_s"] = onset_s

    used = cn0 >= CN0_LOST_DBHZ
    used[used.sum(axis=1) < 4] = True  # receiver keeps a solution on weak satellites
    u = unit_ned(el, az)
    hdop, vdop, pdop = dop_from_geometry(u, used)

    rep_pos = true_pos + solution_error(np.random.default_rng(err_gps_noise), n, dt, hdop, vdop) + mp + mp_pos + offset
    rep_vel = true_vel + offset_dot + vel_noise
    gal_pos = true_pos + 1.2 * solution_error(np.random.default_rng(err_gal_noise), n, dt, hdop, vdop) + mp + 0.8 * mp_pos + gal_offset
    lat, lon, alt = ned_to_geodetic(rep_pos, lat0, lon0, alt_msl0)
    gal_lat, gal_lon, gal_alt = ned_to_geodetic(gal_pos, lat0, lon0, alt_msl0)

    # Raw measurements for satellite 0, consistent with the reported (possibly spoofed) solution.
    u0 = u[:, 0, :]
    sat_rate = np.gradient(sat_range, t)
    geom_range = sat_range - np.einsum("ni,ni->n", u0, rep_pos)
    geom_rate = sat_rate - np.einsum("ni,ni->n", u0, rep_vel)
    pr = geom_range + C * clk_bias * 1e-9 + meas_noise["pr"]
    dop_hz = -(geom_rate + C * clk_drift * 1e-9) / L1_LAMBDA + meas_noise["dop"]
    ambiguity = np.full(n, ambiguity0)
    lock_ms = t * 1000.0 + lock_start
    resets = sorted(set(lock_reset_idx) | {k for k in range(1, n) if used[k - 1, 0] and not used[k, 0]})
    for j, k in enumerate(resets):
        ambiguity[k:] = ambiguity0 + 7919.0 * (j + 1)
        lock_ms[k:] = (t[k:] - t[k]) * 1000.0
    cp = (geom_range + C * clk_bias * 1e-9) / L1_LAMBDA + ambiguity + meas_noise["cp"]
    if R.get("ionosphere"):  # C4: code delayed, carrier advanced by the same slant delay
        iono = iono_delay(orng, el[:, 0], t)
        if attacked and not params.get("iono_matched", True):
            iono = np.where(on, 0.0, iono)  # this spoofer does not reproduce the ionosphere
        pr = pr + iono
        cp = cp - iono / L1_LAMBDA
    pr = pr + mp_pr0

    cn0_used = np.where(used, cn0, np.nan)
    labels = ((t >= onset_s) & attacked).astype(int)
    frame = pd.DataFrame(
        {
            "session_id": str(session_id),
            "source": "simulated",
            "t_gnss_s": t,
            "t_host_ns": (t * 1e9 + host_offset + meas_noise["host"]).astype(np.int64),
            "label": labels,
            "attack_type": attack_type,
            "attack_onset_s": onset_s,
            "lat_deg": lat,
            "lon_deg": lon,
            "alt_m": alt,
            "vel_n_mps": rep_vel[:, 0],
            "vel_e_mps": rep_vel[:, 1],
            "vel_d_mps": rep_vel[:, 2],
            "cn0_dbhz": np.nanmean(cn0_used, axis=1),
            "cn0_std_dbhz": np.nanstd(cn0_used, axis=1),
            "clk_bias_ns": clk_bias + meas_noise["bias"],
            "clk_drift_nsps": clk_drift + meas_noise["drift"],
            "pr_m": pr,
            "cp_cycles": cp,
            "dop_hz": dop_hz,
            "lock_ms": lock_ms,
            "h_acc_m": 1.5 * hdop,
            "v_acc_m": 1.5 * vdop,
            "pdop": pdop,
            "hdop": hdop,
            "vdop": vdop,
            "num_sv": used.sum(axis=1).astype(int),
            "fix_type": 3,
            "gal_lat_deg": gal_lat,
            "gal_lon_deg": gal_lon,
            "gal_alt_m": gal_alt,
            "acc_bx_mps2": imu_acc[:, 0],
            "acc_by_mps2": imu_acc[:, 1],
            "acc_bz_mps2": imu_acc[:, 2],
            "gyr_bx_rps": imu_gyr[:, 0],
            "gyr_by_rps": imu_gyr[:, 1],
            "gyr_bz_rps": imu_gyr[:, 2],
            "roll_rad": meas_noise["att"][:, 0] if att_est is None else att_est[0],
            "pitch_rad": meas_noise["att"][:, 1] if att_est is None else att_est[1],
            "yaw_rad": traj["yaw"],
            "baro_alt_m": baro,
        }
    )
    if return_metadata:
        return frame, meta
    return frame


def generate_dataset(
    n_sessions: int,
    duration_s: float = 60.0,
    sample_rate_hz: float = 10.0,
    attack_type: str = "ramp",
    attack_onset_s: float | None = None,
    seed: int = 0,
) -> list[pd.DataFrame]:
    """n_sessions of one attack type (or clean), seeds seed .. seed + n_sessions - 1."""
    name = normalize_attack_type(attack_type)
    return [
        generate_session(duration_s, sample_rate_hz, name, attack_onset_s, f"{name}_{seed + i:05d}", seed + i)
        for i in range(n_sessions)
    ]


def generate_mixed_dataset(
    n_clean: int,
    n_per_attack: int,
    *,
    duration_s: float = 60.0,
    sample_rate_hz: float = 10.0,
    seed: int = 2026,
    attack_types: tuple[str, ...] = ATTACK_TYPES,
    power_range_db: tuple[float, float] | None = None,
    matched_power: bool = False,
    match_tolerance_db: float = 1.0,
    attacker_overrides: Mapping[str, Any] | None = None,
    realism: Mapping[str, Any] | None = None,
) -> tuple[list[pd.DataFrame], list[Dict[str, Any]]]:
    """Clean sessions plus n_per_attack sessions of each attack type, with metadata.

    power_range_db: draw each attacked session's spoofer power uniformly from this range
    (e.g. (0, 1) for a weak-spoofer set) instead of the default 0-10 dB.
    matched_power: attacked sessions use the careful attacker of C1 (C/N0 matched per satellite
    within match_tolerance_db, geometry reproduced)."""
    power_rng = np.random.default_rng([int(seed), 7])
    plan = [("clean", i) for i in range(n_clean)] + [(a, i) for a in attack_types for i in range(n_per_attack)]
    seeds = np.random.SeedSequence(seed).generate_state(len(plan))
    frames, metas = [], []
    for (attack_type, i), s in zip(plan, seeds):
        attacker = {"power_db": float(power_rng.uniform(*power_range_db))} if power_range_db and attack_type != "clean" else None
        if matched_power and attack_type != "clean":
            attacker = {**(attacker or {}), "matched_power": True, "match_tolerance_db": match_tolerance_db}
        if attacker_overrides and attack_type != "clean":
            attacker = {**(attacker or {}), **attacker_overrides}
        frame, meta = generate_session(
            duration_s, sample_rate_hz, attack_type, None, f"{attack_type}_{i:04d}", int(s), attacker=attacker, realism=realism, return_metadata=True
        )
        frames.append(frame)
        metas.append(meta)
    return frames, metas
