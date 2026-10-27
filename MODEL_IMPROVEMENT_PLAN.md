# Model Improvement Plan (v4): Simulation First, Then Hardware

Goal: make the GNSS spoofing detector as good as we can on simulated data, then test it on hardware. This is a new phase. The v3 results stay as they are and are reported unchanged, including the two gate misses.

## 0. Rules (apply to every step)

1. **Pre-register before running.** Each step writes its plan, grid, rule and targets to `configs/` and commits them before any run that produces results. Commit hash goes into the step's report.
2. **Fresh test sets.** Every new comparison uses a new seed and a new test set. The v3 test sets (`sim_test2`, `sim_test3`, `sim_test4`, `sim_weak3`, `sim_weak4`) are never reused for selection.
3. **Validation only for choices.** Models, features, thresholds and settings are chosen on `sim_fa2`-style validation data. A test set is opened once per locked configuration.
4. **No retuning of targets.** The gate targets in `configs/gate_targets.json` are not changed. New targets, if any, go in a new file (`configs/gate_targets_v4.json`) and are written before the run.
5. **Report everything.** Every variant tried is reported, including those that fail. The consistent-takeover weak-power result is reported in every table.
6. **Label simulated results.** Every number from the simulator is labelled "simulated". Hardware numbers are labelled separately.
7. **Simulator changes are versioned.** A simulator change creates a new config (`sim_v4.json`). Results from `sim_v3` and earlier are never mixed with `sim_v4` in one table without a note.

## 1. Baseline (frozen)

- Model candidates: one-class SVM (locked, `locked_model_v3.json`), LightGBM (adopted, `adopted_model.json`).
- Baseline numbers come from `PAPER_NUMBERS.md`:
  - LightGBM, `sim_test4`: detection 0.991, FA 0.37/h, median/p90 delay 1.48/4.1 s, consistent takeover 0.94, weak 0.948, weak consistent 0.65.
  - One-class SVM, `sim_test2`: detection 0.970, FA 0.58/h, consistent takeover 0.807, weak 0.919, weak consistent 0.533.
- Known gate misses: weak consistent takeover (0.687 gate run, target 0.85), weak p90 delay (13.3 s, target 5 s).

**Step B0 (reproduce).** Rebuild `sim_test4` and `sim_fa2` with the commands in `DATASETS.md`, check hashes against the table, and rerun `final_test.py` on the locked configs. Output must match `reports_v3/` to the printed precision. If it doesn't, stop and fix the pipeline before any new work.

## 2. Phase A: Simulation

### A1. Simulator realism (do first, because it changes the test)

Improvements from `SIMULATOR_IMPROVEMENTS.md` that affect how hard the problem is. Each is a separate config change, committed before generation.

- **C1 matched power and geometry.** The attacker matches the authentic signal power and satellite geometry. This is the case behind the consistent-takeover weakness.
- **C2 adaptive attacker.** The attacker tunes its offset to stay under the detector's visible cues, using only information a real attacker could get (satellite positions, approximate receiver position).
- **C3 realistic IMU.** Bias, scale factor, random walk and temperature drift, with grades for consumer MEMS and tactical IMU.
- **C4 ionosphere term.** Adds a code-carrier divergence from ionosphere delay, so the code-carrier check has real signal.
- **C5 spoofer changes clock.** The spoofer's fake clock bias and drift are visible in the clock layer.
- **C6 multipath.** Adds multipath on the authentic signals, so clean flights are noisier and the false-alarm test is harder.
- **C7 platform variety.** Several airframes (multirotor, fixed wing), speeds and manoeuvres.
- **C8 calibration.** Shows the simulator's noise levels against published receiver specs.

**Step A1 targets (pre-registered):** none. The purpose is to make the simulator harder and more realistic. Report the v3 models on the new simulator before any retraining. This gives the "before" number on the harder simulator.

### A2. New information (features)

These add evidence the attacker does not control or that the current features miss. Each one is built, unit-tested on synthetic data, and then evaluated on validation sessions only.

