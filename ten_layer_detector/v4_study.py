"""Phase A of MODEL_IMPROVEMENT_PLAN.md on the v4 world: features, decision rules, model candidates.

Everything here uses the validation data only (sim_v4_val split three ways, sim_v4_weakval,
sim_v4_fahold). The rules it applies are in configs/feature_rule_v4.json, model_grid_v4.json and
selection_rule_v4.json, committed before any of this ran.
"""
from __future__ import annotations

import math
import pickle
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ProjectConfig
from .dataset import load_sessions
from .features import OPT_IN, available_features, compute_features, warmup_mask
from .layers.base import is_clean_session, persistent_alarm
from .metrics import fa_target_threshold, rising_edges, session_outcome, summarize_outcomes
from .model_selection import UNSUPERVISED, _fit, _make_model, _score, STRENGTH_FEATURES
from .splits import session_type, split_three_way

CACHE = Path(".cache_v4")
CONFIG = "configs/sim_v4.json"

S_V3 = None  # filled by feature_sets()


def feature_sets(columns: list[str]) -> dict[str, list[str]]:
    base = [c for c in columns if c not in OPT_IN]
    s_v3 = [c for c in base if c not in ("imu_att_resid_mps2", "imu_att_resid_long_mps2")]
    s_all = list(base)
    s_att = [c for c in base if c not in ("imu_resid_mps2", "imu_resid_long_mps2")]
    return {"S_v3": s_v3, "S_all": s_all, "S_att": s_att, "S_att_ekf": s_att + list(OPT_IN)}


def _feat(args):
    s, cfg = args
    return compute_features(s, list(available_features(s)) + list(OPT_IN), cfg)


class Data:
    """Sessions and their cached feature tables for one dataset directory."""

    def __init__(self, path: str, cfg, workers: int = 20):
        self.cfg = cfg
        self.sessions, self.meta = load_sessions(path)
        self.power = {str(m["session_id"]): m.get("power_db") for m in self.meta}
        f = CACHE / (Path(path).name + ".pkl")
        if f.exists():
            self.feats = pickle.loads(f.read_bytes())
        else:
            with ProcessPoolExecutor(workers) as ex:
                self.feats = list(ex.map(_feat, [(s, cfg) for s in self.sessions], chunksize=16))
            CACHE.mkdir(exist_ok=True)
            f.write_bytes(pickle.dumps(self.feats))
        self.by_id = {id(s): i for i, s in enumerate(self.sessions)}


class Split:
    """A list of (session, feature table) pairs with active masks, for one feature list."""

    def __init__(self, items, cfg):
        self.items = items  # (session, feats)
        self.cfg = cfg
        self.active = [~warmup_mask(s, cfg) for s, _ in items]

    def X(self, cols):
        return [f[list(cols)].to_numpy(dtype=float) for _, f in self.items]

    def train_xy(self, cols, clean_only=False, keep=None):
        X, y = [], []
        for (s, f), a in zip(self.items, self.active):
            if keep is not None and not keep(s):
                continue
            if clean_only and not is_clean_session(s):
                continue
            X.append(f[list(cols)].to_numpy(dtype=float)[a])
            y.append(s["label"].to_numpy()[a])
        return np.vstack(X), np.concatenate(y)


def make_splits(path: str, cfg):
    d = Data(path, cfg)
    tr, ca, va = split_three_way(d.sessions, cfg.train_fraction, cfg.calibration_fraction, seed=cfg.split_seed)
    pick = lambda ss: Split([(s, d.feats[d.by_id[id(s)]]) for s in ss], cfg)
    return d, pick(tr), pick(ca), pick(va)


# ------------------------------------------------------------------ scorers
class Scorer:
    """A fitted model that maps feature rows to anomaly scores (higher = more anomalous)."""

    def __init__(self, name, cols, cfg, model_seed=None):
        self.name, self.cols = name, list(cols)
        self.cfg = cfg if model_seed is None else replace(cfg, model_seed=model_seed)

    def fit(self, tr: Split, keep=None):
        X, y = tr.train_xy(self.cols, clean_only=(self.name in UNSUPERVISED), keep=keep)
        rng = np.random.default_rng(self.cfg.model_seed)
        if len(X) > 20_000:
            idx = rng.choice(len(X), 20_000, replace=False)
            X, y = X[idx], y[idx]
        self.model = _make_model(self.name, self.cfg.model_seed)
        self.model.fit(X) if self.name in UNSUPERVISED else self.model.fit(X, y)
        return self

    def score(self, X):
        return _score(self.model, self.name, X)


