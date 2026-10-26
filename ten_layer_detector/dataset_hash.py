"""Content hash of a saved dataset, to check that a regenerated dataset is identical.

    python -m ten_layer_detector.dataset_hash datasets/sim_fa2
"""
from __future__ import annotations

import hashlib
import sys

import pandas as pd

from .dataset import load_sessions


def content_hash(path: str) -> tuple[str, int]:
    sessions, _ = load_sessions(path)
    h = hashlib.sha256()
    for s in sessions:
        h.update(pd.util.hash_pandas_object(s, index=False).values.tobytes())
    return h.hexdigest()[:16], len(sessions)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        digest, n = content_hash(p)
        print(f"{p}  sessions={n}  sha256[:16]={digest}")
