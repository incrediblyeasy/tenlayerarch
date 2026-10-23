import struct

import numpy as np

from ten_layer_detector.io.rtl_iq import RTLSDRIQWriter, read_iq_window
from ten_layer_detector.io.ubx import NAV, NAV_CLOCK, NAV_PVT, NAV_SAT, UBXParser, build_frame
from ten_layer_detector.time_base import TimeBase


def _pvt_payload():
    return struct.pack(
        "<IHBBBBBBIiBBBBiiiiIIiiiiiIIHH4BihH",
        345_600_000, 2026, 10, 22, 12, 30, 15, 0x37, 25, -1200, 3, 0x01, 0, 14,
        771_234_567, 286_543_210, 250_000, 215_500, 1800, 2600, 1500, -2500, 100, 2915,
        9_000_000, 300, 500_000, 145, 0, 0, 0, 0, 0, 0, 0, 0,
    )


def test_nav_pvt_decodes_a_92_byte_payload():
    msgs = UBXParser.iter_messages(build_frame(NAV, NAV_PVT, _pvt_payload()))
    pvt = UBXParser.parse_nav_pvt(msgs[0])
    assert pvt["fix_type"] == 3 and pvt["num_sv"] == 14
    assert abs(pvt["lat_deg"] - 28.654321) < 1e-6 and abs(pvt["lon_deg"] - 77.1234567) < 1e-7
    assert pvt["alt_m"] == 215.5 and pvt["vel_e_mps"] == -2.5 and abs(pvt["pdop"] - 1.45) < 1e-9


def test_nav_clock_and_nav_sat():
    clock = build_frame(NAV, NAV_CLOCK, struct.pack("<IiiII", 1000, -12345, 87, 20, 300))
    sat = build_frame(NAV, NAV_SAT, struct.pack("<IBB2B", 1000, 1, 1, 0, 0) + struct.pack("<BBBbhhI", 0, 12, 44, 63, 210, -15, 0x08))
    msgs = UBXParser.iter_messages(clock + sat)
    c = UBXParser.parse_nav_clock(msgs[0])
    s = UBXParser.parse_nav_sat(msgs[1])
    assert c["clk_bias_ns"] == -12345 and c["clk_drift_nsps"] == 87
    assert s["sats"][0] == {"gnss_id": 0, "sv_id": 12, "cn0_dbhz": 44, "elev_deg": 63, "azim_deg": 210, "pr_res_m": -1.5, "used": True, "flags": 8}


def test_bad_checksum_frames_are_rejected():
    good = build_frame(NAV, NAV_PVT, _pvt_payload())
    bad = bytearray(good)
    bad[20] ^= 0xFF
    stats = {}
    msgs = UBXParser.iter_messages(b"\x00junk" + bytes(bad) + good, stats=stats)
    assert len(msgs) == 1 and stats["bad_checksum"] == 1


def test_iq_file_is_8_bit_interleaved_and_round_trips(tmp_path):
    x = (np.cos(np.linspace(0, 20, 1000)) + 1j * np.sin(np.linspace(0, 20, 1000))) * 0.8
    path = RTLSDRIQWriter(tmp_path / "w.bin").write_window(x)
    assert path.stat().st_size == 2 * x.size
    y = read_iq_window(path)
    assert np.max(np.abs(y - x)) < 1.0 / 127.5


def test_time_offset_estimate_and_5ms_acceptance():
    rng = np.random.default_rng(0)
    g = np.arange(0, 600, 0.1)
    host = g * (1 + 20e-6) + 1234.567 + rng.normal(0, 0.0005, g.size)
    tb = TimeBase()
    fit = tb.estimate_offset(g, host)
    assert abs(fit["offset_s"] - 1234.567) < 1e-3 and abs(fit["rate_ppm"] - 20) < 0.5
    assert tb.acceptance_test(g, host)["passed"]
    assert not tb.acceptance_test(g, host + rng.normal(0, 0.01, g.size))["passed"]
