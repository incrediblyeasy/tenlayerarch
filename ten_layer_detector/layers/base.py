from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, Sequence, Tuple

import numpy as np
import pandas as pd

from ..config import DEFAULT_DETECTOR_CONFIG, DetectorConfig
from ..features import MissingInputError, compute_features, required_columns, warmup_mask

__all__ = ["BaseLayer", "LayerResult", "MissingInputError", "NotFittedError", "evaluate_layers", "persistent_alarm", "is_clean_session"]


class NotFittedError(RuntimeError):
    """Raised when a layer is scored or alarmed before fit/calibrate."""


@dataclass
class LayerResult:
    name: str
    score: float
    detector: str
    threshold: float
    alarmed: bool

    @property
    def passed(self) -> bool:
        return not self.alarmed


def is_clean_session(frame: pd.DataFrame) -> bool:
    return "label" not in frame.columns or not bool((frame["label"].to_numpy() != 0).any())


def persistent_alarm(scores: np.ndarray, threshold: float, k: int) -> np.ndarray:
    """True at row i when rows i-k+1..i are all strictly above threshold.

    Strict, so a discrete feature whose clean value sits at the threshold cannot alarm.
    """
    above = np.asarray(scores, dtype=float) > threshold
    if k <= 1 or above.size == 0:
        return above
    run = pd.Series(above.astype(int)).rolling(k, min_periods=k).sum().to_numpy()
    return run >= k


def _pairs(sessions: Iterable[pd.DataFrame], features: Iterable[pd.DataFrame] | None) -> Iterator[Tuple[pd.DataFrame, pd.DataFrame | None]]:
    sessions = list(sessions)
    feats = [None] * len(sessions) if features is None else list(features)
    if len(feats) != len(sessions):
        raise ValueError("features must be parallel to sessions")
    return zip(sessions, feats)


class BaseLayer:
    """A detector layer: causal per-row score, fitted on clean training sessions.

    Default scoring: each feature is normalised by its clean-training median and the
    distance from that median to its 99th percentile; the row score is the maximum over
    the layer's features. Rows in the warm-up (first baseline_s seconds) score 0.
    """

    name = "base"
    feature_names: Tuple[str, ...] = ()
    uses_attacked_sessions = False

    def __init__(self, cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG):
        self.cfg = cfg
        self.threshold: float | None = None
        self._fitted = False

    # -------------------------------------------------------------- inputs
    @property
    def features(self) -> Tuple[str, ...]:
        return tuple(f for f in self.feature_names if f not in self.cfg.exclude_features)

    @property
    def evaluable_by_config(self) -> bool:
        return bool(self.features)

    @property
    def required_columns(self) -> Tuple[str, ...]:
        return required_columns(self.features)

    def _require_columns(self, frame: pd.DataFrame) -> None:
        missing = [c for c in self.required_columns if c not in frame.columns]
        if missing:
            raise MissingInputError(f"{self.name} missing required columns: {missing}")

    def can_run_on(self, frame: pd.DataFrame) -> bool:
        return self.evaluable_by_config and all(c in frame.columns for c in self.required_columns)

    def feature_matrix(self, frame: pd.DataFrame, features: pd.DataFrame | None = None) -> np.ndarray:
        self._require_columns(frame)
        if features is None:
            features = compute_features(frame, self.features, self.cfg)
        missing = [f for f in self.features if f not in features.columns]
        if missing:
            raise MissingInputError(f"{self.name} missing required features: {missing}")
        return features[list(self.features)].to_numpy(dtype=float)

    def _active_rows(self, frame: pd.DataFrame) -> np.ndarray:
        return ~warmup_mask(frame, self.cfg)

    # -------------------------------------------------------------- fitting
    def fit(self, sessions: Iterable[pd.DataFrame], features: Iterable[pd.DataFrame] | None = None) -> "BaseLayer":
        rows = [
            self.feature_matrix(s, f)[self._active_rows(s)]
            for s, f in _pairs(sessions, features)
            if is_clean_session(s) or self.uses_attacked_sessions
        ]
        if not rows:
            raise ValueError(f"{self.name}: fit needs at least one clean session")
        self._fit_rows(np.vstack(rows), sessions=None)
        self._fitted = True
        return self

    def _fit_rows(self, X: np.ndarray, sessions=None) -> None:
        self.center_ = np.median(X, axis=0)
        # The std floor keeps rare discrete features (lock resets, satellite count) from
        # getting a near-zero scale when their 99th percentile equals the median.
        self.scale_ = np.maximum(np.percentile(X, 99, axis=0) - self.center_, X.std(axis=0))
        self.scale_ = np.maximum(self.scale_, 1e-9)

    def _raw_scores(self, X: np.ndarray) -> np.ndarray:
        return np.max((X - self.center_) / self.scale_, axis=1)

    # -------------------------------------------------------------- scoring
    def score_rows(self, frame: pd.DataFrame, features: pd.DataFrame | None = None) -> np.ndarray:
        if not self._fitted:
            raise NotFittedError(f"{self.name}: call fit() before scoring")
        s = self._raw_scores(self.feature_matrix(frame, features))
        s[~self._active_rows(frame)] = 0.0
        return s

    def calibrate(self, clean_sessions: Iterable[pd.DataFrame], features: Iterable[pd.DataFrame] | None = None) -> float:
        """Freeze the threshold at a percentile of per-row scores on clean calibration sessions."""
        scores = [
            self.score_rows(s, f)[self._active_rows(s)]
            for s, f in _pairs(clean_sessions, features)
            if is_clean_session(s)
        ]
        if not scores:
            raise ValueError(f"{self.name}: calibrate needs clean sessions")
        self.threshold = float(np.percentile(np.concatenate(scores), self.cfg.threshold_percentile))
        return self.threshold

    def alarm(self, scores: np.ndarray, threshold: float | None = None, k: int | None = None) -> np.ndarray:
        """Persistent alarm against a threshold frozen by calibrate(), never from `scores` itself."""
        threshold = self.threshold if threshold is None else threshold
        if threshold is None:
            raise NotFittedError(f"{self.name}: call calibrate() before alarm()")
        return persistent_alarm(scores, threshold, self.cfg.persistence_k if k is None else k)

    def score(self, frame: pd.DataFrame, features: pd.DataFrame | None = None) -> float:
        """Session summary: maximum per-row score after warm-up."""
        rows = self.score_rows(frame, features)[self._active_rows(frame)]
        return float(rows.max()) if rows.size else 0.0

    def detect(self, frame: pd.DataFrame, features: pd.DataFrame | None = None) -> LayerResult:
        rows = self.score_rows(frame, features)
        alarms = self.alarm(rows)
        return LayerResult(self.name, float(rows.max()), self.__class__.__name__, float(self.threshold), bool(alarms.any()))


def evaluate_layers(frame: pd.DataFrame, layers: Sequence[BaseLayer]) -> Dict[str, LayerResult]:
    """Run fitted and calibrated layers on one session."""
    features = compute_features(frame, None, layers[0].cfg) if layers else None
    return {layer.name: layer.detect(frame, features) for layer in layers if layer.can_run_on(frame)}
