# Phase 0: Hardware Inventory and Bench Recording Plan

This document turns the next phase of the project plan into a practical checklist before any real bench or flight testing begins.

## 1. Goal

Confirm the exact hardware capabilities and the exact data available from each device before interpreting any real GNSS records. This is the gate before bench recordings and before sim-to-real validation.

This follows the sequence in [TEN_LAYER_PLAN.md](TEN_LAYER_PLAN.md):

1. Phase 0: inventory
2. Phase 1: simulator validation
3. Phase 3: bench recordings
4. generated-data validation
5. flights only after the prior gates pass

## 2. Hardware inventory checklist

### 2.1 GPS receiver

Record the exact device model and firmware version.

Required answers:
- Exact GNSS receiver model
- Whether it is u-blox or another vendor
- Whether NAV-CLOCK is available
- Whether NAV-SAT is available
- Whether RXM-RAWX is available
- Whether raw pseudorange and carrier are enabled
- Whether C/N0 is logged per satellite
- Whether multi-constellation is enabled
- Whether the receiver exposes clock bias and drift in logs

Evidence to collect:
- datasheet page or vendor manual
- screenshot of configuration screen or log output
- sample log showing the message types

### 2.2 Cube Orange

Required answers:
- firmware version
- IMU logging rate
- barometer logging rate
- GPS logging rate
- whether the log uses MAVLink or DataFlash
- whether PVT is logged at enough frequency for the cross-domain and physical layers
- whether barometer and IMU are logged together with GNSS time stamps

Evidence to collect:
- configuration file
- sample log file
- a short clean recording showing time alignment between sensors

### 2.3 RTL-SDR

Required answers:
- exact hardware version
- antenna used
- expected L1 capture bandwidth
- whether the device is indoors or outdoors
- whether the sky view is usable
- whether the setup supports enough SNR for a meaningful IQ capture

Evidence to collect:
- sample IQ file metadata
- signal strength check or a basic sanity capture

### 2.4 Jetson

Required answers:
- exact Jetson model
- CPU and memory
- whether GNSS-SDR can run in real time
- whether the detector pipeline can be run on the recorded sessions without backlog

Evidence to collect:
- benchmark timing of GNSS-SDR on a test segment
- end-to-end processing time for a short dataset

## 3. Bench setup checklist

### 3.1 Required recording sources

For each bench session, collect all of the following when possible:
- GPS module PVT and quality logs
- GPS module clock logs if available
- GPS module raw measurements if available
- Cube Orange IMU and barometer logs
- GNSS position/velocity logs from the controller
- RTL-SDR raw IQ capture
- session metadata with time stamps, source, and conditions

### 3.2 Bench recording procedure

For each session:
1. Record a clean baseline for a fixed duration.
2. Confirm all sensors start at the same reference time.
3. Keep the RF path and antenna placement constant across clean and attacked capture.
4. Note the exact onset time of any spoofing or replay event.
5. Store the session metadata in a standard format.

Minimum metadata fields:
- session_id
- source
- clean_or_attacked
- attack_type
- attack_onset_s
- hardware configuration
- environment notes
- start time and end time
- log file names

## 4. Conducted replay rules

The plan explicitly forbids over-the-air GNSS spoofing during the bench phase.

Required conduct:
- use the HackRF only through attenuators
- route the signal through a shielded enclosure or cable
- verify the RF setup before each test
- never transmit over the air at GNSS frequencies during development

## 5. Data validation gate before moving on

Before moving past the bench data phase, complete the following validation:

1. Compare simulated and real clean distributions for:
   - C/N0
   - DOP
   - residuals
   - clock Allan deviation
   - satellite count
2. Train on simulated data and test on real recorded clean data.
3. Report the sim-to-real gap.
4. Document whether any layer is failing because the simulator is not realistic enough.
5. Confirm that the bench dataset includes a within-condition control: clean and attacked versions of the same trajectory or setup where possible.

If the gap is large or unclear, do not move to flight tests or generated-data claims.

## 6. Concrete next actions for this workspace

The next step in this project is to do the hardware inventory and then create the first real bench dataset.

Planned execution order:
1. Fill in the GPS receiver capability list.
2. Fill in the Cube Orange configuration list.
3. Confirm the Jetson and RTL-SDR setup.
4. Record one clean bench session.
5. Record one conducted spoofed bench session.
6. Validate the files against the detector schema.
7. Run the sim-to-real comparison.

## 7. Minimal template for the hardware report

Use this format in a short project note:

- GPS receiver model:
- GPS messages available:
- Cube Orange version:
- IMU rate:
- Barometer rate:
- GNSS log format:
- RTL-SDR setup:
- Jetson model:
- GNSS-SDR runtime status:
- Bench setup type:
- Safety and legal status:
- Outstanding blockers:

## 8. Safety and legal reminder

- Do not transmit GNSS spoofing over the air.
- Use only a conducted setup for any active signal replay.
- Keep the first flights clean-only until the safety plan is approved.
- Consult local rules before test setups near public or safety-critical systems.

This is the correct next engineering step before any drone work.
