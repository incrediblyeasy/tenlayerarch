import struct

import numpy as np
import pytest

from ten_layer_detector.features import available_features, compute_features
from ten_layer_detector.io.assemble import add_flight_controller, assemble_ubx
from ten_layer_detector.io.dataflash import build_dataflash, read_dataflash
from ten_layer_detector.io.ubx import NAV, NAV_CLOCK, NAV_DOP, NAV_PVT, NAV_SAT, RXM, RXM_RAWX, UBXStream, build_frame
from ten_layer_detector.sim import generate_session


def _pvt(itow, r):
    return struct.pack(
        "<IHBBBBBBIiBBBBiiiiIIiiiiiIIHH4BihH", itow, 2026, 10, 26, 12, 0, 0, 0x37, 25, 0, 3, 0x01, 0, int(r.num_sv),
        round(r.lon_deg * 1e7), round(r.lat_deg * 1e7), round((r.alt_m - 20) * 1e3), round(r.alt_m * 1e3), 1800, 2600,
        round(r.vel_n_mps * 1e3), round(r.vel_e_mps * 1e3), round(r.vel_d_mps * 1e3), 0, 0, 300, 500_000, round(r.pdop * 100),
        0, 0, 0, 0, 0, 0, 0, 0,
    )


def _frames(s):
    out = []
    for r in s.itertuples():
        itow = int(round(r.t_gnss_s * 1000))
        out.append(build_frame(NAV, NAV_PVT, _pvt(itow, r)))
        out.append(build_frame(NAV, NAV_CLOCK, struct.pack("<IiiII", itow, round(r.clk_bias_ns), round(r.clk_drift_nsps), 20, 300)))
        sats = [(r.cn0_dbhz - r.cn0_std_dbhz, 1), (r.cn0_dbhz + r.cn0_std_dbhz, 2), (r.cn0_dbhz, 3)]
        body = struct.pack("<IBB2B", itow, 1, len(sats), 0, 0) + b"".join(
            struct.pack("<BBBbhhI", 0, sv, round(c), 40, 100, 0, 0x08) for c, sv in sats)
        out.append(build_frame(NAV, NAV_SAT, body))
        out.append(build_frame(NAV, NAV_DOP, struct.pack("<IHHHHHHH", itow, 150, round(r.pdop * 100), 90, round(r.vdop * 100), round(r.hdop * 100), 60, 60)))
        raw = struct.pack("<dHbBBB2x", itow * 1e-3, 2300, 18, 1, 0, 1) + struct.pack(
            "<ddfBBBBHBBBBBx", r.pr_m, r.cp_cycles, r.dop_hz, 0, 5, 0, 0, int(r.lock_ms), 44, 3, 2, 1, 0x03)
        out.append(build_frame(RXM, RXM_RAWX, raw))
    return b"".join(out)


@pytest.fixture(scope="module")
def session():
    return generate_session(attack_type="clean", seed=8, duration_s=20.0)


def test_ubx_round_trip_recovers_the_gnss_columns(session):
    stream = UBXStream()
    blob = _frames(session)
    msgs = [m for k in range(0, len(blob), 513) for m in stream.feed(blob[k : k + 513])]
    out = assemble_ubx(msgs)
    assert len(out) == len(session) and stream.bad_checksum == 0
    np.testing.assert_allclose(out["lat_deg"], session["lat_deg"], atol=1e-7)
    np.testing.assert_allclose(out["vel_n_mps"], session["vel_n_mps"], atol=1e-3)
    np.testing.assert_allclose(out["hdop"], session["hdop"], atol=0.01)
    np.testing.assert_allclose(out["clk_drift_nsps"], session["clk_drift_nsps"], atol=1.0)
    np.testing.assert_allclose(out["cn0_dbhz"], session["cn0_dbhz"], atol=1.0)
    assert out["pr_m"].notna().all()


def test_columns_without_a_source_message_are_left_out(session):
    blob = _frames(session)
    stream = UBXStream()
    msgs = [m for m in stream.feed(blob) if (m.msg_class, m.msg_id) == (NAV, NAV_PVT)]
    out = assemble_ubx(msgs)
    assert "hdop" not in out.columns and "clk_bias_ns" not in out.columns and "cn0_dbhz" not in out.columns


def test_flight_controller_merge_aligns_clocks_and_converts_units(session):
    t0 = 1000.0
    boot = 5_000_000  # autopilot clock starts 5 s before the first GNSS epoch
    us = ((session["t_gnss_s"].to_numpy() - session["t_gnss_s"].iloc[0]) * 1e6 + boot).astype("int64")
    gms = (session["t_gnss_s"].to_numpy() * 1000).astype("int64")
    log = build_dataflash([
        (129, "GPS", "QI", "TimeUS,GMS", [[int(a), int(b)] for a, b in zip(us, gms)]),
        (130, "IMU", "QBfff", "TimeUS,I,AccX,AccY,AccZ", [[int(a), 0, float(x), float(y), float(z)] for a, x, y, z in zip(us, session["acc_bx_mps2"], session["acc_by_mps2"], session["acc_bz_mps2"])]),
        (131, "ATT", "Qf", "TimeUS,Yaw", [[int(a), float(np.degrees(y))] for a, y in zip(us, session["yaw_rad"])]),
        (132, "BARO", "Qf", "TimeUS,Alt", [[int(a), float(b)] for a, b in zip(us, session["baro_alt_m"])]),
    ])
    import tempfile, pathlib
    p = pathlib.Path(tempfile.mkdtemp()) / "x.bin"
    p.write_bytes(log)
    merged = add_flight_controller(session[["session_id", "t_gnss_s", "lat_deg"]].copy(), read_dataflash(p))
    assert len(merged) == len(session)
    np.testing.assert_allclose(merged["yaw_rad"], session["yaw_rad"], atol=1e-4)
    np.testing.assert_allclose(merged["acc_bx_mps2"], session["acc_bx_mps2"], atol=1e-4)
    np.testing.assert_allclose(merged["baro_alt_m"], session["baro_alt_m"], atol=1e-4)


def test_assembled_rows_feed_the_feature_code(session):
    blob = _frames(session)
    out = assemble_ubx(UBXStream().feed(blob))
    feats = available_features(out)
    assert {"posvel_mps", "cn0_shift_db", "clk_innov_ns", "code_carrier_m"} <= set(feats)
    f = compute_features(out, feats)
    assert np.isfinite(f.to_numpy()).all()
