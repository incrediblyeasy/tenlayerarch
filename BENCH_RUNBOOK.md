# Bench Recording Runbook

This runbook translates the Phase 0 hardware inventory and the Phase 3 bench-recording stage into a concrete execution checklist for real GNSS and IMU data collection.

## 1. Objective

Record clean and attacked bench sessions in a way that matches the detector schema and can be validated against the simulator. The bench phase is the bridge between simulated data and any flight work.

This phase must happen before any generated-data or flight claims.

## 2. Required folders

Create this directory structure in the workspace root:

```text
bench/
  README.md
  sessions/
    2026-10-22/
      session_001_clean/
        metadata.json
        gps/
        imu/
        rtl/
      session_002_attacked/
        metadata.json
        gps/
        imu/
        rtl/
  validation/
    sim_to_real_summary.csv
    feature_comparison.md
  logs/
    capture_notes.txt
    safety_checklist.md
```

Use a consistent date-based folder for each recording batch.

## 3. Session naming convention

Use this exact pattern:

```text
session_XXX_{clean|attacked}_{label}
```

Examples:
- `session_001_clean_baseline`
- `session_002_attacked_ramp`
- `session_003_clean_repeat`

Keep the `session_id` in the dataset consistent with the folder name.

## 4. Required metadata

Each session folder must contain a `metadata.json` with at least the following fields:

```json
{
  "session_id": "session_001_clean_baseline",
  "source": "bench",
  "environment": "indoor_lab",
  "clean_or_attacked": "clean",
  "attack_type": null,
  "attack_onset_s": null,
  "gps_model": "",
  "cube_orange_firmware": "",
  "jetson_model": "",
  "rtl_sdr_model": "",
  "start_time_utc": "",
  "end_time_utc": "",
  "sample_rate_hz": 10,
  "notes": ""
}
```

For attacked sessions:

```json
{
  "session_id": "session_002_attacked_ramp",
  "source": "bench",
  "environment": "indoor_lab",
  "clean_or_attacked": "attacked",
  "attack_type": "ramp",
  "attack_onset_s": 12.0,
  "gps_model": "",
  "cube_orange_firmware": "",
  "jetson_model": "",
  "rtl_sdr_model": "",
  "start_time_utc": "",
  "end_time_utc": "",
  "sample_rate_hz": 10,
  "notes": "conducted replay through attenuator"
}
```

## 5. Data sources to capture

### 5.1 GPS module

Collect raw GNSS logs if available. At minimum, capture:
- position / PVT
- DOP
- satellite count
- C/N0 per satellite
- clock bias and drift if the receiver exposes them
- raw pseudorange / carrier if the module supports it

Record the data in a simple CSV or parquet file named like:
- `gps_pvt.csv`
- `gps_clock.csv`
- `gps_raw.csv`
- `gps_sat.csv`

### 5.2 Cube Orange

Capture:
- IMU acceleration
- barometer altitude
- GNSS position / velocity streams from the controller
- time alignment between controller logs and GPS logs

Suggested files:
- `imu.csv`
- `baro.csv`
- `controller_gnss.csv`

### 5.3 RTL-SDR

Capture raw IQ or equivalent sample recordings for the L1 RF path:
- `rtl_iq.bin`
- `rtl_iq_metadata.json`

If only a raw capture file is available, include a simple metadata file describing:
- sample rate
- center frequency
- gain
- duration
- antenna path

### 5.4 Conducted replay (if used)

When performing a spoofed bench capture:
- use only conducted replay through attenuators
- use a shielded enclosure or cable path
- never transmit over the air
- record the exact path and attenuation used in metadata

## 6. Bench recording procedure

### Step 1 — hardware check

Before recording, verify:
- GPS module model and message support
- Cube Orange log rate and availability
- RTL-SDR sample rate and antenna setup
- Jetson runtime readiness
- all cables are connected correctly

### Step 2 — clean baseline

Record at least one clean session of fixed duration, such as 60 to 180 seconds.

Procedure:
1. start the GPS logger
2. start the Cube Orange logger
3. start the RTL-SDR capture
4. wait 10 seconds for synchronization
5. collect data for the chosen duration
6. stop all sources
7. store the raw files in the session folder

### Step 3 — attacked replay

Record one attacked bench session with a known onset time and attack type.

Procedure:
1. keep the same receiver and antenna configuration as the clean baseline
2. specify the attack type in metadata
3. trigger the conducted replay at the chosen onset time
4. monitor the GPS module and controller logs for the onset
5. record the attack onset in seconds from the beginning of the session
6. save all files in the attacked session folder

## 7. Schema validation for bench data

Before accepting a session, validate the required columns against the detector schema.

Minimum required columns for a session dataframe:
- `timestamp`
- `label`
- `attack_type`
- `attack_onset_s`
- `session_id`
- `t_gnss_s`
- `cn0_dbhz`
- `clk_bias_ns`
- `clk_drift_nsps`
- `pr_m`
- `gnss_lat`
- `gnss_lon`
- `imu_ax`
- `baro_alt`

Use the same canonical schema as the simulator before running detector evaluation.

## 8. Validation commands

Run the project validation before claiming the dataset is usable:

```bash
cd '/home/dronalab/Desktop/10 Layer archi'
python -m pytest -q
```

Then validate the bench session using the package CLI or a custom loader script:

```bash
python -m ten_layer_detector.cli --mode generate --duration-s 60 --sample-rate-hz 10 --attack-type ramp --attack-onset-s 12
python -m ten_layer_detector.cli --mode evaluate --duration-s 60 --sample-rate-hz 10 --attack-type ramp --attack-onset-s 12
```

For real bench data, the validation is a comparison against the same canonical schema and a feature-distribution check.

## 9. Sim-to-real gate

Before moving to any generated-data or flight phases, complete this gate:

1. compare clean simulated and clean real feature distributions
2. compare C/N0, DOP, residuals, clock Allan deviation, and pseudorange behavior
3. check whether the detector generalizes from simulated clean to real clean data
4. report the sim-to-real gap explicitly
5. only proceed if the gap is understood and bounded

If the real bench data does not validate against the simulator or the detector fails on the clean control, do not proceed to the next phase.

## 10. Minimal bench report structure

Create a short report under `bench/README.md` with:
- date and operator
- hardware inventory summary
- clean session list
- attacked session list
- data quality notes
- schema validation status
- sim-to-real comparison summary
- blockers and next actions

## 11. Safety notes

- No over-the-air GNSS spoofing.
- Only conducted replay is allowed for active attacks.
- Keep the bench environment shielded and controlled.
- Do not move to flights unless the bench phase is validated and the safety plan is approved.

## 12. What is considered success

The bench phase is complete when:
- at least one clean benchmark session is recorded
- at least one attacked benchmark session is recorded
- the raw logs are stored with metadata
- the session files validate against the canonical schema
- the detector can ingest the session with no silent missing-column failures
- the sim-to-real comparison is documented with known deviations

This is the gate before generating new data or attempting any flight test.
