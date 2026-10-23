from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd


class MavlinkLogReader:
    """Basic parser for MAVLink/DataFlash-style logs.

    It accepts plain text logs or CSV exports and returns a pandas DataFrame with
    the same standardized fields used by the project.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def read(self, columns: Iterable[str] | None = None) -> pd.DataFrame:
        if not self.path.exists():
            raise FileNotFoundError(f"Log file not found: {self.path}")

        suffix = self.path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(self.path)
        else:
            rows = []
            with self.path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "," in line:
                        parts = [part.strip() for part in line.split(",")]
                    else:
                        parts = [part.strip() for part in line.split()]
                    if not parts:
                        continue
                    rows.append({"message": parts[0], "raw": line})
            df = pd.DataFrame(rows)

        if columns is not None:
            missing = [col for col in columns if col not in df.columns]
            if missing:
                for col in missing:
                    df[col] = None
        df.setdefault("source", "mavlink")
        return df
