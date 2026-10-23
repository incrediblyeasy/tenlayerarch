# Simulation Phase: Step-by-Step Instructions to Finish It Properly

Goal: finish the simulation phase so that the package produces one trustworthy result: a detector trained and tested on synthetic data, with every layer, the vote and the evaluation measured on separate sessions, and every number reproducible from a config file and a seed.

This document is an instruction set. Each step says what to change, in which file, what the result must be, and how to check it. Do the steps in order. Do not start the bench phase until Section 9 passes.

Starting point (verified on the latest upload, `0404443c-10_Layer_archi.zip`):
- 12 tests pass, but none checks detection.
- `simulator.py` is a wrapper around `sim/generate.py`. The attacks there do not affect the clock, and the velocity of a consistent takeover is not checked against the spoofed path.
- The 10 layers run on the unified generator because `sim/generate.py` writes legacy alias columns. Their scores for clean and attacked sessions are almost identical.
- The vote is `weighted_vote`, a plain average, and nothing calls it.
- `evaluate.py` skips sessions on `KeyError`, uses clean sessions for calibration and false-alarm measurement, and double-counts sessions.
- `bench/` contains placeholder metadata only.

A working reference exists in `/home/claude/sim_study/` (`sim.py`, `features.py`, `run_study.py`, `run_nocn0.py`, `RESULTS.md`). It is a separate study, not part of the package. Use its physics as the starting point for the package's generator, and reproduce its numbers before changing anything else.

---

## Step 0. Freeze the baseline

0.1 Create a branch or copy of the package. Name it `sim-phase-start`.

0.2 Record the current test output and the current state of every file. This is the "before" for the completion report.

0.3 Confirm that `sim_study/` runs in under 10 minutes on this machine. If it does not, reduce session counts in the runner for development only, and restore the full counts for the final run.

Done when: you can say exactly what the package produces today, and `sim_study/` reproduces the numbers in `RESULTS.md` within the stated variation.

---

## Step 1. Remove the duplicate and the placeholder

1.1 Delete `ten_layer_detector/legacy_layers.py`.

1.2 Delete `ten_layer_detector/simulator.py`. Change every import of it (`cli.py`, `pipeline.py`, `evaluate.py`, `__init__.py`, tests) to `ten_layer_detector.sim` or `ten_layer_detector.sim.generate`.

1.3 Delete the legacy alias columns that `sim/generate.py` writes for the old layers (`gnss_lat`, `gnss_lon`, `gnss_alt`, `imu_ax`, `imu_ay`, `imu_az`, `baro_alt`, `pseudorange_m`, `timestamp`, `dop`, `sat_count`, `gnss_lat_deg`, `gnss_lon_deg`). They hide missing inputs. The layers are rewritten in Step 3 to use canonical names only.

1.4 Move `bench/`, `BENCH_RUNBOOK.md` and the session metadata out of the package into `docs/bench_plan/`, or delete them. Do not keep placeholder session folders in the simulation package.

1.5 Remove the `except KeyError: continue` in `evaluate.py`. Missing inputs must raise.

Done when: `grep -r "legacy\|simulator import" ten_layer_detector tests` returns nothing, and the test suite fails on import errors only where you have not yet updated a test.

---

## Step 2. One generator with the physics from `sim_study/`

Replace `ten_layer_detector/sim/` with a port of `/home/claude/sim_study/sim.py`. Keep the file names of the package so the rest of the code keeps working.

2.1 `sim/trajectory.py`: `sample_trajectory(rng, n, fs) -> (t, p, v, a)`.
- Smooth 3D path: sum of three sinusoids per axis with random amplitude and frequency.
- Velocity and acceleration are the analytic derivatives, not finite differences.
- Test: `a` equals the numerical derivative of `v` to within 1e-3 m/s^2 on a 60 s session.

