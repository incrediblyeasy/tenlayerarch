"""Detection metrics: per-session outcomes, rates with Wilson intervals, false alarms per hour, delay."""
from __future__ import annotations

from typing import Dict, Iterable, List

import numpy as np


def wilson_interval(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return float(max(0.0, centre - half)), float(min(1.0, centre + half))


def rising_edges(alarm: np.ndarray) -> int:
    a = np.asarray(alarm, dtype=bool)
    return int(np.sum(a[1:] & ~a[:-1]) + (1 if a.size and a[0] else 0))


def fa_target_threshold(score_sessions: List[np.ndarray], clean_hours: float, start: float, target_per_hour: float, k: int) -> float:
    """Lowest threshold, not below `start`, whose persistent-alarm events on the given clean
    calibration sessions are at most target_per_hour * clean_hours."""
    from .layers.base import persistent_alarm

    allowed = target_per_hour * clean_hours
    pooled = np.concatenate([v[np.isfinite(v)] for v in score_sessions])
    candidates = np.unique(np.r_[start, pooled[pooled >= start]])
    # Events fall (almost always monotonically) as the threshold rises, so binary search.
    lo, hi = 0, len(candidates) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        events = sum(rising_edges(persistent_alarm(v, candidates[mid], k)) for v in score_sessions)
        if events <= allowed:
            hi = mid
        else:
            lo = mid + 1
    return float(candidates[lo])


def session_outcome(alarm: np.ndarray, t: np.ndarray, onset_s: float | None, active: np.ndarray) -> dict:
    """onset_s None means a clean session. Alarms before onset count as false alarms."""
    alarm = np.asarray(alarm, dtype=bool)
    dt = float(np.median(np.diff(t))) if t.size > 1 else 0.0
    if onset_s is None:
        return {"fa_events": rising_edges(alarm), "clean_s": float(active.sum() * dt), "alarmed": bool(alarm.any())}
    pre = t < onset_s
    post_alarm = alarm & ~pre
    first = t[np.argmax(post_alarm)] if post_alarm.any() else None
    return {
        "fa_events_pre_onset": rising_edges(alarm & pre),
        "detected": first is not None,
        "delay_s": float(first - onset_s) if first is not None else float("nan"),
    }


def rate(k: int, n: int) -> dict:
    lo, hi = wilson_interval(k, n)
    return {"rate": k / n if n else float("nan"), "k": int(k), "n": int(n), "ci95": [lo, hi]}


def summarize_outcomes(clean: List[dict], attacked: Dict[str, List[dict]]) -> dict:
    events = sum(o["fa_events"] for o in clean)
    hours = sum(o["clean_s"] for o in clean) / 3600.0
    per_type = {a: rate(sum(o["detected"] for o in outs), len(outs)) for a, outs in sorted(attacked.items())}
    all_outs = [o for outs in attacked.values() for o in outs]
    delays = np.array([o["delay_s"] for o in all_outs if o["detected"]])
    return {
        "per_type": per_type,
        "all_attacks": rate(sum(o["detected"] for o in all_outs), len(all_outs)),
        "fa_events": int(events),
        "clean_hours": hours,
        "false_alarms_per_hour": events / hours if hours else float("nan"),
        "clean_sessions_alarmed": rate(sum(o["alarmed"] for o in clean), len(clean)),
        "pre_onset_fa_events": int(sum(o["fa_events_pre_onset"] for o in all_outs)),
        "delay_median_s": float(np.median(delays)) if delays.size else float("nan"),
        "delay_p90_s": float(np.percentile(delays, 90)) if delays.size else float("nan"),
    }


def compute_classification_metrics(y_true: Iterable[int], y_pred: Iterable[int]) -> Dict[str, float]:
    y_true = np.asarray(list(y_true), dtype=int)
    y_pred = np.asarray(list(y_pred), dtype=int)
    tp = float(np.sum((y_true == 1) & (y_pred == 1)))
    fp = float(np.sum((y_true == 0) & (y_pred == 1)))
    fn = float(np.sum((y_true == 1) & (y_pred == 0)))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"accuracy": float(np.mean(y_true == y_pred)) if len(y_true) else 0.0, "precision": precision, "recall": recall, "f1": f1}
