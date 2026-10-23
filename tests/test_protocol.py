import numpy as np
import pytest

from ten_layer_detector.config import DetectorConfig
from ten_layer_detector.evaluate import evaluate_protocol
from ten_layer_detector.features import CN0_FEATURES
from ten_layer_detector.sim import ATTACK_TYPES
from ten_layer_detector.splits import session_id, split_sessions, split_three_way


def test_three_way_split_is_disjoint_and_stratified(small_dataset):
    sessions, _ = small_dataset
    tr, ca, te = split_three_way(sessions, 0.5, 0.2, seed=1)
    ids = [set(map(session_id, x)) for x in (tr, ca, te)]
    assert not (ids[0] & ids[1] or ids[0] & ids[2] or ids[1] & ids[2])
    assert sum(map(len, ids)) == len(sessions)
    for part in (tr, ca, te):
        assert {s["attack_type"].iloc[0] for s in part} == {"clean", *ATTACK_TYPES}


def test_split_uses_the_seed(small_dataset):
    sessions, _ = small_dataset
    a = [session_id(s) for s in split_sessions(sessions, 0.3, seed=1)[1]]
    b = [session_id(s) for s in split_sessions(sessions, 0.3, seed=2)[1]]
    assert a != b


def test_single_session_cannot_be_split(small_dataset):
    with pytest.raises(ValueError):
        split_sessions(small_dataset[0][:1])


def test_counts_are_correct(protocol_result, small_dataset):
    c = protocol_result["counts"]
    assert sum(c[k]["sessions"] for k in ("train", "calibration", "test")) == len(small_dataset[0])
    n_test_attacked = sum(v for k, v in c["test"]["by_type"].items() if k != "clean")
    assert protocol_result["detectors"]["vote"]["all_attacks"]["n"] == n_test_attacked


def test_all_ten_layers_run_on_simulated_data(protocol_result):
    assert protocol_result["not_evaluated"] == {}
    assert len([n for n in protocol_result["detectors"] if n[0].isdigit()]) == 10


def test_vote_has_few_false_alarms_on_held_out_clean_sessions(protocol_result):
    vote = protocol_result["detectors"]["vote"]
    assert vote["clean_sessions_alarmed"]["rate"] <= 0.1


def test_vote_detects_attacks_on_held_out_sessions(protocol_result):
    vote = protocol_result["detectors"]["vote"]
    assert vote["all_attacks"]["rate"] >= 0.8
    for attack in ("static", "step"):
        assert vote["per_type"][attack]["rate"] >= 0.9, attack


def test_layers_that_should_see_position_attacks_do(protocol_result):
    d = protocol_result["detectors"]
    for attack in ("static", "step"):
        assert max(d["5_cross_domain"]["per_type"][attack]["rate"], d["6_physical"]["per_type"][attack]["rate"]) >= 0.9


def test_excluding_features_marks_layer_not_evaluated(small_dataset):
    sessions, meta = small_dataset
    r = evaluate_protocol(sessions, meta, config=DetectorConfig(exclude_features=CN0_FEATURES), ablation=False)
    assert "2_signal_quality" in r["not_evaluated"]
    assert "2_signal_quality" not in r["detectors"]


def test_missing_layer_inputs_are_reported_not_skipped(small_dataset):
    sessions, meta = small_dataset
    stripped = [s.drop(columns=["gal_lat_deg", "gal_lon_deg", "gal_alt_m"]) for s in sessions]
    r = evaluate_protocol(stripped, meta, ablation=False)
    assert "4_multi_constellation" in r["not_evaluated"]
    assert r["counts"]["test"]["sessions"] == sum(r["counts"]["test"]["by_type"].values())


def test_protocol_is_reproducible(small_dataset, protocol_result, cfg):
    sessions, meta = small_dataset
    again = evaluate_protocol(sessions, meta, config=cfg, ablation=False)
    for name, d in protocol_result["detectors"].items():
        assert d["all_attacks"]["k"] == again["detectors"][name]["all_attacks"]["k"], name
        assert d["fa_events"] == again["detectors"][name]["fa_events"], name
        assert np.isclose(d["threshold"], again["detectors"][name]["threshold"]), name
