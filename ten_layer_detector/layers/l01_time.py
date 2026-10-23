from __future__ import annotations

from .base import BaseLayer


class TimeDomainLayer(BaseLayer):
    """Receiver clock consistency: bias change vs drift, and steps in the drift."""

    name = "1_time_domain"
    feature_names = ("clk_innov_ns", "clk_drift_step_nsps")
