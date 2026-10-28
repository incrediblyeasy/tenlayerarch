# False Alarm Fix, Round 2

Replaces the fix candidates in `FALSE_ALARM_FIX_PLAN.md`. Round 1 is closed; its results are reported as they are.

## 1. Where things stand

Round 1 (diagnosis and two threshold fixes, fresh validation, simulated):

| Arm | Hover | Maneuver | Fixed wing | Large slow | Overall FA/h | Detection |
|---|---|---|---|---|---|---|
| Current threshold | 1.01 | 0.22 | 0.36 | 0.36 | 0.49 | 0.874 |
| Larger calibration | 0.94 | 0.22 | 0.36 | 0.65 | 0.54 | 0.874 |
| Per-type thresholds | 0.94 | 0.07 | 0.14 | 0.36 | 0.38 | 0.867 |

Rates are false alarms per hour of clean flight. Neither arm met the rule (every type at or below 0.8 per hour). p90 delay stayed at 15 to 16 s.

Findings from the diagnosis:

- The calibration mix across aircraft types is balanced, so a mix mismatch is not the cause.
- Speed, acceleration and turn rate are ordinary at the alarm moments, so motion scaling is not the cause.
- Calibration was small (about 3 clean hours per type). Larger calibration did not fix hover.
- Alarms are driven by signal-quality and consistency cues: HDOP, satellite count, and lock resets. The clean-flight nuisances in the simulator make these cues jump.

Corrections to earlier statements:

- The fixed-wing problem did not reproduce: 1.20 per hour on the v4 test, 0.36 on fresh validation. Hover went the other way (0.43 to 1.01). The earlier claim that the fixed-wing excess was real is withdrawn.
- Alarms cluster: the 55 v4 events fell in 38 sessions. Counting them as independent overstated the evidence.
- Overall false alarms ranged from 0.49 to 0.98 per hour across three fresh clean sets. Do not rank aircraft types.

## 2. Working hypothesis

The false alarms come from benign jumps in signal-quality cues during clean flight: satellite drops, HDOP changes, and receiver lock resets. Two possibilities:

- **H1, simulator artifact.** The simulator makes these jumps more often or larger than real receivers do.
- **H2, detector sensitivity.** The detector reads ordinary jumps as suspicious, even if the simulator is realistic.

Round 2 tests H1 first, because it is a measurement and it decides whether the rest of the work is needed.

## 3. Steps

### Step 1: Measure the nuisances in real clean recordings (no model change)

Use the public clean recordings (see `PUBLIC_DATASET_PLAN.md` and `PUBLIC_DATASET_CANDIDATES.md`). They have GNSS measurements but no IMU, so only GNSS-side nuisances can be measured.

Measure, per minute of clean recording:

- Satellite count change (drops and rises), and the size of each change.
- HDOP jump size and frequency.
- Lock resets or cycle slips, where the data flags them. If not flagged, use a jump in pseudorange residual as a proxy and say so.

Report the rates with confidence intervals and the source of each number. Pre-register the metrics in `configs/nuisance_measure_v5.json` before running.

Decision after Step 1:

- If real rates are close to the simulator's, H1 is rejected. Go to Step 3.
- If the simulator is much more active than real data, H1 holds. Go to Step 2.

### Step 2: Calibrate the simulator's clean nuisances to the real rates (only if H1 holds)

- Set the simulator's satellite-drop, HDOP-jump and lock-reset rates to the Step 1 values.
- Commit the new config as `configs/sim_v5.json` before generating any data.
- Keep the old simulator config. Report results on both.
- Generate fresh calibration and validation sets with new seeds. Record hashes in `DATASETS.md`.

### Step 3: Make the detector reset-aware (H2)

Two parts, tested separately:

- **3a. Flag-based gate.** When the receiver flags a reset or lock loss, suppress the signal-quality and consistency alarms for a short hold period (N seconds, with N chosen on validation). The hold is the only new rule.
- **3b. Explained-cue feature.** Add a feature that checks whether a satellite or HDOP change coincides with a flagged event. The model can then learn that an explained jump is ordinary.

Trade-off to measure: a hold period is a window where a spoof could hide. Test attacks timed to start shortly before or during a reset, and report the detection loss.

### Step 4: Retune the threshold only if still needed

If Step 3 is not enough, rerun the threshold work with a larger clean calibration set, balanced across types. This is the same test as round 1, now on the reset-aware detector.

## 4. Rules (apply to every step)

1. **Pre-register.** Each config is committed to `configs/` before the run that produces its results. The commit hash goes in the report.
2. **Fresh data.** Calibration and validation sets use new seeds. The v4 test set (`sim_v4_test`, hash `f9158bccb30cca2d`) is not used for choosing anything, and nor are the round-1 validation sets.
3. **Choose on validation only.** Each fix is chosen from validation results, using a rule written before the run.
4. **Report every arm.** Failed arms are reported with their numbers.
5. **Targets stay as they are.** False-alarm rule from round 1: every aircraft type at or below 0.8 per hour, measured on fresh clean sets. Detection and delay targets from `configs/gate_targets_v4.json`.
6. **Label results.** Simulated, real clean, or real spoofed, kept separate.

## 5. Acceptance criteria

A fix is accepted only if, on a fresh test set:

- Every aircraft type is at or below 0.8 false alarms per hour.
- Detection does not fall by more than a margin written in advance (proposal: 0.02).
- p90 delay does not get worse than the current detector's delay, by more than a margin written in advance (proposal: 1 s).
- Attacks timed around receiver resets are reported separately, with their detection.

If Step 1 shows the real rates match the simulator, the fix is in the detector (Step 3), and the paper must say so.

## 6. Code locations

| File | Relevance |
|---|---|
| `ten_layer_detector/sim/gnss_model.py`, `sim/realism.py` | Clean-flight nuisance settings. Step 2 changes these. |
| `ten_layer_detector/features.py` | Signal-quality features. Step 3 changes these. |
| `ten_layer_detector/io/ubx.py` | Reads receiver flags. Needed for Step 3a on real data. |
| `ten_layer_detector/v4_study.py` | Threshold and alarm rule (persistence and hold). Step 3a adds the hold here. |
| `ten_layer_detector/io/nayfeh_loader.py` | Public clean recordings for Step 1. |
| `ten_layer_detector/metrics.py` | False-alarm counts. |

Each change has a unit test. Existing tests must still pass.

## 7. Order of work

1. Step 1: measure nuisance rates on public clean recordings. Pre-register first.
2. Decide H1 or H2 from Step 1 and record it in `reports_v5/R2_diagnosis.md`.
3. If H1: Step 2, new simulator config, fresh data.
4. Step 3a, then 3b, on validation only. Pick one.
5. Step 4 only if needed.
6. One fresh test, locked configuration, report against section 5.

## 8. Risks

- **Reset-timed attacks.** The hold in Step 3a can create a blind window. Must be measured, not assumed.
- **Real data is small.** Few clean recordings may not pin down the rates. Report intervals wide.
- **Flags may be missing.** If the receiver doesn't flag resets in the public data, Step 1 uses a proxy, and Step 3a can't be tested on that data.
- **Overfitting the simulator again.** Two threshold rounds have already failed. Keep the number of arms small and pre-registered.
