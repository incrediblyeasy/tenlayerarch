from __future__ import annotations

import numpy as np


def clock_state(rng: np.random.Generator, n: int, dt: float) -> tuple[np.ndarray, np.ndarray]:
    """Two-state receiver clock: bias (ns) and drift (ns/s), each with random-walk noise.

    The noise levels are assumptions (TCXO-like) until calibrated from the module's
    measured Allan deviation on the bench.
    """
    drift = rng.normal(0.0, 80.0) + np.cumsum(rng.normal(0.0, rng.uniform(0.05, 0.3) * np.sqrt(dt), n))
    bias = (
        rng.uniform(-1e5, 1e5)
        + np.cumsum(drift * dt)
        + np.cumsum(rng.normal(0.0, rng.uniform(0.5, 2.0) * np.sqrt(dt), n))
    )
    return bias, drift
