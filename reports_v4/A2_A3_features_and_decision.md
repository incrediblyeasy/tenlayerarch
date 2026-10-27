# A2 features and A3 decision logic on the v4 world (simulated, validation data only)

Rules: `configs/feature_rule_v4.json`, `configs/model_grid_v4.json` (committed in 1e2abbc before any v4 data existed). Data: `sim_v4_val` (train/calibration/validation split by session, 4420 sessions), `sim_v4_weakval` (520 sessions, power 0-1 dB), `sim_v4_fahold` (3000 clean sessions, 41.7 h, used only to check false alarms). Hashes in DATASETS.md. Model: LightGBM, persistence 5, calibration margin 0.5 FA/h.

**Sampling noise:** the validation split holds only 18 consistent-takeover sessions and `sim_v4_weakval` 60 weak consistent-takeover sessions, so differences of 0.03-0.10 in those two columns are inside noise. The rule was applied as written anyway.

## A2. Feature sets

| Set | Features | Detection (all) | Matched-power | Consistent takeover | Weak detection | Weak consistent takeover | FA/h on hold-out (upper 95%) | p90 delay (s) | Qualifies |
|---|---|---|---|---|---|---|---|---|---|
| S_v3 | 20 | 0.817 | 0.701 | 0.500 | 0.745 | 0.150 | 0.22 (0.41) | 17.8 | baseline |
| S_all | 22 | 0.913 | 0.866 | 0.556 | 0.857 | 0.167 | 0.29 (0.50) | 15.3 | False |
| S_att | 20 | 0.905 | 0.851 | 0.500 | 0.840 | 0.083 | 0.17 (0.35) | 15.3 | False |
| S_att_ekf | 22 | 0.881 | 0.836 | 0.333 | 0.833 | 0.033 | 0.31 (0.53) | 12.5 | False |

**Result of the rule: `S_v3`.** No candidate raised consistent takeover by 0.03 on both the validation and the weak set. `S_all` (adds the two attitude-aware IMU features) raised overall detection 0.817 -> 0.913 and weak detection 0.745 -> 0.857 but its weak consistent-takeover gain is 0.017, below the margin; this is reported as an observation, not as a pass. The Kalman-filter features (`S_att_ekf`, M5) made consistent takeover worse (0.33 and 0.03 weak). The rule asks for gains on one attack type; it was written before data and was not changed after seeing that the larger gain is elsewhere.

### Drop-one ablation on the chosen set (reported only, nothing removed)

| Dropped | Detection | Consistent takeover | Weak detection | Weak consistent takeover | FA/h (hold-out) | p90 (s) |
|---|---|---|---|---|---|---|
| code_carrier_m | 0.833 | 0.556 | 0.783 | 0.200 | 0.17 | 16.9 |
| allan_dev_nsps | 0.841 | 0.611 | 0.755 | 0.117 | 0.24 | 17.5 |
| const_diff_m | 0.841 | 0.556 | 0.824 | 0.350 | 0.96 | 15.0 |
| dead_reckoning_m | 0.651 | 0.667 | 0.490 | 0.217 | 0.29 | 20.7 |
| baro_resid_m | 0.833 | 0.611 | 0.774 | 0.233 | 0.36 | 17.4 |
| imu_resid_long_mps2 | 0.865 | 0.667 | 0.788 | 0.250 | 0.34 | 17.6 |

Baseline `S_v3` for comparison: detection 0.817, consistent takeover 0.500, weak 0.745, weak consistent takeover 0.150, FA 0.22/h, p90 17.8 s. Dropping `dead_reckoning_m` costs the most (detection 0.651, weak 0.490); dropping `const_diff_m` raises weak consistent takeover (0.35) but pushes hold-out FA to 0.96/h. Single-run differences of a few points are not established.

F2 (pseudorange-ephemeris) was not built: the simulator has no per-satellite positions. F3 (AGC) is hardware-only. See the rule file.

## A3. Decision logic (LightGBM, `S_v3`)

| Rule | Detection | Consistent takeover | Weak detection | Weak consistent takeover | FA/h hold-out (upper 95%) | Median delay (s) | p90 delay (s) |
|---|---|---|---|---|---|---|---|
| persistence_k3 | 0.817 | 0.500 | 0.755 | 0.117 | 0.31 (0.53) | 4.4 | 17.5 |
| persistence_k5 | 0.817 | 0.500 | 0.745 | 0.150 | 0.22 (0.41) | 4.5 | 17.8 |
| persistence_k10 | 0.817 | 0.500 | 0.760 | 0.117 | 0.12 (0.28) | 4.9 | 18.3 |
| cusum_p90.0 | 0.889 | 0.722 | 0.817 | 0.300 | 0.60 (0.89) | 10.1 | 22.9 |
| cusum_p99.0 | 0.897 | 0.778 | 0.857 | 0.483 | 0.58 (0.86) | 5.6 | 18.7 |
| conformal_a0.01_k5 | 0.897 | 0.722 | 0.888 | 0.567 | 2.11 (2.60) | 1.9 | 14.1 |

**Result of the rule: `persistence_k5`.** The choice rule needed a rule with hold-out FA <= 0.7/h, detection within 0.01 of k=5 and a p90 delay at least 0.5 s better. None qualified: CUSUM p99 has p90 18.7 s (worse than 17.8 s), the conformal threshold at alpha 0.01 gives 2.1 FA/h on the hold-out (95% upper bound 2.6), well over 1/h; this is the finite-sample bound failing under distribution shift between calibration and hold-out sessions, so it is not a usable guarantee here.

Observation outside the rule: CUSUM with the 99th-percentile reference raises weak consistent takeover from 0.15 to 0.48 and weak detection from 0.745 to 0.857 at 0.58 FA/h (upper 95% 0.86), with a median delay of 5.6 s instead of 4.5 s. It slows detection of fast attacks while catching slow ones. It is carried to the test as a named, separately labelled variant (see the lock file), because the weak consistent takeover is the main open gap; the choice of that variant was made after seeing these validation numbers.
