from __future__ import annotations

from .base import BaseLayer


class GeometryLayer(BaseLayer):
    """Changes of HDOP and satellite count from the session baseline.

    The schema carries no per-satellite azimuth/elevation, so DOP cannot be recomputed and
    compared with the reported value; that check needs NAV-SAT data.
    """

    name = "3_geometry"
    feature_names = ("hdop_change", "sv_change")
