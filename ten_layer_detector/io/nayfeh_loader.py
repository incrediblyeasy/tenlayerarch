from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def load_nayfeh_workbook(path: str | Path, session_id: str | None = None) -> pd.DataFrame:
    """Load a Nayfeh-style CSV or workbook as a canonical session table.

    The repository is simulation-first, so this is intentionally lightweight: the loader
    standardizes field names and ensures the session metadata is consistent with the
    canonical schema rather than performing a full workbook parser.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Nayfeh workbook not found: {file_path}")

    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(file_path)
    elif suffix in {".xlsx", ".xls"}:
        try:
            frame = pd.read_excel(file_path)
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise ImportError("OpenPyXL is required to read .xlsx/.xls files") from exc
    else:
        raise ValueError(f"Unsupported Nayfeh file type: {suffix!r}")

    lower_cols = {str(col).lower(): col for col in frame.columns}
    rename_map: dict[str, str] = {}
    alias_map = {
        "lat": "lat_deg",
        "lon": "lon_deg",
        "latitude": "lat_deg",
        "longitude": "lon_deg",
        "altitude": "alt_m",
        "cn0": "cn0_dbhz",
        "baroalt": "baro_alt_m",
        "accx": "acc_bx_mps2",
        "accy": "acc_by_mps2",
        "accz": "acc_bz_mps2",
    }
    for raw_name, canonical in alias_map.items():
        if raw_name in lower_cols:
            rename_map[lower_cols[raw_name]] = canonical

    if rename_map:
        frame = frame.rename(columns=rename_map)

    if "session_id" not in frame.columns:
        frame["session_id"] = session_id or file_path.stem
    if "source" not in frame.columns:
        frame["source"] = "nayfeh"
    if "label" not in frame.columns:
        frame["label"] = 0
    return frame
