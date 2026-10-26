# Decision note v3: model selection with 20 features, and the final test

Simulation only. Supersedes `reports_v2/DECISION_NOTE.md` (19 features, small test set). Selection data: `datasets/sim_fa2` (2210 train / 884 calibration / 1326 validation sessions, about 17 clean validation hours). Config `configs/sim_v2.json` (persistence 10 rows, calibration margin 0.25 FA/h). Features: 20 (the 19 of v2 plus a long-window IMU residual). Selection rule: MODEL_SELECTION.md §6 with the minimum-detection amendment of 2026-10-23. All 13 candidates, T1–T8 run. XGBoost 3.2.0 and LightGBM 4.7.0 were rerun on the project machine and reproduce the earlier numbers exactly.

## Selection

| Model | DR (T1) | FA/h (T2) | DR no strength (T3) | DR weak (T4) | DR unseen (T5) | Delay median / p90 s (T6) | T8 DR ± sd | T8 FA/h ± sd | Eligible |
|---|---|---|---|---|---|---|---|---|---|
| xgboost | 0.992 | 0.06 | 0.913 | 1.000 | 0.976 | 1.564 / 4.782 | 0.990 ± 0.006 | 0.10 ± 0.06 | yes |
| lightgbm | 0.992 | 0.06 | 0.937 | 1.000 | 0.968 | 1.478 / 5.568 | 0.979 ± 0.018 | 0.04 ± 0.03 | yes |
| hist_gradient_boosting | 0.984 | 0.12 | 0.865 | 0.875 | 0.952 | 1.581 / 5.499 | 0.970 ± 0.015 | 0.02 ± 0.05 | yes |
| linear_svm | 0.976 | 0.24 | 0.921 | 1.000 | 0.960 | 1.290 / 5.376 | 0.973 ± 0.004 | 0.17 ± 0.07 | yes |
| mlp | 0.976 | 0.30 | 0.937 | 1.000 | 0.952 | 1.070 / 5.764 | 0.984 ± 0.009 | 0.19 ± 0.17 | yes |
| knn | 0.968 | 0.12 | 0.944 | 1.000 | 0.929 | 1.676 / 3.384 | 0.951 ± 0.015 | 0.12 ± 0.19 | yes |
| one_class_svm | 0.968 | 0.78 | 0.929 | 1.000 | 0.968 | 0.993 / 8.313 | 0.971 ± 0.004 | 0.91 ± 0.11 | yes |
| logistic_regression | 0.960 | 0.12 | 0.929 | 1.000 | 0.960 | 1.234 / 3.100 | 0.965 ± 0.006 | 0.14 ± 0.06 | yes |
| random_forest | 0.944 | 0.18 | 0.905 | 0.625 | 0.905 | 2.201 / 6.088 | 0.933 ± 0.010 | 0.14 ± 0.03 | yes |
| extra_trees | 0.857 | 0.24 | 0.810 | 0.125 | 0.865 | 2.295 / 3.664 | 0.878 ± 0.014 | 0.30 ± 0.14 | yes |
| rbf_svm | 0.405 | 1.20 | 0.952 | 0.375 | 0.333 | 5.885 / 24.570 | 0.379 ± 0.020 | 0.71 ± 0.46 | no |
| isolation_forest | 0.079 | 0.18 | 0.595 | 0.000 | 0.079 | 1.506 / 3.993 | 0.081 ± 0.022 | 0.59 ± 0.24 | no |
| decision_tree | 0.000 | 0.00 | 0.937 | 0.000 | 0.246 | – / – | 0.000 ± 0.000 | 0.00 ± 0.00 | no |

Ten models pass eligibility. Nine are tied on detection and robustness within the 0.05 margin, so step 4 picks the lowest median delay. **Winner by the rule: one-class SVM** (0.99 s; next MLP at 1.07 s). The rule was not changed after seeing these results; it was locked in `configs/locked_model_v3.json` before the test set was opened.

### Cautions about the choice

- The tie-break was decided by 0.08 s, one sample interval. It is not a meaningful difference.
- XGBoost and LightGBM detect more on validation (0.992 vs 0.968) with fewer false alarms (0.06 vs 0.78 per hour) and a better 90th-percentile delay (4.8–5.6 s vs 8.3 s). The rule does not weigh these. They were **not** run on the test set. Choosing one of them instead would need a fresh test dataset, because `sim_test2` has now been used once.
- The one-class SVM has the highest false-alarm rate among eligible models, and over 5 seeds it averages 0.91 ± 0.11 FA/h on validation.

## Final test (opened once for the locked model)

Fitted and calibrated on the sim_fa2 train and calibration splits; scored on `datasets/sim_test2` (new seed; 6000 clean and 1050 attacked sessions, never used for selection or tuning).

