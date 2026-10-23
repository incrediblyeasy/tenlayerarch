from __future__ import annotations

from .base import BaseLayer


class MultiConstellationLayer(BaseLayer):
    """Distance between the GPS and the Galileo position solutions.

    Needs gal_lat_deg / gal_lon_deg / gal_alt_m; data without a second solution raises
    MissingInputError and the protocol reports the layer as not evaluated.
    """

    name = "4_multi_constellation"
    feature_names = ("const_diff_m",)
