from __future__ import annotations

import numpy as np
from sklearn.ensemble import IsolationForest

from .base import BaseLayer


class TemporalAnomalyLayer(BaseLayer):
    """Isolation Forest on the residual features of layers 2, 3, 5 and 6, fitted on clean rows only."""

    name = "8_temporal_anomaly"
    feature_names = (
        "cn0_shift_db",
        "cn0_std_drop_db",
        "hdop_change",
        "sv_change",
        "posvel_mps",
        "imu_resid_mps2",
        "baro_resid_m",
        "implied_accel_mps2",
    )
    max_fit_rows = 50_000

    def _fit_rows(self, X, sessions=None):
        rng = np.random.default_rng(self.cfg.model_seed)
        if len(X) > self.max_fit_rows:
            X = X[rng.choice(len(X), self.max_fit_rows, replace=False)]
        self.mu_ = X.mean(axis=0)
        self.sd_ = X.std(axis=0) + 1e-9
        self.model_ = IsolationForest(n_estimators=200, random_state=self.cfg.model_seed, n_jobs=-1)
        self.model_.fit((X - self.mu_) / self.sd_)

    def _raw_scores(self, X):
        return -self.model_.score_samples((X - self.mu_) / self.sd_)
