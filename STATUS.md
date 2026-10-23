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

## False-alarm fix: DONE
- Causes, fix and numbers: reports_v2/DECISION_NOTE.md. 13-model comparison on datasets/sim_fa2 (reports_v2/). Rule picks one-class SVM; locked in configs/locked_model.json; test set (datasets/sim_test, new seed) opened once: detection 0.960, 0.77 FA/h (16 events, 20.8 h, range 0.44-1.25), delay 0.99 s; consistent takeover 0.73. Results: results/final_test.json.
- Reproduce: generate sim_fa2 (--n-clean 4000 --n-per-attack 60 --seed 4444) and sim_test (--n-clean 1500 --n-per-attack 60 --seed 8888) with configs/sim_v2.json, then `compare ... --workers 6` and `python -m ten_layer_detector.final_test ...` (see final_test.py docstring).

## To do next
- Consistent-takeover detection is the weakest (0.73 on test): longer-window drift / IMU feature.
- Repeat the final check on Nayfeh public data and bench data (needs recordings).
- Rule gap: eligibility has no minimum detection rate (decision tree and Isolation Forest pass with ~0 detection).
- Layers 3 and 7, attack naming (0.79), vote vs layer 10: see earlier notes.