| Measure | Result |
|---|---|
| Detection, all attacks | **0.970** (95% CI 0.957–0.978), 7 attack types × 150 sessions |
| False alarms | **0.58 per hour**: 48 events in 83.3 clean hours (exact 95% range 0.42–0.76) |
| Clean sessions with an alarm | 0.7% (of 6000) |
| Median delay / 90th percentile | 1.0 s / 9.1 s |

By attack type: consistent takeover **0.807**; ramp 0.987; step-then-ramp 0.993; dynamic takeover, ramp-then-step, static and step 1.000. Alarms before onset in attacked sessions: 4 events.

**The false-alarm target of 1/h is met, and the whole 95% range (0.42–0.76) is below it.** This replaces the first test (`results/final_test.json`, 19 features, 21 clean hours, range 0.44–1.25).

### Weak spoofers (power 0–1 dB, `datasets/sim_weak`, 420 attacked sessions)

| Measure | Result |
|---|---|
| Detection, all attacks | 0.919 (0.889–0.941) |
| Consistent takeover | **0.533** |
| Ramp | 0.900 |
| Other five types | 1.000 |
| 90th-percentile delay | 12.9 s |

The earlier weak-power figure rested on 8 sessions; this one uses 420. (The false-alarm figure in this file comes from only 1.4 clean hours and is not meaningful; use the sim_test2 figure.)

## What it still fails on

- Weak consistent takeovers: detection 0.53. A consistent takeover with little power keeps velocity and IMU nearly consistent, and the simulated IMU noise hides it.
- Late detections: the 90th-percentile delay is 9 s (13 s for weak spoofers).
- Without signal strength (T3), validation detection is 0.93 for this model.
- Everything is simulated. Clock, sensor and spoofer parameters are assumptions. No bench or flight data yet; the next checks are the Nayfeh public data and the first bench recording (MODEL_SELECTION.md §10, step 7).

## Changes behind the improvement since the first comparison

Larger clean set; persistence 10; calibration margin 0.25/h; features for signed C/N0, satellite drop, HDOP rise, a dead-reckoning residual that ignores short multipath jumps, and a long-window IMU residual; minimum detection in the eligibility rule; `.to_numpy(copy=True)` in `features.py` for pandas 3.0.

## Pre-registered three-model comparison on a fresh test set

Declared in `configs/preregistered_test3.json` and committed before `sim_test3` (seed 6666) was generated or any model scored on it. Same settings, features and training data for all three; nothing tuned afterwards. Test: 6000 clean (83.3 h) and 1050 attacked sessions. Weak: `sim_weak3` (seed 5555, 420 attacked sessions at 0–1 dB).

| | One-class SVM (locked) | XGBoost | LightGBM |
|---|---|---|---|
| Detection | 0.969 (0.956–0.978) | **0.984** (0.974–0.990) | 0.983 (0.973–0.989) |
| False alarms per hour | 0.48 (0.34–0.65), 40 events | **0.12** (0.06–0.22), 10 events | 0.17 (0.09–0.28), 14 events |
| Median delay, s | **0.99** | 1.46 | 1.42 |
| 90th-percentile delay, s | 6.3 | 5.8 | **4.3** |
| Consistent takeover | 0.79 | **0.89** | **0.89** |
| Weak spoofers (0–1 dB), all attacks | 0.938 (0.911–0.957) | 0.945 (0.919–0.963) | **0.957** (0.933–0.973) |
| Weak spoofers, consistent takeover | 0.63 | 0.68 | **0.72** |
| Time per decision, ms | 0.026 | 0.001 | 0.001 |

All three meet the 1/h false-alarm limit on `sim_test3`. (Weak-set false-alarm figures come from 1 clean hour and are not meaningful.)

**Reading.** Both boosted models detect more, raise 3–4 times fewer false alarms (the ranges do not overlap with the one-class SVM's), catch more consistent takeovers, and have a better 90th-percentile delay. The one-class SVM is faster to the first alarm by about 0.4 s in the median. The detection ranges for the three models overlap slightly (0.974–0.978); the false-alarm and consistent-takeover differences are the clearer ones. This supports the earlier validation result that the rule's tie-break (0.08 s) pointed at the less accurate model.

**What this does and does not change.** The locked model stays the one-class SVM, as the rule selected, and its own test result (`sim_test2`: 0.970 detection, 0.58 FA/h) stands. Adopting a boosted model would be a decision made with the help of this comparison, so it would need one more fresh test set (`sim_test3` has now been used to compare them). The v3 consistent-takeover improvement (0.73 to 0.81 for the one-class SVM) is still subject to the caveat that the feature was designed after the v2 test result (see `PROVENANCE.md`).
