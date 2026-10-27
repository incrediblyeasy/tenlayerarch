# A4 model candidates on the v4 world (simulated, validation data only)

Rule files: `configs/model_grid_v4.json`, `configs/selection_rule_v4.json` (committed before any v4 data). Features: the 20 v3 features (A2 result), persistence 5 (A3 result), calibration margin 0.5 FA/h. FA is measured on `sim_v4_fahold` (41.7 clean hours; 'upper' is the 95% upper bound from the event count). Robustness = mean of weak detection, unseen-attack detection and weak consistent takeover. No-strength = refit without C/N0, HDOP and satellite-count features. Validation consistent-takeover has 18 sessions and weak consistent-takeover 60, so differences of 0.05-0.10 are inside noise.

| Candidate | Detection | Matched-power | Consistent takeover | Weak detection | Weak consistent takeover | FA/h hold-out (upper 95%) | Median / p90 delay (s) | No-strength detection | Unseen | Robustness |
|---|---|---|---|---|---|---|---|---|---|---|
| M1_one_class_svm | 0.786 | 0.731 | 0.61 | 0.788 | 0.43 | 0.62 (0.91) | 0.5 / 22.1 | 0.825 | 0.786 | 0.669 |
| M1_lightgbm | 0.817 | 0.701 | 0.50 | 0.745 | 0.15 | 0.22 (0.41) | 4.5 / 17.8 | 0.825 | 0.873 | 0.589 |
| M1_xgboost | 0.841 | 0.746 | 0.56 | 0.762 | 0.12 | 0.58 (0.86) | 5.3 / 17.3 | 0.841 | 0.802 | 0.560 |
| M2_ensemble_0.25 | 0.897 | 0.836 | 0.83 | 0.845 | 0.50 | 0.98 (1.33) | 1.2 / 16.7 | 0.802 | 0.857 | 0.734 |
| M2_ensemble_0.5 | 0.841 | 0.761 | 0.67 | 0.802 | 0.38 | 0.29 (0.50) | 3.1 / 18.4 | 0.802 | 0.857 | 0.681 |
| M2_ensemble_0.75 | 0.833 | 0.746 | 0.61 | 0.781 | 0.25 | 0.34 (0.56) | 3.2 / 18.1 | 0.817 | 0.849 | 0.627 |
| M3_temporal | 0.873 | 0.791 | 0.72 | 0.843 | 0.45 | 0.43 (0.68) | 1.7 / 14.7 | 0.833 | 0.817 | 0.703 |
| M4_autoencoder | 0.698 | 0.642 | 0.39 | 0.757 | 0.32 | 0.82 (1.14) | 0.5 / 22.9 | 0.722 | 0.698 | 0.591 |

**Selected by the rule: `M2_ensemble_0.25`** (0.25 LightGBM + 0.75 one-class SVM, rank-averaged). It had the highest detection (0.897) and robustness (0.734); `M3_temporal` is within the 0.05 margin on both scores (detection 0.873, robustness 0.703), so the two were tied and the rule's tie-break (lowest median delay, 1.23 s against 1.65 s) chose the ensemble; every other candidate is more than 0.05 behind on at least one score. It is eligible only narrowly: hold-out FA 0.98/h against the limit of 1.0, with an upper 95% bound of 1.33/h. The pre-registered target of an upper bound of at most 1 is therefore likely to be missed on the test set.

Observations:
- Single models (SVM 0.786, LightGBM 0.817, XGBoost 0.841) detect less than the ensemble or the temporal model on this harder world; consistent takeover rises from 0.50 (LightGBM) to 0.83 (ensemble 0.25) but the ensemble weights are not monotone (0.5: 0.67, 0.75: 0.61), which is what noise at 18 sessions looks like.
- M3 (temporal summaries) is close: detection 0.873, weak consistent takeover 0.45, p90 delay 14.7 s (the best), FA 0.43/h; it was tied with the ensemble under the rule and lost on median delay. It is reported as variant V2 on the test sets.
- M4 (autoencoder, run because best validation consistent takeover was below 0.85, as the grid file required): detection 0.698, consistent takeover 0.39, FA 0.82/h. Not competitive.
- Signal strength is still not the only source of detection: the no-strength refits keep 0.80-0.84.
- No candidate reaches 0.85 weak consistent takeover on validation (best 0.50).
