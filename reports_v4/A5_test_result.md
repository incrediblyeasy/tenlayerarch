# A5/A6: v4 test result (simulated; opened once)

Locked before the test sets existed: `configs/locked_model_v4.json` (commit d229ad1, 2026-10-27 20:11:53; the test sets were generated after that). Test sets: `sim_v4_test` (7120 sessions: 6000 clean = 83.3 h, 1120 attacked) hash `f9158bccb30cca2d`; `sim_v4_weaktest` (1320 sessions, power 0-1 dB, ordinary attackers) hash `dae37c57d9a1add9`. Each configuration was scored once on each; nothing was rerun or retuned. Platforms: multirotor hover, multirotor maneuver, fixed wing, large slow. Half of the attacked sessions use matched-power attackers (C1) with preserved clock and reproduced ionosphere.

## Main result (v4 world)

| Configuration | Detection (95% CI) | Ordinary / matched-power | Consistent takeover (n=160) | FA/h (upper 95%) | Median / p90 delay (s) | Weak detection | Weak consistent takeover | Weak p90 (s) |
|---|---|---|---|---|---|---|---|---|
| **Primary: ensemble 0.25 LightGBM + 0.75 SVM, persistence 5** | 0.871 (0.851-0.890) | 0.952 / 0.791 | 0.59 | 0.66 (0.86) | 1.0 / 16.2 | 0.849 | 0.49 | 14.9 |
| V1 LightGBM + CUSUM p99 | 0.897 (0.878-0.914) | 0.968 / 0.827 | 0.61 | 0.34 (0.49) | 5.8 / 19.1 | 0.866 | 0.49 | 19.4 |
| V2 temporal (30 s summaries) | 0.878 (0.857-0.896) | 0.955 / 0.800 | 0.59 | 0.24 (0.37) | 2.3 / 16.6 | 0.846 | 0.43 | 16.3 |
| V3 LightGBM, 22 features | 0.904 (0.886-0.920) | 0.961 / 0.848 | 0.44 | 0.36 (0.51) | 2.6 / 16.7 | 0.868 | 0.23 | 17.1 |
| V0 v3 LightGBM (trained on sim_fa2, unchanged) | 0.995 | n/a | 0.97 | **268** (272) | 0.5 / 5.4 | 0.998 | 0.99 | 5.3 |
| V0 v3 one-class SVM (trained on sim_fa2, unchanged) | 0.994 | n/a | 0.97 | **113** (116) | 0.1 / 2.6 | 0.996 | 0.97 | 1.2 |

**Read the V0 rows as broken, not as good.** Detection 0.99 with 113-268 false alarms per hour means the alarm is almost always on. The v3 models use features that assume a level body; the realistic-IMU platforms break them (the C3 finding). The true "before" number on the harder simulator is therefore: the v3 models cannot be used there without retraining. V1-V3 were chosen after seeing validation results and are exploratory; only the primary is the rule-selected configuration.

Per-attack-type detection, primary: static 1.00, step 0.99, step-then-ramp 0.99, ramp-then-step 0.99, ramp 0.86, dynamic takeover 0.67, consistent takeover 0.59.

Per platform, primary (detection / FA per hour): hover 0.88 / 0.43, maneuver 0.89 / 0.77, fixed wing 0.86 / **1.20**, large slow 0.86 / 0.24. The fixed-wing FA is a point estimate from about 21 clean hours; the all-platform upper bound is 0.86/h.

## Targets (`configs/gate_targets_v4.json`, written before any v4 data)

| Target | Primary | Result |
|---|---|---|
| Weak consistent takeover >= 0.85 | 0.49 | **missed** |
| FA upper 95% bound <= 1/h | 0.86 | met overall (fixed-wing alone 1.20 point estimate) |
| p90 delay <= 5 s, full power | 16.2 s | **missed** |
| p90 delay <= 5 s, weak | 14.9 s | **missed** |

No variant meets the weak consistent-takeover or the delay targets either (best weak consistent takeover 0.49; best p90 14.9 s). The v3 gate misses (weak consistent takeover, weak p90) are not closed on the harder world; they are wider.

## What changed in my reading

1. Validation optimism again: the primary's hold-out FA was 0.98/h on validation and 0.66/h on test, so this time the margin held; the spread over platforms (0.24 to 1.20 per hour) shows it is not uniform.
2. Matched-power attackers are the main cost: 0.95 against ordinary attackers, 0.79 against matched ones.
3. Attack types that are not abrupt (ramp, dynamic and consistent takeover) set the detection ceiling; these are detected late or not at all, which is consistent with the long p90 delays; I did not separate delay by attack type, so this is an expectation, not a measurement.
4. Relative to the v3 gate (0.99 detection on the easier world) the headline fall to 0.87 comes from the harder world, not from a worse model; they cannot be compared directly.
5. The validation set (18 consistent-takeover sessions) was too small to separate candidates on consistent takeover: validation promised 0.83 for the primary; the test (n=160) gives 0.59. This is the clearest example of selection noise in this work.

## Not done

C8 (calibration against receiver and IMU specs) and F2/F3 need real data. Phase B (hardware) not started.
