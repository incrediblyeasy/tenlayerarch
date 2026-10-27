# C1: matched-power attacker (simulated)

Plan committed before any data: `configs/simplan_c1.json` (`2f49de2`, 2026-10-27 14:55:46). Simulated data only. Assumptions: the careful attacker matches each satellite's C/N0 to the authentic value up to a Gaussian error (sd 1 dB) and reproduces the satellite geometry; position, velocity, clock coupling, lock reset and Galileo behaviour are sampled as for the default attacker. Datasets `sim_default1` (default attackers, seed 6161) and `sim_matched1` (matched, seed 6060), each 300 clean + 150 sessions per attack type, fresh and used only for this comparison. Detectors are the gate-test detectors (LightGBM, `configs/sim_v3.json`, and the same with all signal-strength features excluded, `configs/sim_v3_nostrength.json`), fitted and calibrated on `sim_fa2` and not changed.

| | Full detector, default attacks | Full detector, **matched power** | No-strength detector, default | No-strength detector, **matched power** |
|---|---|---|---|---|
| Detection, all attacks | 0.989 (0.98–0.99) | 0.898 (0.88–0.91) | 0.965 (0.95–0.97) | 0.969 (0.96–0.98) |
| consistent takeover | 0.933 (0.88–0.96) | 0.353 (0.28–0.43) | 0.780 (0.71–0.84) | 0.813 (0.74–0.87) |
| dynamic takeover | 0.993 (0.96–1.00) | 0.987 (0.95–1.00) | 1.000 (0.98–1.00) | 1.000 (0.98–1.00) |
| ramp | 0.993 (0.96–1.00) | 0.953 (0.91–0.98) | 0.980 (0.94–0.99) | 0.967 (0.92–0.99) |
| ramp then step | 1.000 (0.98–1.00) | 1.000 (0.98–1.00) | 1.000 (0.98–1.00) | 1.000 (0.98–1.00) |
| static | 1.000 (0.98–1.00) | 1.000 (0.98–1.00) | 1.000 (0.98–1.00) | 1.000 (0.98–1.00) |
| step | 1.000 (0.98–1.00) | 1.000 (0.98–1.00) | 0.993 (0.96–1.00) | 1.000 (0.98–1.00) |
| step then ramp | 1.000 (0.98–1.00) | 0.993 (0.96–1.00) | 1.000 (0.98–1.00) | 1.000 (0.98–1.00) |
| Median / p90 delay, s | 0.91 / 3.3 | 1.78 / 15.6 | 1.08 / 13.2 | 0.96 / 13.8 |

## What it shows

- **The full detector depends heavily on the signal-strength cue.** Against the matched-power attacker its detection falls from 0.989 to 0.898, and consistent takeover from 0.93 to **0.35**. Position steps, ramps and static attacks are still caught (0.95–1.00): the position and velocity cues carry those.
- **The detector trained without the signal-strength features is more robust to this attacker** (0.969 on matched attacks against 0.898 for the full detector), at a lower detection on default attacks (0.965 vs 0.989) and a slower 90th-percentile delay on default attacks (13.2 s vs 3.3 s). Its consistent-takeover detection is 0.78–0.81 under both attackers.
- **The hypothesis in the plan held** (the full detector falls on matched attacks; the no-strength detector changes little).

## Limits of this result

- False alarms are not measured here: 300 clean sessions are only about 4 clean hours. The no-strength detector's false-alarm rate on a large clean set has **not** been measured; it must be before it could be considered as a replacement.
- The matched attacker also reproduces geometry, so this is a combined "careful attacker" case; the effect of matching power alone is not separated.
- A detector retrained with matched attacks in training would likely do better; that is a separate logged change, to be tested on a new set, and it does not replace these numbers (plan, rule 4).
- The gate targets in `configs/gate_targets.json` are unchanged and were met by the full detector on default attacks only; under matched power the full detector would miss the consistent-takeover target (0.35 vs 0.85) and the overall target (0.898 vs 0.95).
