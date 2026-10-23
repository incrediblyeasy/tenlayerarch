from __future__ import annotations

from typing import Iterable

import pandas as pd

COMMON_COLUMNS = {
    "session_id": "string",
    "source": "string",
    "t_gnss_s": "float",
    "t_host_ns": "int",
    "label": "int",
    "attack_type": "string",
    "attack_onset_s": "float",
}

GNSS_COLUMNS = {
    "lat_deg": "float",
    "lon_deg": "float",
    "alt_m": "float",
    "vel_n_mps": "float",
    "vel_e_mps": "float",
    "vel_d_mps": "float",
    "cn0_dbhz": "float",
    "cn0_std_dbhz": "float",
    "clk_bias_ns": "float",
    "clk_drift_nsps": "float",
    "pr_m": "float",
    "cp_cycles": "float",
    "dop_hz": "float",
    "lock_ms": "float",
    "h_acc_m": "float",
    "v_acc_m": "float",
    "pdop": "float",
    "hdop": "float",
    "vdop": "float",
    "num_sv": "int",
    "fix_type": "int",
}

# Second-constellation (Galileo-only) solution for layer 4. Optional: data without it
# reports layer 4 as not evaluated.
MULTI_GNSS_COLUMNS = {
    "gal_lat_deg": "float",
    "gal_lon_deg": "float",
    "gal_alt_m": "float",
}

SENSOR_COLUMNS = {
    "acc_bx_mps2": "float",
    "acc_by_mps2": "float",
    "acc_bz_mps2": "float",
    "gyr_bx_rps": "float",
    "gyr_by_rps": "float",
    "gyr_bz_rps": "float",
    "roll_rad": "float",
    "pitch_rad": "float",
    "yaw_rad": "float",
    "baro_alt_m": "float",
}

CANONICAL_COLUMNS = {**COMMON_COLUMNS, **GNSS_COLUMNS, **SENSOR_COLUMNS}
OPTIONAL_COLUMNS = dict(MULTI_GNSS_COLUMNS)


def schema_problems(frame: pd.DataFrame, required: Iterable[str] | None = None) -> list[str]:
    """List of problems; empty when the frame satisfies the schema."""
    problems = []
    required = list(CANONICAL_COLUMNS) if required is None else list(required)
    missing = [c for c in required if c not in frame.columns]
    if missing:
        problems.append(f"missing columns: {missing}")
    if "session_id" in frame.columns and frame["session_id"].nunique() != 1:
        problems.append("a session frame must hold exactly one session_id")
    if "label" in frame.columns and not frame["label"].isin([0, 1]).all():
        problems.append("label must be 0 or 1")
    if {"label", "attack_type"} <= set(frame.columns):
        clean_type = frame["attack_type"].isin(["clean", "none"])
        if (frame["label"].eq(1) & clean_type).any():
            problems.append("rows labelled 1 in a clean session")
    if "t_gnss_s" in frame.columns and not frame["t_gnss_s"].is_monotonic_increasing:
        problems.append("t_gnss_s must be increasing")
    return problems


def validate_schema(frame: pd.DataFrame, required: Iterable[str] | None = None) -> bool:
    return not schema_problems(frame, required)


def session_metadata_template() -> dict:
    return {
        "session_id": "",
        "kind": "clean",
        "source": "sim",
        "attack_type": "clean",
        "attack_start_t_gnss_s": None,
        "attack_end_t_gnss_s": None,
        "receiver_model": None,
        "firmware": None,
        "rates": {},
        "time_offsets": {},
        "seed": 0,
    }
