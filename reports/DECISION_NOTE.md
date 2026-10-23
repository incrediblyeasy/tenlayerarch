# Decision note: model selection (MODEL_SELECTION.md §9, item 3)

Data: `datasets/sim_dev` (310 train / 124 calibration / 186 validation sessions). All 13 candidates, T1–T8 run. Test set not opened. Simulation only.

## Outcome: no winner

Rule §6 step 1 requires ≤ 1 false alarm/h on validation. **No candidate is eligible**, so by the rule the detector does not ship and the test set stays closed.

| Model | DR (T1) | FA/h | DR no strength (T3) | DR weak (T4) | DR unseen (T5) | Median delay s | T8: DR mean ± sd | T8: FA/h mean ± sd |
|---|---|---|---|---|---|---|---|---|
| One-class SVM | 0.937 | 1.2 | 0.952 | 0.889 | 0.937 | 0.30 | 0.938 ± 0.003 | 2.4 ± 1.1 |
| LightGBM | 0.968 | 14.4 | 0.881 | 0.889 | 0.960 | 0.64 | 0.960 ± 0.013 | 14.6 ± 3.3 |
| Logistic regression | 0.944 | 4.8 | 0.897 | 0.778 | 0.937 | 0.75 | 0.944 ± 0.000 | 6.2 ± 1.9 |
| Linear SVM | 0.944 | 7.2 | 0.913 | 0.778 | 0.937 | 0.75 | 0.944 ± 0.000 | 6.0 ± 1.1 |
| MLP | 0.937 | 10.8 | 0.937 | 0.778 | 0.929 | 0.92 | 0.938 ± 0.014 | 3.4 ± 4.0 |
| XGBoost | 0.929 | 10.8 | 0.889 | 0.667 | 0.952 | 0.83 | 0.937 ± 0.012 | 13.2 ± 3.8 |
| HistGradientBoosting | 0.913 | 7.2 | 0.881 | 0.667 | 0.960 | 0.96 | 0.937 ± 0.024 | 10.6 ± 3.8 |
| Extra Trees | 0.897 | 2.4 | 0.857 | 0.556 | 0.929 | 0.96 | 0.902 ± 0.013 | 3.8 ± 2.3 |
| RBF SVM | 0.944 | 12.0 | 0.881 | 0.667 | 0.857 | 1.42 | 0.941 ± 0.008 | 8.2 ± 3.7 |
| Random forest | 0.865 | 6.0 | 0.873 | 0.444 | 0.881 | 1.88 | 0.884 ± 0.018 | 4.6 ± 1.8 |
| Isolation Forest | 0.595 | 1.2 | 0.778 | 0.111 | 0.595 | 0.86 | 0.624 ± 0.034 | 3.1 ± 2.8 |
| kNN | 0.944 | 31.2 | 0.000 | 0.778 | 0.135 | 0.81 | 0.759 ± 0.379 | 25.7 ± 14.4 |
| Decision tree | 0.000 | 0.0 | 0.000 | 0.000 | 0.000 | – | 0.000 | 0.0 |

The weak-spoofer test (T4) has only 9 sessions, so it is coarse. Speed (T7) is under 0.3 ms per decision for every model; see `model_summary.json`.

## What it means

- **Closest: one-class SVM.** It misses the limit by 0.2 FA/h (1.2 vs 1.0), and it is the best or tied-best on T3, T4 and delay. It is trained on clean data only, which suits unseen attacks. But the false-alarm count rests on very few events (the validation set has only about 1.7 clean hours), and over 5 seeds it averages 2.4 ± 1.1 FA/h. It is not eligible, and the 1.2 is not a stable result.
- **The model is not the bottleneck.** Most models detect 0.93–0.97 but at 5–15 FA/h. Which model is used matters less than the false-alarm side, which comes from the features and thresholds (§8).
- **Seed spread matters.** False-alarm rates move by 1–4 FA/h between seeds, which is larger than most gaps between models. Differences smaller than that are ties (§2, rule 5).
- **The decision tree 0.0 is a tied-score artifact** (see the docstring in `model_selection.py`), not a real measurement.
- kNN fails without signal strength (T3 = 0) and on unseen attacks (T5 = 0.14); the rest keep T3 near 0.86–0.95.

## Next steps

1. Fix the false-alarm side: per-session normalisation, longer windows, persistence tuning on calibration data.
2. Use a longer clean validation set so FA/h is not decided by a handful of events.
3. If a model becomes eligible, apply §6 steps 2–5, lock it, then open the test set once.
