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

## Current result (v3): DONE
- 20 features, 13-model comparison on datasets/sim_fa2 (reports_v3/). Rule picks one-class SVM (tie-break by 0.08 s delay; XGBoost/LightGBM look better on validation but were not tested). Locked in configs/locked_model_v3.json, then tested once on datasets/sim_test2 (6000 clean + 1050 attacked): detection 0.970, 0.58 FA/h (range 0.42-0.76, under the 1/h target), delay 1.0 s (p90 9.1 s); consistent takeover 0.807. Weak spoofers (sim_weak, 420 sessions): 0.919, consistent takeover 0.533. Note: reports_v3/DECISION_NOTE.md. Earlier v2 (19 features) and its test are kept as the "before".
- Code fixes done: pandas 3 copy-on-write (features.py, test), eligibility minimum detection 0.5 (amendment in MODEL_SELECTION.md), XGBoost/LightGBM rerun reproduces.
- Reproduce: generate sim_fa2 (--n-clean 4000 --n-per-attack 60 --seed 4444), sim_test2 (--n-clean 6000 --n-per-attack 150 --seed 9999), sim_weak (--n-clean 100 --n-per-attack 60 --seed 7777 --power-range 0 1) with configs/sim_v2.json; `compare ... --out reports_v3 --workers 6`; `python -m ten_layer_detector.final_test` (docstring).

## Pre-registered three-model test (done)
- sim_test3 (fresh): one-class SVM 0.969 / 0.48 FA/h / consistent takeover 0.79; XGBoost 0.984 / 0.12 / 0.89; LightGBM 0.983 / 0.17 / 0.89. Boosted models better except median delay (1.4 vs 1.0 s). Locked model unchanged (one-class SVM); adopting a boosted one needs one more fresh test set. See reports_v3/DECISION_NOTE.md, PROVENANCE.md, PAPER_NUMBERS.md, DATASETS.md.

- LightGBM confirmation on sim_test4 (fresh, pre-registered): detection 0.991, 0.37 FA/h (0.25-0.53), p90 4.1 s, consistent takeover 0.94, weak 0.948. Supports switching to LightGBM; locked file still says one-class SVM until the owner decides.

## To do next
- Weak consistent takeovers (0.53) and late detections (p90 9 s) are the main detector gaps.
- Decide: keep the one-class SVM (rule) or adopt LightGBM/XGBoost (better on the pre-registered test); adopting needs one more fresh test set.
- Repeat the final check on Nayfeh public data and bench data (needs recordings).
- Layers 3 and 7, attack naming (0.79), vote vs layer 10: see earlier notes.

- Hardware readers (RXM-RAWX, NAV-DOP, UBXStream/read_serial, DataFlash .bin) and the row assembler (io/assemble.py: UBX epochs -> detector rows; DataFlash IMU/ATT/BARO merge by clock offset) exist; round-trip tested on synthetic frames only. A real recording will have fewer columns than the simulator (no Galileo-only solution, maybe no IMU), so the model must be retrained on the simulated data restricted to those columns before it can score real data.
