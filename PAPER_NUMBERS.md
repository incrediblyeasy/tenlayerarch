# Numbers and caveats for the paper (v3, all simulated)

Replace the v2 figures (19 features, 0.960 detection, 0.77 FA/h, twelve eligible models) with these.

## Setup
20 features; persistence 10 rows (1 s); calibration margin 0.25 FA/h; fitted and calibrated on `sim_fa2` (2210 train, 884 calibration sessions). Ten of 13 candidate models pass the eligibility rule (at most 1 FA/h, non-zero detection without signal strength, detection at least 0.5).

## Locked model (rule-selected): one-class SVM, test `sim_test2` (6000 clean, 1050 attacked sessions)
- Detection 0.970 (95% CI 0.957-0.978); false alarms 0.58 per hour, 48 events in 83.3 clean hours (exact range 0.42-0.76); median delay 1.0 s, 90th percentile 9.1 s.
- By type: consistent takeover 0.807; ramp 0.987; step-then-ramp 0.993; the other four 1.000.
- Weak spoofers (0-1 dB, `sim_weak`, 420 sessions): 0.919 overall; consistent takeover 0.533; ramp 0.900.

## Pre-registered comparison, fresh test `sim_test3`
| | One-class SVM | XGBoost | LightGBM |
|---|---|---|---|
| Detection | 0.969 | 0.984 | 0.983 |
| FA/h (range) | 0.48 (0.34-0.65) | 0.12 (0.06-0.22) | 0.17 (0.09-0.28) |
| Median / p90 delay s | 0.99 / 6.3 | 1.46 / 5.8 | 1.42 / 4.3 |
| Consistent takeover | 0.79 | 0.89 | 0.89 |
| Weak (0-1 dB) detection | 0.938 | 0.945 | 0.957 |

## Three statements the paper must make
1. **Feature designed after seeing a test result.** The consistent-takeover weakness appeared in the v2 test (0.733). The long-window IMU feature was designed in response and tried on validation sessions; the v3 test set is a new dataset, but the improvement (to about 0.8) is not a blind prediction.
2. **The selection rule was amended after the first comparison.** A minimum detection of 0.5 was added after a decision tree and an Isolation Forest passed with almost no detection. Applied to both later comparisons, the original and amended rules select the same model.
3. **The model choice was a judgement on a tiny difference.** The one-class SVM won the delay tie-break by 0.08 s (one sample interval). On a fresh pre-registered test the boosted models were better on detection, false alarms, consistent takeover and 90th-percentile delay, and slower by about 0.4 s in median delay. Any claim about "the selected model" should say it was selected by the rule, and that boosted models performed better when tested afterwards.

## Also state
- All results are from simulation; clock, sensor and spoofer parameters are assumptions; no bench or flight data yet.
- Hardware parsers are tested only on synthetic frames; there is no row assembler yet.
- Datasets are rebuilt from seeds (`DATASETS.md`, with content hashes); results are in `reports_v3/`, `results/`.
