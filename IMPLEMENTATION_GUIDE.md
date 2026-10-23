# Ten-Layer GNSS Spoofing Detector: Implementation Guide

Purpose: a step-by-step guide to build the ten-layer detector described in the proposal, to the specification in `ARCHITECTURE_REVIEW_AND_HARDWARE_SPEC.md`. It is written so that someone other than the author can build and check each part.

Scope: the detector, its data pipeline, the simulator, evaluation, and the hardware interfaces. It does not cover the paper replications, which are already done in `work/` and are referenced here only as reference code.

## 0. Ground rules

1. **No hand-set thresholds.** Every threshold is computed from clean training data, then frozen before any attacked data is used.
2. **Split by session, never by sample.** A session is one flight, one replay run, or one simulated run. Samples from the same session never appear in both training and test.
3. **Every layer is measured alone first.** Each layer's detection and false-alarm rate is reported before it enters the vote.
4. **Negative results are reported.** A layer that does not detect is reported with the same detail as one that does.
5. **Units are in column names.** `lat_deg`, `alt_m`, `vel_n_mps`, `cn0_dbhz`, `clk_bias_ns`. Nothing is unitless.
6. **Each layer uses only the data its sensor provides.** A layer without its input is dropped and reported as not evaluated. It is never approximated with a different signal.

## 1. Repository layout (target)

```
ten_layer_detector/
  schema.py            canonical record schema, units, validation
  time_base.py         GNSS time, host time, PPS and offset handling
  io/
    nayfeh_loader.py   released Nayfeh workbooks -> canonical schema
    ubx.py             u-blox binary parser (NAV-PVT, NAV-SAT, NAV-CLOCK, RXM-RAWX)
    mavlink_log.py     Cube Orange MAVLink stream and DataFlash log reader
    rtl_iq.py          RTL-SDR IQ window writer and reader
  sim/
    trajectory.py      vehicle trajectories
    gnss_model.py      satellite geometry, pseudorange, C/N0, DOP
    clock_model.py     two-state oscillator with calibrated noise
    sensors.py         IMU and barometer with bias, drift, noise
    attacks.py         attack profiles applied to the measurement stream
    generate.py        session generator, clean and attacked, with metadata
  features.py          rolling features and residuals shared by the layers
  layers/
    base.py            Layer interface: fit, calibrate, score, alarm
    l01_time.py  l02_signal.py  l03_geometry.py  l04_multiconst.py
    l05_cross.py  l06_physical.py  l07_raw.py  l08_temporal.py
    l09_allan.py  l10_learned.py
  vote.py              percentile calibration, weighted vote, attack-type naming
  splits.py            seeded, stratified session splits; leave-one-square-out
  metrics.py           detection rate, false alarms per hour, delay, MDR
  evaluate.py          full protocol: calibrate, freeze, test, ablate, shortcut check
  bench_latency.py     per-decision latency on the Jetson
  reports.py           CSV and Markdown output, including negative results
tests/                 behavioural tests (Section 9)
```

Each module has one job. Layers never read files, and I/O modules never compute detection scores.

## 2. Canonical record schema

Every stream is a table. Columns not produced by a source are null, not filled with a copy of another column.

**Common columns (every row):**

| Column | Type | Meaning |
|---|---|---|
| `session_id` | string | Always a string, e.g. `flight_0007`, `sim_clean_0003`. Never an int. |
| `source` | string | `nayfeh`, `sim`, `bench_replay`, `flight` |
| `t_gnss_s` | float | GNSS time of week in seconds, or the simulator's time |
| `t_host_ns` | int | Jetson receive time, when available |

**GNSS columns (from NAV-PVT and NAV-SAT, or the Nayfeh sheets):**

| Column | Unit | Source |
|---|---|---|
| `lat_deg`, `lon_deg` | degrees | NAV-PVT (1e-7 scale) |
| `alt_m` | m above ellipsoid | NAV-PVT |
| `vel_n_mps`, `vel_e_mps`, `vel_d_mps` | m/s | NAV-PVT |
| `h_acc_m`, `v_acc_m` | m | NAV-PVT |
| `pdop`, `hdop`, `vdop`, `num_sv`, `fix_type` | - | NAV-PVT |
| `sv_id`, `gnss_id`, `cn0_dbhz`, `elev_deg`, `azim_deg` | per satellite | NAV-SAT (long format, one row per satellite per epoch) |
| `clk_bias_ns`, `clk_drift_nsps` | ns, ns/s | NAV-CLOCK |
| `pr_m`, `cp_cycles`, `dop_hz`, `lock_ms` | m, cycles, Hz, ms | RXM-RAWX (optional) |

