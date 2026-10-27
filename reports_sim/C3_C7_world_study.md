# C3-C7: harder simulated worlds (all numbers simulated)

Plans were committed before any run (`configs/simplan_ref.json`, `simplan_c3..c7.json`, commit b559e89). Driver: `ten_layer_detector/world_study.py`; raw results: `results/ws_*.json`. Detector: LightGBM with `configs/sim_v3.json` settings (persistence 5, calibration margin 0.5 FA/h), fitted and calibrated inside the training world, scored on fresh test worlds. "Full" uses all features; "no strength" drops C/N0, HDOP and satellite-count cues. Targets in `configs/gate_targets.json` are unchanged. FA = false alarms per hour of clean flight, with the 95% range in brackets. Each test has 2000 clean sessions (about 1 h of clean flying per 36 sessions), so a rate of 1 FA/h has a range of roughly 0.7-1.5.

Two fixes happened during the study and are logged here, not hidden: the C4 run and the pooled C7 arm first crashed because pooled worlds shared session ids. The code now prefixes ids when worlds are pooled; single-world arms are not affected. Nothing else was changed after seeing results.

## Headline

1. **False alarms are the weak point of every harder world.** In 16 of 32 full-detector tests below (cue-alone arms excluded) the FA rate is above the 1/h target, and the 95% range lies entirely above 1 in 10 of them. For the no-strength detector it is 20 of 32. The calibration step (margin 0.5 FA/h on clean calibration sessions) does not carry over to fresh worlds; this is the validation-underestimates-test effect already noted.
2. **The no-strength detector is not safe.** Without signal-strength cues it raises 1.6/h in the reference world, 22/h with multipath, 148/h with a level-IMU model in a realistic-IMU world, and up to 51/h on a platform it was not trained on. The 0.97 detection quoted for it in C1 comes with this cost.
3. **Single-platform training does not transfer.** The worst case is a fixed-wing test: 15-17/h for models trained on hover or large-slow platforms. The pooled model gives 0.97-2.1/h across platforms, still above target in 3 of 4.
4. **Cues that look strong alone are fragile.** Clock cues alone detect 0.941 when the spoofer shifts the clock and 0.004 when it keeps it consistent. The code-carrier cue alone detects nothing in either ionosphere case (0.000), including the spoofer that does not reproduce the ionosphere.

## REF: reference world (new generator path, defaults)

| Detector | Detection | FA/h (95% range) | p90 delay (s) | Consistent takeover |
|---|---|---|---|---|
| Full | 0.920 | 0.07 (0.01-0.26) | 10.2 | 0.75 |
| No strength | 0.960 | 1.62 (1.18-2.17) | 13.5 | 0.74 |

## C3 realistic IMU (bias, scale, random walk, thrust-aligned attitude)

| Arm (trained in) | Detection | FA/h (range) | p90 (s) | Consistent takeover |
|---|---|---|---|---|
| Base detector (level-IMU features, trained in reference world), full | 0.930 | 1.15 (0.79-1.63) | 6.1 | 0.79 |
| Base detector, no strength | 1.000 | **147.85** (143-152) | 0.6 | 1.00 |
| Attitude-aware features, trained in IMU world, full | 0.993 | 2.84 (2.25-3.54) | 2.2 | 0.95 |
| Attitude-aware, no strength | 0.937 | 1.12 (0.76-1.58) | 15.3 | 0.59 |
| IMU features removed, full | 0.987 | 2.74 (2.16-3.42) | 3.4 | 0.96 |
| IMU features removed, no strength | 0.921 | 1.30 (0.91-1.79) | 16.9 | 0.66 |

Reading: a tilted multirotor has near-zero horizontal specific force, so features that assume a level body break. The 148/h and detection 1.000 of the no-strength base detector is an alarm that is almost always on, not good detection. Removing IMU features entirely raises false alarms rather than lowering detection, which suggests the gain comes from the trained world, not from the attitude features; the world-trained arms cannot separate those two effects (see caveats).

## C4 ionosphere (code delayed, carrier advanced)

| Arm | Test world | Detection | FA/h (range) | Consistent takeover |
|---|---|---|---|---|
| Trained in ionosphere world, full | spoofer reproduces ionosphere | 0.987 | 1.12 (0.76-1.58) | 0.91 |
| | spoofer does not | 0.996 | 2.81 (2.22-3.50) | 0.97 |
| Code-carrier cue alone | either | 0.000 | 0.00 | 0.00 |
| Base detector (not retrained) | reproduces | 0.896 | 0.11 | 0.71 |
| | does not | 0.919 | 0.00 | 0.80 |

