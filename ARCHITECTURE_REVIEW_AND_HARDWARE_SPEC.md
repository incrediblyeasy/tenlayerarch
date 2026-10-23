# Ten-Layer Detector: Review of the Uploaded Starter Code and Hardware-Ready Specification

Scope: the uploaded archive `10 Layer archi` (package `ten_layer_detector`, tests, README, plan). This document has two parts: (1) faults found by reading the code and running it, and (2) a corrected specification that can be implemented on the GPS module, Cube Orange, RTL-SDR, HackRF and Jetson. The code has not been changed here.

## Part 1. Faults in the uploaded code

### 1.1 Verified by running it

| Check | Result | Meaning |
|---|---|---|
| `pytest` | 5 passed | The tests check column names, row counts and types. None checks that a detector detects anything. |
| CLI `evaluate`, step attack at 12 s | Layers 2 to 10 all "passed" with scores from 0.76 to 28.7 against thresholds of 0.45 to 0.7 | Scores are on unrelated scales, so the thresholds have no meaning. |
| `split_sessions` with one session | Train set is empty (`[]`), the one session goes to test | Silent failure. Any pipeline that trains on the train split gets nothing. |
| Clean session (onset beyond the end) | `label.sum() == 1` | A clean session is labelled as attacked in its last sample. |
| `pseudorange_m / gnss_lat` | Exactly 10.0 at every sample | Pseudorange is a copy of the position, not a range. |
| Correlation of `cn0_dbhz` with the step-attack label | 0.023 | The attack does not affect C/N0, so layer 2 cannot detect the attack in this simulator. |

### 1.2 Faults by file

**Layers (`layers.py`): placeholders, not detectors.**

- F1. No layer is trained or fitted. Every threshold (0.45 to 0.7) is hand-set. The README calls the package a "complete simulation-ready project shell". That overstates it: it is a set of heuristics with no calibration.
- F2. Several layers compare quantities with different units or meanings:
  - Layer 4 (multi-constellation) computes `|lon - lat|`. There is no second constellation.
  - Layer 5 (cross-domain) compares GNSS latitude (metres in this simulator, degrees in real data) with IMU acceleration.
  - Layer 6 (physical) compares IMU acceleration with barometric altitude.
  - Layer 7 (raw signal) divides pseudorange magnitude by 100. This is not a raw-signal check.
  - Layer 9 (called "Allan") computes mean absolute difference divided by sample interval. That is not an Allan deviation.
  - Layer 10 (called "learned") is a mean absolute deviation of three averaged signals. Nothing is learned.
- F3. `passed` means `score >= threshold`, i.e. "alarm raised". The report prints this as `PASS`, so an alarm reads as a pass. The meaning is inverted and confusing.
- F4. Layer 1 divides by the standard deviation of the signal, which includes the attack. A bigger attack lowers the score.

**Simulator (`simulator.py`): the data cannot test the layers.**

- F5. No clean class. `ATTACK_TYPES` has no benign type, so clean sessions cannot be generated on purpose. False-alarm rate cannot be measured.
- F6. An onset beyond the end of a session labels the last sample as an attack instead of failing or producing a clean session (verified above).
- F7. `pseudorange_m = 10 * gnss_lat` and `gnss_lon = 0.9 * gnss_lat` are fixed multiples of one signal. Any layer using two of these has perfect correlation by construction.
- F8. `cn0_dbhz` depends on position, not on the attack. A spoofer changes C/N0 in reality (usually upward), so layer 2 has no signal to find.
- F9. `consistent_takeover` is a linear ramp, the same as `ramp`. It does not keep velocity consistent with position, which is the attack the consistency layers must catch. Only the name differs.
- F10. `dynamic_takeover` is a sine wave not tied to the vehicle's motion. `step_then_ramp` uses the step length `length // 8`, which depends on the total duration, not on physical time.
- F11. Attacks are added to position in metres, with no link to a spoofer's power, a satellite set or a receiver's tracking. This makes the simulator unable to reproduce the receiver-indicator effects measured on the real data.
- F12. The IMU and barometer are noisy copies of the same trajectory. Their noise, bias and drift are not modelled, so the cross-domain layers have an unrealistically easy job.
- F13. Every session uses the same trajectory (a sine), and seeds change only the noise. Sessions differ by noise alone.

**Dataset and splitting (`dataset.py`).**

- F14. `split_sessions` with one session returns an empty training set (verified above).
- F15. The split takes the last sessions as test in file order, not at random and not stratified by attack type. Results depend on the order of the list.
- F16. Session IDs have mixed types: `"s0"` is stored as `0` (int), but `"session_0"` stays a string. The split compares `str()` values, which hides the mismatch.
- F17. Nothing checks that the training and test splits contain both classes.

**Pipeline, metrics and reporting.**

