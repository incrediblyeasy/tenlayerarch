"""Causal Kalman filter on the IMU and the GNSS fix; its normalised innovations are features
(MODEL_IMPROVEMENT_PLAN.md, M5).

One filter per horizontal axis with state [position, velocity, accelerometer bias]. The IMU
acceleration, rotated to north and east with the reported attitude, drives the prediction; the
GNSS position and velocity are the measurements. When GNSS is spoofed in a way the IMU does not
agree with, the innovations grow. The returned values are the root of the normalised innovation
squared summed over north and east (about 1 for a consistent filter), averaged over mid_window_s.
Noise values are assumptions, not calibrated (see MODEL_IMPROVEMENT_PLAN.md C8).
"""
from __future__ import annotations

import numpy as np

from .features import _att_accel_ned, _dt, _rows, local_ne, trailing_mean

SIGMA_ACC = 0.3       # m/s^2, accelerometer noise plus vibration
SIGMA_BIAS_WALK = 0.01  # m/s^2/sqrt(s)
SIGMA_POS = 3.0       # m, GNSS position noise
SIGMA_VEL = 0.3       # m/s, GNSS velocity noise


def _axis(accel: np.ndarray, pos: np.ndarray, vel: np.ndarray, dt: float):
    n = len(pos)
    x = np.array([pos[0], vel[0], 0.0])
    P = np.diag([SIGMA_POS**2, SIGMA_VEL**2, 0.1**2])
    F = np.array([[1.0, dt, -0.5 * dt * dt], [0.0, 1.0, -dt], [0.0, 0.0, 1.0]])
    B = np.array([0.5 * dt * dt, dt, 0.0])
    Q = np.diag([0.0, 0.0, SIGMA_BIAS_WALK**2 * dt]) + np.outer(B, B) * SIGMA_ACC**2
    H = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    R = np.diag([SIGMA_POS**2, SIGMA_VEL**2])
    nis_p, nis_v = np.zeros(n), np.zeros(n)
    for k in range(1, n):
        x = F @ x + B * accel[k]
        P = F @ P @ F.T + Q
        z = np.array([pos[k], vel[k]])
        y = z - H @ x
        S = H @ P @ H.T + R
        K = P @ H.T @ np.linalg.inv(S)
        nis_p[k] = y[0] ** 2 / S[0, 0]
        nis_v[k] = y[1] ** 2 / S[1, 1]
        x = x + K @ y
        P = (np.eye(3) - K @ H) @ P
    return nis_p, nis_v


def ekf_nis(frame, cfg):
    dt = _dt(frame)
    an, ae = _att_accel_ned(frame, cfg)
    north, east = local_ne(frame)
    vn = frame["vel_n_mps"].to_numpy(dtype=float)
    ve = frame["vel_e_mps"].to_numpy(dtype=float)
    pn, vn_n = _axis(an, north, vn, dt)
    pe, ve_n = _axis(ae, east, ve, dt)
    return np.sqrt(pn + pe), np.sqrt(vn_n + ve_n)


def f_ekf_innov(frame, cfg):
    """Normalised GNSS position innovation of the IMU-driven filter (1 = consistent)."""
    return trailing_mean(ekf_nis(frame, cfg)[0], _rows(frame, cfg.mid_window_s))


def f_ekf_innov_vel(frame, cfg):
    """Normalised GNSS velocity innovation of the IMU-driven filter (1 = consistent)."""
    return trailing_mean(ekf_nis(frame, cfg)[1], _rows(frame, cfg.mid_window_s))
