"""The ten-layer detector: layers, out-of-fold vote fitting, calibration, attack naming."""
from __future__ import annotations

from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

from .config import DEFAULT_DETECTOR_CONFIG, DetectorConfig
from .features import MissingInputError, compute_features, warmup_mask
from .layers import BaseLayer, LayerResult, make_layers, persistent_alarm
from .layers.base import is_clean_session
from .metrics import fa_target_threshold
from .splits import session_folds
from .vote import AttackNamer, EqualWeightVote, LogisticVote

VOTE = "vote"
VOTE_FA = "vote_at_fa_target"
EQUAL_VOTE = "equal_weight_vote"


def _features_for(sessions: Sequence[pd.DataFrame], cfg: DetectorConfig) -> List[pd.DataFrame]:
    return [compute_features(s, None, cfg) for s in sessions]


class TenLayerDetector:
    """Fit on training sessions, freeze thresholds on clean calibration sessions, then score.

    fit():
      1. Layers that the data cannot feed (or that the config excludes) are recorded in
         `not_evaluated` with the reason; they are not run on substitutes.
      2. Out-of-fold layer scores on the training sessions (k folds by session) are used to
         fit the logistic vote, the equal-weight baseline and the attack namer.
      3. Final layers are fitted on all training sessions.
      4. Thresholds for every layer and both votes are the configured percentile of per-row
         scores on the clean calibration sessions.
    """

    def __init__(self, cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG):
        self.cfg = cfg
        self.layers: List[BaseLayer] = []
        self.not_evaluated: Dict[str, str] = {}
        self.thresholds: Dict[str, float] = {}

    # ------------------------------------------------------------------ fit
    def _select_layers(self, sessions: Sequence[pd.DataFrame]) -> List[BaseLayer]:
        chosen = []
        for layer in make_layers(self.cfg):
            if not layer.evaluable_by_config:
                self.not_evaluated[layer.name] = "all inputs excluded by config"
            elif not all(layer.can_run_on(s) for s in sessions):
                missing = sorted({c for s in sessions for c in layer.required_columns if c not in s.columns})
                self.not_evaluated[layer.name] = f"inputs missing from data: {missing}"
            else:
                chosen.append(layer)
        return chosen

    @staticmethod
    def _fit_layers(layers: List[BaseLayer], sessions, features) -> None:
        for layer in layers:
            layer.fit(sessions, features)

    def layer_matrix(self, frame: pd.DataFrame, features: pd.DataFrame | None = None, layers=None) -> np.ndarray:
        layers = self.layers if layers is None else layers
        if features is None:
            features = compute_features(frame, None, self.cfg)
        return np.column_stack([layer.score_rows(frame, features) for layer in layers])

    def fit(
        self,
        train: Sequence[pd.DataFrame],
        calibration: Sequence[pd.DataFrame],
        train_features: Sequence[pd.DataFrame] | None = None,
        calibration_features: Sequence[pd.DataFrame] | None = None,
    ) -> "TenLayerDetector":
        train = list(train)
        calibration = list(calibration)
        if not any(is_clean_session(s) for s in train) or all(is_clean_session(s) for s in train):
            raise ValueError("training sessions must contain clean and attacked sessions")
        if not any(is_clean_session(s) for s in calibration):
            raise ValueError("calibration sessions must contain clean sessions")
        tf = list(train_features) if train_features is not None else _features_for(train, self.cfg)
        cf = list(calibration_features) if calibration_features is not None else _features_for(calibration, self.cfg)

        self.not_evaluated = {}
        self.layers = self._select_layers(train + calibration)
        if not self.layers:
            raise MissingInputError("no layer can run on this data")
        self.layer_names = [layer.name for layer in self.layers]

        # Out-of-fold layer scores on the training sessions.
        oof: List[np.ndarray | None] = [None] * len(train)
        for fold in session_folds(train, self.cfg.oof_folds, seed=self.cfg.split_seed):
            in_fold = set(fold)
            fit_idx = [i for i in range(len(train)) if i not in in_fold]
            fold_layers = [type(layer)(self.cfg) for layer in self.layers]
            self._fit_layers(fold_layers, [train[i] for i in fit_idx], [tf[i] for i in fit_idx])
            for i in fold:
                oof[i] = self.layer_matrix(train[i], tf[i], fold_layers)
        active = [~warmup_mask(s, self.cfg) for s in train]
        self.oof_X_ = np.vstack([m[a] for m, a in zip(oof, active)])
        self.oof_y_ = np.concatenate([s["label"].to_numpy()[a] for s, a in zip(train, active)])

        self.vote = LogisticVote(self.layer_names, self.cfg.model_seed).fit(self.oof_X_, self.oof_y_)
        self.equal_vote = EqualWeightVote(self.layer_names).fit(self.oof_X_, self.oof_y_)
        attacked = [(m[s["label"].to_numpy() == 1], s["attack_type"].iloc[0]) for m, s in zip(oof, train) if not is_clean_session(s)]
        self.namer = AttackNamer(self.layer_names, self.cfg.model_seed).fit([a for a, _ in attacked], [b for _, b in attacked])

        self._fit_layers(self.layers, train, tf)
        self.calibrate(calibration, cf)
        return self

    def calibrate(self, calibration: Sequence[pd.DataFrame], features: Sequence[pd.DataFrame]) -> Dict[str, float]:
        rows = {name: [] for name in self.detector_names}
        vote_sessions = []
        clean_s = 0.0
        for s, f in zip(calibration, features):
            if not is_clean_session(s):
                continue
            scores = self.score_session(s, f)
            a = ~warmup_mask(s, self.cfg)
            for name in self.detector_names:
                rows[name].append(scores[name][a])
            vote_sessions.append(scores[VOTE])
            t = s["t_gnss_s"].to_numpy(dtype=float)
            clean_s += float(a.sum() * np.median(np.diff(t)))
        pct = self.cfg.threshold_percentile
        self.thresholds = {name: float(np.percentile(np.concatenate(v), pct)) for name, v in rows.items() if name != VOTE_FA}
        self.thresholds[VOTE_FA] = fa_target_threshold(
            vote_sessions, clean_s / 3600.0, self.thresholds[VOTE], self.cfg.fa_per_hour_target, self.cfg.persistence_k
        )
        for layer in self.layers:
            layer.threshold = self.thresholds[layer.name]
        return self.thresholds

    # ------------------------------------------------------------------ scoring
    @property
    def detector_names(self) -> List[str]:
        return [layer.name for layer in self.layers] + [VOTE, VOTE_FA, EQUAL_VOTE]

    def score_session(self, frame: pd.DataFrame, features: pd.DataFrame | None = None) -> Dict[str, np.ndarray]:
        """Per-row scores for every layer and both votes (warm-up rows score 0 / lowest)."""
        m = self.layer_matrix(frame, features)
        warm = warmup_mask(frame, self.cfg)
        out = {name: m[:, j] for j, name in enumerate(self.layer_names)}
        vote = self.vote.score_rows(m)
        equal = self.equal_vote.score_rows(m)
        vote[warm] = -np.inf
        equal[warm] = -np.inf
        out[VOTE] = vote
        out[VOTE_FA] = vote  # same score, threshold set for the false-alarm target
        out[EQUAL_VOTE] = equal
        out["_matrix"] = m
        return out

    def alarms(self, scores: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
        k = self.cfg.persistence_k
        return {name: persistent_alarm(scores[name], self.thresholds[name], k) for name in self.detector_names}

    def detect(self, frame: pd.DataFrame, features: pd.DataFrame | None = None) -> dict:
        """Vote alarm per row, first alarm time, and the named attack type (if alarmed)."""
        scores = self.score_session(frame, features)
        alarm = self.alarms(scores)[VOTE]
        t = frame["t_gnss_s"].to_numpy(dtype=float)
        first = int(np.argmax(alarm)) if alarm.any() else None
        named = self.namer.predict(scores["_matrix"][first:]) if first is not None else None
        return {"alarm": alarm, "first_alarm_s": float(t[first]) if first is not None else None, "attack_type": named, "scores": scores}


# ---------------------------------------------------------------------- helpers
def evaluate_session(frame: pd.DataFrame, detector: TenLayerDetector) -> Dict[str, LayerResult]:
    """Per-layer results for one session with a fitted detector."""
    features = compute_features(frame, None, detector.cfg)
    return {layer.name: layer.detect(frame, features) for layer in detector.layers}


def evaluate_dataset(sessions, detector: TenLayerDetector) -> List[Dict[str, LayerResult]]:
    return [evaluate_session(s, detector) for s in sessions]


def summarize_results(frame: pd.DataFrame, detector: TenLayerDetector) -> Dict[str, float]:
    return {name: result.score for name, result in evaluate_session(frame, detector).items()}