**Sensor columns:**

| Column | Unit | Source |
|---|---|---|
| `acc_bx_mps2`, `acc_by_mps2`, `acc_bz_mps2` | m/s^2, body frame | Cube IMU |
| `gyr_bx_rps`, `gyr_by_rps`, `gyr_bz_rps` | rad/s, body frame | Cube IMU |
| `roll_rad`, `pitch_rad`, `yaw_rad` | rad | Cube ATTITUDE |
| `baro_alt_m` | m | Cube barometer |

**Label columns (sessions only; never inferred from data):**

| Column | Meaning |
|---|---|
| `label` | 0 clean, 1 attacked (inside the attack window) |
| `attack_type` | `none`, `static`, `step`, `ramp`, `step_then_ramp`, `ramp_then_step`, `consistent_takeover`, `dynamic_takeover` |

**Session metadata file (JSON):** `session_id`, `kind` (`clean` or `attack`), `source`, `attack_type`, `attack_start_t_gnss_s`, `attack_end_t_gnss_s` (null for clean), receiver model and firmware, Cube firmware, configured rates, antenna and sky-view notes, measured time offsets, random seed.

**Validation rule:** `schema.validate(df)` fails if a required column is missing, a unit suffix is absent, `session_id` is not a string, or a clean session has any `label` equal to 1.

## 3. Time base

1. Use GNSS time of week (`t_gnss_s`) as the reference for every stream.
2. For each stream, record the host receive time. The offset `t_host_ns - t_gnss_s` is logged.
3. If the module has a PPS output, connect it to a Jetson GPIO input and log edges. PPS gives the offset between the module and the Jetson.
4. The Cube's time is aligned through its GPS time messages. The offset is logged.
5. Acceptance: the offset between streams stays under 5 ms over a 10-minute static test. Streams failing this are not used for layers that need alignment (5, 6).

## 4. Simulator

The simulator produces sessions in the canonical schema, with the same fields real data would have. It exists to test the detector before hardware is used. It must not be used to report detection results without the sim-to-real check (Section 8).

### 4.1 Components

- **Trajectory (`trajectory.py`).** Sample a vehicle path per session: hover, straight legs, turns, climbs, with random speeds (0 to 15 m/s), headings and altitudes (20 to 120 m). Output position, velocity, acceleration, attitude at the sensor rates. Each session has a different path.
- **GNSS model (`gnss_model.py`).** Satellite positions from a simple orbit model (or ephemeris if available). Elevation and azimuth from the receiver position. Pseudorange = geometric range + receiver clock bias + noise. C/N0 from elevation plus noise. DOP computed from the satellite geometry (Section 5.3). Satellite set changes with elevation mask.
- **Clock (`clock_model.py`).** Two-state oscillator: phase `x` (ns) and frequency `y` (ns/s). Process noise parameters are inputs, set from the calibration step (Section 7.1). Default values are labelled as assumptions until calibrated.
- **Sensors (`sensors.py`).** IMU: white noise, constant bias, random-walk bias drift, per-session values. Barometer: noise and a slow drift. Rates as configured on the Cube.
- **Attacks (`attacks.py`).** Each attack is a function of time, applied to the measurement stream. Required behaviour:

| Attack | Applied to | Required property |
|---|---|---|
| `static` | pseudorange, position | constant offset after onset |
| `step` | pseudorange, position | sudden offset at onset |
| `ramp` | pseudorange, position | linear drift after onset |
| `step_then_ramp` | pseudorange, position | step, then linear drift |
| `ramp_then_step` | pseudorange, position | linear drift, then step |
| `consistent_takeover` | position and velocity | the reported velocity equals the time derivative of the spoofed position, so a GNSS-only consistency check does not see it |
| `dynamic_takeover` | position and velocity | a physically plausible manoeuvre, with acceleration within the airframe limit; not a sine wave |

- Spoofing raises C/N0 by an amount with a configured mean and spread (a spoofer is usually stronger than the real signal).
- Attack amplitude, onset, and duration are sampled per session from configured ranges.

### 4.2 Output

`generate_session(config, seed) -> (DataFrame, metadata)`.

