# Ten-Layer GNSS Spoofing Detector: Project Plan

Status: planning. Simulation first, then recorded data on the bench, then drone flights. No layer of the ten-layer design is complete yet. The results so far are in `layered_detector_results.md` (six layers, Nayfeh dataset).

## 1. Goal and order of work

Build the ten-layer detector and test it in this order:

1. **Simulation first.** A physics-based generator produces labelled GNSS and IMU data for clean flights and for each attack type. All ten layers are built and tested on this data.
2. **Dataset generation with AI-assisted methods.** Once the simulator is validated against real recordings, add learned generators to produce more clean windows and attack variants. Each generated dataset is checked before use (Section 5).
3. **Bench recordings.** Record real GNSS signals and sensor data on the ground. Replay recorded and simulated spoofs through a conducted (cabled) setup.
4. **Drone flights.** Run the detector on the Cube Orange and Jetson in flight, after approvals and a safety plan.

Each stage must produce a result before the next one starts. A stage that fails is reported as a failure.

## 2. What the hardware can collect and generate

Device capabilities depend on the exact models. The GPS module model is not confirmed; the entries marked "if u-blox" assume a u-blox receiver, which must be checked before relying on them.

| Device | What it can collect | Layers it feeds | Limits |
|---|---|---|---|
| **GPS module** | PVT, DOP, satellites used, per-satellite C/N0 (if u-blox: NAV-SAT), receiver clock bias and drift (if u-blox: NAV-CLOCK), raw pseudorange and carrier (if u-blox: RXM-RAWX), multi-constellation solutions if enabled | 1 (clock), 2 (C/N0, residuals), 3 (DOP, satellites), 4 (GPS vs Galileo), 7 (raw), 9 (clock Allan) | Clock and raw messages are not in standard ArduPilot logs. They must be read directly from the module, e.g. via a host computer or the Jetson. |
| **Cube Orange** | IMU (acceleration, rotation), barometer, GPS messages via MAVLink or the DataFlash log, flight-controller state | 5 (position vs velocity vs acceleration), 6 (barometer, jerk), 3 and 2 (GPS reference) | Logs GPS messages but not clock bias or raw measurements. IMU and barometer rates depend on the configured log rates. |
| **RTL-SDR V3** | Raw L1 (1575.42 MHz) IQ samples at about 2 MS/s, 8-bit, recorded to file | 7 (carrier phase, code-carrier divergence, via GNSS-SDR tracking), 2 (C/N0 from tracking) | Narrow bandwidth, 8-bit, weak L1 signal indoors. Needs a good antenna and sky view. L1 only. |
| **HackRF** | Can record IQ at higher bandwidth. Can transmit IQ, which we use only for conducted replay. | Dataset source for 7 (higher-quality IQ). Replay test for the whole pipeline. | Transmission must be conducted only: through attenuators into a shielded enclosure or cable. No over-the-air transmission at GNSS frequencies. |
| **Jetson** | Runs GNSS-SDR tracking, the feature pipeline, the detector, and logging. Measures latency on target hardware. | All layers at run time; latency measurement; logging hub | Compute limits on tracking and on learned layers (LSTM, autoencoder). Latency must be measured on the Jetson, not estimated. |

What the hardware cannot collect, and so must come from simulation or public data: a labelled clean and attacked pair from the same flight, a real clock-tracking attacker, real multi-constellation attacks, and a real attack on a drone.

## 3. What we can generate

### 3.1 Physics-based simulator (first)

- **Trajectories.** Simulated drone flights: hover, straight legs, turns, climbs. Position, velocity and acceleration at the rates the sensors use.
- **GNSS measurements.** Satellite geometry from ephemerides; pseudorange with a noise model; DOP and satellite count derived from geometry; C/N0 from elevation with a noise model.
- **Clock model.** A two-state oscillator (phase and frequency) with noise parameters. The parameters are not invented: they are calibrated from the measured Allan deviation of the GPS module once the module is recorded (Stage 3). Until then they are labelled as assumptions. The clock simulation already built uses such parameters.
- **IMU and barometer.** Sensor noise, bias and drift, with rates matching the Cube Orange configuration.
- **Attacks.** Static offset, dynamic takeover, step, ramp (slow drift), step-then-ramp, ramp-then-step, and a consistent takeover in which position and velocity agree with each other. Each attack has a known onset.
- **Output.** The same column schema as the real logs, so the same pipeline reads simulated and real data.

Open-source GNSS signal generators (for example gps-sdr-sim) can produce IQ files for a given trajectory and spoofing scenario. These can be replayed through HackRF in the conducted setup (Stage 3) to test layer 7 on known inputs.

### 3.2 AI-assisted generation (after the simulator is validated)

- **Conditional generative model of clean windows.** Trained on real clean recordings (Nayfeh clean data, then our own), to produce more clean windows for the layers that need many examples (Isolation Forest, autoencoder).
- **Attack variants.** Parameters of the physics attack model are sampled from learned distributions (for example, a fitted distribution of ramp rates), not from fixed values.
- **Adversarial attacker.** A search procedure (for example, reinforcement learning) tries to build attacks that evade the current detector. This is a test of robustness, not a dataset for training. Its output is reported as a worst-case result.

### 3.3 Limits of generated data

