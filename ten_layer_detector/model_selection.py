"""Model comparison (MODEL_SELECTION.md) on per-row causal features.

Every number is measured; nothing is derived from another metric:
- T1 DR: share of attacked validation sessions with a persistent alarm after onset.
- T2 FA/h: alarm events per hour on clean validation sessions.
- T3 no strength clue: refit and recalibrate without C/N0 and DOP/satellite features.
- T4 weak spoofer: DR on validation sessions with spoofer power below 1 dB (needs metadata).
- T5 unseen attack: leave each attack type out of training, test on it; mean DR.
- T6 delay: median / p90 from onset to first alarm.
- T7 speed: measured milliseconds per row decision on this machine.
Thresholds are set on clean calibration sessions: the configured percentile of per-row
scores, raised until calibration false alarms are at most fa_per_hour_target per hour.
Models with discrete scores (decision tree) can tie at the top score and then never alarm,
because alarms need a score strictly above the threshold; that is reported as measured.
Features carry no label-derived values (the old attack_ratio / onset_offset leak is gone).
"""
from __future__ import annotations

import time
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC, LinearSVC, OneClassSVM
from sklearn.tree import DecisionTreeClassifier

from dataclasses import replace

from .config import DEFAULT_DETECTOR_CONFIG, DetectorConfig
from .features import CN0_FEATURES, available_features, compute_features, warmup_mask
from .layers.base import is_clean_session, persistent_alarm
from .metrics import fa_target_threshold, session_outcome, summarize_outcomes
from .splits import session_type

STRENGTH_FEATURES = CN0_FEATURES + ("hdop_change", "sv_change", "sv_drop", "hdop_rise")

MODEL_CANDIDATES = {
    "logistic_regression": {"family": "linear", "settings": {"C": 1.0}},
    "decision_tree": {"family": "tree", "settings": {"max_depth": 8, "min_samples_leaf": 20}},
    "random_forest": {"family": "ensemble", "settings": {"n_estimators": 100, "max_depth": 12, "min_samples_leaf": 20}},
    "extra_trees": {"family": "ensemble", "settings": {"n_estimators": 100, "max_depth": 12, "min_samples_leaf": 20}},
    "hist_gradient_boosting": {"family": "boosted", "settings": {"learning_rate": 0.1, "max_depth": 6, "max_iter": 200}},
    "linear_svm": {"family": "linear", "settings": {"C": 1.0}},
    "rbf_svm": {"family": "kernel", "settings": {"C": 1.0, "gamma": "scale"}},
    "knn": {"family": "distance", "settings": {"n_neighbors": 15}},
    "isolation_forest": {"family": "unsupervised", "settings": {"n_estimators": 200}},
    "xgboost": {"family": "boosted", "settings": {"learning_rate": 0.1, "max_depth": 6, "n_estimators": 200}},
    "lightgbm": {"family": "boosted", "settings": {"learning_rate": 0.1, "num_leaves": 31, "n_estimators": 200}},
    "mlp": {"family": "neural", "settings": {"hidden_layer_sizes": [64, 32], "alpha": 1e-4}},
    "one_class_svm": {"family": "unsupervised", "settings": {"nu": 0.05, "gamma": "scale"}},
}

UNSUPERVISED = ("isolation_forest", "one_class_svm")
SEEDS = (0, 1, 2, 3, 4)

# Training rows are subsampled to this many per fit so every candidate (including the
# kernel SVM) sees the same amount of data.
MAX_TRAIN_ROWS = 20_000

# Eligibility (MODEL_SELECTION.md section 6, step 1).
MAX_FA_PER_HOUR = 1.0
MIN_DETECTION_RATE = 0.5  # a model that detects less than half the attacks is not a detector


def is_eligible(r: dict) -> bool:
    """FA/h within the limit, a non-zero result without the strength clue, and a minimum
    detection rate on the main test. Works on a stored result row."""
    return bool(
        r["far_per_hour"] <= MAX_FA_PER_HOUR
        and r["dr_no_strength"] > 0.0
        and r["dr_validation"] >= MIN_DETECTION_RATE
    )