- F18. `metrics.py` (accuracy, precision, recall, F1) is never called. There is no evaluation loop that turns layer scores into decisions and compares them with labels. So the project cannot report detection rate, false alarms or delay.
- F19. `reporting.py` summarises scores, not detection results.
- F20. Detection delay, false alarms per hour and per-attack-type results are not computed anywhere.

**Tests (`tests/`).**

- F21. The 5 tests check shape and types only. None checks that an attack raises a layer's score, that a clean session does not, or that the split is correct. The split test would pass with a bug that loses data.

**Hardware (not present).**

- F22. There is no code for any device: no parser for the GNSS module's messages (for example u-blox UBX), no MAVLink or DataFlash reader for the Cube Orange, no GNSS-SDR or RTL-SDR reader, no HackRF replay, no Jetson deployment, no latency measurement.
- F23. No time base. Timestamps are seconds from zero. Real streams from three devices need a shared time base (Section 2.2).
- F24. No units or frames. Acceleration is in unspecified units, positions are in unspecified frames, and real GNSS latitude is in degrees.

**Packaging (minor).**

- F25. `pyproject.toml` does not list pytest; `requirements.txt` does. Planned ML (Isolation Forest, random forest) needs scikit-learn, which is not listed.

## Part 2. Corrected specification for hardware

### 2.1 Devices and what they provide

| Device | Interface to Jetson | What it provides | Layers | Notes |
|---|---|---|---|---|
| GNSS module (u-blox assumed; confirm) | UART or USB, UBX binary | NAV-PVT (position, velocity, accuracy, DOP, satellites), NAV-SAT (per-satellite C/N0, elevation, azimuth), NAV-CLOCK (clock bias and drift), RXM-RAWX (pseudorange, carrier phase, lock time), NAV-TIMEGPS | 1, 2, 3, 4 (if both constellations are enabled), 7 (if RXM-RAWX is supported), 9 | Clock and raw messages are not in ArduPilot logs. They must be read from the module directly. |
| Cube Orange (ArduPilot) | UART, MAVLink v2, or DataFlash log copied after the flight | IMU (acceleration, gyro), barometer, attitude estimate (ATTITUDE), GPS as seen by the autopilot (GPS_RAW_INT, GLOBAL_POSITION_INT) | 5, 6, reference for 3 | Log rates depend on configuration. Rates must be set and logged explicitly. |
| RTL-SDR V3 | USB | Raw L1 IQ at up to about 2 MS/s, 8-bit | 7, 2 (C/N0 from tracking) | Needs antenna with sky view. L1 only. Indoors the signal is too weak for tracking. |
| HackRF | Lab PC (not on the drone) | Conducted replay of recorded or simulated IQ. Optional higher-bandwidth IQ recording | Replay test for the whole pipeline; dataset source for 7 | Conducted only: attenuators and shielded enclosure or cable. No over-the-air transmission at GNSS frequencies. |
| Jetson | Hub for all streams | Runs GNSS-SDR tracking (if used), the feature pipeline, the detector, logging to SSD | All at run time; latency measurement | CPU and GPU limits must be measured. Learned layers (LSTM, autoencoder) may not fit the budget. |

### 2.2 Time base

- Reference clock: GNSS time from the module (NAV-PVT / NAV-TIMEGPS). Every record carries a GNSS time stamp (week and time of week, in ms or better).
- Each stream also carries the Jetson's receive time. The offset between device time and receive time is measured and logged.
- If the module provides a PPS output, connect it to a Jetson GPIO input and log the PPS edges. This gives sub-microsecond alignment between the module and the Jetson.
- The Cube Orange time is aligned to GNSS time through its own GPS messages (GPS time in MAVLink). The offset is logged. Stated alignment accuracy must be measured, not assumed.
- Acceptance check before any data is used: the offset between streams stays below 5 ms over a 10-minute static test.

### 2.3 Sampling rates and volumes (target values; confirm on hardware)

| Stream | Rate | Approx. volume per hour |
|---|---|---|
| GNSS PVT and DOP | 5 Hz | < 10 MB |
| NAV-SAT | 1 to 5 Hz | 10 to 50 MB |
| NAV-CLOCK | 1 to 5 Hz | < 5 MB |
| RXM-RAWX (if supported) | 1 to 5 Hz | 100 to 500 MB |
| Cube IMU | 100 Hz logged, decimated to 10 Hz for layers 5 and 6 | 100 to 300 MB |
| Cube barometer | 10 to 50 Hz | < 50 MB |
| RTL-SDR IQ (recording windows only) | 2 MS/s, 8-bit I/Q | about 14 GB per hour. Record in windows of 60 s (about 240 MB each). |

The rates set here are the ones the layers need. Each must be measured on the real device, not assumed.

### 2.4 Unified record format

Every stream is stored as a table with these columns:

- `gnss_week`, `gnss_tow_ms`: GNSS time.
- `host_recv_ns`: Jetson receive time.
- `source`: `gnss_module`, `cube_imu`, `cube_baro`, `rtl_iq`, `sim`.
- Stream-specific fields, with units stated in the column name (for example `lat_deg`, `alt_m`, `vel_n_mps`, `cn0_dbhz`, `clk_bias_ns`, `clk_drift_nsps`, `acc_x_mps2`).

Each session has a metadata file (JSON):

- `session_id` (string, always), `kind` (`clean`, `attack`), `source` (`sim`, `bench_replay`, `flight`).
- `attack_type`, `attack_start_gnss_tow_ms`, `attack_end_gnss_tow_ms` (null for clean).
- Devices and firmware versions, configured rates, sky-view and antenna notes, receiver model, time-offset measurements.

Labels come from the replay log (bench) or from the simulator's known onset. They are never inferred from the data.

### 2.5 Layer specifications

For each layer: inputs, computation, units, threshold rule, and hardware status. Thresholds are never hand-set. Each layer is calibrated on clean sessions only (threshold = 99.9th percentile of its clean score, with a 3-consecutive-exceedance rule where the layer is per-sample).

1. **Time-domain.** Input: `clk_bias_ns`, `clk_drift_nsps` from NAV-CLOCK. Computation: a two-state Kalman filter tracks phase and frequency. The innovation (measured minus predicted offset) is normalised by its predicted standard deviation. The filter's process noise is fitted to the module's Allan deviation on clean static data, not guessed. Status: needs the module's clock messages.
2. **Signal quality.** Input: per-satellite `cn0_dbhz` and elevation from NAV-SAT. Computation: the C/N0 of each satellite compared with a clean baseline in elevation bins; the mean z-score and the count of satellites outside the band. Status: needs NAV-SAT.
3. **Geometry.** Input: satellite elevation and azimuth (NAV-SAT), reported DOP (NAV-PVT). Computation: DOP recomputed from the satellite geometry and compared with the reported DOP; satellite-set change between epochs at a fixed position. Status: needs NAV-SAT.
4. **Multi-constellation.** Input: GPS-only and GPS+Galileo solutions from the module. Computation: distance between the two position solutions, divided by the reported horizontal accuracy. Status: needs the module to output both solutions. If not available, the layer is dropped and reported as such.
5. **Cross-domain.** Input: GNSS position and velocity (NAV-PVT, 5 Hz), Cube IMU acceleration (10 Hz after decimation), Cube attitude. Computation: (a) velocity from differentiated GNSS position compared with GNSS velocity; (b) GNSS acceleration compared with IMU acceleration rotated into the navigation frame using the attitude. Both differences are normalised by the clean baseline. Status: needs the Cube IMU and attitude.
6. **Physical.** Input: GNSS altitude, barometric altitude (Cube), IMU jerk, GNSS speed. Computation: GNSS altitude compared with barometric altitude after removing a slowly varying offset estimated on clean data; jerk compared with the clean maximum for the airframe; speed compared with the maximum for the airframe. Status: needs barometer and IMU.
7. **Raw signal.** Input: carrier phase and code-carrier difference from RXM-RAWX (if supported), or from GNSS-SDR tracking on RTL-SDR IQ. Computation: count of carrier-phase slips per minute; rate of change of code-minus-carrier divergence. Status: RXM-RAWX or IQ recordings. The public dataset does not contain this.
8. **Temporal anomalies.** Input: features from layers 2, 3, 5 and 6, over a trailing 10-second window. Computation: Isolation Forest fitted on clean sessions only. The score is the normalised anomaly. Status: can run once layers 2, 3, 5 and 6 have data.
9. **Allan deviation.** Input: clock offset from NAV-CLOCK at 1 Hz or better. Computation: overlapping Allan deviation at tau = 1, 2 and 4 s, over a window of at least 60 s. The 2-second window in the uploaded design cannot give a reliable Allan estimate. The window length is chosen from the clean noise measurement (Section 2.6). Status: needs NAV-CLOCK.
10. **Learned models.** Input: features from layers 2 to 8. Computation: a random forest trained on labelled sessions, with the clean and attack sessions split by session, not by sample. An autoencoder is added only after the forest is evaluated. Status: needs labelled sessions from Phase 3 onward.

Vote: logistic regression on the layer percentiles, fitted on training sessions. The alarm threshold is set on held-out clean sessions for a fixed false-alarm rate per hour. Attack-type naming: a rule that maps which layers fire to an attack type, tested on labelled attacks before it is reported. Equal weights are reported as a baseline.

### 2.6 Calibration and baseline procedure (before any evaluation)