2.2 `sim/gnss_model.py`:
- Ten satellites as unit directions `D_i(t)` at radius `R_SAT = 2.656e7 m`, elevation 11 to 79 degrees, slow drift.
- Range `rho_i = |R_SAT * D_i - p|`.
- Pseudorange `pr_i = rho_i(p_reported) + clk_m + noise_i`, noise sigma `0.8 + 2*(1 - sin(el_i))` metres.
- C/N0 `cn0_i = 42 + 10*sin(el_i) + N(0,1) + power_db * attacked(t)`.
- DOP from the satellite directions, horizontal and vertical.
- Test: at zero noise, the pseudoranges reproduce the true position to within 1e-6 m.

2.3 `sim/clock_model.py`: receiver clock `clk_ns = 20 + cumsum(N(0, 0.2)) + 0.05 t`. Its parameters are configuration values, labelled as assumptions until calibrated on the bench.

2.4 `sim/sensors.py`:
- IMU: true acceleration plus a per-session bias `N(0, 0.02)` per axis and white noise `N(0, 0.05)`. Level IMU, no attitude (state this in the output metadata).
- Barometer: true altitude plus per-session bias `N(0, 1.0)`, drift `0.01 t`, noise `N(0, 0.3)`.

2.5 `sim/attacks.py`: one function `attack_offset(kind, t, onset, amp, rng, vertical) -> d(t)` with these exact shapes:
- `step`: `s = amp` after onset.
- `ramp`: `s = amp * tau / T`, where `T` is the time from onset to session end.
- `step_then_ramp`: `s = 0.3 amp` then `0.3 amp + 0.7 amp tau/T`.
- `ramp_then_step`: `s = 0.5 amp tau/(T/2)` until mid, then `s = amp`.
- `consistent_takeover`: spoofed position `p + d`, spoofed velocity `v + d'` where `d'` is the numerical derivative of `d` at the sample rate. Velocity is not a free parameter.
- `dynamic_takeover`: `d = amp sin(2 pi tau / 40)`, velocity `v + d'`.
- For the pseudorange-level attacks (`step`, `ramp`, `step_then_ramp`, `ramp_then_step`): reported position `p + d`, reported velocity `v` (Doppler is not spoofed).
- Optional vertical component for `step`, `ramp`, `step_then_ramp` in half of the sessions.

2.6 `sim/generate.py`: `generate_session(config, seed) -> (DataFrame, metadata)`.
- `config` contains: duration, sample rate, attack kind (or `clean`), onset (required to be inside the session for attacked sessions), amplitude, spoofer power, sensor and clock parameters.
- Output columns are exactly the canonical schema in `IMPLEMENTATION_GUIDE.md` Section 2. Units in names. Clean sessions have `label == 0` everywhere.
- Metadata: session id, kind, source `sim`, attack type, attack start and end, all parameters, the seed, and the note "level IMU, no attitude, no multipath, clock not coupled to attack" (or the coupling, if you add it).

2.7 Acceptance tests (add to `tests/test_sim_physics.py`):
- Constant-velocity check: for `consistent_takeover`, the max difference between the reported velocity and the numerical derivative of the reported position is below 0.1 m/s.
- For `dynamic_takeover`, the implied acceleration stays below 15 m/s^2.
- For attacked sessions, the mean C/N0 after onset exceeds the mean before onset by the spoofer power, within 0.5 dB.
- For `ramp`, the reported position departs from the true position linearly at the configured rate, within 0.05 m.
- Two different seeds give different trajectories.
- Clean sessions have no label equal to 1.
- An onset outside the session raises an error.

Done when: all acceptance tests in 2.7 pass, and the reference numbers in Step 8 reproduce from the package generator with the same seeds.

---

## Step 3. Layers: canonical inputs, per-row causal scores, fit on clean data

Rewrite every layer file. Use this interface in `layers/base.py`:

```python
class Layer:
    name: str
    required_columns: tuple[str, ...]

    def fit(self, clean_train: list[pd.DataFrame]) -> None: ...
    def score(self, session: pd.DataFrame) -> np.ndarray:   # one value per row, causal
    def threshold(self) -> float:                            # from calibration, frozen
```

