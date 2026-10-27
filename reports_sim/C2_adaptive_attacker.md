# C2: white-box adaptive attacker (simulated)

Plan committed before any run: `configs/simplan_c2.json` (`9571f6d`, 2026-10-27). Simulated data only. The attacker knows the trained detector (LightGBM, `configs/sim_v3.json`, fitted and calibrated on `sim_fa2`, unchanged), its alarm threshold (4.077) and the persistence rule. For each of 150 simulated worlds per family it tries every value of one free parameter on a fixed grid and keeps the largest one that is not alarmed on after the attack starts (onset 20 s, session 60 s). Two variants: the default attacker (C/N0 raised, geometry as sampled) and the matched-power attacker of C1. Results: `results/c2_adaptive.json`.

## Detection at each fixed value (non-adaptive curve)

Ramp (final offset = rate × 40 s):

| rate, m/s | 0.05 | 0.1 | 0.2 | 0.3 | 0.5 | 0.75 | 1.0 | 1.5 | 2.0 |
|---|---|---|---|---|---|---|---|---|---|
| default attacker | 0.89 | 0.90 | 0.96 | 0.99 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| matched power | 0.36 | 0.35 | 0.38 | 0.71 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

Consistent takeover (acceleration for 5–15 s, then constant velocity):

| accel, m/s² | 0.01 | 0.02 | 0.05 | 0.1 | 0.15 | 0.2 | 0.3 |
|---|---|---|---|---|---|---|---|
| default attacker | 0.85 | 0.87 | 0.89 | 0.95 | 0.96 | 0.97 | 0.98 |
| matched power | 0.19 | 0.19 | 0.22 | 0.28 | 0.30 | 0.37 | 0.59 |

## What the adaptive attacker achieves (worst case over its search)

| | Finds an undetected value | Undetected offset ≥ 25 m | ≥ 50 m | ≥ 100 m | Median / 90th percentile undetected offset |
|---|---|---|---|---|---|
| Ramp, default attacker | 0.11 | 0.00 | 0.00 | 0.00 | 0 / 2 m |
| Ramp, matched power | 0.65 | 0.00 | 0.00 | 0.00 | 8 / 12 m |
| Consistent takeover, default attacker | 0.15 | 0.05 | 0.03 | 0.01 | 0 / 10 m |
| **Consistent takeover, matched power** | **0.82** | **0.73** | **0.64** | **0.25** | **77 / 128 m** |

## What it shows

- **A careful consistent takeover defeats the detector most of the time.** With matched power and geometry, the attacker can steer the vehicle off its path by 50 m or more without an alarm in 64% of worlds, and by 100 m or more in 25% (largest on the grid 145 m). This is the central weakness in the simulated results.
- **Ramps are bounded.** Even a careful attacker cannot ramp faster than about 0.3 m/s (a 12 m final offset) unseen, because a ramp changes position without matching velocity and the position–velocity check catches it. The residual risk is slow drifts.
- **Against the default attacker the detector holds up.** Undetected offsets of 25 m or more occur in at most 5% of worlds (consistent takeover only).
- Detection of the default attacker at tiny rates (0.89 at 0.05 m/s) shows the detector alarms on the C/N0 cue there, not on the path — the same dependence seen in C1.

## Limits

- One free parameter per family, a fixed grid, white-box access. A stronger attacker (more parameters, finer search, joint power and path optimisation, adaptive onset) could do better, so these are lower bounds on the worst case.
- 150 worlds per cell; shares are therefore known to roughly ±4–8 percentage points.
- Detector unchanged. A detector hardened against this attacker (for example trained with matched takeovers, or with a stronger IMU check) is a separate logged change, to be tested on a new set.
- The gate targets are unchanged. Against this attacker the consistent-takeover target (0.85) would not be met (0.18–0.59 depending on acceleration).
