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


def test_long_imu_residual_is_causal_and_finite():
    s = generate_session(attack_type="consistent_takeover", seed=2)
    a = compute_features(s, ["imu_resid_long_mps2"])["imu_resid_long_mps2"].to_numpy()
    cut = s.copy()
    cut.iloc[300:, cut.columns.get_loc("acc_bx_mps2")] += 5.0
    b = compute_features(cut, ["imu_resid_long_mps2"])["imu_resid_long_mps2"].to_numpy()
    assert np.isfinite(a).all() and (a[:300] == b[:300]).all()


def test_quiet_nuisances_option_is_opt_in_and_reduces_satellite_flicker():
    import numpy as np

    from ten_layer_detector.sim import generate_session

    base = generate_session(attack_type="clean", seed=11, session_id="a")
    same = generate_session(attack_type="clean", seed=11, session_id="a", realism={})
    assert base.equals(same)
    quiet = generate_session(attack_type="clean", seed=11, session_id="a", realism={"quiet": {"tracking_s": 3.0, "hysteresis_db": 3.0}})
    changes = lambda f: int(np.sum(np.diff(f["num_sv"].to_numpy()) != 0))
    assert changes(quiet) <= changes(base)
    assert set(quiet.columns) == set(base.columns)
