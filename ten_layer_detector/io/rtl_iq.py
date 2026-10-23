"""RTL-SDR IQ files in the format `rtl_sdr` writes: interleaved unsigned 8-bit I, Q
(offset binary, 127.5 = zero), 2 bytes per complex sample, with a JSON sidecar."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np


class RTLSDRIQWriter:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def write_window(self, samples: np.ndarray, *, sample_rate_hz: float = 2_048_000.0, center_hz: float = 1575.42e6) -> Path:
        """samples: complex values in [-1, 1]; clipped and quantised to 8 bits."""
        arr = np.asarray(samples).astype(np.complex64)
        iq = np.empty(arr.size * 2, dtype=np.float32)
        iq[0::2] = arr.real
        iq[1::2] = arr.imag
        u8 = np.clip(np.round(iq * 127.5 + 127.5), 0, 255).astype(np.uint8)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        u8.tofile(self.path)
        meta = {"format": "cu8", "sample_rate_hz": sample_rate_hz, "center_hz": center_hz, "samples": int(arr.size)}
        self.path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
        return self.path


def read_iq_window(path: str | Path, *, offset_samples: int = 0, count: int = -1) -> np.ndarray:
    """Read an rtl_sdr cu8 file into complex64 in [-1, 1]."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"IQ file not found: {file_path}")
    raw = np.fromfile(file_path, dtype=np.uint8, count=-1 if count < 0 else 2 * count, offset=2 * offset_samples)
    raw = raw[: raw.size - raw.size % 2].astype(np.float32)
    return ((raw[0::2] - 127.5) / 127.5 + 1j * (raw[1::2] - 127.5) / 127.5).astype(np.complex64)