- Config: duration, rates, attack type (or `none`), onset, amplitude range, trajectory options, clock parameters, sensor parameters.
- An onset outside the session raises an error. A clean session has `label` 0 everywhere.
- The same seed always gives the same session.

### 4.3 Simulator acceptance tests

1. For `consistent_takeover`, the velocity change after onset matches the derivative of the spoofed position within 0.1 m/s.
2. For `dynamic_takeover`, the implied acceleration stays below the airframe limit.
3. For clean sessions, `gnss_lon_deg` and `gnss_lat_deg` are not perfectly correlated (the current code gives correlation 1.0).
4. Attack-induced C/N0 shift after onset is between 0.5 and 4 dB.
5. Two sessions with different seeds have different trajectories.

## 5. Features and residuals (`features.py`)

Shared by the layers. All functions take a session DataFrame and return arrays aligned to the rows.

### 5.1 Trailing window

`roll(x, n=10)`: trailing mean over `n` samples, `min_periods = n // 2`. Used for the layer scores in Section 6, so a score at time `t` uses only data up to `t`. This is required for online use on the Jetson.

### 5.2 Position-velocity residual

Convert `lat_deg`, `lon_deg` to local north/east metres about the first sample of the session:

`n = (lat - lat0) * R`, `e = (lon - lon0) * R * cos(lat0)`, with `R = 6371000 m`.

Residual: `r_pv = hypot(dn - v_n_prev*dt, de - v_e_prev*dt)`, where `dn = diff(n)`, `de = diff(e)`, `dt = diff(t_gnss_s)`, and `v_*_prev` is the velocity at the previous sample. Discard samples with `dt > 0.5 s` or `dt <= 0`.

### 5.3 DOP recomputation

For satellites with elevation `el_i` and azimuth `az_i`, the unit line-of-sight vector is `u_i = [cos(el) sin(az), cos(el) cos(az), sin(el)]` (east, north, up). Geometry matrix `G` has rows `[u_i, 1]`. `Q = (G^T G)^-1`.

- `HDOP_calc = sqrt(Q_ee + Q_nn)`
- `VDOP_calc = sqrt(Q_uu)`
- `PDOP_calc = sqrt(trace(Q[:3,:3]))`

Compare with the reported DOP. Require at least 4 satellites.

### 5.4 Acceleration residual

- GNSS acceleration in NED: `a_gnss = diff(v_ned) / dt`.
- IMU specific force in body frame `f_b`. Rotate to NED with the Cube attitude: `f_ned = R(roll, pitch, yaw) * f_b`. Kinematic acceleration: `a_imu = f_ned + g_ned`, where `g_ned = [0, 0, +9.80665]` in NED with z down. **The sign convention must be checked on static data**: at rest, `a_imu` must be near zero. If it is not, the sign or the axis mapping is wrong, and the layer must not be used until fixed.

## 6. Layers

Each layer implements the interface in `layers/base.py`:

```
class Layer:
    name: str
    required_columns: list[str]
    def fit(self, clean_sessions) -> None        # learn calibration from clean data only
    def score(self, session_df) -> np.ndarray    # one score per row, causal
    def calibrate(self, clean_sessions) -> float # threshold at a fixed clean percentile
    def alarm(self, scores) -> np.ndarray        # bool per row, with the persistence rule
```

`score` must not use future samples. `alarm` applies the persistence rule: alarm when `k` consecutive scores exceed the threshold (default `k = 3`). A layer whose `required_columns` are missing is reported as `not_evaluated`.

Threshold rule for every layer: 99.9th percentile of the layer's score on clean training sessions. Stated once; not tuned per layer.

### Layer 1: time-domain (`l01_time.py`)

- Input: `clk_bias_ns`, `clk_drift_nsps`, `t_gnss_s`.
- Two-state Kalman filter, state `x = [phase_ns, freq_nsps]`, step `dt`:
  - `F = [[1, dt], [0, 1]]`
  - `Q = [[sig_x^2*dt + sig_y^2*dt^3/3, sig_y^2*dt^2/2], [sig_y^2*dt^2/2, sig_y^2*dt]]`
  - `H = [1, 0]`, `R = sig_meas^2`
