from __future__ import annotations

from .base import BaseLayer


class CrossDomainLayer(BaseLayer):
    """Position vs velocity vs acceleration: GNSS position change against reported velocity,
    and GNSS-derived acceleration against the IMU."""

    name = "5_cross_domain"
    feature_names = ("posvel_mps", "imu_resid_mps2")
