"""Common time base: offsets between each stream's clock and GNSS time, and the
acceptance test that aligned streams agree to within a tolerance (default 5 ms)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

import numpy as np

DEFAULT_TOLERANCE_S = 0.005


@dataclass
class TimeBase:
    gnss_reference: str = "t_gnss_s"
    host_reference: str = "t_host_ns"

    @staticmethod
    def estimate_offset(gnss_s: Iterable[float], stream_s: Iterable[float]) -> Dict[str, float]:
        """Offset and rate between a stream clock and GNSS time from paired timestamps.

        Fits stream = gnss * (1 + rate) + offset by least squares, and reports the residual
        spread (jitter). Pairs must be the same events seen by both clocks (e.g. the PPS or
        the GNSS message arrival).
        """
        g = np.asarray(list(gnss_s), dtype=float)
        s = np.asarray(list(stream_s), dtype=float)
        if g.shape != s.shape or g.size < 2:
            raise ValueError("need at least two paired timestamps of equal length")
        A = np.column_stack((g - g[0], np.ones_like(g)))
        (slope, intercept), *_ = np.linalg.lstsq(A, s, rcond=None)
        resid = s - A @ np.array([slope, intercept])
        return {
            "offset_s": float(intercept - g[0]),
            "rate_ppm": float((slope - 1.0) * 1e6),
            "jitter_s": float(np.std(resid)),
            "max_abs_residual_s": float(np.max(np.abs(resid))),
        }

    def align_offsets(self, gnss_s: Iterable[float], streams: Dict[str, Iterable[float]]) -> Dict[str, Dict[str, float]]:
        g = list(gnss_s)
        return {name: self.estimate_offset(g, values) for name, values in streams.items()}

    @staticmethod
    def to_gnss_time(stream_s: Iterable[float], fit: Dict[str, float], gnss_start_s: float = 0.0) -> np.ndarray:
        s = np.asarray(list(stream_s), dtype=float)
        return (s - fit["offset_s"] - gnss_start_s) / (1 + fit["rate_ppm"] * 1e-6) + gnss_start_s

    def sync(self, gnss_times: Iterable[float], host_times_ns: Iterable[float]) -> Tuple[np.ndarray, np.ndarray]:
        """Return (gnss_s, host times mapped to GNSS seconds)."""
        g = np.asarray(list(gnss_times), dtype=float)
        h = np.asarray(list(host_times_ns), dtype=float) * 1e-9
        fit = self.estimate_offset(g, h)
        return g, self.to_gnss_time(h, fit, g[0])

    def acceptance_test(self, gnss_s: Iterable[float], stream_s: Iterable[float], tolerance_s: float = DEFAULT_TOLERANCE_S) -> Dict[str, float | bool]:
        fit = self.estimate_offset(gnss_s, stream_s)
        return {**fit, "tolerance_s": tolerance_s, "passed": fit["max_abs_residual_s"] <= tolerance_s}


DEFAULT_TIME_BASE = TimeBase()
