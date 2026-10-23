from __future__ import annotations

from .base import BaseLayer


class RawSignalLayer(BaseLayer):
    """Raw-measurement checks on the tracked satellite: carrier-lock resets and
    code-minus-carrier divergence.

    On hardware this layer is meant to run on RTL-SDR tracking output (GNSS-SDR); here it
    reads the receiver's raw pseudorange, carrier phase and lock time.
    """

    name = "7_raw_signal"
    feature_names = ("lock_reset", "code_carrier_m")
