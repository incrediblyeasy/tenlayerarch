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

## False-alarm fix (in progress)
- Cause found: clean-session false alarms come mostly from satellite-occlusion events (hdop_change feature) and multipath jumps; they last 3-15 s, so persistence alone cannot remove them. The old 5-hour validation set was too small to measure FA/h (1 event = 0.2/h).
- Fix tried: bigger clean set (datasets/sim_fa2: 4000 clean, ~17 clean hours validation), persistence_k 10, calibration margin 0.25/h. Picked from a sweep on validation (one-class SVM: DR 0.897, FA 0.96/h). Config: configs/sim_v2.json. sim_v1/sim_dev results stay as the "before".
- Running: `compare` on sim_fa2 -> reports_v2/ (log: results_compare_v2.log). Long (hours?). If interrupted rerun:
  `.venv/bin/python -m ten_layer_detector.cli --config configs/sim_v2.json compare --data datasets/sim_fa2 --out reports_v2`
- After it finishes: write reports_v2/DECISION_NOTE.md, rebuild zip.
