# How the results were produced (read this before citing any number)

All numbers are from simulated data. This file records, in order, which decisions were made after seeing which results, so that a reader can judge how much each reported number can be trusted.

## 1. Order of events

| Step | What was done | What had been seen before |
|---|---|---|
| 1 | First protocol run on `sim_v1` and first 13-model comparison on `sim_dev` (`results/sim_v1`, `reports/`). No model passed eligibility. | Nothing from the later rounds. |
| 2 | False-alarm diagnosis. Clean-session alarms were traced to satellite occlusions and multipath jumps. Larger clean set `sim_fa2` created; persistence 10 and calibration margin 0.25 FA/h chosen from a sweep **on the sim_fa / sim_fa2 validation sessions**. | Validation results only. |
| 3 | Five features added (signed C/N0 rise and fall, satellite drop, HDOP rise, dead-reckoning residual), chosen by comparing feature sets **on validation sessions** (`sim_fa`, then `sim_fa2`). | Validation results only. |
| 4 | Eligibility rule amended: detection must be at least 0.5 (see section 2). | The first comparisons, which showed a decision tree and an Isolation Forest passing with almost no detection. |
| 5 | Round v2: 13-model comparison on `sim_fa2` (`reports_v2/`), one-class SVM locked (`configs/locked_model.json`), tested once on `sim_test` (`results/final_test.json`): detection 0.960, 0.77 FA/h (range 0.44-1.25), consistent takeover 0.733. | Validation results. |
| 6 | **A long-window IMU feature was added, aimed at the weak consistent-takeover result.** It was designed after the v2 test result showed that weakness, and tried on validation sessions. | The v2 test result. |
| 7 | Round v3: 13-model comparison with 20 features on `sim_fa2` (`reports_v3/`), one-class SVM locked (`configs/locked_model_v3.json`), tested once on a **new** test set `sim_test2` (seed 9999): detection 0.970, 0.58 FA/h (range 0.42-0.76). Weak-power set `sim_weak` (seed 7777). | Validation results, and the v2 test result (step 6). |
| 8 | Pre-registered three-model test on yet another new test set `sim_test3` (seed 6666), see section 4. `configs/preregistered_test3.json` was committed before that data was generated or any model scored on it. | v3 results. |
| 9 | Pre-registered LightGBM confirmation on a fourth fresh set `sim_test4` (seed 3131), `configs/preregistered_test4.json` committed first (`09b52aa`, 2026-10-26 14:39:32). | The test3 result. |
| 10 | LightGBM adopted as the working model (`configs/adopted_model.json`), after steps 8 and 9. This is a judgement made with the test3 and test4 results in hand, not an outcome of the rule. | The test2, test3 and test4 results. |
| 11 | Gate targets committed (`8b9dc33`, 2026-10-26 16:03:51). Features and alarm settings then tuned on validation only (rejected: IMU drift feature, weak-power training, persistence 3, 10 s window; adopted: persistence 5, margin 0.5). Gate test pre-registered (`46cab6c`, 16:14:31) and read once on `sim_test5` / `sim_weak5`: five targets met, two missed, one pending hardware. | The test2-4 results. |
| 12 | Simulator improvements plan (`SIMULATOR_IMPROVEMENTS.md`). C1 plan committed (`2f49de2`, 2026-10-27 14:55:46) before `sim_default1` / `sim_matched1` were generated; result in `reports_sim/C1_matched_power.md`. C2 plan and module committed (`9571f6d`) before any run. | Gate result. |
| 13 | v4 phase (MODEL_IMPROVEMENT_PLAN.md). B0 reproduce passed (bit-identical). Plan, rules, grid and targets committed (`1e2abbc`) before any v4 data; A2 features (rule keeps the 20 v3 features), A3 decision logic (rule keeps persistence 5), A4 models (rule selects the 0.25 LightGBM + 0.75 SVM ensemble) on validation only (`13e0912`, `d229ad1`); lock committed at 2026-10-27 20:11:53 (`d229ad1`) before `sim_v4_test` / `sim_v4_weaktest` were generated; each configuration scored once. | C1-C7 results; the v3 gate result. Variants V1-V3 were picked after seeing validation numbers (exploratory). |
| 14 | v5 false-alarm fix (FALSE_ALARM_FIX_PLAN.md). Diagnosis D1-D4 (script committed `4a6e724` before running; report `fd00010`), then plan and choice rule committed (`18c6dc7`) before `sim_v5_cal` / `sim_v5_val` existed. Neither threshold arm met the choice rule on fresh validation, so the test sets were not generated. The diagnosis statement about fixed wing was corrected after the validation result. | v4 test result and its per-type false-alarm counts. |
| 15 | Round 2 (FALSE_ALARM_FIX_ROUND2.md). Real-clean nuisance metrics pre-registered (`9b4f328`) then measured (`cdb3f93`); simulator calibration grids pre-registered (`17a8a86`) with one amendment after the first grid showed the position-noise gap (`b4c6030`; the real residual percentiles were looked at after the first grid); arms, choice rule, acceptance (`b135fb0`); lock (`caf2766`) before the test sets were generated; test sets read once. Acceptance criteria 2 and 3 were written relative to the retrained baseline in the plan file but mean the old detector in the plan document; reported against the document's wording. | v4 result, round-1 result. |

