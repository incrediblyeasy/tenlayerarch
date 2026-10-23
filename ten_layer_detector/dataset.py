from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List

import pandas as pd

from .splits import split_sessions

REQUIRED_SESSION_COLUMNS = {"t_gnss_s", "label", "attack_type", "attack_onset_s", "session_id"}

__all__ = ["SessionDataset", "split_sessions", "save_sessions", "load_sessions"]


@dataclass
class SessionDataset:
    sessions: List[pd.DataFrame] = field(default_factory=list)
    source: str = "simulated"

    def validate_session_schema(self) -> bool:
        if not self.sessions:
            return False
        return all(REQUIRED_SESSION_COLUMNS.issubset(session.columns) for session in self.sessions)

    def as_dataframe(self) -> pd.DataFrame:
        if not self.sessions:
            return pd.DataFrame()
        return pd.concat(self.sessions, ignore_index=True)


def save_sessions(path: str | Path, sessions: List[pd.DataFrame], metadata: List[dict[str, Any]] | None = None) -> Path:
    """Write sessions to <path>/sessions.csv.gz and metadata to <path>/sessions_meta.json."""
    out = Path(path)
    out.mkdir(parents=True, exist_ok=True)
    pd.concat(sessions, ignore_index=True).to_csv(out / "sessions.csv.gz", index=False, float_format="%.10g")
    if metadata is not None:
        (out / "sessions_meta.json").write_text(json.dumps(metadata, indent=1), encoding="utf-8")
    return out


def load_sessions(path: str | Path) -> tuple[List[pd.DataFrame], List[dict[str, Any]] | None]:
    src = Path(path)
    data = pd.read_csv(src / "sessions.csv.gz", dtype={"session_id": str})
    sessions = [g.reset_index(drop=True) for _, g in data.groupby("session_id", sort=False)]
    meta_path = src / "sessions_meta.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else None
    return sessions, metadata
