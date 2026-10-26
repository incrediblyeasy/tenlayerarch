# Ten-Layer GNSS Spoofing Detector — simulation phase

This package implements the simulation phase of [TEN_LAYER_PLAN.md](TEN_LAYER_PLAN.md): one physics-based generator, ten causal detector layers, a fitted vote, and an evaluation protocol on disjoint sessions. **All results are on simulated data.** Nothing here is a bench or flight result; clock, sensor and spoofer parameters are assumptions until calibrated on hardware.

Results: [results/sim_v1/REPORT.md](results/sim_v1/REPORT.md) (first protocol run), [reports_v3/DECISION_NOTE.md](reports_v3/DECISION_NOTE.md) (current model selection and the single test-set run; `reports_v2/` is the earlier 19-feature round).

## Quick start

```bash
python -m pip install -e .            # or: pip install -r requirements.txt
python -m pytest -q                   # behaviour tests (about 1 minute)

# Reproduce the reported results (config: configs/sim_v1.json)
python -m ten_layer_detector.cli --config configs/sim_v1.json generate --out datasets/sim_v1
python -m ten_layer_detector.cli --config configs/sim_v1.json evaluate --data datasets/sim_v1 --out results/sim_v1
python -m ten_layer_detector.cli --config configs/sim_v1.json generate --out datasets/sim_dev --n-clean 200 --n-per-attack 60 --seed 1111
python -m ten_layer_detector.cli --config configs/sim_v1.json compare --data datasets/sim_dev --out reports

python -m ten_layer_detector.cli demo  # small end-to-end run: one clean and one attacked session
```

Generating `sim_v1` takes about 1 minute; `evaluate` about 4 minutes (two runs: with and without C/N0); `compare` about 5 minutes.

## What is implemented

| Part | File | What it does |
|---|---|---|
| Simulator | `sim/` (`generate.py` is the only generator) | Smooth 3D trajectory; 10 satellites with DOP from geometry; two-state clock; IMU and barometer with bias and drift; Gauss-Markov GNSS error; a Galileo-only second solution. Nuisances in every class: C/N0 occlusions that drop satellites, multipath jumps, per-session C/N0 gain. Seven attacks (static, step, ramp, step-then-ramp, ramp-then-step, consistent takeover, dynamic takeover) with per-session attacker parameters: spoofer power 0–10 dB, clock coupling, geometry change, lock reset, whether Galileo is spoofed too. Clean and attacked sessions with the same seed are identical before onset. |
| Features | `features.py` | 19 causal per-row residuals (incl. signed C/N0, satellite-drop, HDOP-rise and a dead-reckoning residual) (backward differences, trailing windows, session baseline frozen after the first 10 s). |
| Layers | `layers/l01`–`l10` | Each returns one score per row, is fitted on clean training sessions (layer 10 on clean and attacked), raises `MissingInputError` on missing inputs, and alarms only against a threshold frozen on calibration sessions with k = 3 persistence. |
| Vote | `vote.py`, `pipeline.py` | Logistic regression on out-of-fold layer scores (3 folds by session); equal-weight baseline; multinomial attack naming. Two operating points: 99.9th percentile of clean calibration rows, and the threshold that gives ≤ 1 false alarm/h on clean calibration sessions. |
| Protocol | `evaluate.py`, `metrics.py`, `splits.py` | Train / calibration / test split by session (50/20/30, stratified by type). Reports detection rate per attack type with 95 % Wilson intervals, false alarms per hour, median and 90th-percentile delay, ablation, the run without C/N0, detection by spoofer power, naming confusion matrix. |
| Model comparison | `model_selection.py`, `dashboard.py` | Tests T1–T7 of MODEL_SELECTION.md, all measured, on a separate development dataset. |
| Config | `config.py`, `configs/sim_v1.json` | Every setting in one versioned file; `results/*/config_frozen.json` records thresholds and vote weights. |
| Hardware I/O | `io/ubx.py`, `io/dataflash.py`, `io/rtl_iq.py`, `time_base.py`, `bench_latency.py` | UBX framing with checksum check; NAV-PVT, NAV-CLOCK, NAV-SAT and RXM-RAWX decoders; incremental `UBXStream` and `read_serial` for live use; DataFlash `.bin` reader (Cube Orange); `io/assemble.py` joins decoded UBX messages into one detector row per epoch and merges IMU, attitude and barometer from a DataFlash log; RTL-SDR 8-bit IQ read/write; time-offset fit and 5 ms acceptance test; full-pipeline latency. Tested on synthetic frames only. |

## Not done yet (outside the simulation phase or not possible on simulated data)

- **DataFlash** (`io/dataflash.py`) is written to the ArduPilot log format and tested on a synthetic log only; `io/mavlink_log.py` still reads text/CSV.
- **RXM-RAWX, `UBXStream`, `read_serial`** are tested on synthetic bytes only; no live module has been connected. `io/assemble.py` builds detector rows from them (round-trip tested on synthetic frames), but a real recording will lack some simulator columns (e.g. the Galileo-only solution), so a model must be retrained on the available columns first.
- **Nayfeh loader** (`io/nayfeh_loader.py`) is unchanged: first sheet only, no 1e-7 scale conversion.
- **UBX decoders** are written to the u-blox interface description but not yet checked against a recorded log from our module, whose model is still unconfirmed.
- **Layer 3** cannot recompute DOP: the schema has no per-satellite azimuth/elevation (needs NAV-SAT on hardware).
- **Layer 7** reads receiver raw measurements here; on hardware it is meant to use RTL-SDR tracking.
- **Latency** must be measured on the Jetson.
- Sim-to-real checks (plan section 5.2) need bench recordings.

## Layout

```
ten_layer_detector/
  sim/          generator: trajectory, gnss_model, clock_model, sensors, attacks, generate
  features.py   causal per-row residuals
  layers/       base.py + ten layers
  vote.py       logistic vote, equal-weight vote, attack naming
  pipeline.py   TenLayerDetector (fit, calibrate, score, detect)
  evaluate.py   protocol
  metrics.py    rates, Wilson intervals, FA/h, delay
  reporting.py  results files
  model_selection.py, dashboard.py
  io/, time_base.py, bench_latency.py
configs/sim_v1.json
tests/          behaviour tests
results/sim_v1/ protocol results     results/before_fix_sim_v0/  the first test of the old code
reports/        model comparison     backup/  archive of the code before these changes
```
