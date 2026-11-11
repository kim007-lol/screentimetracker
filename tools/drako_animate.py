"""Append Drako's interaction clips without touching mesh, skin, or textures.

The delivered Drako GLBs already carry 21 clips. This script only adds four
new, stage-aware clips on top of them:

  greet      one-shot, looks up and half-spreads the wings
  petting    one-shot, leans into the hand and relaxes the wings
  walk       seamless loop, diagonal gait with a stage-specific wobble
  wing_show  one-shot, baby "pretend wings" / teen practice / adult display

Every new clip animates all 24 joints plus the Hips translation. Existing
Drako clips animate only a handful of joints; writing the full set means a
crossfade can never leave a limb stuck in a previous clip. Hips translation
matches the existing convention (0,0,0 at the start of a clip), so mixing our
clips with the delivered idle cycle does not pop the model.

Usage:
    python tools/drako_animate.py <source_dir> <out_dir>
    python tools/drako_animate.py docs/docs-assets-chr/paket-drako-3d-final mobile/assets/3d
"""

from __future__ import annotations

import json
import math
import os
import struct
import sys

FPS = 30
JOINTS = [
    "Root", "Hips", "Spine", "Chest", "Neck", "Head", "Horn_L", "Horn_R",
    "Wing_L", "Wing_L_Tip", "Wing_R", "Wing_R_Tip",
    "LegFL", "PawFL", "LegFR", "PawFR", "LegBL", "PawBL", "LegBR", "PawBR",
    "Tail_1", "Tail_2", "Tail_3", "Tail_Tip",
]

# Per-stage timing. These are the numbers the Flutter/native registries use.
SPECS = {
    "bayi": {"greet": 2.4, "petting": 2.2, "walk": 1.4, "wing_show": 2.2},
    "remaja": {"greet": 2.0, "petting": 2.0, "walk": 1.0, "wing_show": 1.8},
    "dewasa": {"greet": 2.2, "petting": 2.4, "walk": 1.6, "wing_show": 2.4},
}

# ------------------------------------------------------------------ math


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def qnorm(q):
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    return (x / n, y / n, z / n, w / n)


def qeuler(deg):
    """Quaternion from local X, then Y, then Z degrees."""
    rx, ry, rz = (math.radians(v) * 0.5 for v in deg)
    qx = (math.sin(rx), 0.0, 0.0, math.cos(rx))
    qy = (0.0, math.sin(ry), 0.0, math.cos(ry))
    qz = (0.0, 0.0, math.sin(rz), math.cos(rz))
    return qnorm(qmul(qmul(qz, qy), qx))


def smoothstep(a, b, t):
    if a == b:
        return 1.0 if t >= b else 0.0
    u = max(0.0, min(1.0, (t - a) / (b - a)))
    return u * u * (3.0 - 2.0 * u)


def window(t, start, end, edge):
    return smoothstep(start, start + edge, t) * (
        1.0 - smoothstep(end - edge, end, t)
    )


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------ pose


def pose(**rots):
    """A full-body pose. Unlisted joints stay at the neutral rest rotation."""
    out = {j: [0.0, 0.0, 0.0] for j in JOINTS}
    for name, value in rots.items():
        if name not in out:
            raise KeyError(name)
        out[name] = [float(v) for v in value]
    return out


def add(target, name, xyz):
    dst = target[name]
    dst[0] += xyz[0]
    dst[1] += xyz[1]
    dst[2] += xyz[2]


def blend(a, b, u):
    """Smoothstep blend between two full-body poses."""
    u = u * u * (3.0 - 2.0 * u)
    return {
        j: [lerp(a[j][i], b[j][i], u) for i in range(3)]
        for j in JOINTS
    }


def keyed(keys, u):
    """Interpolate a list of (fraction, pose) pairs at fraction u."""
    if u <= keys[0][0]:
        return {j: list(v) for j, v in keys[0][1].items()}
    for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
        if u <= t1:
            return blend(p0, p1, (u - t0) / (t1 - t0))
    return {j: list(v) for j, v in keys[-1][1].items()}


