"""Causal per-row residual features shared by the layers.

Every feature at row k uses only rows 0..k (backward differences, trailing windows,
and a session baseline that is built during the first `baseline_s` seconds and then
frozen). Larger values are more suspicious.
"""
from __future__ import annotations

from typing import Callable, Dict, Iterable, Sequence, Tuple

import numpy as np
import pandas as pd

from .config import DEFAULT_DETECTOR_CONFIG, DetectorConfig

EARTH_R = 6_378_137.0
L1_LAMBDA = 299_792_458.0 / 1575.42e6


class MissingInputError(KeyError):
    """Raised when a layer or feature is asked to run on data that lacks required inputs."""


# ---------------------------------------------------------------- helpers
def _rows(frame: pd.DataFrame, seconds: float) -> int:
    t = frame["t_gnss_s"].to_numpy(dtype=float)
    dt = float(np.median(np.diff(t))) if t.size > 1 else 1.0
    return max(1, int(round(seconds / dt)))


def _dt(frame: pd.DataFrame) -> float:
    t = frame["t_gnss_s"].to_numpy(dtype=float)
    return float(np.median(np.diff(t))) if t.size > 1 else 1.0


def trailing_mean(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(x).rolling(n, min_periods=1).mean().to_numpy()


def backward_diff(x: np.ndarray, lag: int = 1) -> np.ndarray:
    out = np.zeros_like(x, dtype=float)
    out[lag:] = x[lag:] - x[:-lag]
    return out


def warmup_mask(frame: pd.DataFrame, cfg: DetectorConfig) -> np.ndarray:
    t = frame["t_gnss_s"].to_numpy(dtype=float)
    return (t - t[0]) < cfg.baseline_s


def frozen_baseline(x: np.ndarray, warm: np.ndarray, stat: str = "mean") -> np.ndarray:
    """Expanding statistic during warm-up, then held at its last warm-up value (causal)."""
    s = pd.Series(x).expanding()
    out = (s.median() if stat == "median" else s.mean()).to_numpy(copy=True)
    if warm.any() and not warm.all():
        k = int(np.flatnonzero(warm)[-1])
        out[k + 1 :] = out[k]
    return out


def local_ne(frame: pd.DataFrame, lat_col: str = "lat_deg", lon_col: str = "lon_deg") -> Tuple[np.ndarray, np.ndarray]:
    lat = np.deg2rad(frame[lat_col].to_numpy(dtype=float))
    lon = np.deg2rad(frame[lon_col].to_numpy(dtype=float))
    lat0 = np.deg2rad(frame["lat_deg"].to_numpy(dtype=float)[0])
    lon0 = np.deg2rad(frame["lon_deg"].to_numpy(dtype=float)[0])
    return (lat - lat0) * EARTH_R, (lon - lon0) * EARTH_R * np.cos(lat0)


# ---------------------------------------------------------------- features
def f_posvel(frame, cfg):
    """Displacement over the short window vs integrated reported velocity (m/s)."""
    dt = _dt(frame)
    n1 = _rows(frame, cfg.short_window_s)
    north, east = local_ne(frame)
    vn = frame["vel_n_mps"].to_numpy(dtype=float)
    ve = frame["vel_e_mps"].to_numpy(dtype=float)
    # Cumulative trapezoid integral of velocity; its n1-step difference is the window integral.
    cn = np.cumsum(np.r_[0.0, 0.5 * (vn[1:] + vn[:-1]) * dt])
    ce = np.cumsum(np.r_[0.0, 0.5 * (ve[1:] + ve[:-1]) * dt])
    dn = backward_diff(north, n1) - backward_diff(cn, n1)
    de = backward_diff(east, n1) - backward_diff(ce, n1)
    return np.hypot(dn, de) / (n1 * dt)


def f_imu_resid(frame, cfg):
    """GNSS-velocity acceleration vs IMU specific force, body frame, bias removed (m/s^2)."""
    dt = _dt(frame)
    n1 = _rows(frame, cfg.short_window_s)
    warm = warmup_mask(frame, cfg)
    yaw = frame["yaw_rad"].to_numpy(dtype=float)
    an = trailing_mean(backward_diff(frame["vel_n_mps"].to_numpy(dtype=float)) / dt, n1)
    ae = trailing_mean(backward_diff(frame["vel_e_mps"].to_numpy(dtype=float)) / dt, n1)
    gx = np.cos(yaw) * an + np.sin(yaw) * ae
    gy = -np.sin(yaw) * an + np.cos(yaw) * ae
    rx = gx - trailing_mean(frame["acc_bx_mps2"].to_numpy(dtype=float), n1)
    ry = gy - trailing_mean(frame["acc_by_mps2"].to_numpy(dtype=float), n1)
    rx = rx - frozen_baseline(rx, warm, "median")
    ry = ry - frozen_baseline(ry, warm, "median")
    return trailing_mean(np.hypot(rx, ry), _rows(frame, cfg.mid_window_s))


def f_imu_resid_long(frame, cfg):
    """Like imu_resid, but the signed bias-removed residual is averaged over persist_window_s
    before its magnitude is taken, so zero-mean noise cancels and a slow consistent drift stays (m/s^2)."""
    dt = _dt(frame)
    n1 = _rows(frame, cfg.short_window_s)
    warm = warmup_mask(frame, cfg)
    yaw = frame["yaw_rad"].to_numpy(dtype=float)
    an = trailing_mean(backward_diff(frame["vel_n_mps"].to_numpy(dtype=float)) / dt, n1)
    ae = trailing_mean(backward_diff(frame["vel_e_mps"].to_numpy(dtype=float)) / dt, n1)
    gx = np.cos(yaw) * an + np.sin(yaw) * ae
    gy = -np.sin(yaw) * an + np.cos(yaw) * ae
    rx = gx - trailing_mean(frame["acc_bx_mps2"].to_numpy(dtype=float), n1)
    ry = gy - trailing_mean(frame["acc_by_mps2"].to_numpy(dtype=float), n1)
    rx = rx - frozen_baseline(rx, warm, "median")
    ry = ry - frozen_baseline(ry, warm, "median")
    n = _rows(frame, cfg.persist_window_s)
    return np.hypot(trailing_mean(rx, n), trailing_mean(ry, n))


def _att_accel_ned(frame, cfg):
    """IMU acceleration in NED using the reported roll, pitch and yaw: R(body to NED) f + g (n, e)."""
    roll = frame["roll_rad"].to_numpy(dtype=float)
    pitch = frame["pitch_rad"].to_numpy(dtype=float)
    yaw = frame["yaw_rad"].to_numpy(dtype=float)
    fx = frame["acc_bx_mps2"].to_numpy(dtype=float)
    fy = frame["acc_by_mps2"].to_numpy(dtype=float)
    fz = frame["acc_bz_mps2"].to_numpy(dtype=float)
    cr, sr, cp, sp, cy, sy = np.cos(roll), np.sin(roll), np.cos(pitch), np.sin(pitch), np.cos(yaw), np.sin(yaw)
    an = cy * cp * fx + (cy * sp * sr - sy * cr) * fy + (cy * sp * cr + sy * sr) * fz
    ae = sy * cp * fx + (sy * sp * sr + cy * cr) * fy + (sy * sp * cr - cy * sr) * fz
    return an, ae


def _att_resid_xy(frame, cfg):
    dt = _dt(frame)
    n1 = _rows(frame, cfg.short_window_s)
    warm = warmup_mask(frame, cfg)
    an, ae = _att_accel_ned(frame, cfg)
    gn = trailing_mean(backward_diff(frame["vel_n_mps"].to_numpy(dtype=float)) / dt, n1)
    ge = trailing_mean(backward_diff(frame["vel_e_mps"].to_numpy(dtype=float)) / dt, n1)
    rn = gn - trailing_mean(an, n1)
    re = ge - trailing_mean(ae, n1)
    return rn - frozen_baseline(rn, warm, "median"), re - frozen_baseline(re, warm, "median")


def f_imu_att_resid(frame, cfg):
    """Attitude-aware version of imu_resid: GNSS acceleration against the IMU acceleration rotated
    with roll, pitch and yaw (not yaw only), bias removed (m/s^2). Needed once the body is tilted."""
    rn, re = _att_resid_xy(frame, cfg)
    return trailing_mean(np.hypot(rn, re), _rows(frame, cfg.mid_window_s))


def f_imu_att_resid_long(frame, cfg):
    """Attitude-aware long-window residual: signed residual averaged over persist_window_s first (m/s^2)."""
    rn, re = _att_resid_xy(frame, cfg)
    n = _rows(frame, cfg.persist_window_s)
    return np.hypot(trailing_mean(rn, n), trailing_mean(re, n))


def f_baro_resid(frame, cfg):
    """GNSS altitude minus barometric altitude, relative to the session baseline (m)."""
    warm = warmup_mask(frame, cfg)
    gb = frame["alt_m"].to_numpy(dtype=float) - frame["baro_alt_m"].to_numpy(dtype=float)
    return np.abs(trailing_mean(gb, _rows(frame, cfg.mid_window_s)) - frozen_baseline(gb, warm, "median"))


def f_implied_accel(frame, cfg):
    """Horizontal acceleration implied by the reported positions over 1 s steps (m/s^2)."""
    n1 = _rows(frame, cfg.short_window_s)
    T = n1 * _dt(frame)
    north, east = local_ne(frame)
    vn = backward_diff(north, n1) / T
    ve = backward_diff(east, n1) / T
    return np.hypot(backward_diff(vn, n1), backward_diff(ve, n1)) / T


def f_cn0_shift(frame, cfg):
    """Absolute change of mean C/N0 from the session baseline (dB)."""
    warm = warmup_mask(frame, cfg)
    cn0 = frame["cn0_dbhz"].to_numpy(dtype=float)
    return np.abs(trailing_mean(cn0, _rows(frame, cfg.long_window_s)) - frozen_baseline(cn0, warm))


def f_cn0_std_drop(frame, cfg):
    """Drop of the across-satellite C/N0 spread from the session baseline (dB)."""
    warm = warmup_mask(frame, cfg)
    s = frame["cn0_std_dbhz"].to_numpy(dtype=float)
    return frozen_baseline(s, warm) - trailing_mean(s, _rows(frame, cfg.long_window_s))


def f_hdop_change(frame, cfg):
    warm = warmup_mask(frame, cfg)
    h = frame["hdop"].to_numpy(dtype=float)
    return np.abs(trailing_mean(h, _rows(frame, cfg.short_window_s)) - frozen_baseline(h, warm))


def f_sv_change(frame, cfg):
    warm = warmup_mask(frame, cfg)
    sv = frame["num_sv"].to_numpy(dtype=float)
    return np.abs(trailing_mean(sv, _rows(frame, cfg.short_window_s)) - frozen_baseline(sv, warm, "median"))


def f_clk_innov(frame, cfg):
    """Clock bias change minus drift-predicted change (ns)."""
    dt = _dt(frame)
    bias = frame["clk_bias_ns"].to_numpy(dtype=float)
    drift = frame["clk_drift_nsps"].to_numpy(dtype=float)
    pred = 0.5 * (drift + np.r_[drift[0], drift[:-1]]) * dt
    return trailing_mean(np.abs(backward_diff(bias) - pred), _rows(frame, cfg.short_window_s))


def f_clk_drift_step(frame, cfg):
    """Clock drift now vs its median 3-8 s earlier (ns/s); ignores the slow random walk."""
    drift = frame["clk_drift_nsps"].to_numpy(dtype=float)
    n3 = _rows(frame, 3.0)
    lagged = pd.Series(drift).shift(n3).rolling(_rows(frame, 5.0), min_periods=1).median()
    lagged = lagged.fillna(pd.Series(drift).expanding().median()).to_numpy()
    return np.abs(trailing_mean(drift, _rows(frame, cfg.mid_window_s)) - lagged)


def f_allan(frame, cfg):
    """Overlapping Allan deviation of the clock drift at tau = short window, trailing (ns/s)."""
    drift = frame["clk_drift_nsps"].to_numpy(dtype=float)
    n1 = _rows(frame, cfg.short_window_s)
    yb = trailing_mean(drift, n1)
    d = backward_diff(yb, n1)
    return np.sqrt(0.5 * trailing_mean(d * d, _rows(frame, cfg.allan_window_s)))


def f_lock_reset(frame, cfg):
    """1 while a carrier-lock reset happened within the last lock_hold_s seconds."""
    lock = frame["lock_ms"].to_numpy(dtype=float)
    reset = (backward_diff(lock) < 0).astype(float)
    return pd.Series(reset).rolling(_rows(frame, cfg.lock_hold_s), min_periods=1).max().to_numpy()


def f_code_carrier(frame, cfg):
    """Rate of code-minus-carrier divergence, excluding lock resets (m per step)."""
    cc = frame["pr_m"].to_numpy(dtype=float) - frame["cp_cycles"].to_numpy(dtype=float) * L1_LAMBDA
    d = np.abs(backward_diff(cc))
    reset = backward_diff(frame["lock_ms"].to_numpy(dtype=float)) < 0
    d[reset] = 0.0
    return trailing_mean(d, _rows(frame, cfg.short_window_s))


def f_const_diff(frame, cfg):
    """Distance between the GPS and the Galileo position solutions (m)."""
    north, east = local_ne(frame)
    gn, ge = local_ne(frame, "gal_lat_deg", "gal_lon_deg")
    du = frame["alt_m"].to_numpy(dtype=float) - frame["gal_alt_m"].to_numpy(dtype=float)
    return trailing_mean(np.sqrt((north - gn) ** 2 + (east - ge) ** 2 + du**2), _rows(frame, cfg.mid_window_s))


def f_cn0_rise(frame, cfg):
    """Rise of mean C/N0 above the session baseline (dB). Spoofers raise it; occlusions lower it."""
    warm = warmup_mask(frame, cfg)
    cn0 = frame["cn0_dbhz"].to_numpy(dtype=float)
    return np.maximum(0.0, trailing_mean(cn0, _rows(frame, cfg.long_window_s)) - frozen_baseline(cn0, warm))


def f_cn0_fall(frame, cfg):
    """Fall of mean C/N0 below the session baseline (dB): the occlusion signature."""
    warm = warmup_mask(frame, cfg)
    cn0 = frame["cn0_dbhz"].to_numpy(dtype=float)
    return np.maximum(0.0, frozen_baseline(cn0, warm) - trailing_mean(cn0, _rows(frame, cfg.long_window_s)))


def f_sv_drop(frame, cfg):
    """Satellites lost relative to the session baseline."""
    warm = warmup_mask(frame, cfg)
    sv = frame["num_sv"].to_numpy(dtype=float)
    return np.maximum(0.0, frozen_baseline(sv, warm, "median") - trailing_mean(sv, _rows(frame, cfg.short_window_s)))


def f_hdop_rise(frame, cfg):
    warm = warmup_mask(frame, cfg)
    h = frame["hdop"].to_numpy(dtype=float)
    return np.maximum(0.0, trailing_mean(h, _rows(frame, cfg.short_window_s)) - frozen_baseline(h, warm))


def f_dead_reckoning(frame, cfg):
    """Position minus the velocity integral since the end of warm-up, trailing minimum over
    persist_window_s (m). A step attack stays above the minimum; a short multipath jump does not."""
    dt = _dt(frame)
    warm = warmup_mask(frame, cfg)
    north, east = local_ne(frame)
    vn = frame["vel_n_mps"].to_numpy(dtype=float)
    ve = frame["vel_e_mps"].to_numpy(dtype=float)
    cn = np.cumsum(np.r_[0.0, 0.5 * (vn[1:] + vn[:-1]) * dt])
    ce = np.cumsum(np.r_[0.0, 0.5 * (ve[1:] + ve[:-1]) * dt])
    kb = int(np.flatnonzero(warm)[-1]) if warm.any() else 0
    r = np.hypot((north - north[kb]) - (cn - cn[kb]), (east - east[kb]) - (ce - ce[kb]))
    r[: kb + 1] = 0.0
    return pd.Series(r).rolling(_rows(frame, cfg.persist_window_s), min_periods=1).min().to_numpy()


FeatureFn = Callable[[pd.DataFrame, DetectorConfig], np.ndarray]

FEATURES: Dict[str, Tuple[Tuple[str, ...], FeatureFn]] = {
    "posvel_mps": (("t_gnss_s", "lat_deg", "lon_deg", "vel_n_mps", "vel_e_mps"), f_posvel),
    "imu_resid_mps2": (("t_gnss_s", "vel_n_mps", "vel_e_mps", "yaw_rad", "acc_bx_mps2", "acc_by_mps2"), f_imu_resid),
    "imu_resid_long_mps2": (("t_gnss_s", "vel_n_mps", "vel_e_mps", "yaw_rad", "acc_bx_mps2", "acc_by_mps2"), f_imu_resid_long),
    "imu_att_resid_mps2": (("t_gnss_s", "vel_n_mps", "vel_e_mps", "roll_rad", "pitch_rad", "yaw_rad", "acc_bx_mps2", "acc_by_mps2", "acc_bz_mps2"), f_imu_att_resid),
    "imu_att_resid_long_mps2": (("t_gnss_s", "vel_n_mps", "vel_e_mps", "roll_rad", "pitch_rad", "yaw_rad", "acc_bx_mps2", "acc_by_mps2", "acc_bz_mps2"), f_imu_att_resid_long),
    "baro_resid_m": (("t_gnss_s", "alt_m", "baro_alt_m"), f_baro_resid),
    "implied_accel_mps2": (("t_gnss_s", "lat_deg", "lon_deg"), f_implied_accel),
    "cn0_shift_db": (("t_gnss_s", "cn0_dbhz"), f_cn0_shift),
    "cn0_std_drop_db": (("t_gnss_s", "cn0_std_dbhz"), f_cn0_std_drop),
    "hdop_change": (("t_gnss_s", "hdop"), f_hdop_change),
    "sv_change": (("t_gnss_s", "num_sv"), f_sv_change),
    "clk_innov_ns": (("t_gnss_s", "clk_bias_ns", "clk_drift_nsps"), f_clk_innov),
    "clk_drift_step_nsps": (("t_gnss_s", "clk_drift_nsps"), f_clk_drift_step),
    "allan_dev_nsps": (("t_gnss_s", "clk_drift_nsps"), f_allan),
    "lock_reset": (("t_gnss_s", "lock_ms"), f_lock_reset),
    "code_carrier_m": (("t_gnss_s", "pr_m", "cp_cycles", "lock_ms"), f_code_carrier),
    "cn0_rise_db": (("t_gnss_s", "cn0_dbhz"), f_cn0_rise),
    "cn0_fall_db": (("t_gnss_s", "cn0_dbhz"), f_cn0_fall),
    "sv_drop": (("t_gnss_s", "num_sv"), f_sv_drop),
    "hdop_rise": (("t_gnss_s", "hdop"), f_hdop_rise),
    "dead_reckoning_m": (("t_gnss_s", "lat_deg", "lon_deg", "vel_n_mps", "vel_e_mps"), f_dead_reckoning),
    "const_diff_m": (("t_gnss_s", "lat_deg", "lon_deg", "alt_m", "gal_lat_deg", "gal_lon_deg", "gal_alt_m"), f_const_diff),
}

CN0_FEATURES = ("cn0_shift_db", "cn0_std_drop_db", "cn0_rise_db", "cn0_fall_db")


def required_columns(names: Iterable[str]) -> Tuple[str, ...]:
    cols: list[str] = []
    for name in names:
        for col in FEATURES[name][0]:
            if col not in cols:
                cols.append(col)
    return tuple(cols)


def available_features(frame: pd.DataFrame) -> list[str]:
    return [name for name, (cols, _) in FEATURES.items() if set(cols).issubset(frame.columns)]


def compute_features(
    frame: pd.DataFrame,
    names: Sequence[str] | None = None,
    cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG,
) -> pd.DataFrame:
    """Per-row feature table. Raises MissingInputError if a requested feature lacks inputs."""
    if names is None:
        names = available_features(frame)
    missing = [c for c in required_columns(names) if c not in frame.columns]
    if missing:
        raise MissingInputError(f"missing required columns: {missing}")
    out = {name: np.asarray(FEATURES[name][1](frame, cfg), dtype=float) for name in names}
    return pd.DataFrame(out, index=frame.index)


def acceleration_residual(frame: pd.DataFrame, cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG) -> np.ndarray:
    return f_imu_resid(frame, cfg)


def position_velocity_residual(frame: pd.DataFrame, cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG) -> np.ndarray:
    return f_posvel(frame, cfg)