def _make_model(name: str, seed: int = 0):
    if name == "logistic_regression":
        return Pipeline([("scale", StandardScaler()), ("model", LogisticRegression(class_weight="balanced", max_iter=2000))])
    if name == "decision_tree":
        return DecisionTreeClassifier(max_depth=8, min_samples_leaf=20, class_weight="balanced", random_state=seed)
    if name == "random_forest":
        return RandomForestClassifier(n_estimators=100, max_depth=12, min_samples_leaf=20, class_weight="balanced", random_state=seed, n_jobs=-1)
    if name == "extra_trees":
        return ExtraTreesClassifier(n_estimators=100, max_depth=12, min_samples_leaf=20, class_weight="balanced", random_state=seed, n_jobs=-1)
    if name == "hist_gradient_boosting":
        return HistGradientBoostingClassifier(learning_rate=0.1, max_depth=6, max_iter=200, class_weight="balanced", random_state=seed)
    if name == "linear_svm":
        return Pipeline([("scale", StandardScaler()), ("model", LinearSVC(class_weight="balanced", C=1.0, random_state=seed))])
    if name == "rbf_svm":
        return Pipeline([("scale", StandardScaler()), ("model", SVC(C=1.0, gamma="scale", class_weight="balanced", random_state=seed))])
    if name == "knn":
        return Pipeline([("scale", StandardScaler()), ("model", KNeighborsClassifier(n_neighbors=15, n_jobs=-1))])
    if name == "isolation_forest":
        return Pipeline([("scale", StandardScaler()), ("model", IsolationForest(n_estimators=200, random_state=seed, n_jobs=-1))])
    if name == "xgboost":
        from xgboost import XGBClassifier

        return XGBClassifier(learning_rate=0.1, max_depth=6, n_estimators=200, random_state=seed, n_jobs=-1, verbosity=0)
    if name == "lightgbm":
        from lightgbm import LGBMClassifier

        return LGBMClassifier(learning_rate=0.1, num_leaves=31, n_estimators=200, class_weight="balanced", random_state=seed, n_jobs=-1, verbose=-1)
    if name == "mlp":
        return Pipeline([("scale", StandardScaler()), ("model", MLPClassifier(hidden_layer_sizes=(64, 32), alpha=1e-4, max_iter=300, random_state=seed))])
    if name == "one_class_svm":
        return Pipeline([("scale", StandardScaler()), ("model", OneClassSVM(nu=0.05, gamma="scale"))])
    raise ValueError(f"Unknown model candidate: {name}")


def _score(model, name: str, X: np.ndarray) -> np.ndarray:
    if name in UNSUPERVISED:
        return -model.score_samples(X)
    if hasattr(model, "decision_function"):
        return np.asarray(model.decision_function(X), dtype=float)
    return model.predict_proba(X)[:, 1]


class _Rows:
    """Per-session feature matrices and active-row masks for one feature list."""

    def __init__(self, sessions, feats, columns, cfg):
        self.sessions = list(sessions)
        self.X = [f[list(columns)].to_numpy(dtype=float) for f in feats]
        self.active = [~warmup_mask(s, cfg) for s in self.sessions]

    def stacked(self, keep=None, clean_only=False):
        X, y = [], []
        for i, (s, m, a) in enumerate(zip(self.sessions, self.X, self.active)):
            if keep is not None and not keep(s):
                continue
            if clean_only and not is_clean_session(s):
                continue
            X.append(m[a])
            y.append(s["label"].to_numpy()[a])
        return np.vstack(X), np.concatenate(y)


def _fit(name, rows: _Rows, cfg, keep=None):
    X, y = rows.stacked(keep, clean_only=(name in UNSUPERVISED))
    rng = np.random.default_rng(cfg.model_seed)
    if len(X) > MAX_TRAIN_ROWS:
        idx = rng.choice(len(X), MAX_TRAIN_ROWS, replace=False)
        X, y = X[idx], y[idx]
    model = _make_model(name, cfg.model_seed)
    return model.fit(X) if name in UNSUPERVISED else model.fit(X, y)