def symmetric_wings(p, up, tips=None, fold=False):
    """Move both wings together.

    Local +Z rotates the left wing down and the right wing up, so a symmetric
    lift needs opposite signs. ``up`` > 0 means raised, < 0 means folded down.
    """
    tip = up * 1.3 if tips is None else tips
    add(p, "Wing_L", (0.0, 0.0, -up))
    add(p, "Wing_R", (0.0, 0.0, up))
    add(p, "Wing_L_Tip", (0.0, 0.0, -tip))
    add(p, "Wing_R_Tip", (0.0, 0.0, tip))
    if fold:
        add(p, "Chest", (0.9, 0.0, 0.0))


def alternating_wings(p, amount):
    """Cute asymmetric flutter: one wing rises while the other dips."""
    add(p, "Wing_L", (0.0, 0.0, amount))
    add(p, "Wing_R", (0.0, 0.0, amount))
    add(p, "Wing_L_Tip", (0.0, 0.0, amount * 1.15))
    add(p, "Wing_R_Tip", (0.0, 0.0, amount * 1.15))


def tail_wave(p, amount, phase, lift=0.0):
    for i, joint in enumerate(("Tail_1", "Tail_2", "Tail_3", "Tail_Tip")):
        add(p, joint, (lift * (0.5 + i * 0.15), amount * math.sin(phase - i * 0.55), 0.0))


# ------------------------------------------------------------------ clips


def greet(stage: str, dur: float):
    a = {"bayi": 1.0, "remaja": 1.15, "dewasa": 0.85}[stage]
    lift = {"bayi": 0.055, "remaja": 0.05, "dewasa": 0.02}[stage]
    wing = {"bayi": 9.0, "remaja": 17.0, "dewasa": 16.0}[stage]

    def sample(t):
        u = min(1.0, max(0.0, t / dur))
        env = math.sin(math.pi * u) ** 0.85
        p = pose()
        add(p, "Head", (-13.0 * a * env, 7.0 * math.sin(2 * math.pi * u) * env,
                        5.0 * math.sin(2 * math.pi * u + 0.6) * env))
        add(p, "Neck", (-6.0 * a * env, 2.5 * math.sin(2 * math.pi * u) * env, 0.0))
        add(p, "Chest", (-2.5 * a * env, 0.0, 0.0))
        add(p, "Spine", (-1.2 * a * env, 0.0, 0.0))
        add(p, "Hips", (0.0, 0.0, 2.2 * math.sin(2 * math.pi * u) * env if stage == "bayi" else 0.0))
        symmetric_wings(p, wing * env, tips=wing * 1.35 * env)
        if stage == "bayi":
            alternating_wings(p, 4.0 * math.sin(2 * math.pi * 4.5 * u) * env)
        else:
            symmetric_wings(p, 2.0 * math.sin(2 * math.pi * 2 * u) * env)
        tail_wave(p, {"bayi": 16.0, "remaja": 19.0, "dewasa": 10.0}[stage] * env,
                  2 * math.pi * 1.25 * u, lift=-3.0 * env)
        return p, (0.0, lift * env * (0.35 + 0.65 * math.sin(math.pi * u)), 0.0)

    return sample


def petting(stage: str, dur: float):
    a = {"bayi": 1.0, "remaja": 1.1, "dewasa": 0.9}[stage]

    def sample(t):
        u = min(1.0, max(0.0, t / dur))
        env = window(u, 0.0, 1.0, 0.16)
        nuzzle = math.sin(2 * math.pi * 1.6 * u) * window(u, 0.18, 0.78, 0.12)
        p = pose()
        add(p, "Head", (11.0 * a * env, -6.0 * env + 3.0 * nuzzle,
                        10.0 * a * env + 3.0 * nuzzle))
        add(p, "Neck", (7.0 * a * env, -2.0 * env, 0.0))
        add(p, "Chest", (2.4 * env, 0.0, 0.0))
        add(p, "Spine", (1.6 * env, 0.0, 1.5 * env if stage == "bayi" else 0.0))
        symmetric_wings(p, -6.0 * a * env, tips=-8.0 * a * env)
        if stage == "bayi":
            alternating_wings(p, 3.5 * math.sin(2 * math.pi * 3.0 * u) * env)
            add(p, "Hips", (0.0, 0.0, 2.0 * math.sin(2 * math.pi * 2.0 * u) * env))
        tail_wave(p, {"bayi": 12.0, "remaja": 14.0, "dewasa": 8.0}[stage] * env,
                  2 * math.pi * 1.4 * u, lift=-2.0 * env)
        sink = {"bayi": 0.018, "remaja": 0.012, "dewasa": 0.006}[stage]
        purr = 0.0022 * math.sin(2 * math.pi * 9.0 * u) * env
        return p, (0.0, -sink * env + purr, 0.0)

    return sample