- Innovation `nu = z - H x_pred`, `S = H P H^T + R`. Score: `|nu| / sqrt(S)`.
- `sig_x`, `sig_y`, `sig_meas` are fitted from the static calibration data (Section 7.1), not guessed.
- Requires a clock source (u-blox NAV-CLOCK). Without it, the layer is `not_evaluated`.
- Reference: the clock simulation in `timesim/time_sim.py` implements this filter. Its results on simulated data are reported separately and must not be presented as real results.

### Layer 2: signal quality (`l02_signal.py`)

- Input: `cn0_dbhz`, `elev_deg` per satellite per epoch.
- Fit: for each elevation bin (10 deg width), the mean `mu_b` and standard deviation `sd_b` of C/N0 on clean sessions.
- Per satellite: `z = (cn0 - mu_b) / sd_b`.
- Per epoch, score = fraction of satellites with `|z| > 3`, plus `mean(|z|)` over satellites, combined as their max after normalising each by its clean 99.9th percentile. Two-sided, because a spoofer can raise or lower C/N0.
- Required: NAV-SAT per satellite. Nayfeh data has only aggregate noise and jamming fields; there the layer uses `noise_per_ms` and `jamming_indicator` and is reported as a receiver-indicator layer, not as C/N0.

### Layer 3: geometry (`l03_geometry.py`)

- Input: satellite elevation/azimuth (NAV-SAT), reported DOP and satellite count (NAV-PVT).
- Score components, each normalised by its clean 99.9th percentile:
  - `|DOP_reported - DOP_calc|`, for HDOP, VDOP and PDOP.
  - Change in satellite set between epochs: `1 - Jaccard(set_t, set_{t-1})`.
  - Circular spread of azimuths: `1 - |mean(exp(i*az))|`, which should be stable at a fixed position.
- Score = max of the normalised components.

### Layer 4: multi-constellation (`l04_multiconst.py`)

- Input: GPS-only and GPS+Galileo position solutions from the module (two sets of NAV-PVT, or a receiver configuration that outputs both).
- Score = horizontal distance between the two solutions divided by the reported horizontal accuracy `h_acc_m`.
- Required: module configured for both constellations and outputting both solutions. If not, the layer is `not_evaluated`. The layer must not be approximated.

### Layer 5: cross-domain (`l05_cross.py`)

- Components:
  - (a) Position-velocity residual `r_pv` (Section 5.2), normalised by its clean 99.9th percentile.
  - (b) Acceleration residual `|a_gnss - a_imu|` (Section 5.4), normalised the same way.
- Score = max of (a) and (b).
- Inputs: NAV-PVT and Cube IMU/attitude, time-aligned (Section 3). Part (b) is `not_evaluated` if the IMU is missing or the static sign check fails.

### Layer 6: physical (`l06_physical.py`)

- Components:
  - (a) Altitude consistency: `d = alt_m - baro_alt_m - offset`. `offset` is the median of `d` on clean static data. Score = `|d - median(d over trailing 60 s)|`, normalised.
  - (b) Jerk: `|diff(a_imu) / dt|` (from Cube IMU, decimated to 10 Hz), normalised by the clean 99.9th percentile.
  - (c) Speed: `|v|` against the airframe maximum, as a plausibility check.
- Score = max of normalised components. Requires barometer and IMU.

### Layer 7: raw signal (`l07_raw.py`)

- Input: `pr_m`, `cp_cycles`, `dop_hz`, `lock_ms` from RXM-RAWX, or from GNSS-SDR tracking on RTL-SDR IQ.
- Components:
  - (a) Carrier-phase slips: a cycle slip is flagged when the carrier-phase change minus the Doppler prediction exceeds 0.5 cycles, or when `lock_ms` resets. Score = slips per minute, normalised.
  - (b) Code-carrier divergence: `cmc = pr_m - cp_cycles * lambda`, with `lambda = 0.1903 m` at L1. Score = `|d(cmc)/dt|`, normalised.
- Required: RXM-RAWX (module) or IQ tracking output. The public Nayfeh dataset does not contain raw measurements, so this layer is `not_evaluated` there.

### Layer 8: temporal anomaly (`l08_temporal.py`)

- Input: feature vector from layers 2, 3, 5, 6 over a trailing 10 s window: means and standard deviations.
- Fit: `IsolationForest(n_estimators=200, random_state=seed)` on clean training sessions only.
- Score = negated `score_samples`, normalised by the clean 99.9th percentile.

### Layer 9: Allan deviation (`l09_allan.py`)

