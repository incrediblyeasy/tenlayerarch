# Numbers and caveats for the paper (v3, all simulated)

**Headline model: LightGBM** (adopted 2026-10-26, `configs/adopted_model.json`). Not chosen by the selection rule (which picked the one-class SVM); chosen after the pre-registered tests, and confirmed on a second fresh set. Unbiased estimate (sim_test4): detection 0.991 (0.984-0.995), 0.37 false alarms/h (0.25-0.53), median delay 1.48 s, p90 4.1 s, consistent takeover 0.94, weak spoofers 0.948 (consistent takeover 0.65). Report the one-class SVM numbers below as the rule-selected result.

**Latest (gate test, LightGBM, persistence 5, margin 0.5; `sim_test5`/`sim_weak5`, fresh):** detection 0.994 (0.988-0.997); false alarms 0.72/h (range 0.55-0.93); median / p90 delay 0.94 / 3.2 s; consistent takeover 0.96; weak spoofers 0.950 (consistent takeover **0.687**, p90 delay **13.3 s**). Five of seven measurable gate targets met; the weak consistent-takeover target (0.85) and weak p90-delay target (5 s) are missed and reported as missed. Use these in place of the sim_test4 figures below for the final model settings.

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

## LightGBM confirmation, fresh test `sim_test4` (pre-registered, LightGBM only)
Detection 0.991 (0.984-0.995); FA 0.37/h (0.25-0.53); median / p90 delay 1.48 / 4.1 s; consistent takeover 0.94; weak (0-1 dB) detection 0.948, weak consistent takeover 0.65. (Its sim_test3 false-alarm rate was 0.17/h; quote both, about 0.2-0.4/h.)

## Exploratory (state as such): GNSS-only features
LightGBM without IMU, barometer and Galileo features, on sim_test4 (reused, not unbiased): detection 0.897; consistent and dynamic takeover 0.67; weak spoofers 0.695 (consistent takeover 0.08). Position steps and ramps stay at 0.97-0.99.

## Three statements the paper must make
1. **Feature designed after seeing a test result.** The consistent-takeover weakness appeared in the v2 test (0.733). The long-window IMU feature was designed in response and tried on validation sessions; the v3 test set is a new dataset, but the improvement (to about 0.8) is not a blind prediction.
2. **The selection rule was amended after the first comparison.** A minimum detection of 0.5 was added after a decision tree and an Isolation Forest passed with almost no detection. Applied to both later comparisons, the original and amended rules select the same model.
3. **The model choice was a judgement on a tiny difference.** The one-class SVM won the delay tie-break by 0.08 s (one sample interval). On a fresh pre-registered test the boosted models were better on detection, false alarms, consistent takeover and 90th-percentile delay, and slower by about 0.4 s in median delay. Any claim about "the selected model" should say it was selected by the rule, and that boosted models performed better when tested afterwards (and LightGBM again on a second fresh set).

## Also state
- All results are from simulation; clock, sensor and spoofer parameters are assumptions; no bench or flight data yet.
- Hardware parsers are tested only on synthetic frames; there is no row assembler yet.
- Datasets are rebuilt from seeds (`DATASETS.md`, with content hashes); results are in `reports_v3/`, `results/`.

## v4 harder simulated world (fresh test `sim_v4_test`, opened once; see reports_v4/A5_test_result.md)
Primary (rule-selected, ensemble of LightGBM and one-class SVM): detection 0.871 (0.851-0.890); ordinary attackers 0.952, matched-power attackers 0.791; FA 0.66/h (upper 95% 0.86; fixed-wing alone 1.20); consistent takeover 0.59; weak (0-1 dB) detection 0.849, weak consistent takeover 0.49; median / p90 delay 1.0 / 16.2 s. v4 targets: false-alarm bound met; weak consistent takeover >= 0.85 and p90 <= 5 s missed. Exploratory variants (chosen after seeing validation): CUSUM 0.897, temporal 0.878, all-features 0.904. The v3 models on this world give detection 0.99 with 113-268 FA/h, i.e. they do not work there. State: validation promised consistent takeover 0.83 and the test gave 0.59 (validation set too small, 18 sessions).

## False-alarm variability and the v5 fix attempt (simulated; reports_v5/)
Same primary model, three fresh clean sets: 0.98/h (v4 hold-out, 41.7 h), 0.66/h (v4 test, 83.3 h, upper 95% 0.86), 0.49/h (v5 validation, 55.6 h). Per aircraft type 0.07-1.20/h across sets, with no consistent worst type (fixed wing 1.20 on the v4 test, 0.36 on v5 validation; hover 0.43 and 1.01). False alarms cluster: 55 test events in 38 sessions. Per-type thresholds and a larger calibration set (83 h) did not reduce them on fresh validation (hover 0.94/h in both) and no fix was accepted. Do not cite a per-type false-alarm ranking.