def _threshold(model, name, cal: _Rows, cfg) -> float:
    """Percentile threshold on clean calibration rows, raised until the clean calibration
    sessions give at most fa_per_hour_target alarm events per hour (section 6, step 1)."""
    per_session, hours = [], 0.0
    for s, m, a in zip(cal.sessions, cal.X, cal.active):
        if not is_clean_session(s):
            continue
        sc = _score(model, name, m)
        sc[~a] = -np.inf
        per_session.append(sc)
        hours += a.sum() * float(np.median(np.diff(s["t_gnss_s"].to_numpy()))) / 3600.0
    start = float(np.percentile(np.concatenate([v[np.isfinite(v)] for v in per_session]), cfg.threshold_percentile))
    return fa_target_threshold(per_session, hours, start, cfg.fa_per_hour_target, cfg.persistence_k)


def _validate(model, name, thr, val: _Rows, cfg, keep=None):
    clean, attacked, per_session = [], {}, {}
    n_rows, elapsed = 0, 0.0
    for s, m, a in zip(val.sessions, val.X, val.active):
        if keep is not None and not keep(s):
            continue
        t0 = time.perf_counter()
        sc = _score(model, name, m)
        elapsed += time.perf_counter() - t0
        n_rows += len(m)
        sc[~a] = -np.inf
        alarm = persistent_alarm(sc, thr, cfg.persistence_k)
        t = s["t_gnss_s"].to_numpy(dtype=float)
        if is_clean_session(s):
            clean.append(session_outcome(alarm, t, None, a))
        else:
            o = session_outcome(alarm, t, float(s["attack_onset_s"].iloc[0]), a)
            attacked.setdefault(session_type(s), []).append(o)
            per_session[str(s["session_id"].iloc[0])] = o
    summary = summarize_outcomes(clean, attacked) if clean else None
    return summary, attacked, per_session, 1000.0 * elapsed / max(1, n_rows)