- Input: `clk_bias_ns` at 1 Hz or better, over a window of at least 60 s.
- Overlapping Allan variance at `tau = m * tau0` for `m` in `{1, 2, 4}`, with phase `x` in seconds:
  `sigma_y^2(tau) = sum_{i} (x_{i+2m} - 2 x_{i+m} + x_i)^2 / (2 tau^2 (N - 2m))`.
- Score = `sigma_y(tau)` at each `tau`, compared with the clean range; alarm when outside the clean 0.1 to 99.9 percentile range.
- The window must be at least 60 s. A 2-second window cannot give a reliable Allan estimate at these `tau`. The proposal's 2-second window must be corrected to match (Section 12).

### Layer 10: learned model (`l10_learned.py`)

- Input: feature vector from layers 2 to 8.
- Model: `RandomForestClassifier(n_estimators=200, max_depth=20, min_samples_leaf=20, class_weight="balanced", random_state=seed)`, fitted on training sessions only.
- Score = predicted probability of attack.
- Threshold: 99.9th percentile of out-of-fold clean scores (see Section 7.3 for how out-of-fold scores are produced).
- The autoencoder and LSTM are not implemented until the random forest has been evaluated. Each is then added as a separate layer with its own threshold.

## 7. Calibration, vote and attack naming

### 7.1 Static calibration (before any evaluation)

1. Record at least 60 minutes of static data with the module, Cube and Jetson running.
2. Fit clock parameters `sig_x`, `sig_y`, `sig_meas` for layer 1 by matching the simulated Allan deviation to the measured one at `tau` in {1, 2, 4, 8, 16} s.
3. Fit the IMU static bias and the barometer offset.
4. Check the sign convention of Section 5.4 (at rest, `a_imu` near zero).
5. Freeze all parameters in a versioned config file (`calibration_v1.json`).

### 7.2 Clean calibration

1. Record at least 10 clean flights on different routes, times and altitudes.
2. Compute each layer's clean scores, and the thresholds (99.9th percentile).
3. Freeze the thresholds in the same config file.

### 7.3 Out-of-fold scores for the vote

To fit the vote without the test sessions:

1. Split training sessions into folds (by session, stratified by attack type).
2. For each fold, fit the layers on the other folds and score the held-out fold. This gives out-of-fold scores for every training session.
3. Convert each layer's score to a percentile against the clean out-of-fold scores (`pct = searchsorted(sorted_clean, score, 'right') / N`).

### 7.4 Weighted vote

- Input: the layer percentiles (one column per layer that was evaluated).
- Model: `LogisticRegression(class_weight="balanced")` on standardised percentiles, fitted on training sessions' out-of-fold scores.
- Threshold: the 99.9th percentile of clean out-of-fold vote scores.
- Equal weights are computed as a baseline and reported.

### 7.5 Attack-type naming

Each layer's alarm pattern is recorded per attacked session. A rule maps the pattern to an attack type, for example:

| Pattern | Attack type |
|---|---|
| Layers 2, 3 fire; 5, 6 do not | Receiver-level attack (static, step) |
| Layers 1, 9 fire | Clock-level attack (ramp, step-then-ramp) |
| Layer 5 fires, 2 and 3 do not | Consistent takeover |
| Layer 6 fires | Physical inconsistency (dynamic takeover) |

The rule is fitted on training sessions and tested on held-out sessions. It is reported as correct or incorrect per attack type, with the confusion matrix. It is not reported as a result until tested.

## 8. Evaluation protocol (`evaluate.py`)

### 8.1 Splits

- **Session splits.** Random, with a fixed seed, stratified by attack type. The seed is recorded.
- **Leave-one-geometry-out** (Nayfeh and other datasets with a geometry label). For each held-out geometry, the other geometries are the training pool. Thresholds and vote are fitted inside the pool. The held-out geometry is only scored.
- **Minimum counts.** At least 10 clean and 10 attacked sessions per attack type before a detection rate is reported. Below that, the result is labelled as a pilot.

### 8.2 Protocol steps

1. Load the frozen config. Do not re-fit anything on the test data.
2. For each test session, run each layer's `score` and `alarm`.
3. Compute the metrics in Section 8.3.
4. Run the ablation: remove each layer in turn and refit only the vote.
5. Run the shortcut check: detection with each single feature, and with the receiver-indicator layer removed.
6. Run the sim-to-real check: a detector fitted on simulated sessions, scored on real sessions, with the drop in detection reported.
7. Write results with negative results included (Section 10).

