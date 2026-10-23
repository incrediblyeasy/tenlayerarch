from __future__ import annotations

import numpy as np


def sample_trajectory(rng: np.random.Generator, t: np.ndarray) -> dict[str, np.ndarray]:
    """Smooth 3D flight in local NED metres: cruise plus two sinusoids per horizontal axis.

    Returns true position, velocity and acceleration (analytic, so mutually consistent),
    yaw and yaw rate. Attitude is level apart from yaw.
    """
    n = t.size
    pos = np.zeros((n, 3))
    vel = np.zeros((n, 3))
    acc = np.zeros((n, 3))
    speed = rng.uniform(0.0, 6.0)
    heading = rng.uniform(0.0, 2 * np.pi)
    cruise = speed * np.array([np.cos(heading), np.sin(heading)])
    for axis in (0, 1):
        pos[:, axis] = cruise[axis] * t
        vel[:, axis] = cruise[axis]
        for _ in range(2):
            amp = rng.uniform(2.0, 25.0)
            w = 2 * np.pi / rng.uniform(25.0, 90.0)
            ph = rng.uniform(0.0, 2 * np.pi)
            pos[:, axis] += amp * np.sin(w * t + ph)
            vel[:, axis] += amp * w * np.cos(w * t + ph)
            acc[:, axis] += -amp * w * w * np.sin(w * t + ph)
    alt0 = rng.uniform(20.0, 80.0)
    amp = rng.uniform(0.0, 6.0)
    w = 2 * np.pi / rng.uniform(30.0, 120.0)
    ph = rng.uniform(0.0, 2 * np.pi)
    pos[:, 2] = -(alt0 + amp * np.sin(w * t + ph))  # NED: down is positive
    vel[:, 2] = -amp * w * np.cos(w * t + ph)
    acc[:, 2] = amp * w * w * np.sin(w * t + ph)

    yaw0 = rng.uniform(-np.pi, np.pi)
    yaw_amp = rng.uniform(0.0, 1.0)
    yaw_w = 2 * np.pi / rng.uniform(20.0, 80.0)
    yaw = yaw0 + yaw_amp * np.sin(yaw_w * t)
    yaw_rate = yaw_amp * yaw_w * np.cos(yaw_w * t)
    return {"t": t, "pos": pos, "vel": vel, "acc": acc, "yaw": np.angle(np.exp(1j * yaw)), "yaw_rate": yaw_rate}
