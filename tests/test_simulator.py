import numpy as np
import pytest

from ten_layer_detector.schema import CANONICAL_COLUMNS, MULTI_GNSS_COLUMNS, schema_problems
from ten_layer_detector.sim import ATTACK_TYPES, attack_offset, generate_session, sample_trajectory


def test_session_matches_schema_and_labels():
    s, meta = generate_session(duration_s=30, sample_rate_hz=10, attack_type="ramp", attack_onset_s=12.0, return_metadata=True)
    assert schema_problems(s, list(CANONICAL_COLUMNS) + list(MULTI_GNSS_COLUMNS)) == []
    assert len(s) == 300
    t = s["t_gnss_s"].to_numpy()
    assert (s["label"].to_numpy() == (t >= 12.0)).all()
    assert meta["attack_start_t_gnss_s"] == 12.0 and meta["attack_type"] == "ramp"
    assert "power_db" in meta and "power_db" not in s.columns


def test_clean_session_has_no_attack():
    s = generate_session(attack_type="clean", seed=3)
    assert s["label"].sum() == 0 and (s["attack_type"] == "clean").all()


@pytest.mark.parametrize("bad", [{"attack_onset_s": 100.0}, {"attack_onset_s": -1.0}])
def test_onset_outside_session_is_rejected(bad):
    with pytest.raises(ValueError):
        generate_session(duration_s=30, attack_type="step", **bad)


def test_unknown_attack_type_is_rejected():
    with pytest.raises(ValueError):
        generate_session(attack_type="teleport")


def test_same_seed_is_reproducible():
    a = generate_session(attack_type="dynamic_takeover", seed=9)
    b = generate_session(attack_type="dynamic_takeover", seed=9)
    assert a.equals(b)


@pytest.mark.parametrize("attack", ATTACK_TYPES)
def test_paired_clean_and_attacked_sessions_match_before_onset(attack):
    clean = generate_session(attack_type="clean", seed=5)
    att = generate_session(attack_type=attack, seed=5)
    pre = att["label"].to_numpy() == 0
    num = [c for c in clean.columns if clean[c].dtype.kind in "fi" and c not in ("label", "attack_onset_s")]
    np.testing.assert_allclose(att.loc[pre, num].to_numpy(), clean.loc[pre, num].to_numpy())
    post = ~pre
    changed = [c for c in num if not np.allclose(att.loc[post, c], clean.loc[post, c], rtol=0, atol=1e-9)]
    assert {"lat_deg", "lon_deg"} <= set(changed)


@pytest.mark.parametrize("attack", ["consistent_takeover", "dynamic_takeover"])
def test_takeovers_are_position_velocity_consistent_and_plausible(attack):
    t = np.arange(600) * 0.1
    for seed in range(30):
        rng = np.random.default_rng(seed)
        traj = sample_trajectory(rng, t)
        o, o_dot, _ = attack_offset(rng, attack, t, 20.05, traj["pos"], traj["vel"])
        inconsistency = np.abs(np.gradient(o, t, axis=0) - o_dot)[1:-1].max()
        assert inconsistency < 0.1  # m/s
        assert np.abs(np.gradient(o_dot, t, axis=0)).max() < 3.0  # m/s^2, airframe limit


@pytest.mark.parametrize("attack", ATTACK_TYPES)
def test_every_attack_moves_position_beyond_clean_noise(attack):
    clean = generate_session(attack_type="clean", seed=8)
    att = generate_session(attack_type=attack, seed=8)
    post = att["label"].to_numpy() == 1
    d = np.hypot(att["lat_deg"] - clean["lat_deg"], att["lon_deg"] - clean["lon_deg"]).to_numpy()[post] * 111_000
    assert d.max() > 3.0
