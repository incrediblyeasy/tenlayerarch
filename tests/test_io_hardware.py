import struct

import pytest

from ten_layer_detector.io.dataflash import build_dataflash, read_dataflash
from ten_layer_detector.io.ubx import RXM, RXM_RAWX, UBXMessage, UBXStream, build_frame, parse_rxm_rawx


def _rawx_payload(n=2):
    head = struct.pack("<dHbBBB2x", 345600.25, 2300, 18, n, 0x02, 1)
    meas = b"".join(
        struct.pack("<ddfBBBBHBBBBBx", 2.1e7 + k, 1.1e8 + k, -1234.5 + k, 0, 5 + k, 0, 0, 4000 + k, 41 + k, 3, 2, 1, 0x03)
        for k in range(n)
    )
    return head + meas


def test_rawx_decodes_header_and_measurements():
    out = parse_rxm_rawx(UBXMessage(RXM, RXM_RAWX, _rawx_payload(2)))
    assert out["num_meas"] == 2 and out["week"] == 2300 and out["clock_reset"]
    m = out["meas"][1]
    assert (m["sv_id"], m["cn0_dbhz"], m["lock_ms"]) == (6, 42, 4001)
    assert m["pr_valid"] and m["cp_valid"] and not m["half_cycle"]
    assert m["pr_std_m"] == pytest.approx(0.08)


def test_rawx_rejects_short_or_wrong_payload():
    with pytest.raises(ValueError):
        parse_rxm_rawx(UBXMessage(RXM, RXM_RAWX, _rawx_payload(3)[:-5]))
    with pytest.raises(ValueError):
        parse_rxm_rawx(UBXMessage(0x01, 0x07, _rawx_payload(1)))


def test_stream_handles_frames_split_across_reads_and_garbage():
    frames = [build_frame(RXM, RXM_RAWX, _rawx_payload(2)), build_frame(0x01, 0x22, b"\x00" * 20)]
    blob = b"\x00\xb5junk" + frames[0] + b"\xff\xff" + frames[1]
    stream, got = UBXStream(), []
    for k in range(0, len(blob), 7):  # arbitrary small chunks, splitting frames mid-way
        got += stream.feed(blob[k : k + 7])
    assert [(m.msg_class, m.msg_id) for m in got] == [(RXM, RXM_RAWX), (0x01, 0x22)]
    assert stream.bad_checksum == 0


def test_stream_skips_bad_checksum_and_counts_it():
    good = build_frame(0x01, 0x22, b"\x01" * 20)
    bad = bytearray(build_frame(0x01, 0x22, b"\x02" * 20))
    bad[-1] ^= 0xFF
    stream = UBXStream()
    got = stream.feed(bytes(bad) + good)
    assert len(got) == 1 and got[0].payload == b"\x01" * 20 and stream.bad_checksum == 1


def test_dataflash_reads_scaled_fields_and_text(tmp_path):
    log = build_dataflash([
        (129, "GPS", "QBLLfZ", "TimeUS,Status,Lat,Lng,Alt,Note", [[1_000_000, 3, 47.3977419, 8.5455938, 488.5, "ok"], [1_200_000, 3, 47.3977500, 8.5456000, 488.7, "ok"]]),
        (130, "BARO", "Qf", "TimeUS,Alt", [[1_000_000, 12.5]]),
    ])
    path = tmp_path / "flight.bin"
    path.write_bytes(b"\x00\x01" + log)  # leading garbage is skipped
    out = read_dataflash(path)
    assert set(out) == {"GPS", "BARO"}
    gps = out["GPS"]
    assert list(gps.columns) == ["TimeUS", "Status", "Lat", "Lng", "Alt", "Note"]
    assert gps["Lat"].iloc[0] == pytest.approx(47.3977419, abs=1e-7) and gps["Note"].iloc[1] == "ok"
    assert len(read_dataflash(path, names={"BARO"})) == 1
