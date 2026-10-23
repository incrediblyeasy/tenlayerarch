from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from ..features import FEATURES
from .base import BaseLayer, _pairs


class LearnedModelLayer(BaseLayer):
    """Random forest on the per-row features of layers 1-7 and 9, trained on clean and
    attacked training sessions (row labels). Score: predicted attack probability.

    Inputs the training data does not provide (e.g. no Galileo solution) are left out at
    fit time; the fitted model then requires exactly the inputs it was trained on.
    """

    name = "10_learned"
    feature_names = (
        "clk_innov_ns",
        "clk_drift_step_nsps",
        "cn0_shift_db",
        "cn0_std_drop_db",
        "hdop_change",
        "sv_change",
        "const_diff_m",
        "posvel_mps",
        "imu_resid_mps2",
        "baro_resid_m",
        "implied_accel_mps2",
        "lock_reset",
        "code_carrier_m",
        "allan_dev_nsps",
    )
    uses_attacked_sessions = True

    @property
    def features(self):
        configured = tuple(f for f in self.feature_names if f not in self.cfg.exclude_features)
        return getattr(self, "present_", configured)

    def can_run_on(self, frame):
        if not hasattr(self, "present_"):
            return self.evaluable_by_config and any(set(FEATURES[f][0]) <= set(frame.columns) for f in self.features)
        return super().can_run_on(frame)

    def fit(self, sessions: Iterable[pd.DataFrame], features: Iterable[pd.DataFrame] | None = None):
        pairs = list(_pairs(sessions, features))
        cols = set(pairs[0][0].columns)
        self.present_ = tuple(f for f in self.features if set(FEATURES[f][0]) <= cols)
        X, y = [], []
        for s, f in pairs:
            active = self._active_rows(s)
            X.append(self.feature_matrix(s, f)[active])
            y.append(s["label"].to_numpy()[active])
        X = np.vstack(X)
        y = np.concatenate(y)
        if len(set(y)) < 2:
            raise ValueError(f"{self.name}: fit needs clean and attacked rows")
        self.model_ = RandomForestClassifier(
            n_estimators=150,
            max_depth=12,
            min_samples_leaf=20,
            max_samples=0.3,
            class_weight="balanced",
            random_state=self.cfg.model_seed,
            n_jobs=-1,
        ).fit(X, y)
        self._fitted = True
        return self

    def _raw_scores(self, X):
        return self.model_.predict_proba(X)[:, 1]