def walk(stage: str, dur: float):
    if stage == "bayi":
        # Stubby legs hide a normal gait, so the baby waddles: bigger roll and
        # yaw, a stronger bob, and only a modest leg swing to avoid foot slide.
        leg, knee, bob, sway, yaw, wing = 10.0, 5.0, 0.024, 5.5, 3.0, 5.0
    elif stage == "remaja":
        leg, knee, bob, sway, yaw, wing = 15.0, 5.0, 0.024, 1.8, 1.0, 6.0
    else:
        leg, knee, bob, sway, yaw, wing = 12.0, 4.0, 0.014, 1.2, 0.6, 5.0

    def sample(t):
        phase = 2 * math.pi * (t / dur)
        swing = math.sin(phase)
        p = pose()
        # Diagonal gait: FL + BR move together, FR + BL oppose them.
        add(p, "LegFL", (-leg * swing, 0.0, 0.0))
        add(p, "LegBR", (-leg * swing, 0.0, 0.0))
        add(p, "LegFR", (leg * swing, 0.0, 0.0))
        add(p, "LegBL", (leg * swing, 0.0, 0.0))
        # Small paw counter-rotation keeps the feet from looking glued.
        add(p, "PawFL", (knee * max(0.0, -swing), 0.0, 0.0))
        add(p, "PawBR", (knee * max(0.0, -swing), 0.0, 0.0))
        add(p, "PawFR", (knee * max(0.0, swing), 0.0, 0.0))
        add(p, "PawBL", (knee * max(0.0, swing), 0.0, 0.0))
        # Body roll, yaw, and two bobs per stride.
        add(p, "Hips", (0.0, yaw * swing, sway * swing))
        add(p, "Spine", (0.8 * math.sin(2 * phase), 0.0, -sway * 0.55 * swing))
        add(p, "Chest", (0.6 * math.sin(2 * phase), 0.0, -sway * 0.35 * swing))
        add(p, "Neck", (0.0, -0.5 * yaw * swing, -0.4 * sway * swing))
        add(p, "Head", (-1.5 * math.sin(2 * phase), -0.7 * yaw * swing,
                        -0.8 * sway * swing))
        symmetric_wings(p, wing * (0.5 - 0.5 * math.cos(2 * phase)))
        tail_wave(p, {"bayi": 11.0, "remaja": 14.0, "dewasa": 8.0}[stage],
                  phase - 0.9, lift=-1.5)
        bob_y = bob * (0.5 - 0.5 * math.cos(2 * phase))
        return p, (0.0, bob_y, 0.0)

    return sample


