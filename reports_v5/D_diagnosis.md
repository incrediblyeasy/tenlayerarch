# D1-D4: why the v4 primary model has more false alarms on fixed wing (simulated)

Script: `ten_layer_detector/v5_diag.py`, committed as 4a6e724 before it ran; output `results/v5_diagnosis.json`. It refits the locked primary configuration on `sim_v4_val` and **reproduces the 55 test false-alarm events exactly** (hover 9, maneuver 16, fixed wing 25, large slow 5), so the analysis is of the real model. Nothing was changed in the locked model.

## D1. Per-type mix (Cause B)

| Aircraft | Calibration clean sessions / hours | Training clean sessions | Hold-out hours | Test hours |
|---|---|---|---|---|
| Hover | 204 / 2.8 | 479 | 10.4 | 20.8 |
| Maneuver | 180 / 2.5 | 526 | 10.4 | 20.8 |
| Fixed wing | 224 / 3.1 | 490 | 10.4 | 20.8 |
| Large slow | 192 / 2.7 | 505 | 10.4 | 20.8 |

The aircraft mix is balanced everywhere, so **a different mix between calibration and test is ruled out as the cause.** What D1 does show is size: the whole calibration set is 11.1 clean hours, 2.5-3.1 hours per type. At the 0.5/h calibration target that allows about 1.3-1.6 false alarm events per type. The plan's proposed 20 clean hours per type is seven times more than exists.

## D2. What the 55 events look like (Cause C)

For each event, the speed, acceleration and turn rate at that moment were compared with 30 randomly chosen non-alarm rows per clean session of the same aircraft type.

- **Motion is ordinary at the alarms.** Median percentile of the event's speed among non-alarm rows: 0.42 (hover), 0.51 (maneuver), 0.54 (fixed wing), 0.42 (large slow); for turn rate 0.64, 0.52, 0.51, 0.48; for acceleration 0.57, 0.43, 0.41, 0.32. None is near the top. **A fast turn or high speed is not what triggers the alarms, so Cause C (features not scaled to motion) is not supported.**
- **The features that stand out are the signal-quality and consistency cues** (median percentile of the event value among non-alarm rows, top six per type): `hdop_change`, `hdop_rise`, `sv_change`, `sv_drop`, `lock_reset` and `const_diff_m` at 0.94-1.00 for every type; plus `implied_accel`/`posvel` for hover and `baro_resid` for large slow. Fixed wing is led by `const_diff_m` (0.998). This matches the simulator's clean-flight nuisances (satellite occlusions, multipath jumps, lock resets), not aircraft dynamics.
- The 55 events fall in 38 sessions (at most 4 events in one session), so some sessions alarm repeatedly.

## D3. Per-type thresholds (Cause A), diagnosis only

Threshold the ensemble score would get from each type's own clean calibration sessions, against the pooled threshold 0.9964:

| Aircraft | Own threshold | Calibration events at pooled threshold | Allowed at target |
|---|---|---|---|
| Hover | 0.9923 | 0 | 1.4 |
| Maneuver | 0.9960 | 1 | 1.2 |
| Fixed wing | **0.9996** | 1 | 1.6 |
| Large slow | 0.9990 | 3 | 1.3 |

Fixed wing would get the highest threshold, which points the way Cause A predicts. But the evidence is too thin to rely on: large slow had the most calibration events (3) and the second-highest own threshold, yet had the fewest events on the test (5). Each own threshold rests on 1.2-1.6 allowed events. So **a per-type threshold from today's calibration data would be mostly noise; it is untested, not refuted.**

## D4. Sample size (Cause D)

| Aircraft | Test events / hours | Rate per hour (95% interval) |
|---|---|---|
| Hover | 9 / 20.8 | 0.43 (0.20-0.82) |
| Maneuver | 16 / 20.8 | 0.77 (0.44-1.25) |
| Fixed wing | 25 / 20.8 | 1.20 (0.78-1.77) |
| Large slow | 5 / 20.8 | 0.24 (0.08-0.56) |

Pooled over the three others the rate is 0.48/h (30 events in 62.5 h). Fixed wing against them, one-sided exact test: **p = 0.0008.** The fixed-wing excess is not a small-sample accident in this test set. Fixed wing against maneuver alone is not distinguishable (overlapping intervals). Note the interval uses the 20.8 hours the test actually has; the plan's "about 21 hours" is right, and its true uncertainty is wide (0.78-1.77).

## Verdict on the four causes

| Cause | Verdict |
|---|---|
| A one threshold for all aircraft | Direction supported by D3, but not testable with 2.5-3.1 h calibration per type |
| B calibration mix differs | Ruled out (balanced); calibration is too small instead |
| C features not scaled to motion | Not supported (events occur at ordinary speed, acceleration and turn rate) |
| D small sample | Rejected as the explanation of the fixed-wing excess (p = 0.0008); calibration size remains a problem |

## Consequence for the fixes

- F2 (motion scaling) has no support from D2. It will not be tested; the reason is recorded here.
- F4 (larger, balanced clean calibration) is needed before F1 can even be tried: 20.8 h per type means 1500 clean sessions per type. F1 and F4 are therefore run together, with F4 alone (pooled threshold from the larger set) as a separate arm so the two effects can be told apart.
- The events are driven by signal-quality and consistency cues, so if a per-type threshold is not enough, the next place to look is how those cues are treated for fixed wing, not motion scaling. That is a hypothesis, not a finding.
