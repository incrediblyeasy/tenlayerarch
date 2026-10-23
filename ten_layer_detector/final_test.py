"""Open the test set once for the locked model (MODEL_SELECTION.md section 6, step 5).

The model is fitted and its threshold set on the train and calibration splits of the
selection dataset; every session of a separate, never-used test dataset is then scored.

    python -m ten_layer_detector.final_test --config configs/sim_v2.json \\
        --select-data datasets/sim_fa2 --test-data datasets/sim_test --model one_class_svm --out results/final_test.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import ProjectConfig
from .dataset import load_sessions
from .features import available_features, compute_features
from .model_selection import _fit, _Rows, _score, _threshold, _validate
from .splits import split_three_way


def run(config: str, select_data: str, test_data: str, model: str) -> dict:
    cfg = ProjectConfig.load(config).detector
    sessions, _ = load_sessions(select_data)
    train, cal, _ = split_three_way(sessions, cfg.train_fraction, cfg.calibration_fraction, seed=cfg.split_seed)
    test, _ = load_sessions(test_data)
    cols = [c for c in available_features(train[0]) if c not in cfg.exclude_features]

    def rows(ss):
        return _Rows(ss, [compute_features(s, None, cfg) for s in ss], cols, cfg)

    mdl = _fit(model, rows(train), cfg)
    thr = _threshold(mdl, model, rows(cal), cfg)
    summary, _, per_session, ms = _validate(mdl, model, thr, rows(test), cfg)
    return {"model": model, "threshold": thr, "n_test_sessions": len(test), "ms_per_decision": ms, "summary": summary}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--select-data", required=True)
    p.add_argument("--test-data", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    res = run(a.config, a.select_data, a.test_data, a.model)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(res, indent=2, default=float), encoding="utf-8")
    print(json.dumps(res, indent=2, default=float))


if __name__ == "__main__":
    main()
