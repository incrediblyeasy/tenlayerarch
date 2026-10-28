from __future__ import annotations

import numpy as np

C = 299_792_458.0
L1_HZ = 1575.42e6
L1_LAMBDA = C / L1_HZ
EARTH_R = 6_378_137.0
N_SAT = 10
CN0_LOST_DBHZ = 28.0


def sat_elevation_azimuth(rng: np.random.Generator, t: np.ndarray, n_sat: int = N_SAT) -> tuple[np.ndarray, np.ndarray]:
    """Return (elevation, azimuth) in degrees, shape (n, n_sat), slowly moving."""
    az0 = rng.uniform(0.0, 360.0, n_sat)
    el0 = rng.uniform(12.0, 85.0, n_sat)
    az = az0 + rng.uniform(-0.008, 0.008, n_sat) * t[:, None]
    el = np.clip(el0 + rng.uniform(-0.006, 0.006, n_sat) * t[:, None], 5.0, 89.0)
    return el, az


def unit_ned(el_deg: np.ndarray, az_deg: np.ndarray) -> np.ndarray:
    """Receiver-to-satellite unit vectors in NED."""
    az = np.deg2rad(az_deg)
    el = np.deg2rad(el_deg)
    return np.stack((np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), -np.sin(el)), axis=-1)


def dop_from_geometry(u: np.ndarray, used: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """HDOP, VDOP, PDOP from unit vectors u (n, k, 3) and a used-satellite mask (n, k)."""
    if used is None:
        used = np.ones(u.shape[:2], dtype=bool)
    geom = np.concatenate((-u, np.ones(u.shape[:2] + (1,))), axis=-1) * used[..., None]
    q = np.linalg.pinv(np.einsum("nki,nkj->nij", geom, geom))
    hdop = np.sqrt(q[:, 0, 0] + q[:, 1, 1])
    vdop = np.sqrt(q[:, 2, 2])
    pdop = np.sqrt(q[:, 0, 0] + q[:, 1, 1] + q[:, 2, 2])
    return np.clip(hdop, 0.3, 50.0), np.clip(vdop, 0.3, 50.0), np.clip(pdop, 0.3, 50.0)


def gauss_markov(rng: np.random.Generator, n: int, dt: float, sigma: float, tau: float) -> np.ndarray:
    a = np.exp(-dt / tau)
    out = np.empty(n)
    out[0] = rng.normal(0.0, sigma)
    noise = rng.normal(0.0, sigma * np.sqrt(1 - a * a), n)
    for k in range(1, n):
        out[k] = a * out[k - 1] + noise[k]
    return out


def solution_error(rng: np.random.Generator, n: int, dt: float, hdop: np.ndarray, vdop: np.ndarray, white_scale: float = 1.0) -> np.ndarray:
    """GNSS position error (NED metres): Gauss-Markov scaled by DOP plus white noise (times white_scale)."""
    return np.stack(
        (
            gauss_markov(rng, n, dt, 0.8, 30.0) * hdop / 1.2 + rng.normal(0.0, 0.4 * white_scale, n),
            gauss_markov(rng, n, dt, 0.8, 30.0) * hdop / 1.2 + rng.normal(0.0, 0.4 * white_scale, n),
            gauss_markov(rng, n, dt, 1.2, 30.0) * vdop / 1.6 + rng.normal(0.0, 0.6 * white_scale, n),
        ),
        axis=1,
    )


def ned_to_geodetic(pos_ned: np.ndarray, lat0: float, lon0: float, alt0: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lat = lat0 + np.rad2deg(pos_ned[:, 0] / EARTH_R)
    lon = lon0 + np.rad2deg(pos_ned[:, 1] / (EARTH_R * np.cos(np.deg2rad(lat0))))
    return lat, lon, alt0 - pos_ned[:, 2]