def wing_show(stage: str, dur: float):
    # Key poses are fractions of the clip. Adult holds the open pose longer.
    if stage == "bayi":
        # "Pretend wings": the baby does not unfold a majestic span. It puffs
        # up, rocks side to side, and flaps its little wings in proud, clumsy
        # hops. Body roll and yaw keep both hidden wings peeking into view.
        keys = [
            (0.00, pose()),
            (0.12, pose(Head=(8, 0, -4), Neck=(4, 0, -2), Chest=(2, 0, 0),
                        Wing_L=(0, 0, 8), Wing_R=(0, 0, -8),
                        Wing_L_Tip=(0, 0, 9), Wing_R_Tip=(0, 0, -9),
                        Hips=(0, -3, -3))),
            (0.26, pose(Head=(-14, 5, 9), Neck=(-5, 2, 3), Chest=(-2, 0, 1),
                        Wing_L=(0, 0, -26), Wing_R=(0, 0, 26),
                        Wing_L_Tip=(0, 0, -32), Wing_R_Tip=(0, 0, 32),
                        Hips=(0, 5, 7), Tail_1=(0, 12, 0), Tail_2=(0, 15, 0),
                        Tail_3=(0, 18, 0), Tail_Tip=(0, 20, 0))),
            (0.38, pose(Head=(5, -3, -7), Neck=(2, -1, -3), Chest=(1, 0, 0),
                        Wing_L=(0, 0, 9), Wing_R=(0, 0, -9),
                        Wing_L_Tip=(0, 0, 11), Wing_R_Tip=(0, 0, -11),
                        Hips=(0, -4, -5), Tail_1=(0, -9, 0), Tail_2=(0, -12, 0),
                        Tail_3=(0, -14, 0), Tail_Tip=(0, -16, 0))),
            (0.52, pose(Head=(-15, -5, -9), Neck=(-6, -2, -3), Chest=(-3, 0, 0),
                        Wing_L=(0, 0, -30), Wing_R=(0, 0, 30),
                        Wing_L_Tip=(0, 0, -38), Wing_R_Tip=(0, 0, 38),
                        Hips=(0, -6, -7), Tail_1=(0, -13, 0), Tail_2=(0, -16, 0),
                        Tail_3=(0, -19, 0), Tail_Tip=(0, -21, 0))),
            (0.66, pose(Head=(-9, 4, 8), Neck=(-4, 2, 3), Chest=(-2, 0, 0),
                        Wing_L=(0, 0, -18), Wing_R=(0, 0, 18),
                        Wing_L_Tip=(0, 0, -23), Wing_R_Tip=(0, 0, 23),
                        Hips=(0, 5, 6), Tail_1=(0, 9, 0), Tail_2=(0, 11, 0),
                        Tail_3=(0, 13, 0), Tail_Tip=(0, 15, 0))),
            (0.82, pose(Head=(-7, 0, 2), Neck=(-3, 0, 1), Chest=(-2, 0, 0),
                        Wing_L=(0, 0, -14), Wing_R=(0, 0, 14),
                        Wing_L_Tip=(0, 0, -17), Wing_R_Tip=(0, 0, 17),
                        Tail_1=(0, 5, 0), Tail_2=(0, 6, 0), Tail_3=(0, 7, 0))),
            (0.92, pose(Head=(2, 0, -2), Wing_L=(0, 0, 3), Wing_R=(0, 0, -3),
                        Wing_L_Tip=(0, 0, 4), Wing_R_Tip=(0, 0, -4))),
            (1.00, pose()),
        ]
        hop = 0.042

        def sample(t):
            u = min(1.0, max(0.0, t / dur))
            p = {j: list(v) for j, v in keyed(keys, u).items()}
            # Two eager little hops while the wings flutter.
            hop_env = window(u, 0.18, 0.62, 0.10)
            bob = hop * max(0.0, math.sin(math.pi * (u - 0.18) / 0.22)) * hop_env
            bob += hop * 0.65 * max(0.0, math.sin(math.pi * (u - 0.44) / 0.20)) * window(u, 0.44, 0.64, 0.08)
            flutter = 4.0 * math.sin(2 * math.pi * 7.0 * u) * window(u, 0.20, 0.72, 0.10)
            alternating_wings(p, flutter)
            add(p, "Head", (0.0, 2.5 * math.sin(2 * math.pi * 3.0 * u),
                            3.5 * math.sin(2 * math.pi * 3.5 * u)))
            return p, (0.0, bob, 0.0)

        return sample

    # Teen practice and adult display share a fold/open rhythm, with the adult
    # holding the spread longer and moving more calmly.
    a = 1.0 if stage == "remaja" else 1.0
    open_w = {"remaja": 20.0, "dewasa": 25.0}[stage]
    open_tip = {"remaja": 26.0, "dewasa": 32.0}[stage]
    fold_w = {"remaja": 11.0, "dewasa": 16.0}[stage]
    head_up = {"remaja": 11.0, "dewasa": 9.0}[stage]
    hop = {"remaja": 0.030, "dewasa": 0.012}[stage]
    open_hold = 0.58 if stage == "dewasa" else 0.50

    keys = [
        (0.00, pose()),
        (0.12, pose(Head=(6, 0, 0), Neck=(4, 0, 0), Chest=(2, 0, 0),
                    Wing_L=(0, 0, fold_w), Wing_R=(0, 0, -fold_w),
                    Wing_L_Tip=(0, 0, fold_w * 1.2), Wing_R_Tip=(0, 0, -fold_w * 1.2))),
        (0.26, pose(Head=(-head_up, 0, 0), Neck=(-head_up * 0.45, 0, 0),
                    Chest=(-3.0, 0, 0), Spine=(-1.5, 0, 0),
                    Wing_L=(0, 0, -open_w), Wing_R=(0, 0, open_w),
                    Wing_L_Tip=(0, 0, -open_tip), Wing_R_Tip=(0, 0, open_tip),
                    Tail_1=(0, 13, 0), Tail_2=(0, 16, 0), Tail_3=(0, 18, 0),
                    Tail_Tip=(0, 20, 0))),
        (open_hold, pose(Head=(-head_up * 0.8, 5, 0), Neck=(-head_up * 0.35, 2, 0),
                         Chest=(-2.2, 0, 0), Spine=(-1.0, 0, 0),
                         Wing_L=(0, 0, -open_w * 0.92), Wing_R=(0, 0, open_w * 0.92),
                         Wing_L_Tip=(0, 0, -open_tip * 0.92), Wing_R_Tip=(0, 0, open_tip * 0.92),
                         Tail_1=(0, -8, 0), Tail_2=(0, -10, 0), Tail_3=(0, -12, 0),
                         Tail_Tip=(0, -14, 0))),
        (0.68, pose(Head=(-head_up * 0.5, -4, 0), Neck=(-head_up * 0.2, -2, 0),
                    Chest=(-1.2, 0, 0), Spine=(-0.6, 0, 0),
                    Wing_L=(0, 0, -open_w * 0.55), Wing_R=(0, 0, open_w * 0.55),
                    Wing_L_Tip=(0, 0, -open_tip * 0.55), Wing_R_Tip=(0, 0, open_tip * 0.55),
                    Tail_1=(0, 8, 0), Tail_2=(0, 10, 0), Tail_3=(0, 12, 0),
                    Tail_Tip=(0, 14, 0))),
        (0.80, pose(Head=(-head_up * 0.85, 2, 0), Neck=(-head_up * 0.4, 0, 0),
                    Chest=(-2.6, 0, 0), Spine=(-1.2, 0, 0),
                    Wing_L=(0, 0, -open_w * 1.02), Wing_R=(0, 0, open_w * 1.02),
                    Wing_L_Tip=(0, 0, -open_tip * 1.02), Wing_R_Tip=(0, 0, open_tip * 1.02),
                    Tail_1=(0, -5, 0), Tail_2=(0, -6, 0), Tail_3=(0, -7, 0))),
        (0.92, pose(Head=(-3, 0, 0), Wing_L=(0, 0, -3), Wing_R=(0, 0, 3),
                    Wing_L_Tip=(0, 0, -4), Wing_R_Tip=(0, 0, 4))),
        (1.00, pose()),
    ]

    def sample(t):
        u = min(1.0, max(0.0, t / dur))
        p = {j: list(v) for j, v in keyed(keys, u).items()}
        # One powerful hop at the first spread, then a tiny settle bounce.
        bob = hop * max(0.0, math.sin(math.pi * (u - 0.18) / 0.18)) * window(u, 0.18, 0.38, 0.08)
        if stage == "remaja":
            bob += hop * 0.55 * max(0.0, math.sin(math.pi * (u - 0.50) / 0.18)) * window(u, 0.50, 0.70, 0.08)
        # A tiny living flutter during the hold, not a loop.
        flutter = 1.6 * math.sin(2 * math.pi * 3.0 * u) * window(u, 0.24, 0.82, 0.10)
        symmetric_wings(p, flutter)
        return p, (0.0, bob, 0.0)

    return sample


