# Simulation Phase: Changes Required to Complete

Reviewed: upload `03b93c86-10_Layer_archi.zip`. Its Python code is identical to the previous upload. The only addition is `PHASE0_HARDWARE_INVENTORY.md`. The 11 tests pass, but none of them tests detection.

Separate study: `/home/claude/sim_study/` (generator, features, runner, `RESULTS.md`). It is not in the package and is not connected to the layers.

## 1. Status against the simulation phases

| Phase | Requirement | Status |
|---|---|---|
| 1. Simulator | One generator, physics-consistent attacks, clean sessions, per-session variation | Not complete. Two generators exist. The package's pipeline, CLI and protocol use the old one. The canonical generator (`sim/generate.py`) has an attack-independent clock and a constant-velocity takeover that is not checked for consistency. |
| 1. Simulator | Attacks that change each signal the layers read | Partly. C/N0 and pseudorange change. The clock does not. Velocity-position consistency for takeovers is not tested. |
| 2. Layers on simulation | Each layer reads canonical columns, fails loudly when inputs are missing, and is measured on clean and attacked sessions | Not complete. Layers 1 to 3 read canonical columns. Layers 4 to 10 still read legacy names and raise `KeyError`. Layers 1 to 3 do not separate clean from attacked sessions. |
| 2. Layers on simulation | Per-row, causal scores | Not complete. Each layer returns one number per session. |
| 2. Layers on simulation | Calibrated, fitted on clean training data | Not complete. Layers have hand-set thresholds and are not fitted. |
| 2. Vote | Logistic regression on out-of-fold percentiles, attack naming | Not complete. `weighted_vote` is a plain average and is never called. |
| 2. Evaluation | Disjoint calibration, training and test sessions; detection rate, false alarms per hour, delay | Not complete. Clean sessions are used for both calibration and false-alarm measurement. The protocol runs on the old simulator. The session count is doubled. |
| 2. Evaluation | Ablation, shortcut check, low-power test, leave-one-attack-out | Done only in `sim_study/`, not in the package. |
| 2. Reproducibility | Same seed gives same results; frozen config | Not complete. No config file. |

## 2. Changes required, in order

### 2.1 One simulator

1. Make `sim/generate.py` the only generator. Remove `simulator.py` and update the CLI, the protocol, `pipeline.py` and the tests to import it.
2. Port the physical model from `/home/claude/sim_study/sim.py`:
   - smooth 3D trajectory with random parameters per session;
   - 10 satellites with elevation and azimuth; pseudoranges from the reported position and the receiver clock;
   - C/N0 raised by a per-session spoofer power, which can be near 0 dB;
   - IMU with bias and noise; barometer with bias and drift.
3. Make the attacks change the signals the layers read:
   - clock: the spoofer couples into the receiver clock for at least one attack family, or the time-domain layer is reported as untestable on the simulator;
   - `consistent_takeover`: the reported velocity is the derivative of the spoofed position (check: maximum difference below 0.1 m/s);
   - `dynamic_takeover`: physically plausible acceleration (check: below the airframe limit).
4. Add a clean class and reject onset times outside the session. This is already done in `sim/generate.py`; keep it.
5. Acceptance: each attack type changes at least one signal by more than the clean session-to-session spread. Otherwise it is reported as undetectable from that signal.

### 2.2 Layers read canonical columns

6. Rename each layer's inputs to the canonical schema:
   - layer 4: `gnss_lat`, `gnss_lon` to two GNSS solutions, or reported as not evaluated;
   - layer 5: `gnss_lat`, `imu_ax` to `rp_*`, `rv_*`, `imu_*`;
   - layer 6: `imu_ax`, `baro_alt` to `imu_*`, `baro`;
   - layer 7: `pseudorange_m` to `pr_*`, or reported as not evaluated;
   - layer 8: `gnss_lat` to features from layers 2, 3, 5, 6;
   - layer 9: `timestamp`, `gnss_lat` to `clk_ns`;
   - layer 10: to the features in layers 2 to 8.
7. Replace each `score` with a per-row, causal function (trailing window only). Remove the single-number-per-session interface.
8. Fit each layer on clean training sessions only (the `fit` method, not `calibrate` on test data).
9. Thresholds: 99.9th percentile of clean calibration rows, frozen before testing.

### 2.3 Vote and attack naming

10. Replace `weighted_vote` with the designed vote: logistic regression on standardised out-of-fold percentiles, fitted on training sessions, threshold at the 99.9th percentile of clean out-of-fold votes.
11. Add an equal-weight baseline and report it.
12. Attack naming: fit the rule on training sessions and test it on held-out sessions. Report the confusion matrix. Do not report it until tested.

### 2.4 Evaluation

13. Split disjointly: training (fit), calibration (thresholds), test (report). A session appears in one set only.
14. Compute detection rate per attack type with a 95% interval, false alarms per hour on held-out clean sessions, and median and 90th-percentile delay.
15. Count sessions correctly. Report the number of clean hours and attacked sessions per type.
16. Missing inputs raise an error. Remove the `except KeyError: continue` in the protocol.
17. Run the ablation (remove each layer), the shortcut check (each feature alone, and without C/N0), and the low-power test (spoofer power 0 to 1 dB).
18. Leave-one-attack-out is reported with the caveat that all attacks raise C/N0 in the simulator. It tests generalisation across shapes only.
19. Minimum counts: at least 50 test sessions per attack type before any rate is reported as a result. Ten per type is a pilot.

### 2.5 Reproducibility

20. Put all settings in one versioned config file: simulator parameters, split seeds, window lengths, thresholds, persistence count.
21. Write `results/summary.csv`, `results/ablation.csv`, `results/shortcut.csv`, `results/negative.md` and `results/config_frozen.json` (see `IMPLEMENTATION_GUIDE.md`, Section 10).
22. The same seed must give the same session, scores and metrics. Add a test for this.

### 2.6 Tests

23. Replace shape tests with behaviour tests:
   - clean sessions produce no alarm from any layer at the frozen threshold, over at least 20 seeds;
   - each attack type is detected by at least one layer it should affect, on at least 90% of seeds;
   - missing inputs raise;
   - split: no overlap, both classes present, a single session raises;
   - causality: changing later samples does not change earlier scores;
   - reproducibility.

### 2.7 Documentation

24. Replace "complete simulation-ready project shell" in the README with an accurate status: which layers run on the simulator, which do not, and why.

## 3. Results from `sim_study/` to carry into the package

These are simulation results only, with the limits stated in `RESULTS.md`.

- Main random forest (all features): 0.85 detection, 0.52 false alarms per hour (test: 60 clean, 60 attacked sessions).
- Without C/N0 and DOP, IMU plus barometer: 0.52 detection, 5.2 false alarms per hour. Without C/N0, the GNSS-internal checks alone detect about 10%.
- At 0 to 1 dB spoofer power: 0.27 detection with all features.
- A constant-velocity takeover is invisible to the position-velocity and IMU checks.

These results do not establish that the layered detector works. They show what the simulated data supports, and they are the baseline the package should reproduce.

## 4. Acceptance: simulation phase is complete when

- One simulator, used everywhere. Its attacks are checked (item 5).
- Every layer runs on canonical columns, fails loudly on missing input, and has a per-row causal score.
- The vote is fitted on training sessions and beats the best single layer on held-out sessions, or the report says it does not.
- Evaluation uses disjoint sessions, reports per-type detection with intervals, false alarms per hour, delay, and the ablation, shortcut and low-power tests.
- Results are reproducible from a seed and a frozen config.
- The README and documents describe only what is implemented.