### 8.3 Metrics (`metrics.py`)

- **Detection rate (DR)** per attack type: fraction of attacked sessions with at least one alarm after onset and within a stated window (for example 60 s). Reported with a 95% Wilson interval.
- **Miss rate (MDR)** = 1 - DR.
- **False alarms per hour (FAR/h)** on clean sessions: number of alarm onsets divided by total clean hours. Reported with the number of hours.
- **Detection delay**: time from onset to first alarm, per attacked session. Report the median and the 90th percentile.
- **Latency**: ms per decision, from `bench_latency.py`.

`metrics.py` currently computes accuracy and F1 only. These must be added. The current `compute_classification_metrics` is not used by the pipeline and must be connected to the protocol.

## 9. Tests

Tests check behaviour, not shapes. Minimum set:

1. Clean simulated sessions (no attack) produce no alarm from any layer at the frozen threshold, on at least 20 seeds.
2. Each attack type produces an alarm on at least one layer that the design says should see it, on at least 90% of seeds.
3. A layer fed data without its required columns returns `not_evaluated`, not zero.
4. Split: no session appears in train and test; both classes appear in each split; a single session raises an error.
5. Schema: a clean session with label 1 fails validation; a `session_id` of type int fails.
6. Time offset: a stream with an offset larger than 5 ms is flagged.
7. Causality: changing samples after time `t` does not change scores at `t`.
8. Sign check: on static simulated data, `a_imu` is near zero after the rotation in Section 5.4.
9. Allan: on synthetic white-noise phase data with known `sigma_y`, the estimate is within 10%.
10. Reproducibility: the same seed gives the same session, scores and metrics.

## 10. Reporting

Every evaluation writes:

- `results/summary.csv`: per layer and per vote: DR per attack type, FAR/h, delay, MDR, with intervals and counts.
- `results/ablation.csv` and `results/shortcut.csv`.
- `results/negative.md`: layers and attack types with no detection, and any `not_evaluated` layers with the reason.
- `results/config_frozen.json`: the exact config and seeds used.

Nothing is removed from the report because it is weak. A failed attack type stays in the table.

## 11. Hardware integration

### 11.1 GNSS module (u-blox assumed; confirm model)

- Interface: UART or USB, UBX binary protocol.
- Enable: NAV-PVT, NAV-SAT, NAV-CLOCK, NAV-TIMEGPS. Enable RXM-RAWX if the module supports it. Enable both GPS and Galileo if layer 4 is to run.
- Rates: measure the rates the module can sustain with all messages enabled. Use 5 Hz for NAV-PVT and NAV-SAT, 1 Hz or better for NAV-CLOCK.
- Parse fields: NAV-PVT (iTOW, lon, lat, height, hAcc, vAcc, velN, velE, velD, pDOP, numSV, fixType); NAV-SAT (gnssId, svId, cno, elev, azim, flags); NAV-CLOCK (iTOW, clkB, clkD, tAcc, fAcc); RXM-RAWX (rcvTow, week, prMes, cpMes, doMes, cno, locktime, trkStat).
- Confirm field names and scales against the module's interface description before parsing. Do not assume.

### 11.2 Cube Orange (ArduPilot)

