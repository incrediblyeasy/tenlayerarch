Round 2 (2026-10-28, reports_v5/R2_diagnosis.md and R2_result.md): real clean recordings (12 Nayfeh flights) show the simulator's clean nuisances were 3-9 times too active (H1 holds); simulator recalibrated (configs/sim_v5.json); retraining the same recipe in it gives 0.07 FA/h (upper 95% 0.16, every type <= 0.19) against 0.91 for the old model scored there, but detection 0.719 vs 0.854 and p90 20.1 s vs 16.3 s, so the fix is not accepted as a no-loss fix by the plan's own criteria. Flag gate and explained-cue features did not help enough; gate blind window on reset-timed attacks costs 0.007. v4 targets for weak consistent takeover and delay still missed.

v5 false-alarm fix (2026-10-28): diagnosis (reports_v5/D_diagnosis.md) found balanced calibration mix, ordinary motion at the alarms, and calibration too small (11 h); threshold-only fixes (larger calibration, per-type thresholds) were pre-registered and tried on fresh validation (reports_v5/F_fix_result.md): neither passed the choice rule (hover stays at 0.94/h), so no fix is accepted and the v5 test sets were not opened. The v4 fixed-wing excess did not reproduce on fresh data (0.36/h vs 1.20/h); false alarms cluster in nuisance-event sessions and overall FA ranged 0.49-0.98/h over three fresh clean sets.

v4 phase (MODEL_IMPROVEMENT_PLAN.md) Phase A DONE (2026-10-27): B0 reproduced exactly; C3-C7 report in reports_sim/C3_C7_world_study.md; A2-A4 on validation (reports_v4/A2_A3_features_and_decision.md, A4_model_candidates.md); rule-selected primary = 0.25 LightGBM + 0.75 one-class SVM ensemble on the 20 v3 features, persistence 5; locked in configs/locked_model_v4.json before the test sets were generated. Fresh simulated test (reports_v4/A5_test_result.md): detection 0.871, FA 0.66/h (upper 95% 0.86), consistent takeover 0.59, weak consistent takeover 0.49, p90 delay 16.2 s (weak 14.9 s). v4 targets: FA met; weak consistent takeover (0.85), p90 <= 5 s (full and weak) missed. The v3 models are unusable on the v4 world (113-268 FA/h). Phase B (hardware) not started; needs approvals, Jetson, recordings.

# Status (update after each step)

Simulator improvements (SIMULATOR_IMPROVEMENTS.md): C1 matched power DONE (reports_sim/C1_matched_power.md: full detector 0.989 -> 0.898, consistent takeover 0.93 -> 0.35; no-strength detector 0.969). C2 adaptive attacker DONE (reports_sim/C2_adaptive_attacker.md: careful consistent takeover goes undetected >= 50 m in 64% of worlds, >= 100 m in 25%). Next in order: C3 realistic IMU, then C4 ionosphere, C5 clock, C6 multipath, C7 platforms, C8 calibration (needs bench data).

Gate result (2026-10-26, LightGBM, configs/sim_v3.json, fresh sim_test5/sim_weak5): 5 of 7 measurable targets met; missed: weak consistent takeover 0.687 (target 0.85) and weak p90 delay 13.3 s (target 5 s); decision time pending Jetson. See reports_v3/DECISION_NOTE.md (gate section) and configs/gate_targets.json.

Adopted model: LightGBM (configs/adopted_model.json), chosen after pre-registered tests; the selection rule picked the one-class SVM (configs/locked_model_v3.json). Both are reported.

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

- Exploratory GNSS-only LightGBM (configs/sim_v2_gnss_only.json, sim_test4): detection 0.897, consistent/dynamic takeover 0.67, weak 0.695 (consistent 0.08). IMU is what catches takeovers; record with the flight controller. Details in reports_v3/DECISION_NOTE.md.

## To do next
- Weak consistent takeovers (0.53) and late detections (p90 9 s) are the main detector gaps.
- (Decided) LightGBM adopted in configs/adopted_model.json; one-class SVM remains the rule-selected result.
- Repeat the final check on Nayfeh public data and bench data (needs recordings).
- Layers 3 and 7, attack naming (0.79), vote vs layer 10: see earlier notes.

- Hardware readers (RXM-RAWX, NAV-DOP, UBXStream/read_serial, DataFlash .bin) and the row assembler (io/assemble.py: UBX epochs -> detector rows; DataFlash IMU/ATT/BARO merge by clock offset) exist; round-trip tested on synthetic frames only. A real recording will have fewer columns than the simulator (no Galileo-only solution, maybe no IMU), so the model must be retrained on the simulated data restricted to those columns before it can score real data.
