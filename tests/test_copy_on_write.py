"""Features must work when pandas returns read-only arrays (pandas 3.0 default)."""
import pandas as pd
import pytest

from ten_layer_detector.features import compute_features
from ten_layer_detector.sim import generate_session


@pytest.fixture
def copy_on_write():
    try:
        old = pd.options.mode.copy_on_write
        pd.options.mode.copy_on_write = True
    except Exception:  # pandas 3.0: always on, option removed
        yield
        return
    yield
    pd.options.mode.copy_on_write = old


def test_all_features_compute_under_copy_on_write(copy_on_write):
    frame = generate_session(attack_type="ramp", seed=3)
    out = compute_features(frame)
    assert len(out) == len(frame) and out.notna().all().all()
