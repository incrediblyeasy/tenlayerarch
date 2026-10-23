# Ten-Layer GNSS Spoofing Detector — simulation phase

This package implements the simulation phase of [TEN_LAYER_PLAN.md](TEN_LAYER_PLAN.md): one physics-based generator, ten causal detector layers, a fitted vote, and an evaluation protocol on disjoint sessions. **All results are on simulated data.** Nothing here is a bench or flight result; clock, sensor and spoofer parameters are assumptions until calibrated on hardware.

Results: [results/sim_v1/REPORT.md](results/sim_v1/REPORT.md).

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
| Features | `features.py` | 14 causal per-row residuals (backward differences, trailing windows, session baseline frozen after the first 10 s). |
| Layers | `layers/l01`–`l10` | Each returns one score per row, is fitted on clean training sessions (layer 10 on clean and attacked), raises `MissingInputError` on missing inputs, and alarms only against a threshold frozen on calibration sessions with k = 3 persistence. |
| Vote | `vote.py`, `pipeline.py` | Logistic regression on out-of-fold layer scores (3 folds by session); equal-weight baseline; multinomial attack naming. Two operating points: 99.9th percentile of clean calibration rows, and the threshold that gives ≤ 1 false alarm/h on clean calibration sessions. |
| Protocol | `evaluate.py`, `metrics.py`, `splits.py` | Train / calibration / test split by session (50/20/30, stratified by type). Reports detection rate per attack type with 95 % Wilson intervals, false alarms per hour, median and 90th-percentile delay, ablation, the run without C/N0, detection by spoofer power, naming confusion matrix. |
| Model comparison | `model_selection.py`, `dashboard.py` | Tests T1–T7 of MODEL_SELECTION.md, all measured, on a separate development dataset. |
| Config | `config.py`, `configs/sim_v1.json` | Every setting in one versioned file; `results/*/config_frozen.json` records thresholds and vote weights. |
| Hardware I/O | `io/ubx.py`, `io/rtl_iq.py`, `time_base.py`, `bench_latency.py` | UBX framing with checksum check; NAV-PVT, NAV-CLOCK and NAV-SAT decoders; RTL-SDR 8-bit IQ read/write; time-offset fit and 5 ms acceptance test; full-pipeline latency. Tested on synthetic frames only. |

## Not done yet (outside the simulation phase or not possible on simulated data)

- **MAVLink / DataFlash** (`io/mavlink_log.py`) still reads text/CSV only; it needs `pymavlink` and a Cube Orange log.
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
