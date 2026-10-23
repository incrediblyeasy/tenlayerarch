# Decision note v2: model selection after the false-alarm fix

Simulation only. Selection data: `datasets/sim_fa2` (2210 train / 884 calibration / 1326 validation sessions, about 17 clean validation hours). Config `configs/sim_v2.json` (persistence 10 rows, calibration margin 0.25 FA/h). Features: 19, including the five added in this round. All 13 candidates, T1–T8 run.

## Result of the rule (MODEL_SELECTION.md §6)

| Model | DR (T1) | FA/h (T2) | DR no strength (T3) | DR weak (T4) | DR unseen (T5) | Delay s (T6) | T8 DR ± sd | T8 FA/h ± sd | Eligible |
|---|---|---|---|---|---|---|---|---|---|
| lightgbm | 0.984 | 0.06 | 0.865 | 1.000 | 0.968 | 1.445 | 0.975 ± 0.015 | 0.04 ± 0.03 | yes |
| hist_gradient_boosting | 0.976 | 0.12 | 0.881 | 0.875 | 0.921 | 1.564 | 0.968 ± 0.007 | 0.05 ± 0.04 | yes |
| xgboost | 0.976 | 0.00 | 0.905 | 1.000 | 0.960 | 1.573 | 0.975 ± 0.003 | 0.06 ± 0.07 | yes |
| mlp | 0.976 | 0.18 | 0.952 | 1.000 | 0.952 | 1.302 | 0.976 ± 0.005 | 0.20 ± 0.17 | yes |
| knn | 0.968 | 0.12 | 0.913 | 1.000 | 0.921 | 1.669 | 0.956 ± 0.013 | 0.12 ± 0.19 | yes |
| logistic_regression | 0.960 | 0.54 | 0.905 | 1.000 | 0.968 | 1.234 | 0.957 ± 0.008 | 0.29 ± 0.19 | yes |
| linear_svm | 0.960 | 0.30 | 0.913 | 0.875 | 0.968 | 1.320 | 0.963 ± 0.004 | 0.20 ± 0.10 | yes |
| one_class_svm | 0.960 | 0.90 | 0.921 | 1.000 | 0.960 | 0.992 | 0.962 ± 0.006 | 0.94 ± 0.12 | yes |
| random_forest | 0.937 | 0.12 | 0.841 | 0.625 | 0.881 | 2.213 | 0.929 ± 0.021 | 0.25 ± 0.21 | yes |
| extra_trees | 0.857 | 0.36 | 0.794 | 0.125 | 0.849 | 2.149 | 0.860 ± 0.006 | 0.32 ± 0.14 | yes |
| rbf_svm | 0.381 | 1.38 | 0.952 | 0.375 | 0.357 | 5.288 | 0.383 ± 0.011 | 0.85 ± 0.47 | no |
| isolation_forest | 0.032 | 0.54 | 0.492 | 0.000 | 0.032 | 1.506 | 0.071 ± 0.024 | 0.61 ± 0.16 | yes |
| decision_tree | 0.000 | 0.00 | 0.937 | 0.000 | 0.246 | – | 0.000 ± 0.000 | 0.00 ± 0.00 | yes |

Weak-spoofer (T4) uses only 8 sessions, so it is coarse. Speed is under 0.07 ms per decision for every model.

**Winner by the pre-set rule: one-class SVM.** Ten models pass the eligibility step (≤ 1 FA/h with a non-zero no-strength result). Nine of them are tied on detection and robustness within the 0.05 margin, so step 4 breaks the tie by lowest median delay: one-class SVM 0.99 s, against 1.23–1.67 s for the others. The rule was not changed after seeing results.

## Cautions about the choice

- The tie was decided by about 0.25 s of delay. LightGBM has the best detection (0.984), the best robustness and 0.06 FA/h, but a 1.45 s delay. If delay matters less than margin on false alarms, LightGBM is the safer pick; this is a judgement the rule does not make.
- The one-class SVM has the **highest false-alarm rate of the eligible models** (0.90 FA/h; 0.94 ± 0.12 over 5 seeds). It sits right at the 1/h limit; others are at 0.0–0.5.
- Decision tree and Isolation Forest pass eligibility but detect almost nothing (0.00 and 0.03). The eligibility step has no minimum detection rate; this is a gap in the rule and did not affect the winner.
- RBF SVM and kNN: RBF SVM is not eligible (1.38 FA/h) and detects only 0.38.

## Locked and tested (step 5)

Locked in `configs/locked_model.json` (committed before the test run). Fitted and calibrated on the sim_fa2 train and calibration splits, then scored once on `datasets/sim_test` (new seed, 1500 clean + 420 attacked sessions, never used for selection or tuning):

| Measure | Test result |
|---|---|
| Detection, all attacks | 0.960 (95% CI 0.936–0.975), 403 of 420 |
| False alarms | 0.77 per hour: 16 events in 20.8 clean hours (exact 95% range 0.44–1.25) |
| Clean sessions with an alarm | 0.8% (12 of 1500) |
| Median delay | 0.99 s; 90th percentile 9.3 s |
| Time per decision | 0.027 ms |

By attack type: consistent takeover **0.73** (0.61–0.83); ramp 0.98; the other five types 1.00.
Alarms before attack onset in attacked sessions: 4 events.

The false-alarm target is met on the point estimate, but the upper end of the range (1.25/h) is above the limit, so the target is not shown beyond doubt.

## What it still fails on

- Consistent takeover (velocity kept consistent with the spoofed position): 0.73.
- 90th-percentile delay of 9 s: some attacks are found late.
- Everything is simulated. Clock, sensor and spoofer parameters are assumptions; no bench or flight data yet. The next check is the Nayfeh public data and the first bench recording (MODEL_SELECTION.md §10, step 7).
- Without signal strength (T3) detection falls to 0.92 at 0.96 FA/h on validation.

## Changes behind the improvement

Larger clean set (more reliable threshold and measurement), persistence 10, and five features: signed C/N0 rise and fall, satellite drop, HDOP rise, and a dead-reckoning residual that ignores short multipath jumps. Before these, no model was eligible (`reports/DECISION_NOTE.md`).
