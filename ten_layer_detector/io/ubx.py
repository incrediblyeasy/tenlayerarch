"""UBX framing with checksum check, and decoders for NAV-PVT, NAV-CLOCK and NAV-SAT.

Field layouts follow the u-blox M8/M9/M10 interface description. Confirm against the
exact module and firmware before relying on them (the module model is still open).
Tested on synthetic frames only; not yet on a recorded log.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any, Iterable

SYNC = b"\xb5\x62"
NAV = 0x01
NAV_PVT = 0x07
NAV_CLOCK = 0x22
NAV_SAT = 0x35

_PVT = struct.Struct("<IHBBBBBBIiBBBBiiiiIIiiiiiIIHH4BihH")
_CLOCK = struct.Struct("<IiiII")
_SAT_HEAD = struct.Struct("<IBB2B")
_SAT_SV = struct.Struct("<BBBbhhI")
assert _PVT.size == 92 and _CLOCK.size == 20 and _SAT_HEAD.size == 8 and _SAT_SV.size == 12


@dataclass
class UBXMessage:
    msg_class: int
    msg_id: int
    payload: bytes

    @property
    def name(self) -> str:
        return f"0x{self.msg_class:02x}.{self.msg_id:02x}"


def checksum(body: bytes) -> bytes:
    """8-bit Fletcher checksum over class, id, length and payload."""
    a = b = 0
    for byte in body:
        a = (a + byte) & 0xFF
        b = (b + a) & 0xFF
    return bytes((a, b))


def build_frame(msg_class: int, msg_id: int, payload: bytes) -> bytes:
    body = bytes((msg_class, msg_id)) + struct.pack("<H", len(payload)) + payload
    return SYNC + body + checksum(body)


class UBXParser:
    SYNC1 = 0xB5
    SYNC2 = 0x62

    @classmethod
    def iter_messages(cls, stream: bytes | bytearray | Iterable[int], *, stats: dict | None = None) -> list[UBXMessage]:
        """Frames with a valid checksum. Bad-checksum frames are skipped and counted in stats."""
        data = bytes(stream)
        messages: list[UBXMessage] = []
        bad = 0
        i = 0
        while i + 8 <= len(data):
            if data[i] != cls.SYNC1 or data[i + 1] != cls.SYNC2:
                i += 1
                continue
            length = struct.unpack_from("<H", data, i + 4)[0]
            end = i + 6 + length + 2
            if end > len(data):
                break
            body = data[i + 2 : i + 6 + length]
            if checksum(body) != data[end - 2 : end]:
                bad += 1
                i += 1  # resynchronise on the next sync pair
                continue
            messages.append(UBXMessage(data[i + 2], data[i + 3], data[i + 6 : i + 6 + length]))
            i = end
        if stats is not None:
            stats["bad_checksum"] = bad
            stats["frames"] = len(messages)
        return messages

    @staticmethod
    def parse_nav_pvt(message: UBXMessage) -> dict[str, Any]:
        if (message.msg_class, message.msg_id) != (NAV, NAV_PVT) or len(message.payload) < 92:
            raise ValueError(f"not a 92-byte NAV-PVT payload: {message.name}, {len(message.payload)} bytes")
        f = _PVT.unpack_from(message.payload)
        (itow, year, month, day, hour, minute, second, valid, t_acc, nano, fix_type, flags, flags2, num_sv,
         lon, lat, height, hmsl, h_acc, v_acc, vel_n, vel_e, vel_d, g_speed, head_mot, s_acc, head_acc,
         p_dop, flags3, _r0, _r1, _r2, _r3, head_veh, mag_dec, mag_acc) = f
        return {
            "message": "NAV-PVT", "itow_ms": itow, "year": year, "month": month, "day": day, "hour": hour,
            "minute": minute, "second": second, "valid": valid, "t_acc_ns": t_acc, "nano_ns": nano,
            "fix_type": fix_type, "flags": flags, "flags2": flags2, "num_sv": num_sv,
            "lon_deg": lon * 1e-7, "lat_deg": lat * 1e-7, "height_m": height * 1e-3, "alt_m": hmsl * 1e-3,
            "h_acc_m": h_acc * 1e-3, "v_acc_m": v_acc * 1e-3,
            "vel_n_mps": vel_n * 1e-3, "vel_e_mps": vel_e * 1e-3, "vel_d_mps": vel_d * 1e-3,
            "g_speed_mps": g_speed * 1e-3, "head_mot_deg": head_mot * 1e-5, "s_acc_mps": s_acc * 1e-3,
            "head_acc_deg": head_acc * 1e-5, "pdop": p_dop * 0.01, "flags3": flags3,
        }

    @staticmethod
    def parse_nav_clock(message: UBXMessage) -> dict[str, Any]:
        if (message.msg_class, message.msg_id) != (NAV, NAV_CLOCK) or len(message.payload) < 20:
            raise ValueError(f"not a NAV-CLOCK payload: {message.name}")
        itow, clk_b, clk_d, t_acc, f_acc = _CLOCK.unpack_from(message.payload)
        return {"message": "NAV-CLOCK", "itow_ms": itow, "clk_bias_ns": clk_b, "clk_drift_nsps": clk_d, "t_acc_ns": t_acc, "f_acc_psps": f_acc}

    @staticmethod
    def parse_nav_sat(message: UBXMessage) -> dict[str, Any]:
        if (message.msg_class, message.msg_id) != (NAV, NAV_SAT) or len(message.payload) < 8:
            raise ValueError(f"not a NAV-SAT payload: {message.name}")
        itow, version, num_svs, _, _ = _SAT_HEAD.unpack_from(message.payload)
        if len(message.payload) < 8 + 12 * num_svs:
            raise ValueError("NAV-SAT payload shorter than numSvs entries")
        sats = []
        for k in range(num_svs):
            gnss, sv, cno, elev, azim, pr_res, flags = _SAT_SV.unpack_from(message.payload, 8 + 12 * k)
            sats.append({"gnss_id": gnss, "sv_id": sv, "cn0_dbhz": cno, "elev_deg": elev, "azim_deg": azim,
                         "pr_res_m": pr_res * 0.1, "used": bool(flags & 0x08), "flags": flags})
        return {"message": "NAV-SAT", "itow_ms": itow, "version": version, "num_svs": num_svs, "sats": sats}


def parse_ubx_stream(stream: bytes | bytearray | Iterable[int]) -> list[UBXMessage]:
    return UBXParser.iter_messages(stream)
