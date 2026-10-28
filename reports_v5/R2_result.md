# Round 2 result (simulated world calibrated to real clean data; tests opened once)

Steps and files: Step 1 `R2_diagnosis.md` (real clean recordings, commit cdb3f93 pre-registered 9b4f328); Step 2 `configs/sim_v5.json` (calibration plans committed 17a8a86 and b4c6030 before their runs); arms and rule `configs/round2_plan.json` (b135fb0); lock `configs/locked_model_r2.json` (caf2766, 15:08:10) before the test sets were generated (they were written after that). Test sets: `sim_r2_test` (7120 sessions, 83.3 clean hours, hash `2917ef6fd711fccf`), `sim_r2_weaktest` (1320, `3c215d163f000177`), `sim_r2_resettest` (1120 attacked sessions, every attacker resets the lock at onset, `b194c99dd5293428`). Validation sets: `sim_r2_val` `dbb850779ae3e0b8`, `sim_r2_weakval` `83e4e900284e59f4`, `sim_r2_fahold` `2cfdf2c045c527b4`.

## What was decided

- H1 (simulator artifact) held: real clean flights show about 2 satellite-count drops and 1 HDOP jump per minute; the simulator showed 14 and 10.
- Step 2 calibrated the simulator's satellite flicker, HDOP and position-jump rates to the real intervals (`sim_v5.json`). Still unmatched: large HDOP jumps (0.55 per minute against 0.09 real), the 1 s position/velocity residual (about 15 times real), lock-reset rates (no real flag).
- Step 3/4 on validation: the baseline recipe retrained in the new world already had at most 0.19 false alarms per hour for every aircraft type on the fresh clean hold-out; the flag gate and explained-cue arms did not lower the maximum by the 0.1 the rule required (R3 was worse), so **no detector change was chosen** and Step 4 was not triggered.

## Test result (chosen configuration R1 = baseline recipe retrained in the new world; R0 = the old locked v4 primary scored unchanged; R2 = flag gate, exploratory)

False alarm events (rate per hour) on 20.8 clean hours per aircraft type:

| | Hover | Maneuver | Fixed wing | Large slow | Overall FA/h (upper 95%) |
|---|---|---|---|---|---|
| R0 old primary | 22 (1.06) | 16 (0.77) | 31 (1.49) | 7 (0.34) | 0.91 (1.14) |
| **R1 chosen** | 4 (0.19) | 0 (0.00) | 2 (0.10) | 0 (0.00) | **0.07 (0.16)** |
| R2 5 s flag gate (exploratory) | 4 (0.19) | 0 | 0 | 0 | 0.05 (0.12) |

| Main test | Detection (95% CI) | Consistent takeover | Median / p90 delay (s) | Reset-timed attackers inside this set |
|---|---|---|---|---|
| R0 | 0.854 (0.833-0.874) | 0.48 | 1.0 / 16.3 | 0.864 |
| **R1** | **0.719 (0.692-0.744)** | 0.22 | 5.3 / 20.1 | 0.738 |
| R2 | 0.710 (0.683-0.736) | 0.21 | 5.4 / 20.3 | 0.722 |

Weak (0-1 dB) test: R0 detection 0.842, consistent takeover 0.44, p90 15.8 s; R1 0.729, consistent takeover 0.20, p90 19.6 s; R2 0.713, 0.14, 20.6 s. Weak clean hours are only 2.8, so false-alarm figures there are not informative (upper bounds 1.3-2.6 per hour).

Attacks that reset the receiver lock at onset (`sim_r2_resettest`, 1120 sessions): R0 0.863, R1 **0.742**, R2 gate **0.735**. The 5 s hold costs 0.007 detection on reset-timed attacks and 0.009 on the main test; this is the blind window the plan asked to be measured, and in this simulator it is small. Not tested: an attack that starts a few seconds before a natural reset.

Per attack type, R1 (main test): static 1.00, step 0.94, ramp-then-step 0.88, step-then-ramp 0.82, ramp 0.77, dynamic takeover 0.41, consistent takeover 0.22.

## Against the acceptance criteria

Section 5 of `FALSE_ALARM_FIX_ROUND2.md` has four criteria. The first is met; the second and third are not under the document's own wording.

1. Every aircraft type at or below 0.8 false alarms per hour: **met** (R1: 0.19, 0.00, 0.10, 0.00). The old model does not meet it in this world (hover 1.06, fixed wing 1.49).
2. Detection falls by no more than 0.02: **not met** against the current detector (R0 0.854, R1 0.719; minus 0.135).
3. p90 delay no worse than the current detector's by more than 1 s: **not met** (16.3 s to 20.1 s, plus 3.8 s).
4. Reset-timed attacks reported separately: done (above).

A correction to my own pre-registration: `configs/round2_plan.json` wrote criteria 2 and 3 relative to R1 (the retrained baseline), which makes them true by construction for the chosen arm. The plan document means the current detector, which is R0. I flagged this before opening the test; I am reporting against the document's wording, so **the fix is not accepted as a no-loss fix**: it removes the false alarms and pays with detection and delay.

## What this says

1. **The false-alarm problem is not solved by the simulator calibration alone.** The old model, unchanged, has 0.91 per hour in the calibrated world (0.66 in the v4 world), and fixed wing is its highest type again (1.49). What lowered false alarms was retraining and recalibrating inside the calibrated world: 76 events fell to 6 over 83.3 hours. Hence false-alarm behaviour depends on calibrating in conditions that match the deployment; a threshold set in a noisier or different environment does not transfer.
2. **The reduction comes with a large unused false-alarm budget and a detection loss.** R1 runs at 0.07 per hour against a 0.5 calibration target and a 1.0 limit, and detects 0.72 where the old model detected 0.85. Part of that is the threshold: R1's calibrated threshold sits at 0.99964 on the rank scale, above the old one (0.99643). I did not retune it (no silent retuning); a pre-registered recalibration that spends more of the budget is the obvious next experiment, and it would move false alarms toward the limit.
3. **Per-type claims.** Across the four clean sets where R0 was scored (v4 test, round-1 validation, round-2 validation and test), fixed wing had the highest rate in three (1.20, 1.25, 1.49; hover in the fourth). The pairwise differences with hover and maneuver are not established; with large slow they are. Round 1's statement that no type is consistently worst should be softened to "fixed wing was highest in three of four sets, not significantly so against hover and maneuver".
4. **The simulator is now calibrated on three nuisance families against 12 flights at one open-sky site.** Its clean false-alarm rates are valid for sites like that, not for urban or noisy environments, which the v4 world represents better. Report both.
5. The v4 targets are still missed: weak consistent takeover 0.20 (target 0.85) and p90 delay about 20 s (target 5 s).

## For the paper

Clean-flight false alarms of the old model: 0.66 to 1.5 per hour depending on aircraft type and environment; after matching the simulator's nuisance rates to real recordings and recalibrating, 0.07 per hour (upper 95% 0.16) with detection 0.72 against 0.85 before; the cost, and the fact that the calibration source is one site, must be stated. All numbers are simulated; the nuisance rates come from real clean data.