What this means for a reader:

- The `sim_test2` set (v3 test) was never used for selection or tuning, but **the feature that raised consistent-takeover detection from 0.73 to 0.81 was designed after seeing the v2 test result.** The improvement is therefore not a blind prediction. The v2 and v3 test sets are different datasets, so the v3 number is not scored on data the feature was tuned on.
- The `sim_fa2` validation sessions were used both to choose settings and to select the model. They are not an unbiased estimate; use the test sets for that.
- The model, persistence, calibration margin and features were all chosen on simulated data with simulated spoofers. Nothing says how they transfer to real receivers.

## 2. The eligibility amendment

The original rule (MODEL_SELECTION.md section 6, step 1) required at most 1 false alarm per hour and a non-zero detection rate without the signal-strength fields. After the first full comparison, a decision tree (detection 0.00, never alarms) and an Isolation Forest (0.03) passed it. A minimum detection of 0.5 was then added. The rule was applied to the earlier tables to check that it changes no selected winner:

| Comparison | Eligible, original rule | Eligible, amended rule | Winner, original rule | Winner, amended rule |
|---|---|---|---|---|
| `reports` (first run) | 0 | 0 | none | none |
| `reports_v2` | 12 | 10 | one-class SVM | one-class SVM |
| `reports_v3` | 12 | 10 | one-class SVM | one-class SVM |

The amendment was added after seeing results, and a reviewer should know that. It removed only models that detect almost nothing, and the winner is the same under both versions.

## 3. The model choice is a judgement on a very small difference

Nine eligible models were tied on detection and robustness within the 0.05 margin, so step 4 of the rule picks the lowest median delay. The one-class SVM won with 0.99 s against 1.07 s for the next model. The difference is below one sample interval (0.1 s).

On validation, XGBoost and LightGBM detect more (0.992 vs 0.968), with fewer false alarms (0.06 vs 0.78 per hour) and a better 90th-percentile delay (4.8-5.6 s vs 8.3 s). The rule does not weigh these. The one-class SVM was locked because the rule said so, and the choice should be reported as a judgement call. Section 4 compares the three models on a fresh test set.

## 4. Pre-registered three-model comparison

See `configs/preregistered_test3.json` and `reports_v3/DECISION_NOTE.md` (results section). All three models are reported whatever the outcome; nothing was tuned after seeing them.

## 5. Evidence that each lock came before its test

Each lock file was committed before the test result was written. Commit times and file modification times (local clock):

| Lock commit | Lock time | Result file written |
|---|---|---|
| `76c7aab` (v2) | 2026-10-23 15:46:09 | `results/final_test.json` 15:48:39 |
| `e9a6949` (v3) | 2026-10-26 11:30:35 | `results/final_test_v3.json` 11:34:08 |
| `5670701` (pre-registration, test3) | 2026-10-26 12:27:58 | `results/prereg_*.json` (written after this commit) |
| `09b52aa` (pre-registration, test4) | 2026-10-26 14:39:32 | `results/prereg4_*.json` (written after this commit) |

`git_history.bundle` in the archive carries the full commit chain (`git log --format='%h %aI %s'`). These are timestamps from a local machine; they are consistent but not independently attested. Pushing the branch to a remote, or quoting the commit hashes in the paper, would give an external record.

## 6. Datasets are not in the archive

They are large (233 MB for `sim_fa2` alone) and are rebuilt deterministically from a seed. Check any rebuilt dataset with `python -m ten_layer_detector.dataset_hash datasets/<name>`; the expected hashes are in `DATASETS.md`.

## 7. Hardware code

The RXM-RAWX decoder, `UBXStream`, `read_serial` and the DataFlash `.bin` reader have been tested on synthetic bytes only. `io/assemble.py` turns decoded messages into detector rows (round-trip tested on synthetic frames only). A real recording will lack some simulator columns, so the model must be retrained on the available columns before real data can be scored.