Rules for every layer:
- `score` checks `required_columns` and raises `MissingInputError` naming the missing columns. It never returns zeros.
- `score` uses only rows at or before each row. Test this by changing later rows and checking earlier scores are unchanged.
- `fit` uses only clean training sessions, and stores its parameters.
- The threshold is the 99.9th percentile of the layer's scores on clean calibration sessions. It is computed once, stored in `config_frozen.json`, and never recomputed on test data.
- If a layer's inputs are not in the data, the layer is reported `not_evaluated` with the reason. It is not run on an approximation.

Layer specifications (use the canonical names from the schema):

3.1 Layer 1 (time). Inputs `clk_ns`. Two-state Kalman filter, state (phase, drift), process noise and measurement noise fitted on clean sessions. Score: `|innovation| / sqrt(S)`. Expected on the current simulator: no signal, because the clock is not coupled to attacks. Report that honestly unless you add coupling in Step 2.5. If you add a clock coupling, the coupling must be documented in the metadata.

3.2 Layer 2 (signal quality). Inputs `cn0_i`, `el_i`. Fit mean and standard deviation of C/N0 in 10-degree elevation bins on clean sessions. Score per row: the maximum over satellites of `|z_i|`, two-sided, with `z_i = (cn0_i - mu_bin) / sd_bin`.

3.3 Layer 3 (geometry). Inputs `el_i`, `az_i`, reported DOP. Score: `|DOP_reported - DOP_recomputed|` normalised by its clean 99.9th percentile. Expected: near zero signal, because the spoofer does not change geometry in the simulator. Report it as such.

3.4 Layer 4 (multi-constellation). Requires two GNSS solutions. The simulator has one. Report `not_evaluated`. Do not fake a second solution.

3.5 Layer 5 (cross-domain).
- Position-velocity residual: `|(p_t - p_{t-50})/5 - mean(v over last 50 rows)|`, horizontal and vertical.
- Acceleration residual: `|mean(imu over last 10 rows) - (v_t - v_{t-10})/1.0|`.
- Score: maximum of the two, each normalised by its clean 99.9th percentile.

3.6 Layer 6 (physical).
- Barometer deviation: `|(alt_reported - baro) - ref|`, where `ref` is the mean over the first 10 s of the session (pre-attack, a stated assumption).
- Jerk from IMU, normalised by clean 99.9th percentile.
- Score: maximum.

3.7 Layer 7 (raw signal). Requires carrier phase. The simulator does not produce it. Report `not_evaluated`. The current `pr_m` scale (about 2.6e7) gives meaningless scores; delete the layer's current formula.

3.8 Layer 8 (temporal anomaly). Isolation Forest (200 trees, fixed seed) fitted on clean training rows using the 5-second trailing means of layers 2, 3, 5 and 6 features. Score: negated `score_samples`.

3.9 Layer 9 (Allan). Requires clock samples at 1 Hz for at least 60 s. The simulator's clock is at 10 Hz; downsample to 1 Hz inside the layer. Overlapping Allan at tau = 1, 2, 4 s. Score: the largest ratio to the clean 99.9th percentile. Expected: no signal on the current simulator (clock not coupled). Report it.

3.10 Layer 10 (learned). Random forest (100 trees, depth 8, minimum leaf 50, balanced classes, fixed seed) on the feature vector of layers 2, 3, 5, 6 and 8. Fitted on training sessions only. Score: predicted attack probability. Threshold from clean calibration rows.

Done when: each layer returns `not_evaluated` or a per-row score with no zeros, the causality test passes for every layer, and each layer's clean and attacked score distributions are reported side by side.

---

## Step 4. Vote and attack naming

4.1 Build out-of-fold scores on training sessions:
- Split training sessions into 5 folds, stratified by attack type, with a fixed seed.
- For each fold, fit the layers on the other folds and score the held-out fold.
- Convert each layer's row score to a percentile against the clean out-of-fold scores of the same layer.