Reading: the existing code-carrier feature gives no detection even against the spoofer that ignores the ionosphere, so the expected "cue catches the non-matching spoofer" did not happen. This is a finding about the feature as built, not proof that the physics offers nothing; a dedicated divergence feature (plan item F1) has not been built.

## C5 spoofer clock

| Arm | Clock shifted | Clock preserved |
|---|---|---|
| Full detector: detection / FA/h | 0.970 / 0.79 | 0.947 / 0.76 |
| Clock cues alone: detection | 0.941 | **0.004** |
| Full detector: p90 delay | 2.9 s | 12.8 s |
| Full detector: consistent takeover | 0.88 | 0.75 |

Reading: when the spoofer keeps the clock consistent, the clock layer contributes nothing and the other cues give detection 0.947 with a 12.8 s p90 delay. That is the figure to cite for a careful attacker.

## C6 multipath

| Arm | Test world | Detection | FA/h (range) |
|---|---|---|---|
| Base detector, full | multipath | 0.924 | 1.01 (0.67-1.46) |
| Base detector, no strength | multipath | 0.970 | **22.21** |
| Trained in multipath world, full | multipath | 0.983 | 0.72 (0.44-1.11) |
| Trained in multipath world, no strength | multipath | 0.946 | 0.43 (0.22-0.75) |
| Strength cues alone | reference / multipath | 0.060 / 0.109 | 0.00 |

Reading: training in the noisier world fixes the false alarms of the full detector; the no-strength detector needs it badly.

## C7 platforms (rows: trained on; columns: tested on). Full detector, detection / FA per hour

| Trained on | Hover | Maneuver | Fixed wing | Large slow |
|---|---|---|---|---|
| Multirotor hover | 0.996 / 1.08 | 0.999 / 2.16 | 0.997 / **15.08** | 0.997 / 0.90 |
| Multirotor maneuver | 0.936 / 0.00 | 0.940 / 0.29 | 0.940 / 0.00 | 0.944 / 0.00 |
| Fixed wing | 0.931 / 0.22 | 0.933 / 0.22 | 0.943 / 0.04 | 0.950 / 0.11 |
| Large slow | 0.994 / 1.62 | 0.999 / 3.06 | 0.999 / **16.74** | 0.997 / 1.01 |
| Pooled | 0.993 / 0.97 | 0.997 / 2.12 | 0.997 / 1.33 | 0.997 / 1.51 |

No-strength detector, same layout (detection / FA per hour): hover-trained 0.974/0.68, 0.974/8.21, 0.990/50.98, 0.984/0.94; maneuver-trained 0.961/2.59, 0.966/2.27, 0.971/10.98, 0.974/1.33; fixed-wing-trained 0.803/0.00, 0.796/0.00, 0.814/0.90, 0.787/0.00; large-slow-trained 0.976/0.83, 0.974/3.64, 0.979/29.74, 0.979/0.90; pooled 0.921/0.14, 0.937/0.54, 0.920/2.16, 0.941/0.43.

Reading: the models whose FA looks tiny (maneuver-trained, fixed-wing-trained) also have the lowest detection (0.93-0.95 full, down to 0.79 no strength with consistent takeover near 0.01). Their calibration threshold is high, so a low FA is bought with missed attacks. The pooled model is the most balanced, but its FA is still above 1/h on three of four platforms.

## What to cite (lowest fair numbers)

Any claim of "detection about 0.99, FA under 1/h" is only supported for the reference simulator with a matched training world. Across the harder worlds the fair summary is: detection 0.92-1.00 for the full detector (0.90 against a matched-power attacker, C1; 0.947 with the clock preserved, p90 12.8 s), false alarms 0-3/h with up to 17/h on an unseen platform, and a no-strength detector that is not usable without per-environment retraining.

## Caveats

- Each world is one seed; the study does not repeat worlds, so differences of a few points in detection are not established. FA ranges are the Poisson ranges from clean hours and count only sampling noise of those sessions.
- Realism options (IMU, ionosphere, multipath, platforms) are my model of these effects. They are not checked against receiver or IMU data (C8 needs bench recordings).
- Several arms train with the harder effect present, so they measure the benefit of training in the matching world, not of any single feature. The plan's separate ablations (IMU features removed, cue alone) are reported above, and they do not show a feature-level gain for attitude-aware IMU features.
- The no-strength false-alarm figures are from a threshold set by the same calibration rule; they say the rule's margin is not enough there, not that no threshold could work.