def critical_idle(stage: str, variant: str):
    """Living critical poses: weak, hunched, and visibly trembling.

    The delivered pack ships the four critical idle poses as frozen stills for
    bayi and remaja. The documented contract calls for tremble, cower, and tail
    tremble, so each variant keeps its delivered posture and adds a closed,
    bounded loop. Dewasa keeps the delivered animated clips.

    Variant radii:
      idle_critical    shallow breath + faint shiver
      idle_critical_a  body tremble (shiver dominates)
      idle_critical_b  cower: sinks, lowers and turns its head mid-clip
      idle_critical_c  tail tremble with a quiet body
    """
    tremor = 1.0 if stage == "bayi" else 1.12
    dur = CRITICAL_SPECS[stage][variant]

    def sample(t):
        u = min(1.0, max(0.0, t / dur))
        ph = 2 * math.pi * u
        p = pose()
        hips = (0.0, 0.0, 0.0)

        if variant == "idle_critical":
            # Keep the delivered base pose (Head 6, Spine 6, wings 8).
            add(p, "Head", (6.0 + 0.6 * math.sin(ph),
                            1.1 * math.sin(ph) + 0.25 * math.sin(ph * 7), 0.0))
            add(p, "Neck", (2.0 + 0.35 * math.sin(ph), 0.0, 0.0))
            add(p, "Chest", (1.2 + 0.65 * math.sin(ph), 0.0, 0.0))
            add(p, "Spine", (6.0 + 0.35 * math.sin(ph), 0.0, 0.0))
            symmetric_wings(p, 8.0 + 0.9 * math.sin(ph * 2))
            add(p, "Tail_3", (0.0, 0.8 * math.sin(ph - 0.7), 0.0))
            add(p, "Tail_Tip", (0.0, 2.5 + 1.4 * math.sin(ph - 0.4), 0.0))
            hips = (0.0, 0.00035 * math.sin(ph * 2), 0.0)
        elif variant == "idle_critical_a":
            # Delivered pose is Head 4; the shiver is the point of this clip.
            add(p, "Head", (4.0 + 1.5 * tremor * math.sin(ph * 7),
                            0.7 * tremor * math.sin(ph * 7 + 1.1), 0.0))
            add(p, "Neck", (1.2 + 0.8 * tremor * math.sin(ph * 7), 0.0, 0.0))
            add(p, "Chest", (1.0 + 1.0 * tremor * math.sin(ph * 7 + 0.6), 0.0, 0.0))
            add(p, "Spine", (3.0 + 0.5 * tremor * math.sin(ph * 7 + 0.3), 0.0, 0.0))
            symmetric_wings(p, 3.0 + 2.2 * tremor * math.sin(ph * 7))
            add(p, "Tail_Tip", (0.0, 1.0 + 2.0 * tremor * math.sin(ph * 7 - 0.8), 0.0))
            hips = (0.0, 0.0004 * math.sin(ph * 7), 0.0)
        elif variant == "idle_critical_b":
            # Delivered pose is Head 8, Spine 8, wings 10, Tail_2 2.5.
            cower = 0.5 - 0.5 * math.cos(ph)  # 0 at both ends, 1 mid-clip
            add(p, "Head", (8.0 + 3.0 * cower, 4.0 * cower, 0.0))
            add(p, "Neck", (3.0 + 1.5 * cower, 1.5 * cower, 0.0))
            add(p, "Chest", (2.0 + 1.0 * cower, 0.0, 0.0))
            add(p, "Spine", (8.0 + 2.0 * cower, 0.0, 0.0))
            symmetric_wings(p, 10.0 + 2.5 * cower)
            add(p, "Tail_1", (1.0 * cower, 0.0, 0.0))
            add(p, "Tail_2", (2.5 + 1.0 * cower, 0.0, 0.0))
            add(p, "Tail_3", (1.0 * cower, 0.0, 0.0))
            hips = (0.0, -0.0015 * cower, 0.0)
        else:
            # Delivered pose is tail only (Tail_2 3.5, Tail_3 7.8, Tip 10).
            add(p, "Head", (3.0 + 0.4 * math.sin(ph),
                            1.5 * math.sin(ph * 2), 0.0))
            add(p, "Neck", (1.2, 0.0, 0.0))
            add(p, "Chest", (0.8 + 0.3 * math.sin(ph * 2), 0.0, 0.0))
            add(p, "Spine", (3.0, 0.0, 0.0))
            symmetric_wings(p, 4.0 + 0.6 * math.sin(ph * 2))
            add(p, "Tail_2", (0.0, 3.5 + 2.5 * tremor * math.sin(ph * 6), 0.0))
            add(p, "Tail_3", (0.0, 7.8 + 4.0 * tremor * math.sin(ph * 6 - 0.5), 0.0))
            add(p, "Tail_Tip", (0.0, 10.0 + 6.0 * tremor * math.sin(ph * 6 - 1.0), 0.0))

        return p, hips

    return sample