4.2 Fit the vote: `LogisticRegression(class_weight="balanced")` on standardised percentiles of the evaluated layers. Fit on the out-of-fold rows only.

4.3 Vote threshold: 99.9th percentile of the clean out-of-fold vote values. Frozen.

4.4 Equal-weight baseline: mean of percentiles, with its own threshold computed the same way. Report both.

4.5 Attack naming:
- For each attacked training session, record which layers alarm after onset.
- Fit a decision tree of depth 3 (or a lookup table of alarm patterns) mapping the alarm pattern to an attack type, on training sessions only.
- Test it on held-out sessions. Report the confusion matrix. Do not report a naming accuracy until this test has been run.

4.6 Replace `vote.py` with these functions and delete `weighted_vote`:
`fit_vote(oof_percentiles, labels, layers) -> model`, `vote_score(model, percentiles) -> np.ndarray`, `equal_vote(percentiles) -> np.ndarray`.

Done when: the vote is fitted and frozen, the equal-weight baseline is reported, and the naming matrix exists for held-out sessions.

---

## Step 5. Splits and the evaluation loop

5.1 Split configuration (fixed seeds, recorded in `config_frozen.json`):

| Set | Content | Use |
|---|---|---|
| train | 120 clean, 150 attacked (25 per type), amplitude U(5,15) m, power U(0,6) dB, onset U(30,60) s | fit layers and vote |
| calibrate | 60 clean | frozen thresholds |
| test | 60 clean, 60 attacked (10 per type) | final report |
| test-large | 60 clean, 300 attacked (50 per type) | final report, required for any rate reported as a result |
| low-power | attacked, power U(0,1) dB, 50 per type | C/N0 shortcut removed |
| amplitude | attacked at 3, 10, 30 m, 20 per type per level | amplitude dependence |

The three sets never share a session. Assert this in code.

5.2 Evaluation procedure (`evaluate.py`), in this order:
1. Load the frozen config. Refuse to run if the config hash changed since the thresholds were computed.
2. For each test session, compute every layer's per-row score and the vote.
3. Alarm rule: score above threshold for 5 consecutive rows.
4. Attacked session: detected if an alarm occurs at or after onset. Delay is the first such alarm minus onset. Count alarms before onset as false alarms.
5. Clean session: count alarm onsets (rising edges).
6. Report per attack type: detection rate with a 95% Wilson interval, median and 90th-percentile delay.
7. Report false alarms per hour: total clean alarm onsets divided by total clean hours.
8. Run the ablation: remove each layer in turn and refit only the vote.
9. Run the shortcut check: each layer alone, and the vote without the C/N0 layer.
10. Run the low-power and amplitude sets.
11. Run leave-one-attack-out: refit everything without one attack type, test on that type. State in the report that every attack raises C/N0, so this tests shape generalisation only.

5.3 Metrics (`metrics.py`): replace accuracy and F1 with the functions above. Delete the old functions if nothing calls them.

5.4 Output files (written by `reports.py`):
- `results/summary.csv`: layer, attack type, n, detection rate, interval low and high, median delay, 90th-percentile delay, false alarms per hour, clean hours.
- `results/ablation.csv`, `results/shortcut.csv`, `results/lowpower.csv`, `results/amplitude.csv`, `results/loao.csv`.
- `results/naming_confusion.csv`.
- `results/negative.md`: layers `not_evaluated` with reasons; attack types and layers with no detection. Every weak result is listed.
- `results/config_frozen.json`: every parameter, every seed, the config hash, and the package version.

Done when: one command (`python -m ten_layer_detector.evaluate --config configs/sim_v1.json`) produces all output files from a clean checkout.

---

## Step 6. Config and reproducibility

6.1 Create `configs/sim_v1.json` holding: simulator parameters, sensor parameters, clock parameters, window lengths (5 s for features, 10 samples for accelerations, 60 s for Allan), persistence count (5), percentile for thresholds (99.9), all seeds, split sizes.

6.2 Thresholds, the vote weights and the naming rule are written to `config_frozen.json` by a separate `calibrate` command. The evaluate command refuses to run if they are missing.

