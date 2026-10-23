from __future__ import annotations

import time
from typing import Callable

import numpy as np
import pandas as pd


def measure_latency(func: Callable[..., object], *args, **kwargs) -> tuple[float, object]:
    """Latency of one call in seconds, and its result."""
    start = time.perf_counter()
    result = func(*args, **kwargs)
    return time.perf_counter() - start, result


def pipeline_latency(detector, session: pd.DataFrame, repeats: int = 20) -> dict[str, float]:
    """Time the full detector (features, ten layers, vote) on one session.

    The batch time is divided by the row count, giving ms per decision. Measure on the
    Jetson for the hardware report; numbers from a PC are not a substitute.
    """
    times = []
    for _ in range(repeats):
        dt, _ = measure_latency(detector.detect, session)
        times.append(dt)
    per_row_ms = np.array(times) * 1000.0 / len(session)
    return {
        "rows": len(session),
        "ms_per_decision_mean": float(per_row_ms.mean()),
        "ms_per_decision_p95": float(np.percentile(per_row_ms, 95)),
        "ms_per_decision_p99": float(np.percentile(per_row_ms, 99)),
        "ms_per_session_mean": float(np.mean(times) * 1000.0),
    }
