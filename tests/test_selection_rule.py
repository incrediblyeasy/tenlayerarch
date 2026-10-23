from ten_layer_detector.model_selection import is_eligible, select_model


def _row(name, dr, fa=0.5, ns=0.8, weak=0.8, unseen=0.8, delay=1.0):
    return {"model_name": name, "dr_validation": dr, "far_per_hour": fa, "dr_no_strength": ns, "dr_weak": weak,
            "dr_unseen": unseen, "delay_median_s": delay, "ms_per_decision": 0.01}


def test_model_that_detects_almost_nothing_is_not_eligible():
    assert not is_eligible(_row("tree", dr=0.0, fa=0.0, ns=0.9))
    assert not is_eligible(_row("iforest", dr=0.03, fa=0.5, ns=0.5))


def test_false_alarm_limit_and_no_strength_still_apply():
    assert is_eligible(_row("ok", dr=0.9))
    assert not is_eligible(_row("noisy", dr=0.9, fa=1.5))
    assert not is_eligible(_row("shortcut", dr=0.9, ns=0.0))


def test_degenerate_model_cannot_win():
    rows = [_row("tree", dr=0.0, fa=0.0, delay=0.1), _row("real", dr=0.9, delay=2.0)]
    assert select_model(rows) == "real"
    assert select_model([_row("tree", dr=0.0, fa=0.0)]) is None