- Interface: MAVLink v2 over UART, plus DataFlash logs copied after each flight.
- Messages to stream or log: ATTITUDE, RAW_IMU or SCALED_IMU (the Cube's IMU messages), SCALED_PRESSURE (barometer), GPS_RAW_INT and GLOBAL_POSITION_INT (GPS as seen by the autopilot, for reference).
- Set log rates explicitly. Record the configured rates in the metadata file.
- Confirm message names and fields against the installed firmware version.

### 11.3 RTL-SDR V3 (raw IQ, layer 7)

- Record L1 IQ at 1575.42 MHz, 2.048 MS/s, in windows of 60 s, with `rtl_sdr` writing 8-bit interleaved I/Q.
- Run recordings inside `tmux` so a dropped SSH session does not truncate a file. (A dropped session truncated recordings earlier in this project.)
- Convert to complex float for GNSS-SDR's file source. Check the conversion on a known file before use.
- Antenna with sky view. Indoor recordings are not used for layer 7 results.

### 11.4 HackRF (replay, conducted only)

- Use for replaying recorded or simulated IQ into a shielded enclosure or cable, through a fixed attenuator chain. Record the attenuation and the measured output level before each session.
- Use the lowest gain settings that produce the required signal. Never transmit over the air.
- The replay log records the start and end of each attack, which becomes the label.

### 11.5 Jetson

- Hub for all streams. Write each stream to local SSD with timestamps.
- Measure per-decision latency on the full pipeline (`bench_latency.py`), not on a subset. Report mean, 95th and 99th percentile.
- Check that the feature window (10 s) and the trailing scores run in real time at the stream rates.

## 12. Changes needed to the proposal

These are required so that the proposal matches the implementation plan:

1. Layer 9 (Section 4, layer 9): replace the 2-second rolling window with a window of at least 60 s and Allan tau values of 1, 2 and 4 s. Explain why, as in Section 6 of this guide.
2. Section 5 (Evaluation Plan): add per-hour false alarms, detection delay, and the minimum session counts from Section 8.1.
3. Section 4 (Status): remove any statement that the layers are described in the code. The code is a placeholder until Phase 2 below is complete.
4. Add the hardware interface list (Section 11) to the plan.

## 13. Implementation phases and gates

| Phase | Work | Gate (must pass to continue) |
|---|---|---|
| 0. Repair the existing package | Replace `layers.py` placeholders with the interface in Section 6 (layers 2, 3, 6, 8 first). Fix the metrics wiring. Fix layer 7's scale. Add the behavioural tests (Section 9). | Tests 1, 3, 4, 5 pass |
| 1. Simulator | Implement Section 4 including the attack fixes and acceptance tests 4.3 (1) to (5). | Section 4.3 tests pass |
| 2. Layers on simulation | Layers 1, 2, 3, 5, 6, 8, 9, 10 on simulated data. Thresholds from clean simulated sessions. Vote, attack naming, ablation, shortcut check. | False alarms on clean simulated sessions at the frozen thresholds are measured and reported |
| 3. Nayfeh reference | Port the leave-one-square-out protocol from `work/layered/layered_eval.py` into the package, with the Nayfeh loader. Reproduce its numbers. | Ported code reproduces the reference numbers within rounding |
| 4. Hardware parsers | UBX, MAVLink, DataFlash, RTL-SDR writer. Time base and offsets. Rates measured. | Offset test (Section 3) passes; rates recorded |
| 5. Static calibration | Section 7.1. Clock and IMU parameters fitted. | Sign check (test 8) passes on real static data |
| 6. Bench replay | Replay through HackRF, conducted. Record the module, Cube and RTL-SDR. | Replayed attacks detected or not, reported with labels |
| 7. Clean flights and thresholds | Section 7.2. Thresholds frozen. | Config frozen and hashed |
| 8. Attacked flights | After approvals (Section 14). Minimum counts (Section 8.1). | Rates reported only when minimum counts are met |

Phases 1 and 2 are simulation only. The simulation results are labelled as simulation in every report.

## 14. Safety and legal

- Transmission: conducted only. HackRF output goes into a shielded enclosure or cable through attenuators. Transmit level is checked before each session. No over-the-air transmission at GNSS frequencies.
- Flights: a written safety plan and approval before any flight. The first flights carry no spoofing signal.
- Ground recording of GNSS is passive. Check local rules before any active test near public or safety-critical systems.

## 15. Decisions the team must make

1. The GNSS module model. Layers 1, 4, 7, 9 depend on what it outputs.
2. The Cube Orange firmware version, since message names and rates depend on it.
3. Whether layer 4 runs at all (depends on item 1).
4. The persistence count `k` and the detection window (Section 8.3). These are fixed before evaluation.
5. Whether the random forest is the final learned layer or the autoencoder is also evaluated.

## Appendix A. Reference: Nayfeh protocol

`work/layered/layered_eval.py` (in the working folder) already implements a leave-one-square-out evaluation on the Nayfeh data with six layers. Its results are in `work/results/layered_detector_results.md`. It is the reference for Phase 3. Its limits, which the port must keep stated:

- Layers 1, 4, 7, 9 are not in the reference (no clock, multi-constellation or raw data).
- Layers 5 and 6 are partial (no IMU or barometer).
- Detection on that dataset comes mainly from receiver indicators, not from navigation consistency.
- The 70 m fold has a high false-alarm rate, which is not yet explained.
- Its results must not be presented as detection of the full architecture.