class Autoencoder:
    """M4: MLP autoencoder (32-8-32) trained on clean rows only; score = mean squared reconstruction
    error of the standardised features."""

    name = "autoencoder"

    def __init__(self, cols, cfg, model_seed=None):
        self.cols = list(cols)
        self.cfg = cfg if model_seed is None else replace(cfg, model_seed=model_seed)

    def fit(self, tr: "Split", keep=None):
        from sklearn.neural_network import MLPRegressor
        from sklearn.preprocessing import StandardScaler

        X, _ = tr.train_xy(self.cols, clean_only=True, keep=keep)
        rng = np.random.default_rng(self.cfg.model_seed)
        if len(X) > 20_000:
            X = X[rng.choice(len(X), 20_000, replace=False)]
        self.scaler = StandardScaler().fit(X)
        Z = self.scaler.transform(X)
        self.model = MLPRegressor(hidden_layer_sizes=(32, 8, 32), max_iter=200, early_stopping=True, random_state=self.cfg.model_seed).fit(Z, Z)
        return self

    def score(self, X):
        Z = self.scaler.transform(X)
        return np.mean((self.model.predict(Z) - Z) ** 2, axis=1)


class Ensemble:
    """M2: weighted average of two scorers after mapping each score to a clean-calibration rank.
    The rank of a score is its empirical CDF position among the clean calibration scores; above
    the clean maximum it continues linearly (1 + (x - max) / (max - median)) so that ordering
    among anomalous scores is kept."""

    def __init__(self, a: Scorer, b: Scorer, weight_a: float):
        self.a, self.b, self.w = a, b, weight_a
        self.name = f"ensemble_{a.name}_{b.name}_{weight_a}"
        self.cols = None

    def calibrate(self, ca: Split):
        self.ref = {}
        for key, sc in (("a", self.a), ("b", self.b)):
            vals = np.concatenate([sc.score(f[sc.cols].to_numpy(dtype=float))[act] for (s, f), act in zip(ca.items, ca.active) if is_clean_session(s)])
            self.ref[key] = np.sort(vals)
        return self

    def _rank(self, key, x):
        ref = self.ref[key]
        r = np.searchsorted(ref, x) / len(ref)
        top = x > ref[-1]
        r[top] = 1.0 + (x[top] - ref[-1]) / max(ref[-1] - np.median(ref), 1e-9)
        return r

    def score_frame(self, f):
        a = self._rank("a", self.a.score(f[self.a.cols].to_numpy(dtype=float)))
        b = self._rank("b", self.b.score(f[self.b.cols].to_numpy(dtype=float)))
        return self.w * a + (1 - self.w) * b


def session_scores(scorer, split: Split):
    """Per-session score arrays, inactive (warm-up) rows set to -inf."""
    out = []
    for (s, f), act in zip(split.items, split.active):
        sc = scorer.score_frame(f) if isinstance(scorer, Ensemble) else scorer.score(f[scorer.cols].to_numpy(dtype=float))
        sc = np.asarray(sc, dtype=float).copy()
        sc[~act] = -np.inf
        out.append(sc)
    return out


# ------------------------------------------------------------------ decision rules
def _hours(split: Split, only_clean=True):
    h = 0.0
    for (s, _), a in zip(split.items, split.active):
        if only_clean and not is_clean_session(s):
            continue
        h += a.sum() * float(np.median(np.diff(s["t_gnss_s"].to_numpy()))) / 3600.0
    return h


def _cusum_stat(sc, ref):
    z = np.where(np.isfinite(sc), sc - ref, 0.0)
    c = np.cumsum(z)
    return c - np.minimum.accumulate(np.minimum(c, 0.0))  # S_t = max(0, S_{t-1} + z_t)


class Rule:
    """Turns score arrays into alarms. fit() uses clean calibration sessions only."""

    def __init__(self, kind: str, cfg, k: int = 5, ref_pct: float | None = None, alpha: float = 0.01):
        self.kind, self.cfg, self.k, self.ref_pct, self.alpha = kind, cfg, k, ref_pct, alpha
        self.label = {"persistence": f"persistence_k{k}", "cusum": f"cusum_p{ref_pct}", "conformal": f"conformal_a{alpha}_k{k}"}[kind]

    def fit(self, cal_scores: list[np.ndarray], hours: float):
        pooled = np.concatenate([v[np.isfinite(v)] for v in cal_scores])
        if self.kind == "persistence":
            start = float(np.percentile(pooled, self.cfg.threshold_percentile))
            self.thr = fa_target_threshold(cal_scores, hours, start, self.cfg.fa_per_hour_target, self.k)
        elif self.kind == "conformal":
            m = np.array([np.max(pd.Series(v).rolling(self.k, min_periods=self.k).min().fillna(-np.inf).to_numpy()) for v in cal_scores])
            m = np.sort(m)
            n = len(m)
            idx = min(n - 1, math.ceil((n + 1) * (1 - self.alpha)) - 1)
            self.thr = float(m[idx])
        elif self.kind == "cusum":
            self.ref = float(np.percentile(pooled, self.ref_pct))
            allowed = self.cfg.fa_per_hour_target * hours
            stats = [_cusum_stat(v, self.ref) for v in cal_scores]
            hi_h = max(float(s.max()) for s in stats) + 1.0
            lo_h, hi = 0.0, hi_h
            for _ in range(40):
                mid = 0.5 * (lo_h + hi)
                ev = sum(rising_edges(s > mid) for s in stats)
                if ev <= allowed:
                    hi = mid
                else:
                    lo_h = mid
            self.thr = float(hi)
        return self

    def alarm(self, sc: np.ndarray) -> np.ndarray:
        if self.kind == "cusum":
            return _cusum_stat(sc, self.ref) > self.thr
        return persistent_alarm(sc, self.thr, self.k)


