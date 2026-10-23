# Ten-Layer Detector: Status Review of the Latest Upload

Reviewed: the upload `2da6d2c2-10_Layer_archi.zip` (package `ten_layer_detector`). Method: installed the requirements, ran the test suite, read the layer, vote, evaluation and I/O code, and ran the layers on the new simulator. Nothing in the code was changed.

## Summary

The package installs and its 9 tests pass. It is not yet a working detector. The tests check shapes and imports, not detection. When the layers are run on the new simulator, most of them receive none of their inputs, and the ones that run do not separate clean from attacked sessions.

## 1. What runs

| Item | Result |
|---|---|
| Install from `requirements.txt` | Works (numpy, pandas, pytest, scikit-learn) |
| `pytest` | 9 passed |
| New simulator `sim/generate.py` | Produces the canonical schema (`lat_deg`, `cn0_dbhz`, `pr_m`, `acc_bx_mps2`, ...) and metadata. Clean and attacked sessions are supported. |

## 2. Faults found by running the code

### 2.1 Layers do not receive their inputs (critical)

Each layer declares `required_columns`. Running every layer on 15 seeds of each session type, eight layers have missing inputs and return 0.0 without an error:

| Layer | Missing columns on the new schema |
|---|---|
| 4 multi-constellation | `gnss_lat`, `gnss_lon` |
| 5 cross-domain | `gnss_lat`, `imu_ax` |
| 6 physical | `imu_ax`, `baro_alt` |
| 7 raw signal | `pseudorange_m` |
| 8 temporal anomaly | `gnss_lat` |
| 9 Allan | `timestamp`, `gnss_lat` |
| 10 learned | `gnss_lat`, `imu_ax` |

The cause is that the layers still use the legacy column names, while the schema uses the canonical ones. A missing input gives 0.0, which looks like a normal score. There is no error.

### 2.2 The layers that do run do not detect (critical)

Mean score over 15 seeds per session type (clean, step, ramp, consistent takeover, dynamic takeover):

| Layer | Clean | Attacked types | Observation |
|---|---|---|---|
| 1 time domain | 0.084 | 0.084 for all types | Identical. The simulator does not change the clock, so the layer cannot see the attack. |
| 2 signal quality | 0.850 | 0.833 to 0.842 | Moves in the opposite direction to what a spoof produces, and the change is tiny (about 0.01 against a spread of 0.003). |
| 3 geometry | 0.737 | 0.737 for all types | Identical. |

### 2.3 Two simulators and two layer sets

- `simulator.py` (old) is what the CLI and pipeline use.
- `sim/generate.py` (new) is the canonical one.
- `layers/` (new package) and `legacy_layers.py` (old single-file copy, 154 lines) contain the same heuristics with different function signatures.

The CLI therefore still runs the old generator and the old layers, and the new code is not connected to anything the user can run.

### 2.4 The protocol does not measure detection (critical)

`evaluate.py`:

- Calls `calibrate` on training sessions, which sets a threshold, but never calls `fit`.
- Computes no detection rate, false alarms per hour, or delay.
- Its per-layer summary is the mean score over test sessions, which is not a detection result.

`layers/base.py`:

- `alarm()` sets its threshold from the 99.9th percentile of the scores it is applied to. When it is applied to test data, the threshold is taken from the test data. This is leakage.
- `score()` returns one number per session, not one causal score per row as the implementation guide requires. Persistence and per-row alarms cannot be computed from it.

### 2.5 The vote is not the designed vote

`vote.py` contains `weighted_vote`, which is a weighted average of the scores. It has no logistic regression, no fitting on out-of-fold scores, no threshold at a clean-data percentile, and no attack naming. Nothing calls it.

### 2.6 Hardware parsers

| Module | Result |
|---|---|
| `io/ubx.py`, `parse_nav_pvt` | Crashes on a valid 92-byte NAV-PVT payload: "requires a buffer of 27 bytes". The format string does not match the 24-byte slice it reads. Field names are also incomplete. |
| `io/ubx.py`, framing | Splits frames by sync bytes and length. Not tested on real logs. No checksum check. |
| `io/mavlink_log.py` | Reads text lines or CSV. It does not decode MAVLink messages and cannot read a Cube Orange stream or a DataFlash log. |
| `io/nayfeh_loader.py` | Reads only the first sheet of a workbook. Does not convert the 1e-7 degree latitude and longitude scale. Cannot reproduce the earlier Nayfeh results. |
| `io/rtl_iq.py` | Writes complex64 (8 bytes per sample). The RTL-SDR records 8-bit samples, so the file layout does not match the hardware. |
| `time_base.py` | `sync` only checks that two arrays have the same length. `align_offsets` returns a median, not an offset. The 5 ms acceptance test is not implemented. |
| `bench_latency.py` | Times one function call. It does not measure the full pipeline. |

### 2.7 Documentation

The README and the earlier status text describe the package as a "complete simulation-ready project shell" and say it "covers the core software architecture and validation flow". The checks above show that the validation flow is not implemented, so that wording should be removed.

## 3. What is in good shape

- The canonical schema and the metadata design are clear and match the implementation guide.
- The new simulator produces the required columns and supports clean sessions.
- Split-by-session logic exists and handles the single-session case.

## 4. Required fixes, in order

1. **Connect the layers to the canonical schema.** Rewrite each layer's inputs to the schema columns. A missing input must raise an error, not return 0.0.
2. **Remove the duplicate code.** Delete `legacy_layers.py` and the old simulator from the CLI path. Make the CLI use `sim/generate.py`.
3. **Make the layers per-row and causal.** Each layer returns one score per row using only past samples. Fit each layer on clean training sessions only.
4. **Implement the protocol.** Fit on training sessions, freeze thresholds at the 99.9th percentile of clean out-of-fold scores, then report detection rate per attack type, false alarms per hour, and delay on held-out sessions. Fix the leakage in `alarm()`.
5. **Verify on simulated data before hardware.** Each layer must separate clean from attacked sessions on the simulator, or it is reported as not working. Tests should check detection and false-alarm rates on seeds, not shapes.
6. **Implement the designed vote** (logistic regression on out-of-fold percentiles) and attack naming, then run ablation.
7. **Fix the hardware parsers** (UBX NAV-PVT field layout, MAVLink decoding, Nayfeh multi-sheet loading with unit conversion, 8-bit IQ writer, real time-offset computation) and test each against recorded data.
8. **Correct the documentation** to describe what is implemented.

## 5. Acceptance for "working"

The package is working when all of the following hold on simulated data, with thresholds frozen from clean sessions:

- No layer returns a score when an input is missing. It raises an error.
- Each layer's detection rate and false-alarm rate per hour are reported per attack type.
- The vote beats the best single layer on held-out sessions, or the report says it does not.
- Results are reproducible from a seed.

Hardware work is accepted separately, against recorded data from each device.