BUILDERS = {
    "greet": greet,
    "petting": petting,
    "walk": walk,
    "wing_show": wing_show,
}
LOOPING = {"walk"}

# Dewasa already ships animated critical idles; only the two younger stages
# need the documented tremble/cower loop.
CRITICAL_SPECS = {
    "bayi": {
        "idle_critical": 1.44,
        "idle_critical_a": 1.44,
        "idle_critical_b": 1.44,
        "idle_critical_c": 1.44,
    },
    "remaja": {
        "idle_critical": 1.20,
        "idle_critical_a": 1.20,
        "idle_critical_b": 1.20,
        "idle_critical_c": 1.20,
    },
}


# ------------------------------------------------------------------ GLB


def load_glb(path):
    raw = open(path, "rb").read()
    magic, version, _ = struct.unpack("<III", raw[:12])
    if magic != 0x46546C67 or version != 2:
        raise ValueError("not a glTF 2.0 binary")
    off = 12
    js = None
    binary = bytearray()
    while off < len(raw):
        clen, ctype = struct.unpack("<II", raw[off:off + 8])
        off += 8
        data = raw[off:off + clen]
        off += clen
        if ctype == 0x4E4F534A:
            js = json.loads(data.decode("utf-8"))
        elif ctype == 0x004E4942:
            binary.extend(data)
    if js is None:
        raise ValueError("missing JSON chunk")
    return js, binary


