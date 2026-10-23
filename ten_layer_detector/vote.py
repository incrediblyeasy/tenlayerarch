"""Combining layer scores: the designed logistic vote, an equal-weight baseline, and
attack-type naming. All are fitted on out-of-fold layer scores from training sessions."""
from __future__ import annotations

from typing import Iterable, Mapping, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def _squash(scores: np.ndarray) -> np.ndarray:
    """Compress heavy-tailed layer scores (log-like for large values, sign-preserving)."""
    return np.arcsinh(np.asarray(scores, dtype=float))


class LogisticVote:
    """Logistic regression on standardised, squashed per-row layer scores."""

    def __init__(self, layer_names: Sequence[str], seed: int = 0):
        self.layer_names = list(layer_names)
        self.model = Pipeline(
            [("scale", StandardScaler()), ("lr", LogisticRegression(class_weight="balanced", max_iter=2000, random_state=seed))]
        )

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> "LogisticVote":
        self.model.fit(_squash(scores), np.asarray(labels, dtype=int))
        return self

    def score_rows(self, scores: np.ndarray) -> np.ndarray:
        """Log-odds of attack (does not saturate the way the probability does near 1)."""
        return self.model.decision_function(_squash(scores))

    @property
    def weights(self) -> dict[str, float]:
        return dict(zip(self.layer_names, self.model.named_steps["lr"].coef_[0].astype(float)))


class EqualWeightVote:
    """Baseline: mean of squashed layer scores, each standardised on clean training rows."""

    def __init__(self, layer_names: Sequence[str]):
        self.layer_names = list(layer_names)

    def fit(self, scores: np.ndarray, labels: np.ndarray) -> "EqualWeightVote":
        clean = _squash(scores)[np.asarray(labels) == 0]
        self.mu_ = clean.mean(axis=0)
        self.sd_ = clean.std(axis=0) + 1e-9
        return self

    def score_rows(self, scores: np.ndarray) -> np.ndarray:
        return ((_squash(scores) - self.mu_) / self.sd_).mean(axis=1)


class AttackNamer:
    """Multinomial logistic regression naming the attack type from the layer scores seen
    after the alarm (training: after the true onset)."""

    def __init__(self, layer_names: Sequence[str], seed: int = 0):
        self.layer_names = list(layer_names)
        self.model = Pipeline(
            [("scale", StandardScaler()), ("lr", LogisticRegression(max_iter=5000, C=1.0, random_state=seed))]
        )

    @staticmethod
    def session_features(scores: np.ndarray) -> np.ndarray:
        s = _squash(scores)
        if s.shape[0] == 0:
            return np.zeros(2 * s.shape[1])
        return np.concatenate((s.max(axis=0), s.mean(axis=0)))

    def fit(self, attack_phase_scores: Iterable[np.ndarray], attack_types: Iterable[str]) -> "AttackNamer":
        X = np.vstack([self.session_features(s) for s in attack_phase_scores])
        self.model.fit(X, list(attack_types))
        return self

    def predict(self, attack_phase_scores: np.ndarray) -> str:
        return str(self.model.predict(self.session_features(attack_phase_scores)[None, :])[0])


def weighted_vote(
    layer_scores: Mapping[str, float] | Iterable[float],
    weights: Mapping[str, float] | Iterable[float] | None = None,
) -> float:
    """Weighted mean of scores (helper; the detector uses LogisticVote)."""
    if isinstance(layer_scores, Mapping):
        weights = {k: 1.0 for k in layer_scores} if weights is None else weights
        if not isinstance(weights, Mapping):
            raise TypeError("weights must be a mapping when layer_scores is a mapping")
        total = sum(float(weights.get(k, 1.0)) for k in layer_scores)
        return float(sum(float(layer_scores[k]) * float(weights.get(k, 1.0)) for k in layer_scores) / total) if total else 0.0
    values = np.asarray(list(layer_scores), dtype=float)
    w = np.ones_like(values) if weights is None else np.asarray(list(weights), dtype=float)
    if w.shape != values.shape:
        raise ValueError("weights must have the same shape as layer_scores")
    return float(np.sum(values * w) / np.sum(w)) if np.sum(w) else 0.0
