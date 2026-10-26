# Remaining Work Before the Hardware Phase

Status date: 2026-10-26. Based on the archive `e1a8a995-ten_layer_archi.zip` (commit `b4d8be9`). All results are simulation or public data unless stated.

## Update, 2026-10-26 (after the gate test)

Gate read once on fresh `sim_test5` / `sim_weak5` with LightGBM (`configs/sim_v3.json`): **five of seven measurable targets met; two missed.** Missed: weak-spoofer consistent takeover 0.687 (target 0.85) and weak-spoofer 90th-percentile delay 13.3 s (target 5 s). Decision time still needs the Jetson. Full table and analysis: `reports_v3/DECISION_NOTE.md`. Section 2 below describes the state before this test. Decision needed from the owner: accept the two misses as documented simulator limits, or revise those two targets (before the next test set, with the reason recorded).

## 1. What "ready for hardware" means

A simulation can never be perfect. Its results only show that the detector behaves as designed under the simulator's assumptions. So the simulation phase should end when the detector meets a **gate of pre-set targets**, measured on a fresh test set, and the known gaps are written down. Hardware then tests the assumptions.

The targets below are proposed. The project owner should confirm them and commit them to the repository **before** the next test set is generated.

| Measure (fresh test set, LightGBM) | Proposed target | Current (test4) | Status |
|---|---|---|---|
| Detection, all attacks | at least 0.95 | 0.991 | Met |
| False alarms per hour, upper 95% bound | at most 1.0 | 0.53 | Met |
| Detection, consistent takeover | at least 0.85 | 0.94 (full power) | Met at full power |
| Detection, weak spoofer (0 to 1 dB), all attacks | at least 0.90 | 0.948 | Met |
| Detection, weak spoofer, consistent takeover | at least 0.85 | 0.65 | **Not met** |
| 90th-percentile delay, full power | at most 5 s | 4.1 s | Met |
| 90th-percentile delay, weak spoofer | at most 5 s | 14.8 s | **Not met** |
| Decision time | at most 10 ms on target hardware | 0.007 ms on PC | Not measured on Jetson |

Two gate items fail: weak-spoofer consistent takeover and weak-spoofer delay. These are the main blockers for simulation.

## 2. Blockers for the simulation gate

1. **Consistent takeover at weak power (0.65).** A GNSS-only model detects only 0.08 of weak consistent takeovers, so the IMU is essential. The IMU-based feature (the long-window residual) must be tested on weak-power data, and a longer-window or IMU-integrated check should be considered.
2. **Weak-spoofer delay (90th percentile 14.8 s).** The alarm rule (10 consecutive rows) probably delays weak attacks. Test a shorter persistence, or a second feature that reacts faster, on a fresh set.
3. **Two models, one locked.** `configs/locked_model_v3.json` still names the one-class SVM. `configs/adopted_model.json` names LightGBM. The owner must choose one, record the decision, and update the paper. The LightGBM result is the stronger one, but its confirmation set (sim_test4) has now been used for an exploratory GNSS-only test, so it is no longer a clean holdout.
4. **Test set reuse.** From now on, each claim needs a new test set (for example sim_test5). sim_test4 must not be used again for model choice.

## 3. Simulator assumptions that hardware must test

These are not bugs. They are the limits of the simulator, and the hardware phase exists to check them.

- The spoofer does not change the receiver clock. In reality, a spoofer usually does, so the clock layer's behaviour on hardware is unknown.
- There is no multipath (reflections).
- The IMU is level, with no attitude.
- Clock parameters (10 ps, 0.1 ps, 30 ns) are assumed, not measured. Calibrate them from the GPS module's Allan deviation.
- The attacker does not adapt to the detector.
- Signal strength always rises under attack in the simulator. A real spoofer may use lower power.

## 4. Layers not yet complete

| Layer | Gap |
|---|---|
| 3 Geometry | DOP cannot be recomputed from the schema (no per-satellite azimuth or elevation). The NAV-DOP decoder exists, but the NAV-SAT recomputation check is not built. |
| 4 Multi-constellation | Needs a second satellite-system solution (Galileo). The GPS module may not provide one. |
| 7 Raw signal | Needs carrier tracking from the RTL-SDR (for example GNSS-SDR). Not built. The code reads the receiver's raw fields instead. |
| 9 Allan deviation | Coded, but not evaluated on real clock data. |
| Attack naming | 79% accuracy. Needs work or a clear statement that it is a secondary output. |
| Vote vs layer 10 | Not compared on the current model. |

Layers 4 and 7 may not be possible with the current hardware. If so, the paper should say "not evaluated" and why.

## 5. Public-data check (Nayfeh)

- Re-run the final model on the Nayfeh public data.
- The public data has no IMU, barometer or clock, so only a reduced model can run. Report it as a reduced model.
- Keep this separate from the simulation results.

## 6. Software to finish before hardware

- **Row assembler:** works on synthetic frames only. Test it on a real GPS log.
- **Column mismatch:** a real recording will have fewer columns than the simulator (for example no Galileo solution, and maybe no IMU). The model must be retrained on simulated data restricted to the columns that will exist on the bench. The GNSS-only configuration is the fallback, but it detects takeovers poorly (see section 2).
- **Parsers:** UBX stream, RXM-RAWX, NAV-DOP and DataFlash `.bin` are tested on synthetic frames only. Test each on a real log.
- **MAVLink / DataFlash:** confirm the Cube Orange log rates for the IMU and barometer.
- **Live reader:** `read_serial` exists but is untested on hardware.
- **Reproducibility:** datasets are gitignored and rebuilt from seeds. Verify the hashes in `DATASETS.md` on the owner's machine, and record the Python and library versions (pandas 3.0 required the copy-on-write fix).

## 7. Hardware preparation (Phase 0 and before)

- Confirm the GPS module model, firmware, and which messages are enabled (NAV-CLOCK, NAV-SAT, NAV-DOP, RXM-RAWX).
- Confirm the Cube Orange firmware and log rates.
- Confirm the Jetson model, and measure decision time on it.
- Set up the antenna and sky view for the module and RTL-SDR.
- Write the bench runbook steps for ground recordings (clean first).
- Calibrate the clock Allan deviation from the module.
- Get the safety plan and approvals for any conducted HackRF test and any flight. No over-the-air transmission.

## 8. Writing and admin

- Update the research paper to the current numbers. Use `PAPER_NUMBERS.md` and state both the rule-selected and the adopted model.
- Update the progress report.
- Decide on SpaceSec 2027 (deadline 6 December 2026). The paper must be anonymised for double-blind review, and the topic fit should be checked.
- Confirm the Spanghero and Gormus references against the published papers.
- Fill in author details.
- Discuss the model choice and the gate with the professor.

## 9. Order of work

1. Owner confirms the gate targets, and commits them.
2. Choose the model (one-class SVM or LightGBM). Update the locked or adopted file, and record the decision.
3. Fix the two failing gate items on a fresh set (sim_test5). Pre-register the test before generating it.
4. Confirm the row assembler and parsers on one real GPS log (Phase 0 and the first ground recording).
5. Retrain on the bench column set, then re-test on simulation.
6. Pass the gate. Write the simulation-results section of the paper.
7. Move to bench recordings, then the Jetson latency test, then approved flights.
