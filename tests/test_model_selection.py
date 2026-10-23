import numpy as np

from ten_layer_detector.model_selection import MODEL_CANDIDATES, evaluate_model_candidates, select_model
from ten_layer_detector.splits import split_three_way


def test_candidates_are_measured_not_derived(small_dataset, cfg):
    sessions, meta = small_dataset
    tr, ca, va = split_three_way(sessions, 0.5, 0.2, seed=3)
    rows = evaluate_model_candidates(tr, ca, va, meta, cfg=cfg, candidates=["logistic_regression", "isolation_forest"])
    assert [r["model_name"] for r in rows] == ["logistic_regression", "isolation_forest"]
    for r in rows:
        for key in ("dr_validation", "far_per_hour", "dr_no_strength", "ms_per_decision"):
            assert np.isfinite(r[key]), key
        assert r["dr_unseen"] != 0.9 * r["dr_validation"]
        assert r["eligible"] == (r["far_per_hour"] <= 1.0 and r["dr_no_strength"] > 0)


def test_select_model_follows_the_rule():
    rows = [
        {"model_name": "a", "eligible": False, "dr_validation": 0.99},
        {"model_name": "b", "eligible": True, "dr_validation": 0.8, "dr_weak": 0.5, "dr_unseen": 0.5, "delay_median_s": 2.0, "ms_per_decision": 1.0},
        {"model_name": "c", "eligible": True, "dr_validation": 0.82, "dr_weak": 0.52, "dr_unseen": 0.5, "delay_median_s": 1.0, "ms_per_decision": 1.0},
    ]
    assert select_model(rows) == "c"
    assert select_model([rows[0]]) is None
    assert "random_forest" in MODEL_CANDIDATES
