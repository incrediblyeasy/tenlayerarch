# Test of the detector on simulated dataset `sim_v1`

Simulation only. These numbers say nothing about bench or flight performance.

## Dataset

`datasets/sim_v1/` (built by `scripts/make_sim_dataset.py`, seed 2026, ~14 s to rebuild):

- 550 sessions, 60 s at 10 Hz, 330 000 rows, canonical schema plus `cn0_std_dbhz`.
- 200 clean, 50 each of: static, step, ramp, step_then_ramp, ramp_then_step, consistent_takeover, dynamic_takeover. Onset is uniform in 15 to 35 s.
- Physics: smooth 3D trajectory, 10 satellites with DOP from geometry, two-state clock, IMU and barometer with bias and drift, Gauss-Markov GNSS error.
- Nuisances in every class: C/N0 occlusion dips that drop satellites, multipath position jumps, per-session C/N0 gain offset.
- Per-session attacker parameters, stored only in `sessions_meta.json`:
  - spoofer power, 0 to 10 dB;
  - clock coupling, p = 0.5 (0.3 for takeovers);
  - geometry change, p = 0.5 (0.3 for takeovers);
  - lock reset, p = 0.5.
- Takeovers keep the reported velocity equal to the derivative of the spoofed position (checked: under 0.03 m/s), with acceleration under about 2.6 m/s².

## Protocol

`scripts/evaluate_on_dataset.py`, split seed 7:

- Session-disjoint split, stratified by type. Train: 120 clean and 30 per attack type. Test: 80 clean and 20 per attack type.
- Thresholds are the 99th percentile of clean **training** scores. All rates are measured on held-out sessions, at session level (any alarm in the session).
- Detection delay is not measured, because the layers return one score per session.

## 1. The ten layers (unchanged package code)

| Layer | AUC | False alarm | Detection | With in-code threshold (FA / det.) |
|---|---|---|---|---|
| 1 time domain | 0.33 | 0.03 | 0.02 | 1.00 / 0.76 |
| 2 signal quality | 0.80 | 0.08 | 0.65 | 0.99 / 0.99 |
| 3 geometry | 0.44 | 0.01 | 0.12 | 1.00 / 1.00 |
| 4 multi-constellation | 0.42 | 0.03 | 0.01 | 1.00 / 1.00 |
| 5 cross-domain | 0.41 | 0.01 | 0.01 | 1.00 / 1.00 |
| 6 physical | 0.46 | 0.04 | 0.01 | 1.00 / 1.00 |
| 7 raw signal | 0.52 | 0.00 | 0.03 | 1.00 / 1.00 |
| 8 temporal anomaly | 0.47 | 0.03 | 0.01 | 0.00 / 0.00 |
| 9 Allan | 0.70 | 0.00 | 0.07 | 0.00 / 0.00 |
| 10 learned | 0.92 | 0.03 | 0.69 | 1.00 / 1.00 |

- Eight of ten layers detect almost nothing, even though the dataset contains the signals they are meant to read (see section 3).
- Layers 2 and 10 detect through C/N0. Layer 10's formula, the mean of lat, acc_x and C/N0, is not a model; it reacts to the C/N0 rise by accident.
- The hand-set thresholds in the code are unusable: they alarm on every session, or on none.

## 2. `model_selection` candidates (package session features)

| Model | With package features (leak) FA / det. | Leak removed FA / det. |
|---|---|---|
| hist_gradient_boosting | 0.00 / 1.00 | 0.01 / 0.98 |
| random_forest | 0.00 / 1.00 | 0.05 / 0.95 |
| decision_tree | 0.00 / 1.00 | 0.03 / 0.91 |
| logistic_regression | 0.00 / 1.00 | 0.05 / 0.86 |
| extra_trees | 0.00 / 1.00 | 0.04 / 0.85 |
| rbf_svm | 0.01 / 1.00 | 0.06 / 0.84 |
| linear_svm | 0.00 / 1.00 | 0.13 / 0.83 |
| knn | 0.08 / 0.89 | 0.13 / 0.78 |
| isolation_forest | 0.04 / 0.14 | 0.03 / 0.21 |

- With the package's feature vector, `attack_ratio` and `onset_offset` give every supervised model a perfect score. These features must be removed from `model_selection._session_feature_vector`.
- With them removed, the best supervised model, gradient boosting, still detects 0.98 at 0.01 false alarms. It relies on C/N0: the top single features are `cn0_dbhz_delta` (AUC 0.97) and `cn0_dbhz_std`. Without the C/N0 features, detection is 0.90 at a **0.31** false-alarm rate.
- These are whole-session summaries, so they are not causal and cannot give a detection delay.

## 3. Reference check: is the dataset detectable, and through what?

Physics residuals computed within each session, against its first 10 s.

| Feature | AUC alone |
|---|---|
| C/N0 rise | 0.99 |
| C/N0 spread drop | 0.95 |
| GNSS alt − baro | 0.85 |
| Position vs velocity | 0.78 |
| GNSS acceleration vs IMU | 0.70 |
| Clock drift step | 0.70 |
| Lock resets | 0.70 |
| HDOP change | 0.61 |
| Satellite-count change | 0.50 |

| Reference model | AUC | FA | Detection |
|---|---|---|---|
| Logistic regression, all features | 0.99 | 0.00 | 0.96 |
| Random forest, all features | 0.995 | 0.03 | 0.90 |
| Logistic regression, without C/N0 | 0.94 | 0.03 | 0.84 (ramp 0.65, step_then_ramp 0.65) |
| Random forest, without C/N0 | 0.97 | 0.09 | 0.90 |

Random forest with all features, detection by spoofer power:

| Spoofer power | Sessions | Detection |
|---|---|---|
| 0–1 dB | 20 | 0.40 |
| 1–3 dB | 28 | 0.93 |
| 3–6 dB | 38 | 1.00 |
| 6–10 dB | 54 | 1.00 |

## Conclusions

1. The dataset is detectable by physically meaningful checks: barometer, position-velocity, IMU and clock, not only C/N0. The package's layers 1 and 3 to 9 do not pick this up. The layer formulas, not the data, are the bottleneck.
2. The model comparison in `reports/` (winner `hist_gradient_boosting`, detection 1.0) is produced by the label leak. Without the leak, the ranking still holds on this dataset, but it depends on C/N0.
3. Low-power spoofing (0–1 dB) is the weak case: 0.40 detection even for the reference model.
4. The C/N0 dominance is partly a simulator choice: every spoofer adds 0 to 10 dB. Results without C/N0 are the more conservative ones.
5. Counts are small: 20 test sessions per attack type, so a 95% interval is about ±0.2. The plan asks for 50 per type before any rate is reported as a result. Re-run with `--n-per-attack 125` for that.

## Reproduce

```bash
.venv/bin/python scripts/make_sim_dataset.py --out datasets/sim_v1
.venv/bin/python scripts/evaluate_on_dataset.py --data datasets/sim_v1 --out results/sim_v1
```