def measure(scores, split: Split, rule: Rule, power=None):
    """Outcomes of a rule on scored sessions: summary plus per-session detections."""
    clean, attacked, per_session = [], {}, {}
    for sc, (s, _), act in zip(scores, split.items, split.active):
        alarm = rule.alarm(sc)
        t = s["t_gnss_s"].to_numpy(dtype=float)
        if is_clean_session(s):
            clean.append(session_outcome(alarm, t, None, act))
        else:
            o = session_outcome(alarm, t, float(s["attack_onset_s"].iloc[0]), act)
            attacked.setdefault(session_type(s), []).append(o)
            per_session[str(s["session_id"].iloc[0])] = {**o, "type": session_type(s)}
    return (summarize_outcomes(clean, attacked) if clean else None), per_session


def _rate(sess: dict, pred):
    v = [o["detected"] for k, o in sess.items() if pred(k, o)]
    return float(np.mean(v)) if v else float("nan"), len(v)


def _delay_p(sess: dict, q, pred=lambda k, o: True):
    d = [o["delay_s"] for k, o in sess.items() if o["detected"] and pred(k, o)]
    return float(np.percentile(d, q)) if d else float("nan")


def fa_ci(events, hours):
    from scipy.stats import chi2

    return float(chi2.ppf(0.975, 2 * (events + 1)) / 2 / hours)


def evaluate(scorer, rule: Rule, ca: Split, va: Split, weak: Split, fah: Split) -> dict:
    """Metrics on all validation sets for one fitted scorer and one fitted rule."""
    sv, sw, sf = session_scores(scorer, va), session_scores(scorer, weak), session_scores(scorer, fah)
    mv, pv = measure(sv, va, rule)
    mw, pw = measure(sw, weak, rule)
    mf, _ = measure(sf, fah, rule)
    ct = lambda k, o: o["type"] == "consistent_takeover"
    return {
        "dr_val": mv["all_attacks"]["rate"], "dr_val_ordinary": _rate(pv, lambda k, o: "_o_" in k)[0], "dr_val_matched": _rate(pv, lambda k, o: "_m_" in k)[0],
        "ct_val": _rate(pv, ct)[0], "n_ct_val": _rate(pv, ct)[1],
        "far_val": mv["false_alarms_per_hour"],
        "far_hold": mf["false_alarms_per_hour"], "far_hold_events": mf["fa_events"], "far_hold_hours": mf["clean_hours"],
        "far_hold_upper95": fa_ci(mf["fa_events"], mf["clean_hours"]),
        "dr_weak": mw["all_attacks"]["rate"], "ct_weak": _rate(pw, ct)[0], "n_ct_weak": _rate(pw, ct)[1],
        "delay_median_s": mv["delay_median_s"], "delay_p90_s": mv["delay_p90_s"], "delay_p90_weak_s": mw["delay_p90_s"],
        "per_type_val": {a: r["rate"] for a, r in mv["per_type"].items()},
        "per_type_weak": {a: r["rate"] for a, r in mw["per_type"].items()},
    }


def calibrate_rule(scorer, rule: Rule, ca: Split):
    sc = session_scores(scorer, ca)
    clean = [v for v, (s, _) in zip(sc, ca.items) if is_clean_session(s)]
    return rule.fit(clean, _hours(ca))


def run(name_or_scorer, cols, cfg, rule_kw, splits, seed=None):
    tr, ca, va, weak, fah = splits
    scorer = name_or_scorer if not isinstance(name_or_scorer, str) else Scorer(name_or_scorer, cols, cfg, seed).fit(tr)
    rule = calibrate_rule(scorer, Rule(cfg=cfg, **rule_kw), ca)
    return scorer, rule, evaluate(scorer, rule, ca, va, weak, fah)
