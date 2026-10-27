# B0: reproduction check (simulated data)

Date: 2026-10-27. Rebuilt `sim_test4` from seed 3131 with `configs/sim_v2.json` into a scratch directory: hash `daede0a5e2628fa8`, equal to DATASETS.md. `sim_fa2` on disk also hashes to `1cfed463a74b3576`.

LightGBM fitted on `sim_fa2` with `configs/sim_v2.json`, scored on `sim_test4`: the full summary is identical to `results/prereg4_lightgbm_test4.json` (detection 0.9914, 0.372 FA/h, delay median 1.483 s, p90 4.121 s, threshold 4.5846). Result: **pipeline reproduces exactly** (`results/b0_v2_lightgbm_test4.json`).

Side observation, not a new test: the adopted settings (`configs/sim_v3.json`, persistence 5, margin 0.5) scored on the same `sim_test4` give detection 0.993, **1.06 FA/h**, p90 3.1 s (`results/b0_v3cfg_lightgbm_test4.json`). sim_test4 was a test set of an earlier round; this number was not used for any choice. It agrees with the gate result: the sim_v3 settings trade lower delay for a false-alarm rate near 1/h on fresh data, and the calibration margin of 0.5 does not guarantee the target.