- **F1 code-carrier divergence** (needs C4). Uses `code_carrier_m` already present in layer 7.
- **F2 pseudorange-ephemeris consistency.** Checks each pseudorange against the satellite position from the broadcast ephemeris. Not built yet.
- **F3 AGC feature.** From u-blox `MON-HW` (agcCnt), if the module firmware provides it. Hardware-only, so sim version is a simple model of gain changes.
- **F4 long-window IMU drift.** Already in the feature set. Re-tune its window only on validation sessions.
- **F5 barometer-GNSS altitude check.** Already in the feature set. Check its behaviour under C3 IMU and temperature drift.
- **F6 Allan deviation (layer 9).** Currently not tested. Evaluate on validation sessions with the C3 IMU model.
- **F7 multi-constellation consistency (layer 4).** Currently not tested. Evaluate only if the sim generates Galileo and GPS together with independent errors.

**Step A2 rule:** a feature enters the model only if it improves validation detection on consistent takeover and weak-power validation sessions by a margin set in advance (proposal: at least 0.03), and does not raise validation false alarms above 1 per hour. The margin is written in `configs/feature_rule_v4.json` before the run.

### A3. Decision logic (scores to alarm)

- **D1 CUSUM on scores.** A sequential test on the model score, with the reference value and decision threshold chosen on validation clean data. Targets the 90th-percentile delay. Pre-register the average run length on clean data (proposal: at least 1 hour between false alarms in expectation).
- **D2 persistence grid.** Compare the 10-row rule with CUSUM and with a short rule. Validation only.
- **D3 conformal threshold.** Set the threshold so that the false-alarm rate on clean calibration sessions has a stated bound. Use MAPIE or a direct implementation. Compare with the current 99.9th-percentile rule.

### A4. Model candidates

- **M1 current models** (one-class SVM, LightGBM), retrained on the v4 features.
- **M2 ensemble.** Calibrated average of the SVM and LightGBM scores. Weight chosen on validation only.
- **M3 temporal model.** A small temporal convolutional network or GRU over a 30-second feature history. Trained on `sim_fa2`-style train data, with early stopping on validation. Size limit: inference under 10 ms on the Jetson (checked in Phase B).
- **M4 autoencoder.** Trained on clean sessions only; reconstruction error as the score. Optional, run only if M1–M3 leave a gap.
- **M5 hybrid.** EKF innovation (GNSS minus IMU/baro prediction) as an input feature for LightGBM.

Keep the existing grids from `MODEL_SELECTION.md` for M1. For M2–M5, write the grid into `configs/model_grid_v4.json` before running.

### A5. Selection and test

1. Run the grid on validation data only. Record every run.
2. Apply the selection rule from `MODEL_SELECTION.md` section 6, with one addition: weak consistent takeover on validation counts in the robustness score. The rule is written in `configs/selection_rule_v4.json` before the run.
3. Lock the chosen configuration (`configs/locked_model_v4.json`), with a commit hash.
4. Generate a fresh test set with a new seed (`sim_test5` or a new name, with its hash in `DATASETS.md`).
5. Open the test set once. Report detection, false alarms per session and per hour (count and rate), delay median and p90, consistent takeover, weak power, weak consistent takeover, with confidence intervals.
6. If a target is missed, report the miss. Do not rerun the same test set.

### A6. Targets

Keep the v3 targets (`gate_targets.json`) as they are. Also report, in `configs/gate_targets_v4.json` written before the test:

- weak consistent takeover: at least 0.85 (unchanged target, may be missed)
- false alarms: at most 1 per hour, measured as an upper 95% bound
- p90 delay: at most 5 s (full power and weak)

## 3. Phase B: Hardware

Hardware work starts only after Phase A's test is reported. It does not reuse simulated test data.

### Safety and approval (apply to every step)

- No over-the-air GNSS transmission. Spoof tests are conducted through attenuators, a combiner, or a shielded enclosure only.
- Written institutional approval and a WPC (India) check before any transmit test.
- Props off for all Cube Orange tests.
- The vehicle is not flown without written approval.

### B1. Prerequisites

- Phase 0 inventory: confirm the u-blox module model and firmware, and that it outputs NAV-PVT, NAV-CLOCK, NAV-SAT, NAV-DOP and RXM-RAWX. Record which are available.
- Confirm the Jetson Orin Nano is set up with the software stack.
- Confirm that the parsers (`io/ubx.py`, `io/assemble.py`) decode real frames, not only synthetic ones. Any mismatch is fixed and retested before any data is collected.

