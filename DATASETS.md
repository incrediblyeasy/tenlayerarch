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
