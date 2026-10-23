from __future__ import annotations

from typing import Any

import numpy as np

ATTACK_TYPES = (
    "static",
    "step",
    "ramp",
    "step_then_ramp",
    "ramp_then_step",
    "consistent_takeover",
    "dynamic_takeover",
)

_ALIASES = {"none": "clean", "clean": "clean", "static_offset": "static"}


def normalize_attack_type(attack_type: str) -> str:
    name = str(attack_type).strip().lower()
    name = _ALIASES.get(name, name)
    if name != "clean" and name not in ATTACK_TYPES:
        raise ValueError(f"Unsupported attack_type {attack_type!r}")
    return name


def sample_attacker(rng: np.random.Generator, attack_type: str) -> dict[str, Any]:
    """Per-session attacker parameters (never written to the row data).

    power_db: spoofer power above the authentic signals, 0-10 dB.
    clock_coupled: the spoofer does not reproduce the receiver clock, so bias/drift change.
    geometry_changed: the spoofer simulates its own satellite set.
    lock_reset: carrier lock is lost during capture.
    spoofs_galileo: the second constellation is spoofed as well.
    """
    sophisticated = attack_type in {"consistent_takeover", "dynamic_takeover"}
    return {
        "power_db": float(rng.uniform(0.0, 10.0)),
        "clock_coupled": bool(rng.random() < (0.3 if sophisticated else 0.5)),
        "geometry_changed": bool(rng.random() < (0.3 if sophisticated else 0.5)),
        "lock_reset": bool(rng.random() < 0.5),
        "spoofs_galileo": bool(rng.random() < (0.7 if sophisticated else 0.5)),
    }


def attack_offset(
    rng: np.random.Generator,
    attack_type: str,
    t: np.ndarray,
    onset_s: float,
    true_pos: np.ndarray,
    true_vel: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Spoofing offset o(t) and its derivative o_dot(t) in NED, plus the shape parameters.

    The reported velocity is true_vel + o_dot: o_dot = 0 leaves velocity untouched
    (position/velocity inconsistent); a matched o_dot keeps them consistent.
    """
    n = t.size
    o = np.zeros((n, 3))
    o_dot = np.zeros((n, 3))
    tau = np.clip(t - onset_s, 0.0, None)
    on = t >= onset_s
    h = rng.uniform(0.0, 2 * np.pi)
    vert = rng.uniform(-0.3, 0.3)
    d = np.array([np.cos(h), np.sin(h), vert])
    perp = np.array([-np.sin(h), np.cos(h), 0.0])
    params: dict[str, Any] = {"direction_deg": float(np.rad2deg(h)), "vertical_fraction": float(vert)}

    if attack_type == "static":
        # Spoofer broadcasts a fixed location: reported position frozen, velocity zero.
        dist = rng.uniform(50.0, 300.0)
        p_fix = true_pos[int(np.argmax(on))] + dist * d
        o[on] = p_fix - true_pos[on]
        o_dot[on] = -true_vel[on]
        params["distance_m"] = float(dist)
    elif attack_type == "step":
        dist = rng.uniform(10.0, 100.0)
        o[on] = dist * d
        params["step_m"] = float(dist)
    elif attack_type == "ramp":
        rate = rng.uniform(0.2, 2.0)
        o = rate * tau[:, None] * d
        params["rate_mps"] = float(rate)
    elif attack_type == "step_then_ramp":
        step = rng.uniform(5.0, 30.0)
        rate = rng.uniform(0.2, 1.0)
        o[on] = step * d
        o += rate * np.clip(tau - 5.0, 0.0, None)[:, None] * d
        params.update(step_m=float(step), rate_mps=float(rate))
    elif attack_type == "ramp_then_step":
        rate = rng.uniform(0.2, 1.0)
        t_ramp = rng.uniform(8.0, 15.0)
        step = rng.uniform(10.0, 50.0)
        o = rate * np.minimum(tau, t_ramp)[:, None] * d
        o[tau > t_ramp] += step * d
        params.update(rate_mps=float(rate), ramp_s=float(t_ramp), step_m=float(step))
    elif attack_type == "consistent_takeover":
        a = rng.uniform(0.05, 0.3)
        t_acc = rng.uniform(5.0, 15.0)
        ta = np.minimum(tau, t_acc)
        o = (0.5 * a * ta**2 + a * t_acc * np.clip(tau - t_acc, 0.0, None))[:, None] * d
        o_dot = (a * ta)[:, None] * d
        params.update(accel_mps2=float(a), accel_s=float(t_acc))
    elif attack_type == "dynamic_takeover":
        w = 2 * np.pi / rng.uniform(20.0, 60.0)
        amp_max = 2.0 / (w * w)  # keep spoofed acceleration near the airframe limit (~2 m/s^2)
        amp_a = rng.uniform(0.2, 1.0) * amp_max
        amp_b = rng.uniform(0.2, 1.0) * amp_max
        # Both components start with zero offset and zero velocity, so there is no jump at onset.
        o = (amp_a * (1 - np.cos(w * tau)))[:, None] * d + (0.25 * amp_b * (1 - np.cos(2 * w * tau)))[:, None] * perp
        o_dot = (amp_a * w * np.sin(w * tau))[:, None] * d + (0.5 * amp_b * w * np.sin(2 * w * tau))[:, None] * perp
        o[~on] = 0.0
        o_dot[~on] = 0.0
        params.update(period_s=float(2 * np.pi / w), amp_a_m=float(amp_a), amp_b_m=float(amp_b))
    else:
        raise ValueError(f"unknown attack type {attack_type!r}")
    return o, o_dot, params
