"""Session-level splits. A session is never split across sets."""
from __future__ import annotations

from collections import defaultdict
from typing import Sequence, Tuple

import numpy as np
import pandas as pd


def session_id(session: pd.DataFrame) -> str:
    if "session_id" not in session.columns:
        raise ValueError("Every session must include a session_id column to split by session")
    return str(session["session_id"].iloc[0])


def session_type(session: pd.DataFrame) -> str:
    if "attack_type" in session.columns:
        return str(session["attack_type"].iloc[0])
    return "attacked" if "label" in session.columns and session["label"].any() else "clean"


def _check_unique(sessions: Sequence[pd.DataFrame]) -> None:
    ids = [session_id(s) for s in sessions]
    if len(set(ids)) != len(ids):
        raise ValueError("session_id values must be unique")


def _by_type(sessions: Sequence[pd.DataFrame], seed: int | None) -> dict[str, list[int]]:
    rng = np.random.default_rng(seed)
    groups: dict[str, list[int]] = defaultdict(list)
    for i, s in enumerate(sessions):
        groups[session_type(s)].append(i)
    for idx in groups.values():
        rng.shuffle(idx)
    return dict(sorted(groups.items()))


def split_sessions(
    sessions: Sequence[pd.DataFrame],
    test_fraction: float = 0.5,
    *,
    seed: int | None = None,
) -> Tuple[list[pd.DataFrame], list[pd.DataFrame]]:
    """Two-way split by session, stratified by attack type, shuffled by seed."""
    if not sessions:
        return [], []
    if len(sessions) < 2:
        raise ValueError("At least two sessions are required to create a train/test split")
    if not 0.0 < test_fraction < 1.0:
        raise ValueError("test_fraction must be between 0 and 1")
    _check_unique(sessions)
    train, test = [], []
    for idx in _by_type(sessions, seed).values():
        k = int(round(len(idx) * test_fraction))
        if len(idx) >= 2:
            k = min(max(k, 1), len(idx) - 1)
        test += idx[:k]
        train += idx[k:]
    if not train or not test:
        raise ValueError("split produced an empty set; add sessions")
    return [sessions[i] for i in sorted(train)], [sessions[i] for i in sorted(test)]


def split_three_way(
    sessions: Sequence[pd.DataFrame],
    train_fraction: float,
    calibration_fraction: float,
    *,
    seed: int | None = None,
) -> Tuple[list[pd.DataFrame], list[pd.DataFrame], list[pd.DataFrame]]:
    """Disjoint train / calibration / test sets, stratified by attack type."""
    if not (0 < train_fraction < 1 and 0 < calibration_fraction < 1 and train_fraction + calibration_fraction < 1):
        raise ValueError("fractions must be in (0, 1) and sum to less than 1")
    _check_unique(sessions)
    tr, ca, te = [], [], []
    for idx in _by_type(sessions, seed).values():
        n_tr = int(round(len(idx) * train_fraction))
        n_ca = int(round(len(idx) * calibration_fraction))
        tr += idx[:n_tr]
        ca += idx[n_tr : n_tr + n_ca]
        te += idx[n_tr + n_ca :]
    return [sessions[i] for i in sorted(tr)], [sessions[i] for i in sorted(ca)], [sessions[i] for i in sorted(te)]


def session_folds(sessions: Sequence[pd.DataFrame], k: int, *, seed: int | None = None) -> list[list[int]]:
    """k disjoint folds of session indices, stratified by attack type."""
    if k < 2:
        raise ValueError("k must be at least 2")
    folds: list[list[int]] = [[] for _ in range(k)]
    j = 0
    for idx in _by_type(sessions, seed).values():
        for i in idx:
            folds[j % k].append(i)
            j += 1
    return [sorted(f) for f in folds]
