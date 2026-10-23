from __future__ import annotations

from .base import BaseLayer


class AllanDeviationLayer(BaseLayer):
    """Fast trailing Allan deviation of the receiver clock drift (tau = 1 s, 10 s window)."""

    name = "9_allan"
    feature_names = ("allan_dev_nsps",)
