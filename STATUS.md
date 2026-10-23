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
- Cause: clean-session false alarms mostly come from satellite-occlusion events (hdop_change) and multipath jumps; they last 3-15 s so persistence alone cannot fix them. The old 5-hour validation set could not measure FA/h (1 event = 0.2/h).
- Done: bigger clean set (datasets/sim_fa2: 4000 clean, ~17 clean h validation); configs/sim_v2.json (persistence_k 10, calibration margin 0.25/h).
- Done: 5 new features in features.py (cn0_rise_db, cn0_fall_db, sv_drop, hdop_rise, dead_reckoning_m) + tests/test_new_features.py. On sim_fa2 (old -> all features): logistic regression DR 0.913 -> 0.960, FA/h 1.38 -> 0.54; one-class SVM DR 0.897 -> 0.960, FA/h 0.96 -> 0.90. Both under the 1/h limit with the new features.
- Running: full `compare` (13 models, T1-T8) with the new features -> reports_v2/ (log results_compare_v2.log, ~1.5-2.5 h, no partial saves). If interrupted rerun:
  `.venv/bin/python -m ten_layer_detector.cli --config configs/sim_v2.json compare --data datasets/sim_fa2 --out reports_v2`
- After it finishes: write reports_v2/DECISION_NOTE.md, apply MODEL_SELECTION.md section 6, lock the winner, open the test set once (not yet done), rebuild the zip.

## To do next
- Consistent-takeover detection is still the weakest (0.78): longer-window drift / IMU feature.
- Layers 3 and 7, attack naming (0.79), vote vs layer 10: see earlier notes.