def write_glb(js, binary, path):
    js_bytes = json.dumps(js, separators=(",", ":")).encode("utf-8")
    js_bytes += b" " * ((-len(js_bytes)) % 4)
    bin_bytes = bytes(binary) + b"\x00" * ((-len(binary)) % 4)
    total = 12 + 8 + len(js_bytes) + 8 + len(bin_bytes)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js_bytes), 0x4E4F534A))
        f.write(js_bytes)
        f.write(struct.pack("<II", len(bin_bytes), 0x004E4942))
        f.write(bin_bytes)


def add_accessor(js, binary, values, kind, minmax=False):
    n = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[kind]
    if len(binary) % 4:
        binary.extend(b"\x00" * (4 - len(binary) % 4))
    offset = len(binary)
    for v in values:
        binary.extend(struct.pack("<" + "f" * n, *v))
    js["bufferViews"].append(
        {"buffer": 0, "byteOffset": offset, "byteLength": len(values) * n * 4}
    )
    acc = {
        "bufferView": len(js["bufferViews"]) - 1,
        "componentType": 5126,
        "count": len(values),
        "type": kind,
    }
    if minmax:
        acc["min"] = [min(v[i] for v in values) for i in range(n)]
        acc["max"] = [max(v[i] for v in values) for i in range(n)]
    js["accessors"].append(acc)
    return len(js["accessors"]) - 1


