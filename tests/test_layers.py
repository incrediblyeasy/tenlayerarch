import numpy as np
import pandas as pd
import pytest

from ten_layer_detector.features import FEATURES, compute_features
from ten_layer_detector.layers import LAYER_CLASSES, MissingInputError, NotFittedError, make_layers, persistent_alarm
from ten_layer_detector.sim import generate_session


@pytest.fixture(scope="module")
def fitted_layers(small_dataset, cfg):
    sessions, _ = small_dataset
    train = sessions[::2]
    cal = [s for s in sessions[1::2] if s["label"].sum() == 0]
    layers = make_layers(cfg)
    for layer in layers:
        layer.fit(train)
        layer.calibrate(cal)
    return layers


@pytest.mark.parametrize("cls", LAYER_CLASSES)
def test_missing_inputs_raise(cls):
    layer = cls()
    with pytest.raises(MissingInputError):
        layer.feature_matrix(pd.DataFrame({"t_gnss_s": [0.0, 0.1, 0.2]}))


def test_layer4_without_galileo_raises():
    s = generate_session(attack_type="clean").drop(columns=["gal_lat_deg", "gal_lon_deg", "gal_alt_m"])
    with pytest.raises(MissingInputError):
        make_layers()[3].feature_matrix(s)


def test_scoring_before_fit_raises():
    with pytest.raises(NotFittedError):
        make_layers()[0].score_rows(generate_session())


def test_alarm_needs_a_frozen_threshold():
    with pytest.raises(NotFittedError):
        make_layers()[0].alarm(np.ones(10))


def test_alarm_threshold_does_not_come_from_the_scores(fitted_layers):
    layer = fitted_layers[0]
    tiny = np.full(50, layer.threshold * 0.5)
    assert not layer.alarm(tiny).any()


def test_persistence_needs_k_consecutive_rows():
    s = np.array([0, 2, 2, 0, 2, 2, 2, 0], dtype=float)
    np.testing.assert_array_equal(persistent_alarm(s, 1.0, 3), [0, 0, 0, 0, 0, 0, 1, 0])


@pytest.mark.parametrize("name", list(FEATURES))
def test_features_are_causal(name):
    s = generate_session(attack_type="step", seed=4)
    k = 300
    modified = s.copy()
    numeric = [c for c in s.columns if s[c].dtype.kind == "f" and c != "t_gnss_s"]
    modified.loc[k:, numeric] = modified.loc[k:, numeric] * 1.7 + 13.0
    a = compute_features(s, [name])[name].to_numpy()[:k]
    b = compute_features(modified, [name])[name].to_numpy()[:k]
    np.testing.assert_allclose(a, b)


def test_layer_scores_are_per_row_and_causal(fitted_layers):
    s = generate_session(attack_type="ramp", seed=6)
    k = 350
    modified = s.copy()
    modified.loc[k:, "lat_deg"] += 0.01
    modified.loc[k:, "cn0_dbhz"] += 9.0
    for layer in fitted_layers:
        a = layer.score_rows(s)
        assert a.shape == (len(s),)
        np.testing.assert_allclose(a[:k], layer.score_rows(modified)[:k], err_msg=layer.name)


def test_warmup_rows_never_alarm(fitted_layers, cfg):
    s = generate_session(attack_type="static", attack_onset_s=2.0, seed=1)
    warm = s["t_gnss_s"].to_numpy() < cfg.baseline_s
    for layer in fitted_layers:
        assert not layer.alarm(layer.score_rows(s))[warm].any(), layer.name