1. **Static baseline.** At least 60 minutes of clean static data with the GNSS module, the Cube and the Jetson running. Used to fit the clock noise model (layer 1, layer 9) and the static noise of every stream.
2. **Clean flights.** At least 10 clean flights, each with a different route and time of day, to fit the calibration of layers 2, 3, 5, 6 and 8 and to set thresholds.
3. **Offsets.** Barometer offset and IMU mounting alignment estimated from the static and clean data.

Thresholds set from these data are frozen before any attacked session is used.

### 2.7 Sessions and minimum counts

- A session is one flight or one replay run. Splits are by session.
- Before any detection rate is reported, the evaluation requires at least 10 clean and at least 10 attacked sessions per attack type. Fewer than that is reported as a pilot result, not a rate.
- Each attack type is represented in training and test sessions. The split is random with a fixed seed and stratified by attack type, and its seed is recorded.

### 2.8 Evaluation outputs

For each layer and for the vote:

- Detection rate per attack type, with a confidence interval.
- False alarms per hour on clean sessions, with the number of hours.
- Detection delay (seconds from onset to first alarm), per attack type.
- Latency on the Jetson (milliseconds per decision), measured under the full load of the pipeline.
- Ablation: each layer removed in turn.
- Shortcut check: detection without the receiver-indicator layer, and detection by each feature alone.

Negative results are reported with the same detail as positive ones.

### 2.9 Safety and legal constraints

- No over-the-air transmission. HackRF is used only conducted (attenuators, shielded enclosure or cable). Transmit level is checked before each session.
- The first flights carry no spoofing. Flight tests need a written safety plan and approval.
- Ground recording of GNSS is passive. Check local rules before any active test near public or safety-critical systems.

## Part 3. Corrections for the simulator (before it is used for results)

The simulator must generate what the real hardware would produce, or it is not a useful test. Required changes:

1. Clean sessions are a first-class type. An onset beyond the session end is an error, not a silent attack label.
2. Pseudorange is computed from satellite geometry, receiver clock bias, and noise. It is not a scaled copy of position.
3. C/N0 depends on elevation and on the attack. A spoofer raises C/N0 by a configured amount with a configured spread.
4. Attack types:
   - Static and step: a fixed offset applied to the pseudoranges.
   - Ramp: slow drift in pseudoranges and in the receiver clock.
   - `consistent_takeover`: the spoofer's position and velocity agree with each other, so GNSS-only consistency checks cannot see it. The attack is then detectable only through IMU, barometer or clock.
   - `dynamic_takeover`: the spoofed trajectory follows a physically plausible manoeuvre, not a sine wave.
5. IMU and barometer have noise, bias and drift that differ per session. Clock noise uses the calibrated Allan parameters.
6. Trajectories vary: different routes, speeds, turns and altitudes across sessions.
7. Output uses the unified record format (Section 2.4), with units in the column names.

## Part 4. Implementation plan with gates

| Step | Work | Gate |
|---|---|---|
| 0. Fix the code | Fix F14 to F21 (split, clean class, metrics loop, tests that check behaviour). Remove the placeholder layers from the package or mark them as stubs. | Tests check detection on a known attack and no detection on clean data |
| 1. Simulator | Implement Part 3. Generate clean and attacked sessions with metadata. | Checks from Part 2.7 pass on the simulated data |
| 2. Layers on simulation | Implement layers 1 to 10 against Part 2.5. Calibrate on clean simulated sessions. Run the ablation and shortcut check. | Each layer's false-alarm rate measured on clean simulated data |
| 3. Hardware interfaces | Parsers for UBX (NAV-PVT, NAV-SAT, NAV-CLOCK, RXM-RAWX), MAVLink or DataFlash, and the RTL-SDR IQ writer. Measure the actual rates. Measure time offsets (Section 2.2). | Acceptance check on time offset (5 ms) and measured rates |
| 4. Static baseline | Section 2.6 (1). Fit clock and noise models. Compare with the simulator's assumed values and update Part 3 if they differ. | Simulator and real static data agree within a stated tolerance |
| 5. Bench replay | Conducted replay of simulated and recorded attacks via HackRF. Record the module, the Cube and the RTL-SDR. | Detection on replayed attacks reported, with the replay labels |
| 6. Clean flights | Section 2.6 (2). Calibrate on real flights. | Thresholds frozen before attacked sessions are used |
| 7. Attacked flights | Only after approvals (Section 2.9). Session counts per Section 2.7. | Minimum counts met before rates are reported |

## Part 5. Open items

1. GNSS module model, and whether NAV-CLOCK, NAV-SAT and RXM-RAWX are available and enabled.
2. Cube Orange firmware, configured log rates, and whether GPS time is available in MAVLink.
3. Jetson model and power budget on the drone; GNSS-SDR real-time performance on it.
4. RTL-SDR antenna and sky-view placement.
5. Attenuator and enclosure setup for HackRF, and transmit-level check procedure.
6. Approval process and safety plan for flights.
