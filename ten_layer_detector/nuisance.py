"""Rates of benign GNSS-side nuisances in clean data (FALSE_ALARM_FIX_ROUND2.md, Step 1).

The metrics are defined in configs/nuisance_measure_v5.json before any rate was computed.
Works on any table with a time column (s), satellites, hdop, lat, lon, vel_n, vel_e, so the same
code measures real recordings and simulated sessions.
"""
from __future__ import annotations

import numpy as np

EARTH_R = 6_378_137.0
FAMILIES = ("sat_drop", "sat_rise", "hdop_jump", "position_jump")
PRIMARY = {"sat_drop": 1, "sat_rise": 1, "hdop_jump": 0.2, "position_jump": 3.0}
ALSO = {"sat_drop": (2, 3), "sat_rise": (2, 3), "hdop_jump": (0.1, 0.5), "position_jump": (2.0, 5.0)}


def _back(x: np.ndarray, t: np.ndarray, window_s: float):
    """x at the sample about window_s earlier (index of last sample at or before t - window_s); NaN if none."""
    idx = np.searchsorted(t, t - window_s, side="right") - 1
    ok = idx >= 0
    out = np.full(len(x), np.nan)
    out[ok] = x[idx[ok]]
    return out, idx, ok


def rising(ind: np.ndarray) -> int:
    ind = np.asarray(ind, dtype=bool)
    return int(np.sum(ind[1:] & ~ind[:-1]) + (1 if ind.size and ind[0] else 0))


def episodes(t, sats, hdop, lat_deg, lon_deg, vn, ve, window_s: float = 1.0, levels: dict | None = None) -> dict:
    """Episode counts for each family and level, and the recording length in minutes."""
    t = np.asarray(t, dtype=float)
    levels = levels or {k: (PRIMARY[k],) + ALSO[k] for k in FAMILIES}
    sats, hdop = np.asarray(sats, dtype=float), np.asarray(hdop, dtype=float)
    s_prev, idx, ok = _back(sats, t, window_s)
    h_prev, _, _ = _back(hdop, t, window_s)
    lat, lon = np.deg2rad(np.asarray(lat_deg, float)), np.deg2rad(np.asarray(lon_deg, float))
    north, east = lat * EARTH_R, lon * EARTH_R * np.cos(lat[0])
    cn = np.cumsum(np.r_[0.0, 0.5 * (np.asarray(vn, float)[1:] + np.asarray(vn, float)[:-1]) * np.diff(t)])
    ce = np.cumsum(np.r_[0.0, 0.5 * (np.asarray(ve, float)[1:] + np.asarray(ve, float)[:-1]) * np.diff(t)])
    pj = np.full(len(t), np.nan)
    pj[ok] = np.hypot((north[ok] - north[idx[ok]]) - (cn[ok] - cn[idx[ok]]), (east[ok] - east[idx[ok]]) - (ce[ok] - ce[idx[ok]]))
    out = {"minutes": float((t[-1] - t[0]) / 60.0), "counts": {}}
    with np.errstate(invalid="ignore"):
        for k in levels["sat_drop"]:
            out["counts"][f"sat_drop>={k}"] = rising((s_prev - sats) >= k)
        for k in levels["sat_rise"]:
            out["counts"][f"sat_rise>={k}"] = rising((sats - s_prev) >= k)
        for x in levels["hdop_jump"]:
            out["counts"][f"hdop_jump>={x}"] = rising(np.abs(hdop - h_prev) >= x - 1e-9)
        for d in levels["position_jump"]:
            out["counts"][f"position_jump>={d}"] = rising(pj >= d)
    return out


def pooled_rate(records: list[dict], key: str, n_boot: int = 10_000, seed: int = 0):
    """Pooled events per minute and a bootstrap-over-recordings 95% interval."""
    ev = np.array([r["counts"][key] for r in records], dtype=float)
    mn = np.array([r["minutes"] for r in records], dtype=float)
    rate = ev.sum() / mn.sum()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ev), size=(n_boot, len(ev)))
    boots = ev[idx].sum(axis=1) / mn[idx].sum(axis=1)
    return float(rate), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def verdict(sim: tuple, real: tuple) -> str:
    """Family verdict from the pre-registered rule: sim and real are (rate, lo, hi)."""
    if sim[0] > 2 * real[2]:
        return "much_more_active"
    if sim[0] < 0.5 * real[1]:
        return "much_quieter"
    return "close"
