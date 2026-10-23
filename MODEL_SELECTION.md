# Model Selection Plan: Which Algorithm Should Our Detector Use?

## 1. Purpose

Our detector needs one model that decides, for each short window of drone data, whether GPS is clean or spoofed. Several algorithms could do this. This document sets out how we will compare them fairly, which algorithms we will test, and the rule we use to pick the winner.

We are not bound to the models in the four reference papers. The papers are inputs to our design. The choice of model is made here, by measurement, on our own data.

## 2. Ground rules

1. **Choose the model with validation data only.** The test set is opened once, at the end, to report the final number.
2. **Pick the selection rule before running anything.** Section 6 is fixed before the results are seen. Changing it afterwards is not allowed.
3. **Keep the same features for every model.** Only the algorithm changes, so the comparison is fair.
4. **Keep flights together.** All windows from one session go into the same split. Otherwise the model can memorise a flight and look better than it is.
5. **Report uncertainty.** Each result gets a range over several random seeds and over sessions (bootstrap). A difference smaller than the range is treated as a tie.
6. **Do not compare on the easy shortcut alone.** Every model is also tested without the signal-strength (C/N$_0$) and DOP fields (Section 5, test T3), because a spoofer may not raise its power.

## 3. Data

| Source | Use | Notes |
|---|---|---|
| Simulator (`/home/claude/sim_study/`) | Main data for selection | Clean and six attack types. Features built by `features.py`. Splits from `run_study.py`. |
| Public Nayfeh data | Second check only | Real recordings, but only 4 squares and no IMU or clock. Used to see whether the winner also works on real data. |
| Real bench and flight data | Final check (later phase) | Not yet recorded. |

### Splits (simulator)

| Split | Content | Used for |
|---|---|---|
| Train | 120 clean and 150 attacked sessions | Fit each model |
| Validation | 60 clean and 60 attacked sessions, new seeds | Choose algorithm and tune settings |
| Calibration | 60 clean sessions | Set the alarm threshold (99.9th percentile of clean scores) |
| Test | 60 clean and 60 attacked sessions, opened once | Final report |

The simulator generates the sessions. Each session is one trajectory with its own satellites, noise and attack, so sessions are independent.

### Features (current set, nine trailing 5-second features)

posvel, prres, cn0_mean, cn0_spread, dop_h, dop_v, clk_innov, accres, baro_dev. All are receiver-side or sensor-side. True position and velocity are never used as inputs.

## 4. Candidate algorithms

Grouped by type. Each gets a default setting and a small, fixed tuning grid (Section 4.2).

### 4.1 Candidates

| # | Algorithm | Type | Why it is on the list |
|---|---|---|---|
| A1 | Logistic regression | Linear, supervised | Simple baseline. Easy to explain. Very fast. |
| A2 | Decision tree | Tree, supervised | Single-tree baseline. Shows whether ensembles help. |
| A3 | Random forest | Ensemble of trees | Already built in our pipeline. Robust with default settings. |
| A4 | Extra Trees | Ensemble of random trees | Similar to A3, often faster and less prone to overfitting. |
| A5 | Gradient boosting (scikit-learn HistGradientBoosting) | Boosted trees | Strong on tabular data. Built into scikit-learn, no extra install. |
| A6 | XGBoost | Boosted trees | Widely used, often strong on tabular data. |
| A7 | LightGBM | Boosted trees | Fast training and inference. Useful for an onboard computer. |
| A8 | Linear SVM | Linear margin classifier | Strong linear baseline. Needs scaled features. |
| A9 | RBF SVM | Kernel classifier | Can model curved boundaries. Slow on large data. |
| A10 | Small neural network (MLP, 2 hidden layers) | Neural net | Can learn complex patterns. Needs scaling and more data. |
| A11 | k-nearest neighbours | Distance-based | Simple non-parametric baseline. Slow at run time. |
| A12 | Isolation Forest | Unsupervised anomaly | Trained on clean data only. Matches the real case where attacks are rare or unseen. |
| A13 | One-class SVM | Unsupervised anomaly | Second unsupervised option, trained on clean data only. |

Supervised models (A1–A11) learn from clean and attacked sessions. Unsupervised models (A12–A13) learn only from clean sessions and flag anything different. We keep both kinds, because a real drone may meet attacks that were not in the training data.

### 4.2 Tuning grid (fixed before running)

Each supervised model gets a small grid, searched on the validation set only.

| Algorithm | Settings searched |
|---|---|
| A1 Logistic regression | C in {0.01, 0.1, 1, 10} |
| A2 Decision tree | max depth in {4, 8, 12}; min samples leaf in {20, 50, 100} |
| A3 Random forest | trees in {100, 300}; max depth in {8, 12}; min leaf in {20, 50} |
| A4 Extra Trees | same as A3 |
| A5 HistGradientBoosting | learning rate in {0.05, 0.1}; max depth in {3, 6}; iterations in {100, 300} |
| A6 XGBoost | learning rate in {0.05, 0.1}; max depth in {3, 6}; trees in {100, 300} |
| A7 LightGBM | learning rate in {0.05, 0.1}; leaves in {15, 31}; trees in {100, 300} |
| A8 Linear SVM | C in {0.1, 1, 10} |
| A9 RBF SVM | C in {1, 10}; gamma in {scale, 0.1} |
| A10 MLP | hidden sizes in {(32,16), (64,32)}; alpha in {1e-4, 1e-3} |
| A11 kNN | k in {5, 15, 31} |
| A12 Isolation Forest | trees in {100, 300}; contamination fixed by calibration |
| A13 One-class SVM | nu in {0.01, 0.05}; gamma in {scale} |

