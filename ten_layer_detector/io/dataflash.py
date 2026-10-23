"""Reader for ArduPilot DataFlash binary logs (.bin), such as those a Cube Orange writes.

No pymavlink needed. A log is a stream of records: 0xA3 0x95, a message-type byte, then a
fixed-size payload. FMT records (type 128) describe every other record type, so the reader
learns the layout from the log itself. Tested on a synthetic log only; check it on a real
Cube Orange log before relying on it. The array format 'a' (int16[32]) and 'Z' (char[64])
are read as raw bytes and text respectively.
"""
from __future__ import annotations

import struct
from pathlib import Path

import pandas as pd

HEAD = b"\xa3\x95"
FMT_TYPE = 128
FMT_LEN = 89  # 3 header bytes, then type, length, name[4], format[16], labels[64]

# format character -> (struct code, scale or None)
_CODES = {
    "b": ("b", None), "B": ("B", None), "h": ("h", None), "H": ("H", None), "i": ("i", None), "I": ("I", None),
    "f": ("f", None), "d": ("d", None), "q": ("q", None), "Q": ("Q", None), "M": ("B", None),
    "c": ("h", 0.01), "C": ("H", 0.01), "e": ("i", 0.01), "E": ("I", 0.01), "L": ("i", 1e-7),
    "n": ("4s", None), "N": ("16s", None), "Z": ("64s", None), "a": ("64s", None),
}


def _layout(fmt: str) -> tuple[struct.Struct, list[float | None]]:
    return struct.Struct("<" + "".join(_CODES[c][0] for c in fmt)), [_CODES[c][1] for c in fmt]


def _text(raw: bytes) -> str:
    return raw.split(b"\x00")[0].decode("ascii", "replace")


def read_dataflash(path: str | Path, names: set[str] | None = None) -> dict[str, pd.DataFrame]:
    """One DataFrame per message name (GPS, IMU, BARO, ATT, ...), optionally only those in `names`."""
    data = Path(path).read_bytes()
    formats: dict[int, tuple[str, struct.Struct, list, list[str], int]] = {}
    rows: dict[str, list[list]] = {}
    i, n = 0, len(data)
    while i + 3 <= n:
        if data[i : i + 2] != HEAD:
            i += 1
            continue
        mtype = data[i + 2]
        if mtype == FMT_TYPE:
            if i + FMT_LEN > n:
                break
            t, length, name, fmt, labels = struct.unpack_from("<BB4s16s64s", data, i + 3)
            struct_, scales = _layout(_text(fmt))
            formats[t] = (_text(name), struct_, scales, _text(labels).split(","), length)
            i += FMT_LEN
            continue
        spec = formats.get(mtype)
        if spec is None:
            i += 1  # record type whose FMT has not been seen: resynchronise
            continue
        name, struct_, scales, labels, length = spec
        if i + length > n:
            break
        if names is None or name in names:
            vals = struct_.unpack_from(data, i + 3)
            rows.setdefault(name, []).append(
                [_text(v) if isinstance(v, bytes) else (v * sc if sc else v) for v, sc in zip(vals, scales)]
            )
        i += length
    columns = {spec[0]: spec[3] for spec in formats.values()}
    return {name: pd.DataFrame(r, columns=columns[name]) for name, r in rows.items()}


def build_dataflash(messages: list[tuple[int, str, str, str, list[list]]]) -> bytes:
    """Test helper. Each item is (type, name, format, labels, list of value rows); returns a log
    with all FMT records first, then the data records."""
    out = bytearray()
    for t, name, fmt, labels, _ in messages:
        struct_, _ = _layout(fmt)
        out += HEAD + bytes([FMT_TYPE]) + struct.pack("<BB4s16s64s", t, 3 + struct_.size, name.encode(), fmt.encode(), labels.encode())
    for t, _, fmt, _, value_rows in messages:
        struct_, scales = _layout(fmt)
        for values in value_rows:
            raw = [v.encode() if isinstance(v, str) else (round(v / sc) if sc else v) for v, sc in zip(values, scales)]
            out += HEAD + bytes([t]) + struct_.pack(*raw)
    return bytes(out)
