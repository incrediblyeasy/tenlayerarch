import numpy as np

from ten_layer_detector.features import EARTH_R, compute_features
from ten_layer_detector.sim import generate_session


def _north_offset(frame, metres, start_s, end_s):
    out = frame.copy()
    t = out["t_gnss_s"].to_numpy()
    on = (t >= start_s) & (t < end_s)
    out.loc[on, "lat_deg"] += np.degrees(metres / EARTH_R)
    return out


def test_dead_reckoning_ignores_short_jump_but_keeps_persistent_step():
    base = generate_session(attack_type="clean", seed=5)
    short = compute_features(_north_offset(base, 20.0, 30.0, 33.0), ["dead_reckoning_m"])["dead_reckoning_m"].to_numpy()
    step = compute_features(_north_offset(base, 20.0, 30.0, 61.0), ["dead_reckoning_m"])["dead_reckoning_m"].to_numpy()
    ref = compute_features(base, ["dead_reckoning_m"])["dead_reckoning_m"].to_numpy()
    after = slice(380, 600)
    assert step[after].min() > ref[after].max() + 10.0
    assert short.max() < ref.max() + 5.0


def test_cn0_rise_and_fall_have_opposite_signs():
    base = generate_session(attack_type="clean", seed=8)  # no nuisance events
    t = base["t_gnss_s"].to_numpy()
    up, down = base.copy(), base.copy()
    up.loc[t >= 30, "cn0_dbhz"] += 6.0
    down.loc[t >= 30, "cn0_dbhz"] -= 6.0
    fu = compute_features(up, ["cn0_rise_db", "cn0_fall_db"])
    fd = compute_features(down, ["cn0_rise_db", "cn0_fall_db"])
    assert fu["cn0_rise_db"].iloc[-1] > 5.0 and fu["cn0_fall_db"].iloc[-1] < 1.0
    assert fd["cn0_fall_db"].iloc[-1] > 5.0 and fd["cn0_rise_db"].iloc[-1] < 1.0
