# Negative results and limits

- Layer 3_geometry detects only 0.07 of attacks on its own.
- Layer 7_raw_signal detects only 0.03 of attacks on its own.
- The vote does not beat the best single layer (10_learned: detect 0.97 at 3.0 FA/h; vote: 0.98 at 4.8 FA/h).
- At the 99.9th-percentile threshold the vote raises 4.80 false alarms/h, above the 1/h target.
- At the threshold set for 1 FA/h on calibration sessions, the vote detects 0.92 at 2.40 FA/h on held-out clean sessions (4 events in 1.67 h). The target is not met on the test set.
- At the false-alarm target the vote detects 0.71 of consistent_takeover attacks (95% CI 0.57-0.81).
- At the false-alarm target the vote detects 0.80 of ramp attacks (95% CI 0.68-0.89).
- Attack naming is correct for 0.79 of detected attacks (n=349); see the confusion matrix.
- Without C/N0 features the vote detects 0.89 at 1.80 FA/h (with C/N0: 0.98 at 4.80 FA/h).
- All results are on simulated data. Clock, sensor and spoofer parameters are assumptions until calibrated on the bench.
