# Decision note v3: model selection with 20 features, and the final test

> **Update, 2026-10-26: adopted model.** The rule selected the one-class SVM (locked in `configs/locked_model_v3.json`). After the pre-registered tests below, **LightGBM was adopted** (`configs/adopted_model.json`) as a judgement, not by the rule; see the last two sections and `PROVENANCE.md`. Its unbiased test result is on `sim_test4`.

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

## LightGBM confirmation on a second fresh test set

Declared in `configs/preregistered_test4.json` and committed before `sim_test4` (seed 3131) and `sim_weak4` (seed 2121) were generated. LightGBM only, same settings. LightGBM was chosen from `sim_test3` and validation, so this set is what lets a choice of LightGBM rest on data not used to make it.

| | LightGBM, sim_test4 | LightGBM, sim_test3 | One-class SVM, sim_test2 (locked) |
|---|---|---|---|
| Detection | **0.991** (0.984–0.995) | 0.983 | 0.970 |
| False alarms per hour | 0.37 (0.25–0.53), 31 events in 83.3 h | 0.17 (0.09–0.28) | 0.58 (0.42–0.76) |
| Median / 90th-percentile delay, s | 1.48 / 4.1 | 1.42 / 4.3 | 1.0 / 9.1 |
| Consistent takeover | 0.94 | 0.89 | 0.807 |
| Weak spoofers (0–1 dB), all attacks | 0.948 (0.922–0.965) | 0.957 | 0.919 |
| Weak spoofers, consistent takeover | 0.65 | 0.72 | 0.53 |

The 1/h false-alarm limit is met (whole range under 0.53). The false-alarm rate differs between the two fresh sets (0.17 vs 0.37) by more than their ranges suggest, so these two sets are best read together: LightGBM's rate on fresh simulated data is about 0.2–0.4 per hour, below the one-class SVM's 0.5–0.6 on its test sets. Weak consistent takeover remains the weak point for every model (0.53–0.72).

**What this means.** The result from `sim_test3` repeats on a set not used to choose LightGBM: it detects more, raises fewer false alarms, catches more consistent takeovers and has a better 90th-percentile delay than the rule-selected one-class SVM; it is slower to the first alarm by about 0.5 s in the median. The locked model file (`configs/locked_model_v3.json`) still names the one-class SVM, as the rule selected. Switching to LightGBM is a decision for the project owner, and this note and `sim_test3` are the evidence for it. If it is made, it should be reported as a choice made after the pre-registered tests, with this confirmation as support.

## Exploratory: LightGBM with GNSS-only features (not pre-registered)

`configs/sim_v2_gnss_only.json` drops the four features that need an IMU, barometer or Galileo-only solution (`imu_resid_mps2`, `imu_resid_long_mps2`, `baro_resid_m`, `const_diff_m`), as a recording from the GPS module alone would. Retrained on `sim_fa2`, scored on `sim_test4` and `sim_weak4`. **Exploratory only:** it reuses `sim_test4`, which was used for the LightGBM confirmation, so it is not an unbiased estimate and is not for headline numbers.

| | All 20 features (sim_test4) | GNSS-only (sim_test4) | GNSS-only, weak 0–1 dB (sim_weak4) |
|---|---|---|---|
| Detection | 0.991 | 0.897 (0.877–0.914) | 0.695 (0.650–0.737) |
| False alarms per hour | 0.37 | 0.12 (0.06–0.22) | – |
| Median / p90 delay, s | 1.48 / 4.1 | 2.66 / 9.2 | 5.87 / 18.8 |
| Consistent takeover | 0.94 | 0.67 | 0.08 |
| Dynamic takeover | 1.00 | 0.67 | 0.13 |
| Ramp, step, static, ramp-then-step, step-then-ramp | 0.99–1.00 | 0.97–0.99 | 0.90–0.97 |

**Reading.** Without an IMU the detector still catches position steps and ramps, but consistent and dynamic takeovers (velocity kept consistent with the spoofed position) drop to about 0.67 and almost vanish at weak power (0.08–0.13). Those attacks are visible mainly through the IMU. A first recording that includes the flight controller's IMU and barometer is therefore much more useful than a GPS-module-only recording.

## Gate result (REMAINING_WORK.md section 1), read once on `sim_test5` and `sim_weak5`

Targets committed in `configs/gate_targets.json` (`8b9dc33`) before any of this data existed; test plan in `configs/preregistered_test5.json` (`46cab6c`, committed before `sim_test5` was generated). Model: LightGBM with `configs/sim_v3.json` (persistence 5, calibration margin 0.5 FA/h). Test: 6000 clean sessions (83 h) and 1050 attacked sessions; weak set: 150 sessions per attack type at 0–1 dB (1050 attacked).

| Target | Result | Verdict |
|---|---|---|
| Detection, all attacks ≥ 0.95 | 0.994 (0.988–0.997) | Met |
| False alarms per hour, upper 95% bound ≤ 1.0 | 0.72/h, 60 events in 83.3 h, range 0.55–0.93 | Met |
| Consistent takeover, full power ≥ 0.85 | 0.96 (0.92–0.98) | Met |
| Weak spoofers (0–1 dB), all attacks ≥ 0.90 | 0.950 (0.936–0.962) | Met |
| Weak spoofers, consistent takeover ≥ 0.85 | **0.687 (0.61–0.76)** | **Missed** |
| 90th-percentile delay, full power ≤ 5 s | 3.2 s (median 0.94 s) | Met |
| 90th-percentile delay, weak spoofers ≤ 5 s | **13.3 s** | **Missed** |
| Decision time ≤ 10 ms on target hardware | 0.012 ms per decision on the development PC | Not measured on the Jetson |

Five of the seven measurable targets are met; two are missed; one is pending hardware. The two missed targets are reported as missed and the targets are not redefined.

### Why the two weak-power targets are missed

- **Delay is set by the attack, not by the alarm rule.** On the weak validation set, steps and static attacks are caught in a median of 0.7–1.9 s, but ramps take a median of 9 s and ramp-then-step 13.6 s: the detector fires once the position offset has grown beyond the noise, which takes time for a slow ramp. Shorter persistence (5, 3), a longer feature window (10 s) and training on weak-power attacks did not shorten the weak delay; persistence 3 and weak-power training made detection worse.
- **Consistent takeover at weak power** has no signal-strength cue, and the IMU cue is limited by IMU noise. An IMU velocity-drift feature (integrating the IMU since the end of warm-up) was tried and rejected: its value on clean sessions late in the run (median 2.4 m/s) was as large as on attacked ones (3.3 m/s), because IMU noise random-walks when integrated, and adding it lowered weak consistent takeover from 0.66 to 0.24 on validation.
- Both were tuned only on `sim_fa2` validation and `sim_weakval`. A reasonable reading is that, in this simulator, 0.85 for weak consistent takeover and 5 s for weak ramps are not reachable without raising false alarms. Whether to relax these targets for a later round is the owner's decision and would be made before the next test set, with the reason recorded.

### One more thing to note

False alarms on the test set (0.72/h) are higher than on the validation set for the same settings (0.12/h, 2 events in 17 h). The settings were chosen on validation, and the same pattern held in the earlier rounds (validation 0.06/h, test 0.17–0.37/h). Test figures are the honest ones; validation false-alarm figures underestimate. The upper bound on the test set (0.93/h) is under the limit but close to it.
