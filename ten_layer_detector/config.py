"""All detector and evaluation settings in one versioned, frozen place."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

CONFIG_VERSION = "sim-1.0"


@dataclass(frozen=True)
class DatasetConfig:
    n_clean: int = 400
    n_per_attack: int = 170
    duration_s: float = 60.0
    sample_rate_hz: float = 10.0
    seed: int = 2026


@dataclass(frozen=True)
class DetectorConfig:
    # Rows before baseline_s are a warm-up: the session baseline is built from them and
    # no alarm is raised. The detector assumes the first baseline_s seconds are clean.
    baseline_s: float = 10.0
    # Trailing (causal) window lengths in seconds.
    short_window_s: float = 1.0
    mid_window_s: float = 2.0
    long_window_s: float = 3.0
    allan_window_s: float = 10.0
    persist_window_s: float = 5.0
    lock_hold_s: float = 5.0
    # Alarm: per-row score above the threshold for persistence_k consecutive rows.
    threshold_percentile: float = 99.9
    persistence_k: int = 3
    # Second vote operating point: threshold raised on clean calibration sessions until
    # alarm events per hour are at or below this target (MODEL_SELECTION.md: 1/h).
    fa_per_hour_target: float = 1.0
    # Session split (fractions of each attack type) and out-of-fold folds on train.
    train_fraction: float = 0.5
    calibration_fraction: float = 0.2
    oof_folds: int = 3
    split_seed: int = 7
    model_seed: int = 0
    # Features excluded everywhere (used for the shortcut test, e.g. without C/N0).
    exclude_features: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectConfig:
    version: str = CONFIG_VERSION
    dataset: DatasetConfig = field(default_factory=DatasetConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "ProjectConfig":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        det = dict(raw.get("detector", {}))
        det["exclude_features"] = tuple(det.get("exclude_features", ()))
        return cls(
            version=raw.get("version", CONFIG_VERSION),
            dataset=DatasetConfig(**raw.get("dataset", {})),
            detector=DetectorConfig(**det),
        )


DEFAULT_CONFIG = ProjectConfig()
DEFAULT_DETECTOR_CONFIG = DEFAULT_CONFIG.detector

__all__ = ["CONFIG_VERSION", "DatasetConfig", "DetectorConfig", "ProjectConfig", "DEFAULT_CONFIG", "DEFAULT_DETECTOR_CONFIG", "replace"]
