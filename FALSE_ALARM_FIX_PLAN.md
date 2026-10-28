# False Alarm Fix Plan (v5)

Goal: lower false alarms on clean flights, especially on fixed-wing aircraft, without losing detection of spoofing. This is a new phase. The v4 results stay as they are and are reported unchanged.

## 1. The problem

On the v4 test set (simulated, opened once), the locked primary model (0.25 LightGBM + 0.75 one-class SVM, persistence 5) gave:

- **55 false alarm events** over 6,000 clean flights (83.3 clean hours).
- Per aircraft type (about 1,500 clean flights each, inferred from equal clean hours of 20.8 h each):
  - Hovering multirotor: 9 events, 0.43 per hour
  - Maneuvering multirotor: 16 events, 0.77 per hour
  - Fixed wing: 25 events, 1.20 per hour (about 21 clean hours; a noisy estimate)
  - Large slow aircraft: 5 events, 0.24 per hour
- The upper 95% bound on the whole set is 0.86 per hour, so the overall target (at most 1 per hour) is met. Fixed wing is the weak spot.
- Validation false-alarm rate was 0.98 per hour; test was 0.66 per hour. The gap shows the rate depends on which clean flights are used.
- A conformal (statistically bounded) threshold gave 2.1 per hour on held-out clean flights. The report names the cause: distribution shift between calibration and held-out clean sessions.

Source files: `reports_v4/A5_test_result.md`, `reports_v4/A2_A3_features_and_decision.md`, `reports_v4/A4_model_candidates.md`, `results/v4_test.json`.

## 2. Suspected causes (not yet confirmed)

**Cause A: one threshold for all aircraft.** The alarm line is set once, from clean calibration flights pooled across all four types (`v4_study.py`, the threshold set around lines 202 to 212, using `metrics.fa_target_threshold`). Fixed-wing flights are fast (15 to 30 m/s) and swing widely (side-to-side swings of 50 to 200 m). Their normal motion can look unusual against a line drawn for the whole mix. This would explain why fixed wing has the most false alarms.

**Cause B: calibration does not match new clean flights.** The calibration set may have a different mix of aircraft types, or different motion, from the test set. The conformal result is evidence for this. We have not checked the per-type mix of the calibration split (`splits.py`, `split_three_way`).

**Cause C: the features are not scaled to the aircraft's motion.** Residuals (differences between GNSS and inertial or barometric estimates) grow with speed and acceleration. A fast turn can produce a large residual with no spoofing present.

**Cause D: small sample.** Fixed wing rests on about 21 clean hours. Its false-alarm rate could be off by a wide margin.

## 3. Diagnosis (do first, no changes to the model)

Each step is a read-only analysis. None of them changes the locked model.

**D1. Per-type mix of calibration and held-out sets.** Count sessions and clean hours per aircraft type in `sim_v4_val` (calibration part) and in `sim_v4_fahold`. Confirms or rules out Cause B.

**D2. Event-level false-alarm analysis.** For each of the 55 false-alarm events on the test set, record the 20 feature values in the window that triggered the alarm, and the aircraft's speed, acceleration and turn rate at that moment. Compare with the same features on clean non-alarm windows of the same type. Confirms or rules out Cause C.

**D3. Threshold by type.** For each aircraft type, compute the threshold that would give the target false-alarm rate on that type's own clean calibration flights. Report how far each type's threshold is from the pooled one. Large gaps support Cause A.

**D4. Sample size.** Compute the confidence interval for each type's false-alarm rate. Shows whether the fixed-wing figure is distinguishable from the others.

Write D1 to D4 results to `reports_v5/D_diagnosis.md`, with the commit hash of the scripts used.

## 4. Candidate fixes

Each candidate is tested on a fresh calibration set and a fresh test set. Choose the fix from validation data only.

**F1. Per-type threshold.** Each aircraft type gets its own alarm line, set from its own clean calibration flights, using the same target rule as today. The drone knows its airframe, so it can pick the right line at run time. Expected to help if Cause A is confirmed. Needs enough clean calibration hours per type (proposal: at least 20 hours per type).