A generator learns the features of the data it is trained on. If the training recordings differ between clean and attacked flights, the generator will reproduce that difference. A detector trained on generated data can then score well for the wrong reason, as the Nayfeh results showed for supervised models. So every generated dataset is checked as in Section 5 before it is used to report a result.

## 4. Layers and what each needs

| Layer | Data source for simulation | Data source for bench and drone | Status |
|---|---|---|---|
| 1. Time-domain | Simulated clock | GPS module clock messages | Simulation exists (time-based clock filter). Real data missing. |
| 2. Signal quality | Simulated C/N0 and residuals | Module C/N0, RTL-SDR tracking | Partly run on Nayfeh (receiver indicators). |
| 3. Geometry | Simulated DOP and satellites | Module DOP and satellites | Partly run on Nayfeh. |
| 4. Multi-constellation | Simulated GPS and Galileo | Module with both constellations enabled | Not started. |
| 5. Cross-domain | Simulated IMU and position | Cube Orange IMU and GNSS | Partly run on Nayfeh (GNSS only). Needs IMU. |
| 6. Physical | Simulated IMU and barometer | Cube Orange barometer and IMU | Partly run (GNSS only). Needs barometer and IMU. |
| 7. Raw signal | Replayed IQ from simulator | RTL-SDR or HackRF recordings | Not started. |
| 8. Temporal anomalies | Simulated clean flights | Logged flights | Run on Nayfeh (Isolation Forest). |
| 9. Fast Allan deviation | Simulated clock | GPS module clock | Not started on real data. |
| 10. Learned models | Simulated and generated data | Logged flights, held-out sessions | Random Forest run on Nayfeh. Autoencoder and LSTM not started. |

## 5. Dataset design and validation

### 5.1 Labels and splits

- Every window carries: attack type, onset time, true position, session ID, source (real, simulated, generated).
- Splits are by session, never by window. A session is one flight or one simulated run.
- Clean and attacked data for the same condition (same trajectory, same satellite geometry) must be available. This is the within-session control that the Nayfeh data lacks.

### 5.2 Checks before a dataset is used

1. **Simulator against real data.** Compare the distributions of each feature (C/N0, DOP, residuals, clock Allan deviation) between simulated and real clean data. Report the differences.
2. **Train on simulated, test on real.** A detector trained only on simulated data is tested on real recordings. This is the main test of whether the simulator is useful. A large drop in performance is reported as a sim-to-real gap.
3. **Generated data.** A classifier is trained to separate generated windows from real windows. If it succeeds, the generator is not yet realistic enough and its data is not used for results.
4. **No shortcut.** Each layer is checked for whether the attack can be read from a single feature (as in the receiver-indicator shortcut). A layer that depends on one feature is reported as such.

## 6. Phases

| Phase | Work | Output | Gate to next phase |
|---|---|---|---|
| 0. Inventory | Confirm the GPS module model and which messages it outputs. Confirm Cube Orange log rates. Confirm Jetson model and GNSS-SDR run speed. | One-page hardware report | Module messages for clock and C/N0 confirmed |
| 1. Simulator | Build the physics simulator and attack generator. Build the labelled dataset format. | Simulated dataset with checks from 5.2 (1) | Simulator features reviewed against the Nayfeh clean data |
| 2. Layers on simulation | Implement layers 1 to 10 on simulated data. Run ablations. | Results per layer and for the vote, on simulated data | Each layer's false-alarm rate measured on clean simulated data |
| 3. Bench recordings | Record the GPS module (clock, C/N0, raw), the RTL-SDR (IQ), and the Cube Orange (IMU, baro) on the ground. Calibrate clock parameters from the module's Allan deviation. Replay simulated and recorded spoofs through HackRF, conducted only. | Real clean and replayed-attack datasets. Calibrated simulator parameters. | Sim-to-real check (5.2 (2)) reported |
| 4. Generated data | Train generative models on real clean data. Run the generated-data checks. | Generated datasets, each with its check results | Generated data passes 5.2 (3) or is not used |
| 5. Drone flights | Logged flights with IMU, barometer and GNSS. Safety plan and approvals before any flight. | Flight datasets with clean and attacked segments | Approvals and safety plan in place |
| 6. Report | Results for all layers, including failures and the sim-to-real gap | Report | — |

## 7. Safety and legal constraints

- **No over-the-air transmission.** HackRF and any other transmitter are used only in conducted mode: through attenuators into a shielded enclosure or cable. Transmit power and setup are checked before each session.
- **Flight tests.** Require a written safety plan and approval before any flight. Flights carry no spoofing signal unless the approved plan permits it, and the first flights are clean recordings only.
- **Real-world GNSS.** Recording GNSS on the ground is passive. Check local rules before any active test near public or safety-critical systems.

## 8. Open items

1. GPS module model and whether its messages (NAV-CLOCK, NAV-SAT, RXM-RAWX) are enabled.
2. Cube Orange firmware version, log rates, and whether IMU and barometer can be logged at the rates the layers need.
3. Jetson model, and whether GNSS-SDR runs in real time on it.
4. Antenna and sky-view setup for the RTL-SDR and the module.
5. Approval process and safety plan for drone flights.
6. Selection of the generator model for Section 3.2, once the simulator is validated.
