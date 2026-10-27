# Simulator Improvements Plan

Status date: 2026-10-27. Scope: all UAVs and drones, not a single small platform.

## 1. Purpose

The simulator decides how much the detector's results can be trusted. Right now it is easier than reality in several ways, so the current results overstate performance. This plan lists the changes that make the simulator harder and more varied, the test each one supports, and the rules for running them.

The aim is not higher scores. The aim is results that hold up when the simulator is made more realistic. A score that drops after a fair change is a useful result.

## 2. Known gaps in the current simulator

| # | Gap | Why it matters |
|---|---|---|
| G1 | Every attack raises C/N0 on all satellites | The signal-strength cue looks stronger than it would be against a careful attacker |
| G2 | Attacks are fixed, not adaptive | The detector is not tested against an attacker that knows its cues |
| G3 | IMU is level, with no attitude; simple noise | The IMU-based consistency check is probably flattered |
| G4 | No ionosphere term in pseudorange or carrier | The code-versus-carrier cue cannot be tested |
| G5 | The spoofer does not change the receiver clock | The clock check has no signal in the full simulation |
| G6 | No multipath | Simulated signals look cleaner than real ones |
| G7 | One flight profile family | "All UAVs" is not tested across different platforms |
| G8 | Noise and clock parameters are assumed | Results depend on values never measured on hardware |

## 3. Changes

Each change lists its test, the measure to report, and the expected direction of effect. Expected direction is a hypothesis, not a result.

### C1. Matched-power spoofer (addresses G1)
- Add attacks where the spoofer's C/N0 matches the authentic signal on each satellite, within a stated tolerance.
- Keep the current high-power attacks, so both cases are reported.
- Measure: detection and false alarms per hour for each power case, reported side by side.
- Expected: detection falls for the signal-strength cue, and the other cues carry more of the result.

### C2. Adaptive attacker (addresses G2)
- Model an attacker that knows the detector's features and tunes its path or power to lower the detector's score, within a fixed budget (for example, a maximum path deviation or power).
- Use a simple search, such as random or gradient-free optimisation, and report the attack that gets through most often.
- Measure: detection under the adaptive attacker, and the attacker's cost (deviation or power used).
- Expected: detection falls. The worst-case number is the one to report.

### C3. Realistic IMU (addresses G3)
- Add attitude (roll, pitch, yaw) and a level-to-body transform.
- Add bias that drifts slowly (random walk), scale-factor error, and realistic white noise. Use values from published IMU datasheets for an entry-level UAV IMU, labelled as assumptions until calibrated.
- Measure: IMU-based feature alone and in the full detector, with and without the IMU, plus drift over time.
- Expected: the IMU feature becomes weaker. The integration failure seen earlier should appear clearly, which is a useful result.

### C4. Ionosphere term (addresses G4)
- Add an ionospheric delay to the code and an equal and opposite advance to the carrier, varying with elevation and time of day.
- Add a spoofer variant that does not reproduce the ionospheric difference, and one that does.
- Measure: code-versus-carrier cue alone, and in the full detector, for both variants.
- Expected: the cue works against the non-matching spoofer and fails against the matching one. Both results are reported.

### C5. Spoofer changes the receiver clock (addresses G5)
- For time-based attacks, the spoofer shifts the receiver's clock offset and drift.
- Measure: clock check alone and in the full detector.
- Expected: the clock check detects these attacks. The result shows how much of the detector depends on the clock.

### C6. Multipath (addresses G6)
- Add a reflected signal for each satellite, with delay, amplitude and phase drawn from a stated distribution.
- Measure: all checks, with and without multipath, to see which cues are affected.
- Expected: false alarms rise, particularly for the signal-quality and geometry checks.

### C7. Platform variety (addresses G7)
- Add flight profiles for at least three UAV classes: slow multirotor hover and manoeuvre, faster fixed-wing with sustained speed, and a larger vehicle with slower dynamics.
- Keep the same attack types across platforms.
- Measure: detection and false alarms per platform, and whether one model works across all three.
- Expected: some checks depend on platform dynamics. Results should be reported per platform, not pooled.

### C8. Parameter calibration (addresses G8)
- Once bench or flight data exist, fit the noise, clock and IMU parameters to them, and rerun the simulator.
- Until then, every parameter is labelled as an assumption, and a sensitivity sweep shows how results change across a stated range.
- Measure: detection and false alarms across the parameter range.

## 4. Rules

1. **Commit before generating.** Each change is committed, with its test plan, before any new dataset is generated.
2. **Fresh test sets.** Each new configuration uses a new test set. No test set is used for tuning and for reporting.
3. **Report all configurations.** The results before and after each change are reported side by side, including the ones that get worse.
4. **No silent retuning.** If the detector is changed to handle a new condition, the change is logged with its reason, and a new test set is used.
5. **Targets are not redefined.** The gate targets in configs/gate_targets.json stay as they are. A missed target is reported as missed.
6. **Results are labelled simulated.** Every number from this plan is marked as simulated, with the assumptions listed beside it.

## 5. Order of work

1. C1 (matched power) and C2 (adaptive attacker). These test the largest weakness and are the most important for a reviewer.
2. C3 (realistic IMU). This tests the IMU claim, which the current results rely on.
3. C4 (ionosphere) and C5 (clock). These enable the two cues that are currently missing.
4. C6 (multipath). This makes the clean-signal assumption fairer.
5. C7 (platform variety). This tests the "all UAVs" scope.
6. C8 (calibration). Only after real recordings exist.

## 6. Outputs

For each change:
- A configuration file committed before data generation.
- A report with before and after results, using the same measures and confidence ranges.
- A short note stating what the change tested and what it showed.

The final simulator report collects these, with a table of the score under each configuration. The paper should cite the lowest score that a fair configuration produces, not the highest.

## 7. What this plan does not do

- It does not make the detector better. Any improvement needs its own change and a fresh test.
- It does not replace hardware testing. Simulated results, however fair, are not evidence about real receivers.
- It does not set the final gate. Changes to the gate are a separate decision by the project owner, made before the new test set is generated.
