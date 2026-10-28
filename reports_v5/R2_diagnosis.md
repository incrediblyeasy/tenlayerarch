# Round 2 Step 1: nuisance rates, real clean recordings against the simulator

Pre-registered in `configs/nuisance_measure_v5.json` (commit 9b4f328) before any rate was computed; code `ten_layer_detector/nuisance.py`, `nuisance_run.py`, results `results/nuisance_v5.json`. Real data: the 12 clean Nayfeh et al. recordings from `ML implementaion nayfeh/.../Collected dataset/*/Clean.xlsx` (COEX Clover, PX4 GPS fields, about 5 Hz, 63.9 minutes in total). Simulated data: clean sessions of `sim_v4_fahold` (3000 sessions) and `sim_fa2` (4000). Rates are episodes per minute of clean flight; real interval = bootstrap over the 12 recordings, simulator interval = bootstrap over sessions.

Inputs the plan named (`PUBLIC_DATASET_PLAN.md`, `PUBLIC_DATASET_CANDIDATES.md`) do not exist in the repository; the Nayfeh files were the only real clean GNSS data on this machine. Each sheet joins several flights, so sheets were cut at gaps (time step above 1 s or not positive); one sheet (`test_35m_dyn2`) had no header row and was read with the standard column names.

## Primary comparison (pre-registered threshold per family)

| Family | Real (95% interval) | Simulator v4 world | Verdict | Simulator original (sim_fa2) | Verdict |
|---|---|---|---|---|---|
| Satellite count drop >= 1 in 1 s | 2.07 (1.46-2.70) | 13.98 | much_more_active | 6.21 | much_more_active |
| Satellite count rise >= 1 in 1 s | 2.15 (1.51-2.89) | 13.90 | much_more_active | 6.13 | much_more_active |
| HDOP change >= 0.2 in 1 s | 1.08 (0.64-1.58) | 10.05 | much_more_active | 4.42 | much_more_active |
| Position minus velocity integral >= 3 m in 1 s | 0.00 (0.00-0.00) | 1.66 | much_more_active | 0.54 | much_more_active |

## Other thresholds (also pre-registered)

| Metric | Real | Simulator v4 | Simulator original |
|---|---|---|---|
| sat_drop>=2 | 0.11 (0.04-0.19) | 1.07 | 0.64 |
| sat_drop>=3 | 0.00 (0.00-0.00) | 0.20 | 0.17 |
| sat_rise>=2 | 0.08 (0.03-0.14) | 1.06 | 0.62 |
| sat_rise>=3 | 0.00 (0.00-0.00) | 0.18 | 0.16 |
| hdop_jump>=0.1 | 1.85 (1.20-2.45) | 14.64 | 6.39 |
| hdop_jump>=0.5 | 0.09 (0.02-0.19) | 4.24 | 1.99 |
| position_jump>=2.0 | 0.00 (0.00-0.00) | 25.80 | 3.80 |
| position_jump>=5.0 | 0.00 (0.00-0.00) | 0.48 | 0.41 |

**Decision by the pre-registered rule: 4 of 4 families are much more active in the simulator, so H1 holds (simulator artifact) and the plan moves to Step 2.** The position-jump verdict is degenerate: real data has zero such episodes, so the real interval is 0-0 and any simulated rate counts as 'much more active'. It does not change the decision: with the rule of three (0 events in 63.9 min gives an upper bound near 0.05 per minute), the simulator's 1.66 per minute is still more than 30 times that.

What the numbers say: the simulator's satellite count changes about 7 times as often as the receiver's in the real recordings (14 against 2 per minute), HDOP jumps about 9 times as often (10 against 1.1), and the original simulator is already 3-4 times too active. The v4 world is worse than the original because its multipath option adds C/N0 fluctuation. Reading the generator, the cause is plain: a satellite counts as used when its C/N0 is above 28 dB-Hz at each sample, and every sample carries independent 1 dB noise (plus the multipath fluctuation), so satellites near the threshold flicker in and out; a real receiver's solution holds satellites steadily.

Caveats (from the pre-registration): 12 recordings, about 64 minutes, one drone and receiver, one open-sky site at 20-70 m, so a quiet site may under-state the nuisances of other places; `satellites_used` and HDOP are what the PX4 driver reports, not visible satellites; lock resets could not be measured (no flag, no pseudorange), so the simulator's lock-reset behaviour is still unvalidated; the real data has no C/N0, so the signal-strength features cannot be checked against it. Labels: real clean and simulated are kept separate.