def build_clip(js, binary, name, duration, sample, looping):
    frames = int(round(duration * FPS))
    times = [i * duration / frames for i in range(frames + 1)]
    poses = []
    hips = []
    for i, t in enumerate(times):
        # Sample the loop with its exact endpoint so first == last and the
        # three.js loop never sees a seam.
        p, h = sample(t)
        poses.append(p)
        hips.append(h)
    if looping:
        first = poses[0]
        last = poses[-1]
        if any(abs(first[j][i] - last[j][i]) > 1e-6 for j in JOINTS for i in range(3)):
            raise ValueError(f"{name}: loop does not close")
        if any(abs(hips[0][i] - hips[-1][i]) > 1e-6 for i in range(3)):
            raise ValueError(f"{name}: hips loop does not close")

    nodes = {n.get("name"): i for i, n in enumerate(js["nodes"]) if n.get("name")}
    missing = [j for j in JOINTS if j not in nodes]
    if missing:
        raise ValueError(f"missing joints: {missing}")

    source = add_accessor(js, binary, [(t,) for t in times], "SCALAR", minmax=True)
    samplers = []
    channels = []
    for joint in JOINTS:
        quats = []
        prev = None
        for p in poses:
            q = qeuler(p[joint])
            if prev is not None and sum(a * b for a, b in zip(prev, q)) < 0:
                q = tuple(-v for v in q)
            quats.append(q)
            prev = q
        out = add_accessor(js, binary, quats, "VEC4")
        samplers.append({"input": source, "output": out, "interpolation": "LINEAR"})
        channels.append(
            {
                "sampler": len(samplers) - 1,
                "target": {"node": nodes[joint], "path": "rotation"},
            }
        )
    out = add_accessor(js, binary, hips, "VEC3")
    samplers.append({"input": source, "output": out, "interpolation": "LINEAR"})
    channels.append(
        {
            "sampler": len(samplers) - 1,
            "target": {"node": nodes["Hips"], "path": "translation"},
        }
    )
    return {"name": name, "samplers": samplers, "channels": channels}


def rebuild(src, dst, stage):
    js, binary = load_glb(src)
    if "DrakoSkin" not in [s.get("name") for s in js.get("skins", [])]:
        raise ValueError(f"{src}: not a Drako rig")
    js["animations"] = [
        a for a in js.get("animations", []) if a.get("name") not in BUILDERS
    ]
    for name, duration in SPECS[stage].items():
        sample = BUILDERS[name](stage, duration)
        js["animations"].append(
            build_clip(js, binary, name, duration, sample, name in LOOPING)
        )
    replaced = 0
    if stage in CRITICAL_SPECS:
        # Replace the frozen critical stills in place so the clip order and
        # every other delivered animation stay untouched.
        replacements = {
            name: build_clip(
                js, binary, name, duration,
                critical_idle(stage, name), True,
            )
            for name, duration in CRITICAL_SPECS[stage].items()
        }
        for index, anim in enumerate(js["animations"]):
            name = anim.get("name")
            if name in replacements:
                js["animations"][index] = replacements.pop(name)
                replaced += 1
        if replacements:
            raise ValueError(
                f"{stage}: missing critical clips {sorted(replacements)}"
            )
    js["buffers"][0]["byteLength"] = len(binary)
    js["asset"]["generator"] = "drako_animate.py"
    write_glb(js, binary, dst)
    print(
        f"{stage}: {src} -> {dst} "
        f"({len(binary) / 1e6:.2f} MB bin, {len(js['animations'])} clips, "
        f"{replaced} critical spell(s) replaced)"
    )


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: drako_animate.py <source_dir> <out_dir>")
    src_dir, out_dir = sys.argv[1], sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    for stage in ("bayi", "remaja", "dewasa"):
        rebuild(
            os.path.join(src_dir, f"drako_{stage}.glb"),
            os.path.join(out_dir, f"drako_{stage}.glb"),
            stage,
        )


if __name__ == "__main__":
    main()
