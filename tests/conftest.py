import pytest

from ten_layer_detector.config import DetectorConfig
from ten_layer_detector.sim import generate_mixed_dataset

# Small, fixed-seed dataset shared by the behaviour tests (simulation only).
SMALL = dict(n_clean=60, n_per_attack=15, seed=42)


@pytest.fixture(scope="session")
def small_dataset():
    return generate_mixed_dataset(SMALL["n_clean"], SMALL["n_per_attack"], seed=SMALL["seed"])


@pytest.fixture(scope="session")
def cfg():
    return DetectorConfig()


@pytest.fixture(scope="session")
def protocol_result(small_dataset, cfg):
    from ten_layer_detector.evaluate import evaluate_protocol

    sessions, meta = small_dataset
    return evaluate_protocol(sessions, meta, config=cfg)
