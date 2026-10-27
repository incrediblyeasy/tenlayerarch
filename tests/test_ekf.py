import numpy as np

from ten_layer_detector.config import DEFAULT_DETECTOR_CONFIG as CFG
from ten_layer_detector.features import OPT_IN, available_features, compute_features
from ten_layer_detector.sim import generate_session


def test_opt_in_features_are_not_default():
    s = generate_session(attack_type="clean", seed=1, session_id="c")
    assert not set(OPT_IN) & set(available_features(s))


def test_ekf_is_consistent_on_clean_and_reacts_to_a_step():
    clean = compute_features(generate_session(attack_type="clean", seed=2, session_id="c"), list(OPT_IN), CFG)
    step = generate_session(attack_type="step", seed=2, session_id="s")
    f = compute_features(step, list(OPT_IN), CFG)
    onset = float(step["attack_onset_s"].iloc[0])
    after = step["t_gnss_s"].to_numpy() > onset
    assert clean["ekf_innov_m"].to_numpy()[100:].max() < 1.5
    assert f["ekf_innov_m"].to_numpy()[after].max() > 3 * clean["ekf_innov_m"].to_numpy()[100:].max()


def test_ekf_is_causal():
    s = generate_session(attack_type="ramp", seed=3, session_id="r")
    full = compute_features(s, ["ekf_innov_m"], CFG)["ekf_innov_m"].to_numpy()
    cut = compute_features(s.iloc[:300].copy(), ["ekf_innov_m"], CFG)["ekf_innov_m"].to_numpy()
    assert np.allclose(full[:300], cut, equal_nan=True)
