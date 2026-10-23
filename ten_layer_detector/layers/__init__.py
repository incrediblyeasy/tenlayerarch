from __future__ import annotations

from typing import List

from ..config import DEFAULT_DETECTOR_CONFIG, DetectorConfig
from .base import BaseLayer, LayerResult, MissingInputError, NotFittedError, evaluate_layers, persistent_alarm
from .l01_time import TimeDomainLayer
from .l02_signal import SignalQualityLayer
from .l03_geometry import GeometryLayer
from .l04_multiconst import MultiConstellationLayer
from .l05_cross import CrossDomainLayer
from .l06_physical import PhysicalLayer
from .l07_raw import RawSignalLayer
from .l08_temporal import TemporalAnomalyLayer
from .l09_allan import AllanDeviationLayer
from .l10_learned import LearnedModelLayer

LAYER_CLASSES = (
    TimeDomainLayer,
    SignalQualityLayer,
    GeometryLayer,
    MultiConstellationLayer,
    CrossDomainLayer,
    PhysicalLayer,
    RawSignalLayer,
    TemporalAnomalyLayer,
    AllanDeviationLayer,
    LearnedModelLayer,
)


def make_layers(cfg: DetectorConfig = DEFAULT_DETECTOR_CONFIG) -> List[BaseLayer]:
    """Fresh, unfitted instances of all ten layers."""
    return [cls(cfg) for cls in LAYER_CLASSES]


# Unfitted instances, for introspection (names, required columns). Fit before scoring.
ALL_LAYERS = make_layers()

__all__ = [
    "ALL_LAYERS",
    "LAYER_CLASSES",
    "make_layers",
    "BaseLayer",
    "LayerResult",
    "MissingInputError",
    "NotFittedError",
    "evaluate_layers",
    "persistent_alarm",
    "TimeDomainLayer",
    "SignalQualityLayer",
    "GeometryLayer",
    "MultiConstellationLayer",
    "CrossDomainLayer",
    "PhysicalLayer",
    "RawSignalLayer",
    "TemporalAnomalyLayer",
    "AllanDeviationLayer",
    "LearnedModelLayer",
]
