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