6.3 Add a test: running the evaluation twice with the same config gives byte-identical `summary.csv`.

6.4 Add a test: changing one test session's samples after time t does not change scores before t.

Done when: the two reproducibility tests pass, and the summary is identical across two runs.

---

## Step 7. Tests that check detection, not shapes

Replace the current tests with the following. Each one is a claim the package must satisfy before the next phase.

7.1 Clean sessions: no layer alarms at its frozen threshold on at least 20 clean sessions not used for calibration (false alarm check).
7.2 Attacks: for each attack type, at least one layer alarms within 30 s of onset on at least 90% of attacked sessions. If a type is not detectable by any layer on the simulator, the test asserts that fact explicitly and the report records it. Do not silently skip it.
7.3 Missing input raises `MissingInputError` for every layer.
7.4 Splits: no session in two sets; both classes present in each attacked set; a one-session split raises.
7.5 Causality for every layer.
7.6 Reproducibility (Step 6).
7.7 Vote: fitted only on out-of-fold rows (assert on the training data indices).
7.8 Evaluation refuses a stale config.

Done when: all tests pass. A test that fails because the simulator makes a type undetectable is changed to assert that fact, not removed.

---

## Step 8. Reference numbers to reproduce

Before you accept the package, the package must reproduce the `sim_study/` numbers from its own generator, with the same seeds and settings, within sampling variation:

| Result | Reference (sim_study, RESULTS.md) |
|---|---|
| RF, all features: overall detection | 0.85 |
| RF, all features: false alarms per hour | 0.52 |
| LR, all features: false alarms per hour | 3.65 |
| RF without C/N0 and DOP, IMU plus baro: detection | 0.52 |
| RF at 0 to 1 dB power: detection | 0.27 |
| Single feature `cn0_mean`: detection range | 0.5 to 0.7 |

If the package does not reproduce these numbers, the difference is a bug in one of the two implementations. Find it before continuing. Do not change the reference to match the package.

---

## Step 9. Completion gate for the simulation phase

The simulation phase is complete when every line below is true, and the completion report shows the evidence for each:

1. One generator, from `sim/`. No legacy imports, no alias columns, no duplicate layer files.
2. Every attack type changes at least one signal by more than the clean session-to-session spread, or is reported as undetectable from that signal.
3. Every layer returns per-row causal scores from canonical columns, or is reported `not_evaluated` with the reason.
4. Thresholds, vote weights and naming rules are fitted on training data and frozen. Test data is not used for any fit or threshold.
5. The vote is compared with the equal-weight baseline and with the best single layer on the test-large set. If the vote does not beat the best single layer, the report says so.
6. Detection rate, interval, delay, false alarms per hour, ablation, shortcut check, low-power test, amplitude sweep and leave-one-attack-out are all produced by one command.
7. Each reported rate is based on at least 50 attacked sessions per type, or it is labelled as a pilot.
8. Reproducibility tests pass. The package reproduces the Step 8 reference numbers.
9. `negative.md` lists every layer or attack type that does not work on the simulator.
10. README and status documents describe exactly the above and nothing more.

---

## Step 10. What not to do yet

- Do not start the bench phase, or keep bench placeholder files in the package, until Step 9 passes.
- Do not report any number from the old `simulator.py`, or from the layers before Step 3.
- Do not tune thresholds, weights or window lengths on the test sets. If a choice must change, record it as a new config version and rerun everything.
- Do not claim the layered detector works. Claim only what the Step 9 report shows.
- Do not add layers 4, 7 or 9 with approximated inputs to make the count reach ten. Report them as not evaluated.

## Appendix: time estimate

- Steps 0 to 2: about 2 to 3 days.
- Step 3: about 2 days.
- Steps 4 and 5: about 2 days.
- Steps 6 and 7: about 1 day.
- Running the full evaluation and writing the report: about half a day on this machine, longer if the test-large and amplitude sets are run at full size with the random forest.
