from __future__ import annotations

import numpy as np

GRAVITY = 9.80665


def imu_signal(rng: np.random.Generator, true_acc: np.ndarray, yaw: np.ndarray, yaw_rate: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Body-frame specific force (m/s^2) and angular rate (rad/s), level attitude assumed."""
    n = true_acc.shape[0]
    f_ned = true_acc - np.array([0.0, 0.0, GRAVITY])
    acc = np.stack(
        (
            np.cos(yaw) * f_ned[:, 0] + np.sin(yaw) * f_ned[:, 1],
            -np.sin(yaw) * f_ned[:, 0] + np.cos(yaw) * f_ned[:, 1],
            f_ned[:, 2],
        ),
        axis=1,
    )
    acc += rng.normal(0.0, 0.05, 3) + rng.normal(0.0, 0.05, (n, 3))
    gyr = np.zeros((n, 3))
    gyr[:, 2] = yaw_rate
    gyr += rng.normal(0.0, 0.002, 3) + rng.normal(0.0, 0.003, (n, 3))
    return acc, gyr


def baro_signal(rng: np.random.Generator, alt_true_m: np.ndarray, dt: float) -> np.ndarray:
    """Barometric altitude: per-session bias, random-walk drift and white noise."""
    n = alt_true_m.size
    return (
        alt_true_m
        + rng.normal(0.0, 10.0)
        + np.cumsum(rng.normal(0.0, 0.03 * np.sqrt(dt), n))
        + rng.normal(0.0, 0.25, n)
    )