The number of combinations is small, so the search is cheap. Every model gets the same number of tries.

## 5. Tests

Each candidate goes through the same tests on the validation set. The test set is used only for the final chosen model.

| Test | What it checks | Measure |
|---|---|---|
| T1 Main | Overall detection on the usual attack mix | Detection rate (DR) at the fixed false-alarm target |
| T2 False alarms | Behaviour on clean flights | False alarms per hour on clean validation sessions |
| T3 No strength clue | Does the model still work if C/N$_0$ and DOP are removed? | DR and FAR with those fields removed |
| T4 Weak spoofer | Attacks at 0 to 1 dB power, not seen with normal power in the test | DR and median delay |
| T5 Unseen attack type | Leave one attack type out of training, test on it | DR on the unseen type |
| T6 Delay | Time from attack start to first alarm | Median and 90th-percentile delay |
| T7 Speed | Time to make one decision, on the PC now and on the Jetson later | Milliseconds per decision; model size |
| T8 Stability | Repeat with 5 random seeds | Mean and spread of DR and FAR |

## 6. Selection rule (fixed in advance)

**Step 1: Eligibility.** A model is eligible only if, on the validation set:
- false alarms are at most 1 per hour at the threshold set on calibration data, and
- detection with the strength clue removed (T3) is reported and is not zero, and
- detection on the main test (T1) is at least 0.5.

*Amendment, 2026-10-23:* the 0.5 floor was added after the first full comparison showed a decision tree (0.00 detection) and an Isolation Forest (0.03) passing the original two conditions. It changed no winner: the same model was selected before and after. Results from before this amendment are marked in `reports_v2/DECISION_NOTE.md`.

**Step 2: Main score.** Among eligible models, rank by DR on T1 (validation). Higher is better.

**Step 3: Robustness score.** Rank by the average of DR on T4 (weak spoofer) and T5 (unseen attack). This matters more than the main score, because a model that only works on known attacks at normal power would fail in the field.

**Step 4: Tie rule.** If two models are within the uncertainty range (Section 2, rule 5) on both the main and robustness scores, choose the one with lower delay (T6), then the faster one (T7), then the simpler one.

**Step 5: Lock and test.** The chosen model and its settings are written down. Only then is the test set opened, once, for the final report.

If no model is eligible, the detector does not ship. We report the best failure and go back to the features (Section 8).

## 7. Output of the comparison

For each candidate, one row in a results table:

| Model | Settings | DR (T1) | FAR/h (T2) | DR no strength (T3) | DR weak (T4) | DR unseen (T5) | Delay median (T6) | ms/decision (T7) | Eligible |
|---|---|---|---|---|---|---|---|---|---|

Also a bar chart of the main and robustness scores, and a short note on the winner: why it won, and what it still fails on.

## 8. Expected problems and how we handle them

| Problem | Response |
|---|---|
| All models fail without the strength clue | Expected. The model is not the bottleneck. Work on features (e.g., per-session normalisation, longer windows) and on training with weak-power attacks. |
| A complex model (boosting, MLP) wins by a small margin | Use the tie rule. Prefer the simpler model unless the gap is clearly larger than the uncertainty range. |
| Validation score is much higher than test score | Sign of overfitting or of tuning on noise. Reduce the grid; do not choose the model by the test set. |
| Simulator favours one model | Repeat the top three on the Nayfeh public data (second check) and on the first bench recording when available. |
| Results depend on the threshold | Report DR at a fixed FAR target and show the full trade-off curve for the top three models. |

## 9. Deliverables

1. Script that runs all candidates with the grid above and writes one CSV row per run.
2. Results table and charts (Section 7).
3. One-page decision note: chosen model, settings, the rule that picked it, and its known weak points.
4. Updated detector configuration file that the final software uses.

## 10. Order of work

1. Freeze the feature set and the splits (no changes after this point).
2. Run tests T1, T2 and T3 for all candidates on validation data.
3. Apply the eligibility check and remove ineligible models.
4. Run T4, T5, T6, T7 and T8 for the remaining candidates.
5. Apply the selection rule (Section 6).
6. Open the test set once for the chosen model. Report.
7. Repeat the final check on the Nayfeh public data and, later, on bench data.

## 11. What this plan does not decide

- It does not decide the final features. Feature work is a separate step (Section 8).
- It does not measure on-board speed on the Jetson. That is a later step, once the Jetson is set up.
- It does not decide the alarm logic (how many consecutive alarms make a warning). That is set on calibration data, not here.
