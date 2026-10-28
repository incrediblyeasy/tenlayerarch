import numpy as np

from ten_layer_detector.nuisance import episodes, pooled_rate, rising, verdict


def _flat(n=100, dt=0.2):
    t = np.arange(n) * dt
    return t, np.full(n, 10.0), np.full(n, 1.0), np.full(n, 40.0), np.full(n, 10.0), np.zeros(n), np.zeros(n)


def test_rising_counts_episodes_not_samples():
    assert rising(np.array([0, 1, 1, 0, 1, 0], bool)) == 2


def test_quiet_recording_has_no_events():
    r = episodes(*_flat())
    assert all(v == 0 for v in r["counts"].values())


def test_satellite_drop_hdop_jump_and_position_jump_are_found():
    t, s, h, lat, lon, vn, ve = _flat()
    s[50:] -= 2
    h[60:70] += 0.3
    lat = lat.copy()
    lat[80:] += 10 / 6_378_137.0 * 180 / np.pi  # 10 m north step, velocity still zero
    r = episodes(t, s, h, lat, lon, vn, ve)["counts"]
    assert r["sat_drop>=1"] == 1 and r["sat_drop>=2"] == 1 and r["sat_drop>=3"] == 0
    assert r["hdop_jump>=0.2"] >= 1 and r["hdop_jump>=0.5"] == 0
    assert r["position_jump>=3.0"] == 1


def test_window_is_in_seconds_not_rows():
    a = episodes(*_flat(dt=0.2))
    t, s, h, lat, lon, vn, ve = _flat(dt=0.1)
    s[50:] -= 1
    b = episodes(t, s, h, lat, lon, vn, ve)
    assert a["counts"]["sat_drop>=1"] == 0 and b["counts"]["sat_drop>=1"] == 1


def test_rate_and_verdict():
    recs = [{"counts": {"x": 2}, "minutes": 1.0}, {"counts": {"x": 4}, "minutes": 1.0}, {"counts": {"x": 3}, "minutes": 1.0}]
    r = pooled_rate(recs, "x", n_boot=500)
    assert abs(r[0] - 3.0) < 1e-9 and r[1] <= 3.0 <= r[2]
    assert verdict((20.0, 0, 0), (3.0, 2.0, 4.0)) == "much_more_active"
    assert verdict((3.0, 0, 0), (3.0, 2.0, 4.0)) == "close"
    assert verdict((0.5, 0, 0), (3.0, 2.0, 4.0)) == "much_quieter"