**F2. Motion-scaled features.** Divide each residual by a motion scale, such as the aircraft's typical speed or acceleration for its type (taken from the platform settings in `sim/realism.py`), so that fast flights and slow flights are measured on the same scale. Expected to help if Cause C is confirmed. Larger change: needs the feature code and tests updated.

**F3. Two-check confirmation.** An alarm requires two independent checks to agree (for example, the GNSS-consistency score and the inertial score both above their own thresholds). Expected to cut false alarms, but may add delay, which is already our weakest number (16.2 s at p90 on v4). Must report the delay trade-off.

**F4. Larger calibration set.** Enlarge the clean calibration set, balanced across types, so each threshold rests on enough data. Does not fix a cause, but reduces the risk of a bad threshold from small samples. Can be combined with F1 or F2.

**F5. Stronger persistence.** Increase the persistence count from 5. Simple, but adds delay directly. Only as a last resort.

Recommended order: finish D1 to D4, then test F1 alone. If fixed wing is still above target, test F2 and F4 together. Test F3 only if delay is acceptable.

## 5. Rules (apply to every step)

1. **Pre-register before running.** Each new configuration is written to `configs/` and committed before any run that produces results. Commit hash goes in the report.
2. **Fresh sets.** Calibration and test sets are new seeds. The v4 test set (`sim_v4_test`, hash `f9158bccb30cca2d`) and the hold-out set (`sim_v4_fahold`) are not reused for choosing a fix.
3. **Choose on validation only.** A fix is chosen from validation results, with a rule written before the run.
4. **Report everything.** Every fix tried, including ones that fail, goes in the report with its false-alarm count, detection and delay.
5. **Targets do not move.** The false-alarm target (upper 95% bound at most 1 per hour), the detection targets and the delay targets stay as in `configs/gate_targets_v4.json`. Any new target is written before the run.
6. **Label results.** All results are labelled simulated.

## 6. Acceptance criteria

A fix is accepted only if, on the fresh test set:

- The upper 95% false-alarm bound is at most 1 per hour for every aircraft type, not only overall. Fixed wing is the critical case.
- Detection of the full attack mix does not fall by more than a margin written in advance (proposal: 0.02).
- Delay does not get worse by more than a margin written in advance (proposal: 1 s at p90).
- The change is explained by the diagnosis in section 3, not by a lucky split.

If no fix meets all four, the report says so, and the paper states the per-type false-alarm rates as they are.

## 7. Code locations

| File | Relevance |
|---|---|
| `ten_layer_detector/v4_study.py` | Threshold set from pooled calibration (around lines 202 to 220). F1 and F4 change this. |
| `ten_layer_detector/metrics.py` | `fa_target_threshold` and the false-alarm counting. |
| `ten_layer_detector/splits.py` | `split_three_way`. D1 checks the per-type mix here. |
| `ten_layer_detector/features.py` | F2 changes the residual scaling. |
| `ten_layer_detector/sim/realism.py` | `PLATFORMS` holds the per-type speed and motion settings. F2 uses them. |
| `ten_layer_detector/v4_test.py` | Test runner. Used for the new fresh test. |
| `configs/locked_model_v4.json` | Stays unchanged. The new locked file is `locked_model_v5.json`. |

Each code change has a unit test. Existing tests must still pass.

## 8. Order of work

1. D1 per-type mix of calibration and held-out sets.
2. D2 event-level analysis of the 55 false alarms.
3. D3 per-type thresholds, diagnosis only.
4. D4 confidence intervals per type.
5. Write `reports_v5/D_diagnosis.md` and decide which candidate fix to test.
6. Pre-register the chosen fix in `configs/`, commit.
7. Generate fresh calibration and test sets, record hashes in `DATASETS.md`.
8. Lock the fix on validation, then run the fresh test once.
9. Report against the acceptance criteria in section 6.

## 9. Risks

- **Overfitting the fix to the simulator.** A per-type threshold works only if the simulator's type-specific motion resembles real aircraft. Real-flight checks are needed before trusting it.
- **Delay trade-off.** F3 and F5 can lower false alarms by slowing detection, and delay is already weak.
- **Small fixed-wing sample.** Even a good fix may need more clean fixed-wing hours to show the bound is met with confidence.
- **Changing the target.** It is tempting to relax the 1 per hour target. That is not allowed under these rules.
