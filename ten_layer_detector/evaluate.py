"""Evaluation protocol: disjoint train / calibration / test sessions, frozen thresholds,
per-type detection with 95% intervals, false alarms per hour, delay, ablation, attack
naming and detection by spoofer power."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Any, Dict, List, Sequence

import numpy as np
import pandas as pd

from .config import DEFAULT_DETECTOR_CONFIG, DetectorConfig
from .features import compute_features, warmup_mask
from .layers import persistent_alarm
from .layers.base import is_clean_session
from .metrics import rate, session_outcome, summarize_outcomes
from .pipeline import EQUAL_VOTE, VOTE, VOTE_FA, TenLayerDetector
from .splits import session_id, session_type, split_three_way
from .vote import LogisticVote

POWER_BINS = ((0.0, 1.0), (1.0, 3.0), (3.0, 6.0), (6.0, 10.01))


def _onset(session: pd.DataFrame) -> float | None:
    if is_clean_session(session):
        return None
    if "attack_onset_s" in session.columns:
        return float(session["attack_onset_s"].iloc[0])
    t = session["t_gnss_s"].to_numpy()
    return float(t[np.argmax(session["label"].to_numpy() != 0)])


def _outcomes(sessions: Sequence[pd.DataFrame], alarms: Sequence[np.ndarray], cfg: DetectorConfig):
    clean: List[dict] = []
    attacked: Dict[str, List[dict]] = defaultdict(list)
    per_session: Dict[str, dict] = {}
    for s, alarm in zip(sessions, alarms):
        t = s["t_gnss_s"].to_numpy(dtype=float)
        active = ~warmup_mask(s, cfg)
        onset = _onset(s)
        out = session_outcome(alarm, t, onset, active)
        per_session[session_id(s)] = out
        if onset is None:
            clean.append(out)
        else:
            attacked[session_type(s)].append(out)
    return summarize_outcomes(clean, attacked), per_session


def _counts(sets: Dict[str, Sequence[pd.DataFrame]]) -> dict:
    out = {}
    for name, sessions in sets.items():
        types = pd.Series([session_type(s) for s in sessions]).value_counts().sort_index()
        hours = sum(float(s["t_gnss_s"].iloc[-1] - s["t_gnss_s"].iloc[0]) for s in sessions if is_clean_session(s)) / 3600
        out[name] = {"sessions": len(sessions), "by_type": {k: int(v) for k, v in types.items()}, "clean_hours": hours}
    return out


def evaluate_protocol(
    sessions: Sequence[pd.DataFrame],
    metadata: Sequence[dict] | None = None,
    *,
    config: DetectorConfig = DEFAULT_DETECTOR_CONFIG,
    seed: int | None = None,
    ablation: bool = True,
) -> Dict[str, Any]:
    """Run the full protocol. Missing layer inputs are reported, never silently skipped."""
    cfg = config if seed is None else replace(config, split_seed=seed)
    sessions = list(sessions)
    if len(sessions) < 6:
        raise ValueError("evaluate_protocol needs at least 6 sessions")
    train, cal, test = split_three_way(sessions, cfg.train_fraction, cfg.calibration_fraction, seed=cfg.split_seed)
    if not test or all(is_clean_session(s) for s in test) or not any(is_clean_session(s) for s in test):
        raise ValueError("test set must contain clean and attacked sessions; add sessions")

    feats = {id(s): compute_features(s, None, cfg) for s in sessions}
    det = TenLayerDetector(cfg).fit(train, cal, [feats[id(s)] for s in train], [feats[id(s)] for s in cal])

    cal_scores = [det.score_session(s, feats[id(s)]) for s in cal]
    test_scores = [det.score_session(s, feats[id(s)]) for s in test]
    test_alarms = [det.alarms(sc) for sc in test_scores]

    detectors: Dict[str, Any] = {}
    per_session: Dict[str, Dict[str, dict]] = {}
    for name in det.detector_names:
        detectors[name], per_session[name] = _outcomes(test, [a[name] for a in test_alarms], cfg)
        detectors[name]["threshold"] = det.thresholds[name]

    # Attack naming, on attacked test sessions the vote detected.
    confusion: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s, sc, al in zip(test, test_scores, test_alarms):
        onset = _onset(s)
        if onset is None:
            continue
        t = s["t_gnss_s"].to_numpy()
        post = al[VOTE] & (t >= onset)
        if post.any():
            k = int(np.argmax(post))
            confusion[session_type(s)][det.namer.predict(sc["_matrix"][k:])] += 1
    named = sum(sum(v.values()) for v in confusion.values())
    correct = sum(confusion[a].get(a, 0) for a in confusion)
    naming = {
        "confusion": {a: dict(v) for a, v in sorted(confusion.items())},
        "accuracy": rate(correct, named),
    }

    # Ablation: refit the vote without one layer at a time (same OOF scores, same splits).
    ablation_rows = []
    if ablation:
        cal_clean = [(sc["_matrix"], ~warmup_mask(s, cfg)) for s, sc in zip(cal, cal_scores) if is_clean_session(s)]
        for j, removed in enumerate([None] + det.layer_names):
            cols = [c for c in range(len(det.layer_names)) if det.layer_names[c] != removed]
            names = [det.layer_names[c] for c in cols]
            vote = LogisticVote(names, cfg.model_seed).fit(det.oof_X_[:, cols], det.oof_y_)
            thr = float(np.percentile(np.concatenate([vote.score_rows(m[:, cols])[a] for m, a in cal_clean]), cfg.threshold_percentile))
            alarms = []
            for s, sc in zip(test, test_scores):
                v = vote.score_rows(sc["_matrix"][:, cols])
                v[warmup_mask(s, cfg)] = -np.inf
                alarms.append(persistent_alarm(v, thr, cfg.persistence_k))
            summary, _ = _outcomes(test, alarms, cfg)
            ablation_rows.append({
                "removed_layer": removed or "(none)",
                "detect_all": summary["all_attacks"]["rate"],
                "false_alarms_per_hour": summary["false_alarms_per_hour"],
                "delay_median_s": summary["delay_median_s"],
                **{f"detect_{a}": r["rate"] for a, r in summary["per_type"].items()},
            })

    # Detection by spoofer power (needs generator metadata).
    by_power: List[dict] = []
    if metadata:
        power = {str(m["session_id"]): m.get("power_db") for m in metadata}
        for lo, hi in POWER_BINS:
            ids = [session_id(s) for s in test if not is_clean_session(s) and power.get(session_id(s)) is not None and lo <= power[session_id(s)] < hi]
            row = {"power_db": f"{lo:g}-{min(hi, 10):g}", "n": len(ids)}
            for name in det.detector_names:
                row[name] = float(np.mean([per_session[name][i]["detected"] for i in ids])) if ids else float("nan")
            by_power.append(row)

    layer_names = det.layer_names
    best_layer = max(layer_names, key=lambda n: (detectors[n]["all_attacks"]["rate"], -detectors[n]["false_alarms_per_hour"]))
    def dominates(name: str) -> bool:
        a, b = detectors[name], detectors[best_layer]
        return bool(a["all_attacks"]["rate"] > b["all_attacks"]["rate"] and a["false_alarms_per_hour"] <= b["false_alarms_per_hour"])

    vote_vs_best = {
        "best_layer": best_layer,
        "best_layer_detect": detectors[best_layer]["all_attacks"]["rate"],
        "best_layer_fa_per_hour": detectors[best_layer]["false_alarms_per_hour"],
        "vote_detect": detectors[VOTE]["all_attacks"]["rate"],
        "vote_fa_per_hour": detectors[VOTE]["false_alarms_per_hour"],
        "vote_at_fa_target_detect": detectors[VOTE_FA]["all_attacks"]["rate"],
        "vote_at_fa_target_fa_per_hour": detectors[VOTE_FA]["false_alarms_per_hour"],
        # The vote beats the best layer if it detects more at no more false alarms, at either operating point.
        "vote_beats_best_layer": dominates(VOTE) or dominates(VOTE_FA),
    }

    return {
        "config": cfg.__dict__ | {"exclude_features": list(cfg.exclude_features)},
        "counts": _counts({"train": train, "calibration": cal, "test": test}),
        "not_evaluated": det.not_evaluated,
        "detectors": detectors,
        "vote_weights": det.vote.weights,
        "vote_vs_best_layer": vote_vs_best,
        "ablation": ablation_rows,
        "naming": naming,
        "by_power": by_power,
        "detector": det,
    }


__all__ = ["evaluate_protocol", "POWER_BINS", "VOTE", "EQUAL_VOTE"]
