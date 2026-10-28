# Datasets (not in the archive; rebuilt from seeds)

All use `configs/sim_v2.json` and the commands below. Rebuild, then check with
`python -m ten_layer_detector.dataset_hash datasets/<name>`. Regeneration was checked to be bit-for-bit deterministic (same seed, same hash).

| Name | Use | Command (after `python -m ten_layer_detector.cli --config configs/sim_v2.json generate`) | Sessions | Hash (sha256, first 16) |
|---|---|---|---|---|
| `sim_fa2` | train, calibration, validation (selection) | `--out datasets/sim_fa2 --n-clean 4000 --n-per-attack 60 --seed 4444` | 4420 | `1cfed463a74b3576` |
| `sim_test2` | v3 test, opened once | `--out datasets/sim_test2 --n-clean 6000 --n-per-attack 150 --seed 9999` | 7050 | `52a2cac0c128f4e5` |
| `sim_weak` | v3 weak-power (0-1 dB) | `--out datasets/sim_weak --n-clean 100 --n-per-attack 60 --seed 7777 --power-range 0 1` | 520 | `4b6fbeb77e7def34` |
| `sim_test3` | pre-registered three-model test | `--out datasets/sim_test3 --n-clean 6000 --n-per-attack 150 --seed 6666` | 7050 | `af453a77bf15a97a` |
| `sim_weak3` | pre-registered weak-power | `--out datasets/sim_weak3 --n-clean 100 --n-per-attack 60 --seed 5555 --power-range 0 1` | 520 | `92cafa8ce659b7fa` |
| `sim_test4` | pre-registered LightGBM confirmation | `--out datasets/sim_test4 --n-clean 6000 --n-per-attack 150 --seed 3131` | 7050 | `daede0a5e2628fa8` |
| `sim_weak4` | pre-registered weak-power | `--out datasets/sim_weak4 --n-clean 100 --n-per-attack 60 --seed 2121 --power-range 0 1` | 520 | `f3812adb3c54fb39` |
| `sim_test5` | gate test, read once | `--config configs/sim_v3.json --out datasets/sim_test5 --n-clean 6000 --n-per-attack 150 --seed 4242` | 7050 | `dcbe2fd67d9807f6` |
| `sim_weak5` | gate weak-power test | `--out datasets/sim_weak5 --n-clean 100 --n-per-attack 150 --seed 2424 --power-range 0 1` | 1150 | `ca991614e120e3f2` |
| `sim_weakval` | weak-power validation (tuning) | `--out datasets/sim_weakval --n-clean 300 --n-per-attack 150 --seed 1212 --power-range 0 1` | 1350 | `75380847c1587a25` |
| `sim_weaktrain` | weak-power training experiment (rejected) | `--out datasets/sim_weaktrain --n-clean 1 --n-per-attack 150 --seed 1313 --power-range 0 1` | 1051 | `34e1a04286eba2c7` |
| `sim_default1` | C1 baseline (default attackers) | `--config configs/sim_v3.json --out datasets/sim_default1 --n-clean 300 --n-per-attack 150 --seed 6161` | 1350 | `d694c8538f398625` |
| `sim_matched1` | C1 matched-power attackers | `--out datasets/sim_matched1 --n-clean 300 --n-per-attack 150 --seed 6060 --matched-power` | 1350 | `2496a0678c013a0f` |

Earlier rounds: `sim_v1`, `sim_dev` (first comparison), `sim_fa` (small, 1620 sessions, used for quick feature checks), `sim_test` (v2 test, used once). Their generation commands are in README.md and STATUS.md; `sim_test` is `--n-clean 1500 --n-per-attack 60 --seed 8888`.

## v4 world (configs/sim_v4.json; built by `ten_layer_detector/world_v4.py`, all use realistic IMU, ionosphere, multipath, four platform classes, half matched-power attackers)

| Name | Use | Command | Sessions | Hash (sha256, first 16) |
|---|---|---|---|---|
| `sim_v4_val` | train, calibration, validation (all v4 choices) | `python -m ten_layer_detector.world_v4 --out datasets/sim_v4_val --seed 41000 --n-clean 1000 --n-per-attack 15` | 4420 | `0a2d4fc093fbcf33` |
| `sim_v4_weakval` | weak-power validation | `... --out datasets/sim_v4_weakval --seed 42000 --n-clean 25 --n-per-attack 15 --weak` | 520 | `cc2260c32a5305f3` |
| `sim_v4_fahold` | clean-only false-alarm hold-out | `... --out datasets/sim_v4_fahold --seed 45000 --n-clean 750 --n-per-attack 0` | 3000 | `e3b48d0949ca9fe3` |
| `sim_v4_test` | v4 test, opened once | `... --out datasets/sim_v4_test --seed 43000 --n-clean 1500 --n-per-attack 40` | 7120 | `f9158bccb30cca2d` |
| `sim_v4_weaktest` | v4 weak-power test, opened once | `... --out datasets/sim_v4_weaktest --seed 44000 --n-clean 50 --n-per-attack 40 --weak` | 1320 | `dae37c57d9a1add9` |
| `sim_v5_cal` | v5 false-alarm fix: threshold calibration (clean only) | `python -m ten_layer_detector.world_v4 --out datasets/sim_v5_cal --seed 51000 --n-clean 1500 --n-per-attack 0` | 6000 | `c6dd390c46f5e15f` |
| `sim_v5_val` | v5 fix choice (validation) | `... --out datasets/sim_v5_val --seed 52000 --n-clean 1000 --n-per-attack 30` | 4840 | `618db6d845eda8bf` |

`sim_v5_test` (seed 53000) and `sim_v5_weaktest` (seed 54000) are planned in `configs/v5_plan.json` but were not generated: no fix passed the choice rule.

## Round 2 (v5 world, configs/sim_v5.json; commands in that file, built by `world_v4.py --quiet-json configs/sim_v5.json`)

| Name | Use | Sessions | Hash (sha256, first 16) |
|---|---|---|---|
| `sim_r2_val` | train, calibration, validation | 4420 | `dbb850779ae3e0b8` |
| `sim_r2_weakval` | weak-power validation | 520 | `83e4e900284e59f4` |
| `sim_r2_fahold` | clean-only per-type false-alarm check | 3000 | `2cfdf2c045c527b4` |
| `sim_r2_test` | round 2 test, opened once | 7120 | `2917ef6fd711fccf` |
| `sim_r2_weaktest` | weak-power test, opened once | 1320 | `3c215d163f000177` |
| `sim_r2_resettest` | attackers reset the lock at onset (`--force-reset`), opened once | 1120 | `b194c99dd5293428` |

`sim_r2_cal` (Step 4) was not generated. Real clean recordings used for calibration: Nayfeh et al. `Clean.xlsx` (12 sheets), not part of this repository.
