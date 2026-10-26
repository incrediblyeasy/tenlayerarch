"""Turn decoded receiver and flight-controller data into detector rows.

`assemble_ubx` joins NAV-PVT, NAV-CLOCK, NAV-SAT, NAV-DOP and RXM-RAWX messages into one row
per epoch (GNSS columns of schema.py). `add_flight_controller` adds IMU, attitude and barometer
columns from a DataFlash log. Columns whose source message never appears are left out, so the
detector reports the affected layers as not evaluated instead of scoring NaN.

Not yet checked against a recording: the UBX layouts follow the u-blox interface description
and the DataFlash field names follow ArduPilot's logger (GPS, IMU, ATT, BARO); both need a real
log from the actual module and Cube Orange. The second-constellation (Galileo-only) solution
is not produced here, so layer 4 stays not evaluated unless it is added separately.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .ubx import (NAV, NAV_CLOCK, NAV_DOP, NAV_PVT, NAV_SAT, RXM, RXM_RAWX, UBXMessage, UBXParser, parse_nav_dop,
                  parse_rxm_rawx)

GPS_GNSS_ID = 0


def _best_gps_measurement(rawx: dict) -> dict | None:
    """The strongest GPS signal with a valid pseudorange and carrier phase."""
    ok = [m for m in rawx["meas"] if m["gnss_id"] == GPS_GNSS_ID and m["pr_valid"] and m["cp_valid"]]
    return max(ok, key=lambda m: m["cn0_dbhz"]) if ok else None


def assemble_ubx(messages: list[UBXMessage], session_id: str = "live", source: str = "ubx") -> pd.DataFrame:
    """One row per NAV-PVT epoch. Other messages join on the same iTOW (RAWX on rounded rcvTow)."""
    pvt, clock, sat, dop, raw = {}, {}, {}, {}, {}
    for m in messages:
        key = (m.msg_class, m.msg_id)
        try:
            if key == (NAV, NAV_PVT):
                d = UBXParser.parse_nav_pvt(m); pvt[d["itow_ms"]] = d
            elif key == (NAV, NAV_CLOCK):
                d = UBXParser.parse_nav_clock(m); clock[d["itow_ms"]] = d
            elif key == (NAV, NAV_SAT):
                d = UBXParser.parse_nav_sat(m); sat[d["itow_ms"]] = d
            elif key == (NAV, NAV_DOP):
                d = parse_nav_dop(m); dop[d["itow_ms"]] = d
            elif key == (RXM, RXM_RAWX):
                d = parse_rxm_rawx(m); raw[int(round(d["rcv_tow_s"] * 1000))] = d
        except ValueError:
            continue  # a malformed payload costs that message, not the run
    rows = []
    for itow in sorted(pvt):
        p = pvt[itow]
        row = {
            "session_id": session_id, "source": source, "t_gnss_s": itow * 1e-3,
            "lat_deg": p["lat_deg"], "lon_deg": p["lon_deg"], "alt_m": p["alt_m"],
            "vel_n_mps": p["vel_n_mps"], "vel_e_mps": p["vel_e_mps"], "vel_d_mps": p["vel_d_mps"],
            "h_acc_m": p["h_acc_m"], "v_acc_m": p["v_acc_m"], "pdop": p["pdop"],
            "num_sv": p["num_sv"], "fix_type": p["fix_type"],
        }
        if itow in clock:
            row["clk_bias_ns"], row["clk_drift_nsps"] = clock[itow]["clk_bias_ns"], clock[itow]["clk_drift_nsps"]
        if itow in sat:
            used = [s["cn0_dbhz"] for s in sat[itow]["sats"] if s["used"] and s["cn0_dbhz"] > 0]
            if used:
                row["cn0_dbhz"], row["cn0_std_dbhz"] = float(np.mean(used)), float(np.std(used))
        if itow in dop:
            row["hdop"], row["vdop"], row["pdop"] = dop[itow]["hdop"], dop[itow]["vdop"], dop[itow]["pdop"]
        if itow in raw:
            best = _best_gps_measurement(raw[itow])
            if best:
                row["pr_m"], row["cp_cycles"], row["dop_hz"], row["lock_ms"] = best["pr_m"], best["cp_cycles"], best["doppler_hz"], best["lock_ms"]
        rows.append(row)
    frame = pd.DataFrame(rows)
    return frame.dropna(axis=1, how="all") if len(frame) else frame


def add_flight_controller(gnss: pd.DataFrame, log: dict[str, pd.DataFrame], tolerance_s: float = 0.05) -> pd.DataFrame:
    """Add acc_b*, gyr_b*, roll/pitch/yaw (rad) and baro_alt_m from a DataFlash log by nearest time.

    The autopilot clock (TimeUS since boot) is tied to GPS time with the log's own GPS messages
    (GMS, milliseconds of week), by median offset. Rows with no sample within tolerance_s keep NaN
    and are dropped from the result, so nothing is interpolated across gaps."""
    if "GPS" not in log or not {"TimeUS", "GMS"} <= set(log["GPS"].columns):
        raise ValueError("DataFlash log has no GPS message with TimeUS and GMS to align the clocks")
    g = log["GPS"]
    offset_s = float(np.median(g["GMS"].to_numpy(dtype=float) * 1e-3 - g["TimeUS"].to_numpy(dtype=float) * 1e-6))
    out = gnss.sort_values("t_gnss_s").reset_index(drop=True)

    def merge(name, columns, rename, scale=None):
        nonlocal out
        if name not in log:
            return
        columns = [c for c in columns if c in log[name].columns]  # use whichever fields the log has
        if not columns:
            return
        df = log[name].copy()
        if name == "IMU" and "I" in df.columns:
            df = df[df["I"] == df["I"].min()]  # first IMU instance only
        df["t_gnss_s"] = df["TimeUS"].to_numpy(dtype=float) * 1e-6 + offset_s
        df = df[["t_gnss_s", *columns]].rename(columns=rename).sort_values("t_gnss_s")
        for col, k in (scale or {}).items():
            if col in df.columns:
                df[col] = df[col] * k
        out = pd.merge_asof(out, df, on="t_gnss_s", direction="nearest", tolerance=tolerance_s)

    merge("IMU", ["AccX", "AccY", "AccZ", "GyrX", "GyrY", "GyrZ"],
          {"AccX": "acc_bx_mps2", "AccY": "acc_by_mps2", "AccZ": "acc_bz_mps2", "GyrX": "gyr_bx_rps", "GyrY": "gyr_by_rps", "GyrZ": "gyr_bz_rps"})
    merge("ATT", ["Roll", "Pitch", "Yaw"], {"Roll": "roll_rad", "Pitch": "pitch_rad", "Yaw": "yaw_rad"},
          {"roll_rad": np.pi / 180, "pitch_rad": np.pi / 180, "yaw_rad": np.pi / 180})
    merge("BARO", ["Alt"], {"Alt": "baro_alt_m"})
    added = [c for c in out.columns if c not in gnss.columns]
    return out.dropna(subset=added).reset_index(drop=True) if added else out
