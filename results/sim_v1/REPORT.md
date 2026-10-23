# Results on simulated dataset `sim_v1`

Simulation only. These numbers say nothing about bench or flight performance. Config: `configs/sim_v1.json`. Split by session, 50/20/30 train/calibration/test. Test set: 357 attacked sessions (51 per type) and 60 clean sessions (1.67 h of clean flight).

## Headline

| Detector | Detection | FA/h (clean test) | Median delay |
|---|---|---|---|
| Best single layer (10 learned) | 0.969 (0.95–0.98) | 3.0 | 0.72 s |
| Vote, 99.9th-percentile threshold | 0.978 (0.96–0.99) | 4.8 | 0.40 s |
| Vote, threshold for ≤1 FA/h on calibration | 0.924 (0.89–0.95) | 2.4 | 0.41 s |
| Equal-weight vote | 0.941 | 11.4 | 0.35 s |

**The false-alarm target of 1 per hour is not met by any detector on the test set.** The vote does not beat layer 10 alone. Layers 3 (0.07) and 7 (0.03) are close to useless on this data.

## Layers alone

See `summary.csv`. Layers 5 (0.68), 6 (0.61) and 8 (0.67) catch the step, static and ramp-then-step attacks (≈1.0) but almost none of the consistent takeover or ramp attacks. Layers 1, 2, 4 and 9 sit near 0.43–0.45.

## Without C/N0 (`shortcut.csv`)

| | With C/N0 | Without |
|---|---|---|
| Layer 10 | 0.969 | 0.599 (FA 0/h) |
| Vote | 0.978 | 0.888 (1.8 FA/h) |
| Vote at FA target | 0.924 | 0.863 |

Layer 10 leans heavily on signal strength. The vote loses less because other layers cover for it.

## By spoofer power (`by_power.csv`)

Vote detection: 0–1 dB 0.94, 1–3 dB 0.95, 3–6 dB 0.98, 6–10 dB 1.00. At the FA target: 0.87, 0.89, 0.92, 0.96. Weak spoofers are harder, as expected.

## Ablation (`ablation.csv`)

Removing layer 10 costs the most (0.978 → 0.908, consistent takeover 0.92 → 0.65). Removing layer 5 costs 0.011. Removing layer 4 or 6 slightly raises detection but also raises false alarms (4: 4.8 → 6.0/h, 6: → 8.4/h). Other layers change little, so they add little to the vote here.

## Limits

See `negative.md`. All parameters (clock, sensors, spoofer) are assumptions until calibrated on hardware; attack naming is correct for only 0.79 of detected attacks.
