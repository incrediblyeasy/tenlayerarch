from __future__ import annotations

from .base import BaseLayer


class SignalQualityLayer(BaseLayer):
    """C/N0 against the session baseline (two-sided shift) and loss of across-satellite spread."""

    name = "2_signal_quality"
    feature_names = ("cn0_shift_db", "cn0_std_drop_db")
