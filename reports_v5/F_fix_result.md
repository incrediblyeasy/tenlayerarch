# v5: threshold fixes for false alarms (simulated, validation only; test sets not opened)

Plan and rule: `configs/v5_plan.json` (commit 18c6dc7, before any v5 data). Runner: `ten_layer_detector/v5_run.py`. Data: `sim_v5_cal` (6000 clean sessions, 83.3 h, 20.8 h per aircraft type, hash `c6dd390c46f5e15f`) and `sim_v5_val` (4840 sessions, 13.9 clean hours per type, hash `618db6d845eda8bf`). The model is the locked v4 primary scorer, unchanged; only the thresholds differ. Raw output: `results/v5_val.json`.

## Result on fresh validation

False alarm events (rate per hour) per aircraft type, 13.9 clean hours each; detection is over all attacked sessions.

| Arm | Hover | Maneuver | Fixed wing | Large slow | Overall FA/h | Detection | p90 delay (s) | Eligible |
|---|---|---|---|---|---|---|---|---|
| A0 baseline (v4 threshold, 11.1 h calibration) | 14 (1.01) | 3 (0.22) | 5 (0.36) | 5 (0.36) | 0.49 | 0.874 | 15.5 | reference |
| A4 larger calibration (pooled, 83.3 h) | 13 (0.94) | 3 (0.22) | 5 (0.36) | 9 (0.65) | 0.54 | 0.874 | 15.4 | no |
| A1 per-type threshold (20.8 h each) | 13 (0.94) | 1 (0.07) | 2 (0.14) | 5 (0.36) | 0.38 | 0.867 | 16.3 | no |

Choice rule (all four types at most 0.8/h, detection within 0.02 of A0, p90 within 1 s): neither arm qualifies, because hover stays at 0.94/h in both. **By the rule written in advance, nothing was tested on `sim_v5_test`; those sets were not generated. No fix is accepted.**

## What this changes about the diagnosis

1. **The fixed-wing problem did not reproduce.** With the same model and the same baseline threshold, fixed wing had 1.20/h on the v4 test and 0.36/h here; hover went the other way (0.43 to 1.01) and maneuver from 0.77 to 0.22. The exact test in `D_diagnosis.md` (p = 0.0008) picked the worst of four aircraft after the fact and counted events as independent, so it overstated the case. I withdraw "the fixed-wing excess is real"; what holds is that per-type rates vary between clean sets far more than counting noise explains. Pooled over the two sets (34.7 h per type), the baseline rates are fixed wing 0.86, hover 0.66, maneuver 0.55, large slow 0.29 per hour: all in one range, none clearly the problem.
2. **Why the rates swing:** the 55 test events fell in 38 sessions (up to 4 per session); false alarms come in clusters in sessions with nuisance events (satellite drops, HDOP jumps, lock resets, constellation differences, per D2). That makes the counts overdispersed, so the Poisson intervals in the reports understate the real uncertainty. I did not measure the overdispersion directly; this is the explanation consistent with the numbers.
3. **Overall false alarms across three fresh clean sets for the same model:** 0.98/h (v4 hold-out), 0.66/h (v4 test), 0.49/h (v5 validation). The overall target is met on the test but a spread of 0.5 to 1.0 is what a user should expect.
4. **Threshold changes do not help the cluster problem.** Per-type thresholds moved events by single digits in either direction (hover 14 to 13, maneuver 3 to 1, fixed wing 5 to 2, large slow 5, or 9 with the pooled larger calibration), while detection fell 0.007 and p90 rose 0.8 s. These differences are within what the clustering explains and are not evidence for or against per-type thresholds.

## What was not done, and why

- **F2 (motion scaling):** not supported by the diagnosis (D2).
- **F3 (two-check) and F5 (persistence):** the plan allows them only if delay is acceptable. Delay is already 15-16 s at p90 against a 5 s target, so adding delay is not defensible; both are left for a new pre-registration.
- **The v5 test sets were never generated or scored.** `configs/v5_plan.json` seeds 53000 and 54000 stay unused.

## For the paper

State the per-type and overall false-alarm rates with the spread between clean sets (0.49-0.98/h overall; per type 0.07-1.2/h), say that clean-flight false alarms are clustered in nuisance-event sessions, and that threshold tuning by aircraft type did not reduce them on fresh validation. All simulated.
