# Status (update after each step)

## Done
- Simulation phase, `evaluate` on sim_v1, full `compare` run (13 models + T8): no eligible model, closest is one-class SVM at 1.2 FA/h. See results/sim_v1/REPORT.md, reports/DECISION_NOTE.md.
- Code added: candidates xgboost, lightgbm, mlp, one_class_svm and T8 (5 seeds) in `model_selection.py`; T8 columns in `dashboard.py`.

## To do
- False-alarm fix (per-session normalisation, longer windows, persistence tuning), timeboxed; rerun `evaluate` and `compare`.

## Known
- results/ and reports/ are tracked (small). datasets/ is gitignored (233 MB); rebuild with the generate commands in README.md.
- Decision tree 0.0 detection is the tied-score artifact described in model_selection.py's docstring, not a real result.
- Hardware items (MAVLink, UBX check, Jetson latency, sim-to-real) wait on recordings.
