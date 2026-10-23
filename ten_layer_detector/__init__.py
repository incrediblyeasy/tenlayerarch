"""Ten-layer GNSS spoofing detector (simulation phase)."""

from .bench_latency import measure_latency, pipeline_latency
from .config import DEFAULT_CONFIG, DetectorConfig, ProjectConfig
from .dataset import SessionDataset, load_sessions, save_sessions
from .evaluate import evaluate_protocol
from .layers import ALL_LAYERS, BaseLayer, LayerResult, MissingInputError, evaluate_layers, make_layers
from .model_selection import MODEL_CANDIDATES, evaluate_model_candidates, select_model
from .pipeline import TenLayerDetector, evaluate_dataset, evaluate_session, summarize_results
from .sim import ATTACK_TYPES, generate_dataset, generate_mixed_dataset, generate_session
from .splits import split_sessions, split_three_way
from .vote import AttackNamer, EqualWeightVote, LogisticVote, weighted_vote

split_sessions_by_session = split_sessions

__all__ = [
    "ATTACK_TYPES",
    "generate_session",
    "generate_dataset",
    "generate_mixed_dataset",
    "TenLayerDetector",
    "evaluate_session",
    "evaluate_dataset",
    "summarize_results",
    "evaluate_protocol",
    "split_sessions",
    "split_sessions_by_session",
    "split_three_way",
    "LogisticVote",
    "EqualWeightVote",
    "AttackNamer",
    "weighted_vote",
    "measure_latency",
    "pipeline_latency",
    "SessionDataset",
    "save_sessions",
    "load_sessions",
    "BaseLayer",
    "LayerResult",
    "MissingInputError",
    "ALL_LAYERS",
    "make_layers",
    "evaluate_layers",
    "MODEL_CANDIDATES",
    "evaluate_model_candidates",
    "select_model",
    "DEFAULT_CONFIG",
    "DetectorConfig",
    "ProjectConfig",
]
