"""Opt-in realism options for the simulator (SIMULATOR_IMPROVEMENTS.md, C3-C7).

Every option is off by default. All randomness here comes from its own stream, seeded
(seed, 11), so enabling an option never changes the base world (trajectory, sky, clock,
noise) of a session. All parameter values are assumptions, to be replaced by calibration
once bench data exist (C8).
"""
from __future__ import annotations

import numpy as np

from .gnss_model import gauss_markov

GRAVITY = 9.80665

# C7 platform classes: ranges for speed, position oscillation, altitude, and whether yaw follows the velocity.
PLATFORMS = {
    "multirotor_hover": dict(speed=(0.0, 1.5), amp=(0.5, 4.0), period=(20.0, 60.0), alt=(10.0, 50.0), alt_amp=(0.0, 2.0), yaw_follows_velocity=False),
    "multirotor_maneuver": dict(speed=(0.0, 6.0), amp=(2.0, 25.0), period=(25.0, 90.0), alt=(20.0, 80.0), alt_amp=(0.0, 6.0), yaw_follows_velocity=False),
    "fixed_wing": dict(speed=(15.0, 30.0), amp=(50.0, 200.0), period=(60.0, 120.0), alt=(100.0, 300.0), alt_amp=(0.0, 15.0), yaw_follows_velocity=True),
    "large_slow": dict(speed=(0.0, 4.0), amp=(5.0, 40.0), period=(60.0, 150.0), alt=(30.0, 120.0), alt_amp=(0.0, 4.0), yaw_follows_velocity=False),
}


def _rot(roll, pitch, yaw):
    """Body-to-NED rotation matrices, shape (n, 3, 3), ZYX Euler angles."""
    cr, sr, cp, sp, cy, sy = np.cos(roll), np.sin(roll), np.cos(pitch), np.sin(pitch), np.cos(yaw), np.sin(yaw)
    R = np.empty((roll.size, 3, 3))
    R[:, 0] = np.stack((cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr), axis=1)
    R[:, 1] = np.stack((sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr), axis=1)
    R[:, 2] = np.stack((-sp, cp * sr, cp * cr), axis=1)
    return R


def realistic_imu(orng: np.random.Generator, true_acc: np.ndarray, yaw: np.ndarray, dt: float):
    """Thrust-aligned attitude and the measurements of an entry-level IMU.

    The body z axis follows the specific force (thrust or lift), so horizontal acceleration is
    seen through tilt, not through body x/y specific force. Returns (acc_body, gyro_body,
    roll_est, pitch_est). Assumed values: accelerometer white noise 0.2 m/s^2 (vibration),
    turn-on bias sd 0.1 m/s^2, bias random walk 0.003 m/s^2/sqrt(s), scale-factor error sd 0.5 %;
    gyro white noise 0.01 rad/s, turn-on bias sd 0.005 rad/s; attitude estimate error sd 0.005 rad
    white plus 0.01 rad bias.
    """
    n = true_acc.shape[0]
    f = true_acc - np.array([0.0, 0.0, GRAVITY])  # specific force, NED
    zb = -f / np.linalg.norm(f, axis=1, keepdims=True)  # body z (down) axis in NED
    zy = np.stack((np.cos(-yaw) * zb[:, 0] - np.sin(-yaw) * zb[:, 1], np.sin(-yaw) * zb[:, 0] + np.cos(-yaw) * zb[:, 1], zb[:, 2]), axis=1)
    pitch = np.arctan2(zy[:, 0], zy[:, 2])
    roll = np.arctan2(-zy[:, 1], np.hypot(zy[:, 0], zy[:, 2]))
    R = _rot(roll, pitch, yaw)
    f_body = np.einsum("nji,nj->ni", R, f)
    sf = 1.0 + orng.normal(0.0, 0.005, 3)
    bias = orng.normal(0.0, 0.1, 3) + np.cumsum(orng.normal(0.0, 0.003 * np.sqrt(dt), (n, 3)), axis=0)
    acc = f_body * sf + bias + orng.normal(0.0, 0.2, (n, 3))
    phi_d, th_d, psi_d = np.gradient(roll, dt), np.gradient(pitch, dt), np.gradient(np.unwrap(yaw), dt)
    gyr = np.stack(
        (
            phi_d - psi_d * np.sin(pitch),
            th_d * np.cos(roll) + psi_d * np.sin(roll) * np.cos(pitch),
            psi_d * np.cos(roll) * np.cos(pitch) - th_d * np.sin(roll),
        ),
        axis=1,
    )
    gyr = gyr + orng.normal(0.0, 0.005, 3) + orng.normal(0.0, 0.01, (n, 3))
    roll_est = roll + orng.normal(0.0, 0.01) + orng.normal(0.0, 0.005, n)
    pitch_est = pitch + orng.normal(0.0, 0.01) + orng.normal(0.0, 0.005, n)
    return acc, gyr, roll_est, pitch_est


def iono_delay(orng: np.random.Generator, el_deg: np.ndarray, t: np.ndarray) -> np.ndarray:
    """L1 slant ionospheric delay (metres): vertical delay 3-12 m with a slow +-10 % variation,
    times the thin-shell obliquity factor. The code is delayed by this amount and the carrier phase
    advanced by the same amount."""
    vertical = orng.uniform(3.0, 12.0) * (1.0 + 0.1 * np.sin(2 * np.pi * t / orng.uniform(200.0, 600.0) + orng.uniform(0.0, 2 * np.pi)))
    el = np.deg2rad(el_deg)
    return vertical / np.sqrt(1.0 - (0.9782 * np.cos(el)) ** 2)


def multipath(orng: np.random.Generator, n: int, dt: float, el_deg: np.ndarray):
    """Correlated multipath: (position error NED m, per-satellite C/N0 fluctuation dB, pseudorange
    error of satellite 0 in m). Low-elevation satellites are worse. Assumed distributions."""
    tau = orng.uniform(8.0, 25.0)
    pos = np.stack((gauss_markov(orng, n, dt, 1.5, tau), gauss_markov(orng, n, dt, 1.5, tau), gauss_markov(orng, n, dt, 2.5, tau)), axis=1)
    n_sat = el_deg.shape[1]
    cn0 = np.stack([gauss_markov(orng, n, dt, 1.0 + 2.0 * (1.0 - el_deg[0, j] / 90.0), orng.uniform(5.0, 20.0)) for j in range(n_sat)], axis=1)
    pr0 = gauss_markov(orng, n, dt, 0.5 + 1.5 * (1.0 - el_deg[0, 0] / 90.0), orng.uniform(5.0, 20.0))
    return pos, cn0, pr0
