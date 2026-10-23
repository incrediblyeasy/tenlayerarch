from __future__ import annotations

from .base import BaseLayer


class PhysicalLayer(BaseLayer):
    """Physical plausibility: GNSS altitude vs barometer, and acceleration implied by the positions."""

    name = "6_physical"
    feature_names = ("baro_resid_m", "implied_accel_mps2")