def evaluate_model_candidates(
    train: Sequence[pd.DataFrame],
    calibration: Sequence[pd.DataFrame],
    validation: Sequence[pd.DataFrame],
    metadata: Iterable[dict] | None = None,
    *,
    cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG,
    candidates: Sequence[str] | None = None,
    unseen: bool = True,
    seeds: bool = True,
) -> list[dict[str, Any]]:
    """Run T1-T7 for each candidate. Sets must be disjoint by session."""
    train, calibration, validation = list(train), list(calibration), list(validation)
    feats = {id(s): compute_features(s, None, cfg) for s in train + calibration + validation}
    columns = [c for c in available_features(train[0]) if c not in cfg.exclude_features]
    no_strength = [c for c in columns if c not in STRENGTH_FEATURES]
    power = {str(m["session_id"]): m.get("power_db") for m in (metadata or [])}

    def rows(sessions, cols):
        return _Rows(sessions, [feats[id(s)] for s in sessions], cols, cfg)

    tr, ca, va = rows(train, columns), rows(calibration, columns), rows(validation, columns)
    tr_ns, ca_ns, va_ns = rows(train, no_strength), rows(calibration, no_strength), rows(validation, no_strength)
    attack_types = sorted({session_type(s) for s in train if not is_clean_session(s)})

    results = []
    for name in candidates or MODEL_CANDIDATES:
        model = _fit(name, tr, cfg)
        thr = _threshold(model, name, ca, cfg)
        main, _, per_session, ms = _validate(model, name, thr, va, cfg)

        m_ns = _fit(name, tr_ns, cfg)
        ns, _, _, _ = _validate(m_ns, name, _threshold(m_ns, name, ca_ns, cfg), va_ns, cfg)

        weak_ids = [sid for sid, o in per_session.items() if power.get(sid) is not None and power[sid] < 1.0]
        dr_weak = float(np.mean([per_session[i]["detected"] for i in weak_ids])) if weak_ids else float("nan")

        dr_unseen = float("nan")
        if unseen and name not in UNSUPERVISED:
            rates = []
            for a in attack_types:
                m_u = _fit(name, tr, cfg, keep=lambda s, a=a: session_type(s) != a)
                _, att, _, _ = _validate(m_u, name, _threshold(m_u, name, ca, cfg), va, cfg, keep=lambda s, a=a: session_type(s) in (a, "clean"))
                if a in att:
                    rates.append(np.mean([o["detected"] for o in att[a]]))
            dr_unseen = float(np.mean(rates)) if rates else float("nan")
        elif name in UNSUPERVISED:
            dr_unseen = main["all_attacks"]["rate"]  # trained on clean rows only: every attack type is unseen

        seed_dr, seed_far = [], []
        for sd in SEEDS if seeds else ():
            cs = replace(cfg, model_seed=sd)
            m_s = _fit(name, tr, cs)
            r_s, _, _, _ = _validate(m_s, name, _threshold(m_s, name, ca, cs), va, cs)
            seed_dr.append(r_s["all_attacks"]["rate"])
            seed_far.append(r_s["false_alarms_per_hour"])

        results.append(
            {
                "model_name": name,
                "settings": MODEL_CANDIDATES[name]["settings"],
                "dr_validation": main["all_attacks"]["rate"],
                "dr_validation_ci95": main["all_attacks"]["ci95"],
                "far_per_hour": main["false_alarms_per_hour"],
                "clean_sessions_alarmed": main["clean_sessions_alarmed"]["rate"],
                "dr_no_strength": ns["all_attacks"]["rate"],
                "far_no_strength_per_hour": ns["false_alarms_per_hour"],
                "dr_weak": dr_weak,
                "n_weak": len(weak_ids),
                "dr_unseen": dr_unseen,
                "delay_median_s": main["delay_median_s"],
                "delay_p90_s": main["delay_p90_s"],
                "ms_per_decision": ms,
                "t8_dr_mean": float(np.mean(seed_dr)) if seed_dr else float("nan"),
                "t8_dr_std": float(np.std(seed_dr)) if seed_dr else float("nan"),
                "t8_far_mean": float(np.mean(seed_far)) if seed_far else float("nan"),
                "t8_far_std": float(np.std(seed_far)) if seed_far else float("nan"),
                "per_type": {a: r["rate"] for a, r in main["per_type"].items()},
            }
        )
        results[-1]["eligible"] = is_eligible(results[-1])
    return results


def select_model(results: Iterable[dict[str, Any]], tie_margin: float = 0.05) -> str | None:
    """MODEL_SELECTION.md section 6. Returns None when no model is eligible."""
    rows = [r for r in results if is_eligible(r)]
    if not rows:
        return None

    def nz(v):
        return 0.0 if v is None or not np.isfinite(v) else float(v)

    def robustness(r):
        return 0.5 * nz(r.get("dr_weak")) + 0.5 * nz(r.get("dr_unseen"))

    best_dr = max(nz(r["dr_validation"]) for r in rows)
    best_rob = max(robustness(r) for r in rows)
    # Models within the tie margin of the best on both scores are tied; break by delay, then speed.
    tied = [r for r in rows if best_dr - nz(r["dr_validation"]) <= tie_margin and best_rob - robustness(r) <= tie_margin]
    if tied:
        winner = min(tied, key=lambda r: (nz(r.get("delay_median_s")), nz(r.get("ms_per_decision"))))
    else:
        winner = max(rows, key=lambda r: (robustness(r), nz(r["dr_validation"])))
    return str(winner["model_name"])


__all__ = ["MODEL_CANDIDATES", "MAX_FA_PER_HOUR", "MIN_DETECTION_RATE", "is_eligible", "STRENGTH_FEATURES", "evaluate_model_candidates", "select_model"]