### B2. Decision latency on the Jetson

- Run `bench_latency.py` on the Jetson with the locked model. Target: decision time at most 10 ms, measured over at least 1,000 windows, reported as median and 99th percentile.
- If the target is missed, the model is simplified before Phase B continues. Do not change the target.

### B3. Real data collection

- **Static recordings:** GNSS module on a bench, authentic signals only. Used to measure the false-alarm rate on real clean data. Target: no more than the Phase A false-alarm rate, checked with confidence intervals.
- **Replay recordings:** use RTL-SDR (receive-only) to record real signals, then replay them through the detector. Spoofed replays are generated only through the approved setup in the safety section.
- **HackRF:** conducted tests only, with attenuators or a shielded enclosure.

### B4. Simulation-to-hardware check

- Run the locked Phase A model on the hardware data without retraining.
- Report the drop in each metric against the simulated result.
- Retrain only if a new rule was pre-registered for hardware data, using a separate split. Do not tune on the hardware test data.

### B5. Public data check (optional)

- Run the locked model on the Nayfeh public recordings, using the GNSS-only features, which those recordings support. Report as a separate result.

## 4. Code work list

| File | Work |
|---|---|
| `ten_layer_detector/sim/generate.py` | C1, C2, C4, C5, C6, C7 |
| `ten_layer_detector/sim/sensors.py` | C3 IMU model, F5 barometer drift |
| `ten_layer_detector/sim/gnss_model.py` | ionosphere term (C4), multipath (C6) |
| `ten_layer_detector/sim/attacks.py` | C1 matched power, C2 adaptive attacker |
| `ten_layer_detector/features.py` | F1, F2 inputs, F3 input, F4 window setting |
| `ten_layer_detector/layers/l04_multiconst.py` | F7 |
| `ten_layer_detector/layers/l09_allan.py` | F6 |
| `ten_layer_detector/layers/l08_temporal.py` | M3 input windows |
| `ten_layer_detector/layers/l10_learned.py` | M1, M2, M4 |
| `ten_layer_detector/vote.py` | D1 CUSUM, D2 persistence grid |
| `ten_layer_detector/model_selection.py` | selection rule v4 (A5) |
| `ten_layer_detector/evaluate.py`, `final_test.py` | confidence intervals, count reporting, one-time test |
| `ten_layer_detector/io/ubx.py`, `io/assemble.py` | real-frame checks (B1) |
| `ten_layer_detector/bench_latency.py` | B2 on the Jetson |
| `configs/` | every new config committed before its run |
| `DATASETS.md` | new datasets, commands and hashes |

Each code change has a unit test. Existing tests must still pass (`pytest`).

## 5. Definition of done

**Simulation:** the locked v4 configuration is reported on a fresh test set, with all variants, counts, confidence intervals and every missed target. The reproduction check from B0 still passes.

**Hardware:** the Jetson decision time is measured against the 10 ms target, real-data false-alarm rate is reported, and the simulation-to-hardware drop is reported. All results are labelled by source (simulated, bench, replay).

## 6. Risks

- **Simulator overfitting.** Improvements may only fit our simulator. Mitigation: C3, C6 and C7 add variety, and the hardware check in B4 tests transfer.
- **Post-hoc changes.** Adding features or models after seeing weak-power results repeats the earlier process concern. Mitigation: every change is pre-registered and a fresh test set is used.
- **Data size.** A few thousand sessions may be too few for deep models. Mitigation: M3 and M4 are optional and must beat M1 on validation before they are tested.
- **Latency.** Deep models may miss 10 ms on the Jetson. Mitigation: B2 is checked before any deep model is adopted.
- **Hardware data.** Real-world effects may not exist in the simulator. Mitigation: B3 static and replay tests are reported separately from simulation.

## 7. Order of work

1. B0 reproduce v3 results.
2. A1 simulator realism, report v3 models on the harder simulator.
3. A2 new features, validation only.
4. A3 decision logic, validation only.
5. A4 model candidates, validation only.
6. A5 lock and open the fresh test set once.
7. A6 report with targets.
8. B1 prerequisites and parser checks.
9. B2 Jetson latency.
10. B3 static and replay recordings.
11. B4 simulation-to-hardware check.
12. B5 optional public-data check.
