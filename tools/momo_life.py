"""Append six "life" animation clips to the three repaired Momo GLBs.

The repaired assets already contain six localized clips (idle_fresh, idle_tired,
idle_critical, sleep, tap_reaction, celebrate). This script only appends:
  greet (2.0s), look_around (3.0s), groom (3.2s), stretch (2.6s),
  walk (1.2s loop), petting (2.0s)

Every new clip has 26 channels like the existing ones:
  22 joint rotations + Hips.translation + Chest.scale + Blink_L/R weights.

Hard deformation rules:
  * Chest.scale is always (1, 1, 1)
  * Hips.translation is always the Hips node rest translation (no global body
    movement; the native window owns translation)
  * Root.rotation stays identity
  * all motion is joint rotation plus eyelid morph weights
  * Neck receives 78% of the authored head rotation via share_head_motion(),
    Head keeps 22%, matching the face weighting of the repaired rig

The original GLBs are copied to %TEMP%/momo_life_backup before any write, and
an existing backup is never overwritten (a timestamp suffix is added instead).

Usage:
    python tools/momo_life.py
    python tools/momo_life.py mobile/assets/3d/momo_bayi.glb [...]
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

from momo_animate import (  # noqa: E402  (path set above)
    FPS,
    JOINTS,
    P,
    STAGE,
    add_accessor,
    keyed,
    load_glb,
    qeuler,
    rest_translation,
    share_head_motion,
    smoothstep,
    write_glb,
)

FILES = ("momo_bayi.glb", "momo_remaja.glb", "momo_dewasa.glb")
ASSETS = TOOLS.parent / "mobile" / "assets" / "3d"
LEGACY = (
    "idle_fresh", "idle_tired", "idle_critical", "sleep", "tap_reaction",
    "celebrate",
)
LIFE = (
    ("greet", 2.0),
    ("look_around", 3.0),
    ("groom", 3.2),
    ("stretch", 2.6),
    ("walk", 1.2),
    ("petting", 2.0),
)
LOOPS = {"walk"}


def pulse(t, center, width):
    """Smooth 0 -> 1 -> 0 blink pulse with exact zero outside its support."""
    if abs(t - center) >= width:
        return 0.0
    u = (t - (center - width)) / (2.0 * width)
    return 0.5 - 0.5 * math.cos(2.0 * math.pi * u)


# ---------------------------------------------------------------- new clips

def greet(stage):
    """Looks up, nods hello, ears perk, tail wags, one blink.

    The front paws are chest fur, not articulated limbs: raising them tears
    the chest open into a fur "wing". So the greeting is carried by the head,
    ears, spine and tail, with only a tiny paw lift for weight.
    """
    s = STAGE[stage]
    cfg = {
        1: dict(nod=1.18, tilt=6.0, beats=2.0, tail=1.0, ear=9.0, lift=6.0),
        2: dict(nod=1.00, tilt=3.5, beats=3.0, tail=1.25, ear=11.0, lift=5.0),
        3: dict(nod=0.75, tilt=2.3, beats=1.5, tail=0.75, ear=7.0, lift=4.0),
    }[stage]
    tail = s["tail"]

    def pose(t):
        up = smoothstep(0.24, 0.52, t) * (1.0 - smoothstep(1.52, 1.86, t))
        beat = math.sin(2.0 * math.pi * cfg["beats"] * (t - 0.45) / 0.9)
        nod = math.sin(2.0 * math.pi * 1.4 * (t - 0.32))
        sway = math.sin(2.0 * math.pi * 1.1 * (t - 0.30))
        tail_ph = 2.0 * math.pi * s["tail_cycles"] * t / 2.0
        amp = 0.55 * cfg["tail"]
        blink = 0.95 * pulse(t, 1.16, 0.17)
        return P(
            spine=(-1.4 * up, 0.0, -1.2 * up * sway),
            chest=(0.0, 0.0, 0.8 * up * sway),
            neck=(-1.2 * up, 1.0 * up * sway, -0.5 * up * cfg["tilt"] / 6.0),
            head=((-10.0 + 2.2 * nod) * cfg["nod"] * up,
                  4.5 * sway * up,
                  -cfg["tilt"] * up),
            ear_l=(0.0, 1.5 * up * sway, cfg["ear"] * up),
            ear_r=(0.0, 1.5 * up * sway, -cfg["ear"] * up),
            arm_l=(0.0, 0.0, -1.5 * up),
            forearm_l=(0.0, 0.0, 0.8 * up),
            paw_l=(0.0, 0.0, 0.0),
            arm_r=(-3.0 * up, 0.0, (cfg["lift"] + 1.2 * beat) * up),
            forearm_r=(-1.0 * up, 0.0, 0.45 * cfg["lift"] * up),
            paw_r=(0.0, 0.0, 0.35 * cfg["lift"] * beat * up),
            leg_l=(0.0, 0.0, -0.8 * up * sway),
            foot_l=(0.0, 0.0, 0.5 * up * sway),
            leg_r=(0.0, 0.0, 0.8 * up * sway),
            foot_r=(0.0, 0.0, -0.5 * up * sway),
            tail1=(2.5 * up, tail[0] * amp * up * math.sin(tail_ph), 0.0),
            tail2=(3.0 * up, tail[1] * amp * up * math.sin(tail_ph - 0.40), 0.0),
            tail3=(2.5 * up, tail[2] * amp * up * math.sin(tail_ph - 0.80), 0.0),
            tail_tip=(2.0 * up, tail[3] * amp * up * math.sin(tail_ph - 1.20), 0.0),
            blink=blink,
        )
    return pose


def look_around(stage):
    """Turn left, pause, turn right, return; ears follow, tail sways, blink."""
    s = STAGE[stage]
    look = s["look"]
    tail = s["tail"]
    ear_y = look * 0.55
    amp = 0.55

    def tail_pose(scale, phase=0.0):
        return dict(
            tail1=(3.5, tail[0] * amp * scale, 0.0),
            tail2=(3.0, tail[1] * amp * scale * math.cos(phase), 0.0),
            tail3=(2.5, tail[2] * amp * scale * math.cos(phase), 0.0),
            tail_tip=(2.0, tail[3] * amp * scale * math.cos(phase), 0.0),
        )

    keys = [
        (0.0, P()),
        (0.45, P(
            spine=(0.0, look * 0.05, 0.0),
            chest=(0.0, look * 0.04, 0.0),
            neck=(0.0, look * 0.05, 0.0),
            head=(1.4, look * 0.50, -0.8),
            ear_l=(0.0, ear_y * 0.45, 3.0),
            ear_r=(0.0, ear_y * 0.45, -3.0),
            **tail_pose(0.45),
        )),
        (0.95, P(
            spine=(0.0, look * 0.10, -0.6),
            chest=(0.0, look * 0.05, 0.0),
            neck=(0.0, look * 0.07, 0.0),
            head=(0.0, look, -1.2),
            ear_l=(0.0, ear_y, 4.5),
            ear_r=(0.0, ear_y, -4.5),
            **tail_pose(0.90),
        )),
        (1.50, P(
            spine=(0.0, look * 0.08, -0.5),
            chest=(0.0, look * 0.04, 0.0),
            neck=(0.0, look * 0.05, 0.0),
            head=(1.2, look * 0.95, -1.0),
            ear_l=(0.0, ear_y * 0.95, 4.0),
            ear_r=(0.0, ear_y * 0.95, -4.0),
            **tail_pose(0.95, math.pi * 0.35),
        )),
        (1.95, P(
            spine=(0.0, -look * 0.10, 0.6),
            chest=(0.0, -look * 0.05, 0.0),
            neck=(0.0, -look * 0.07, 0.0),
            head=(0.0, -look, 1.2),
            ear_l=(0.0, -ear_y, 4.5),
            ear_r=(0.0, -ear_y, -4.5),
            **tail_pose(-0.85),
        )),
        (2.45, P(
            spine=(0.0, -look * 0.08, 0.5),
            chest=(0.0, -look * 0.04, 0.0),
            neck=(0.0, -look * 0.05, 0.0),
            head=(1.0, -look * 0.92, 1.0),
            ear_l=(0.0, -ear_y * 0.92, 3.8),
            ear_r=(0.0, -ear_y * 0.92, -3.8),
            **tail_pose(-0.30, math.pi * 0.5),
        )),
        (2.70, P(
            head=(1.5, 0.0, 0.0),
            ear_l=(0.0, 0.0, 3.0),
            ear_r=(0.0, 0.0, -3.0),
            **tail_pose(0.30, math.pi * 0.7),
        )),
        (2.84, P(
            head=(0.8, 0.0, 0.0),
            ear_l=(0.0, 0.0, 2.0),
            ear_r=(0.0, 0.0, -2.0),
            tail1=(2.0, tail[0] * 0.12, 0.0),
            tail2=(1.8, tail[1] * 0.12, 0.0),
            tail3=(1.5, tail[2] * 0.12, 0.0),
            tail_tip=(1.2, tail[3] * 0.12, 0.0),
            blink=0.92,
        )),
        (2.95, P(
            head=(0.2, 0.0, 0.0),
            ear_l=(0.0, 0.0, 0.5),
            ear_r=(0.0, 0.0, -0.5),
            tail1=(0.5, tail[0] * 0.03, 0.0),
            tail2=(0.4, tail[1] * 0.03, 0.0),
            tail3=(0.3, tail[2] * 0.03, 0.0),
            tail_tip=(0.2, tail[3] * 0.03, 0.0),
            blink=0.08,
        )),
        (3.0, P()),
    ]
    return keyed(keys)


def groom(stage):
    """Head dips to the planted right paw, rubs twice, eyes half closed.

    The paw itself barely moves: only the head travels down to meet it.
    """
    cfg = {
        1: dict(lean=1.15, strokes=2.2, eye=0.76),
        2: dict(lean=1.00, strokes=3.0, eye=0.82),
        3: dict(lean=0.82, strokes=1.7, eye=0.78),
    }[stage]

    def pose(t):
        up = smoothstep(0.30, 0.82, t) * (1.0 - smoothstep(2.62, 2.98, t))
        stroke_env = smoothstep(0.90, 1.08, t) * (1.0 - smoothstep(2.25, 2.48, t))
        stroke = math.sin(2.0 * math.pi * cfg["strokes"] * (t - 0.90)) * stroke_env
        nuzzle = math.sin(2.0 * math.pi * 0.9 * (t - 0.60)) * up
        lean = cfg["lean"]
        blink = cfg["eye"] * smoothstep(0.55, 1.0, t) * (
            1.0 - smoothstep(2.45, 2.95, t)
        )
        tail_ph = 2.0 * math.pi * 0.55 * t
        return P(
            spine=(3.4 * up, 1.2 * up, 0.6 * nuzzle),
            chest=(1.0 * up, 0.5 * up, 0.0),
            neck=(1.2 * up, 1.5 * up, -1.2 * up),
            head=((15.0 + 1.2 * stroke + 0.8 * nuzzle) * lean * up,
                  4.5 * lean * up + 0.4 * nuzzle,
                  -8.0 * lean * up + 0.8 * stroke * up),
            ear_l=(0.0, 2.5 * up, -6.0 * up),
            ear_r=(0.0, 2.5 * up, 6.0 * up),
            arm_r=(-3.0 * up, 0.0, -5.0 * lean * up - 0.8 * stroke),
            forearm_r=(-1.0 * up, 0.0, -5.0 * lean * up - 1.2 * stroke),
            paw_r=(2.0 * up, 0.0, -2.0 * up - 0.8 * stroke),
            arm_l=(0.0, 0.0, 3.0 * up),
            forearm_l=(0.0, 0.0, -1.5 * up),
            paw_l=(0.0, 0.0, 0.8 * up),
            leg_l=(0.0, 0.0, -0.8 * up),
            foot_l=(0.0, 0.0, 0.5 * up),
            leg_r=(0.0, 0.0, 0.8 * up),
            foot_r=(0.0, 0.0, -0.5 * up),
            tail1=(-3.5 * up, 6.0 * up + 1.2 * up * math.sin(tail_ph), 0.0),
            tail2=(-3.0 * up, 9.0 * up + 1.4 * up * math.sin(tail_ph - 0.40), 0.0),
            tail3=(-2.5 * up, 12.0 * up + 1.6 * up * math.sin(tail_ph - 0.80), 0.0),
            tail_tip=(-2.0 * up, 14.0 * up + 1.8 * up * math.sin(tail_ph - 1.20), 0.0),
            blink=blink,
        )
    return pose


def stretch(stage):
    """Chest lowers, back arches, head rises then dips; arms only drift.

    Reaching the front paws out drags the chest fur flap with them (it is not
    an articulated limb), so the arch and the head do all the work here.
    """
    k = {1: 1.12, 2: 1.0, 3: 0.82}[stage]
    keys = [
        (0.0, P()),
        (0.30, P(
            spine=(4.0 * k, 0.0, 0.0),
            chest=(-1.0 * k, 0.0, 0.0),
            neck=(1.0 * k, 0.0, 0.0),
            head=(3.0 * k, 0.0, 0.0),
            ear_l=(0.0, 0.0, -2.0 * k),
            ear_r=(0.0, 0.0, 2.0 * k),
            arm_l=(-4.0 * k, 0.0, -1.0),
            forearm_l=(-1.5 * k, 0.0, 0.0),
            paw_l=(-1.0 * k, 0.0, 0.0),
            arm_r=(-4.0 * k, 0.0, 1.0),
            forearm_r=(-1.5 * k, 0.0, 0.0),
            paw_r=(-1.0 * k, 0.0, 0.0),
            tail1=(3.0 * k, 1.0 * k, 0.0),
            tail2=(4.0 * k, 1.5 * k, 0.0),
            tail3=(3.5 * k, 2.0 * k, 0.0),
            tail_tip=(3.0 * k, 2.5 * k, 0.0),
        )),
        (0.78, P(
            spine=(13.0 * k, 0.0, 0.0),
            chest=(-5.0 * k, 0.0, 0.0),
            neck=(-5.0 * k, 0.0, 0.0),
            head=(-12.0 * k, 0.0, 0.0),
            ear_l=(0.0, 0.0, -3.0 * k),
            ear_r=(0.0, 0.0, 3.0 * k),
            arm_l=(-12.0 * k, 0.0, -2.0 * k),
            forearm_l=(-4.0 * k, 0.0, 0.0),
            paw_l=(-2.0 * k, 0.0, 0.0),
            arm_r=(-12.0 * k, 0.0, 2.0 * k),
            forearm_r=(-4.0 * k, 0.0, 0.0),
            paw_r=(-2.0 * k, 0.0, 0.0),
            leg_l=(-2.0 * k, 0.0, -1.0 * k),
            leg_r=(-2.0 * k, 0.0, 1.0 * k),
            foot_l=(1.0 * k, 0.0, 0.0),
            foot_r=(1.0 * k, 0.0, 0.0),
            tail1=(12.0 * k, 2.0 * k, 0.0),
            tail2=(14.0 * k, 3.0 * k, 0.0),
            tail3=(12.0 * k, 4.0 * k, 0.0),
            tail_tip=(8.0 * k, 5.0 * k, 0.0),
        )),
        (1.18, P(
            spine=(15.0 * k, 0.0, 0.0),
            chest=(-6.0 * k, 0.0, 0.0),
            neck=(-6.0 * k, 0.0, 0.0),
            head=(-16.0 * k, 0.0, 0.0),
            ear_l=(0.0, 0.0, -3.5 * k),
            ear_r=(0.0, 0.0, 3.5 * k),
            arm_l=(-14.0 * k, 0.0, -2.5 * k),
            forearm_l=(-5.0 * k, 0.0, 0.0),
            paw_l=(-2.5 * k, 0.0, 0.0),
            arm_r=(-14.0 * k, 0.0, 2.5 * k),
            forearm_r=(-5.0 * k, 0.0, 0.0),
            paw_r=(-2.5 * k, 0.0, 0.0),
            leg_l=(-2.5 * k, 0.0, -1.0 * k),
            leg_r=(-2.5 * k, 0.0, 1.0 * k),
            foot_l=(1.2 * k, 0.0, 0.0),
            foot_r=(1.2 * k, 0.0, 0.0),
            tail1=(15.0 * k, 2.0 * k, 0.0),
            tail2=(17.0 * k, 3.0 * k, 0.0),
            tail3=(14.0 * k, 4.0 * k, 0.0),
            tail_tip=(9.0 * k, 5.0 * k, 0.0),
        )),
        (1.55, P(
            spine=(11.0 * k, 0.0, 0.0),
            chest=(-4.0 * k, 0.0, 0.0),
            neck=(2.0 * k, 0.0, 0.0),
            head=(6.0 * k, 0.0, 0.0),
            ear_l=(0.0, 0.0, -2.0 * k),
            ear_r=(0.0, 0.0, 2.0 * k),
            arm_l=(-10.0 * k, 0.0, -2.0 * k),
            forearm_l=(-4.0 * k, 0.0, 0.0),
            paw_l=(-2.0 * k, 0.0, 0.0),
            arm_r=(-10.0 * k, 0.0, 2.0 * k),
            forearm_r=(-4.0 * k, 0.0, 0.0),
            paw_r=(-2.0 * k, 0.0, 0.0),
            tail1=(9.0 * k, -1.0 * k, 0.0),
            tail2=(10.0 * k, -2.0 * k, 0.0),
            tail3=(8.0 * k, -2.5 * k, 0.0),
            tail_tip=(6.0 * k, -3.0 * k, 0.0),
            blink=0.90,
        )),
        (1.90, P(
            spine=(5.5 * k, 0.0, 0.0),
            chest=(-2.0 * k, 0.0, 0.0),
            neck=(1.0 * k, 0.0, 0.0),
            head=(7.0 * k, 0.0, 0.0),
            ear_l=(0.0, 0.0, -1.0 * k),
            ear_r=(0.0, 0.0, 1.0 * k),
            arm_l=(-5.0 * k, 0.0, -1.0),
            forearm_l=(-2.0 * k, 0.0, 0.0),
            arm_r=(-5.0 * k, 0.0, 1.0),
            forearm_r=(-2.0 * k, 0.0, 0.0),
            tail1=(5.0 * k, -1.0 * k, 0.0),
            tail2=(5.5 * k, -2.0 * k, 0.0),
            tail3=(4.5 * k, -2.5 * k, 0.0),
            tail_tip=(3.0 * k, -3.0 * k, 0.0),
            blink=0.30,
        )),
        (2.20, P(
            spine=(-1.2, 0.0, 0.0),
            head=(-2.0, 0.0, 0.0),
            arm_l=(-1.5, 0.0, 0.0),
            arm_r=(-1.5, 0.0, 0.0),
            tail1=(1.5, 0.5, 0.0),
            tail2=(1.5, 1.0, 0.0),
            tail3=(1.0, 1.2, 0.0),
            tail_tip=(0.8, 1.4, 0.0),
            blink=0.10,
        )),
        (2.6, P()),
    ]
    return keyed(keys)


def walk(stage):
    """Walk-in-place: alternating legs, counter-swinging arms, stable head/tail."""
    amp = {1: 7.0, 2: 8.5, 3: 6.0}[stage]
    arm_amp = amp * 0.55
    tail = STAGE[stage]["tail"]

    def pose(t):
        ph = 2.0 * math.pi * t / 1.2
        s = math.sin(ph)
        return P(
            spine=(0.0, -0.6 * s, 0.9 * s),
            chest=(0.0, 0.0, -0.5 * s),
            neck=(0.0, 0.3 * s, -0.2 * s),
            head=(0.8 * math.sin(2.0 * ph), 0.0, -0.3 * s),
            ear_l=(0.0, 0.0, 1.5),
            ear_r=(0.0, 0.0, -1.5),
            arm_l=(-arm_amp * s, 0.0, 1.5),
            forearm_l=(-2.0 * s, 0.0, 0.0),
            paw_l=(1.0 * s, 0.0, 0.0),
            arm_r=(arm_amp * s, 0.0, -1.5),
            forearm_r=(2.0 * s, 0.0, 0.0),
            paw_r=(-1.0 * s, 0.0, 0.0),
            leg_l=(amp * s, 0.0, 0.0),
            foot_l=(-0.45 * amp * s, 0.0, 0.0),
            leg_r=(-amp * s, 0.0, 0.0),
            foot_r=(0.45 * amp * s, 0.0, 0.0),
            tail1=(2.0, tail[0] * 0.22 * math.sin(ph - 0.25), 0.0),
            tail2=(2.0, tail[1] * 0.22 * math.sin(ph - 0.55), 0.0),
            tail3=(1.5, tail[2] * 0.22 * math.sin(ph - 0.85), 0.0),
            tail_tip=(1.0, tail[3] * 0.22 * math.sin(ph - 1.15), 0.0),
            blink=0.0,
        )
    return pose


def petting(stage):
    """Eyes close, head leans/tips into the touch, ears relax, tail curls slowly."""
    lean = {1: 1.12, 2: 1.0, 3: 0.82}[stage]
    tail = STAGE[stage]["tail"]
    amp = 0.85

    def tpose(scale, phase=0.0):
        return dict(
            tail1=(-5.0 * scale, tail[0] * amp * scale, 0.0),
            tail2=(-4.5 * scale, tail[1] * amp * scale * math.cos(phase), 0.0),
            tail3=(-4.0 * scale, tail[2] * amp * scale * math.cos(phase + 0.2), 0.0),
            tail_tip=(-3.0 * scale, tail[3] * amp * scale * math.cos(phase + 0.4), 0.0),
        )

    keys = [
        (0.0, P()),
        (0.22, P(
            spine=(0.8 * lean, -1.2 * lean, 0.8 * lean),
            chest=(0.0, -0.5 * lean, 0.5 * lean),
            neck=(0.0, -0.5 * lean, 0.5 * lean),
            head=(1.5 * lean, -2.0 * lean, 3.0 * lean),
            ear_l=(0.0, -1.5 * lean, -3.0 * lean),
            ear_r=(0.0, -1.5 * lean, 3.0 * lean),
            arm_l=(0.0, 0.0, 1.5 * lean),
            arm_r=(0.0, 0.0, -1.5 * lean),
            **tpose(0.35),
            blink=0.25,
        )),
        (0.50, P(
            spine=(1.5 * lean, -2.0 * lean, 1.5 * lean),
            chest=(0.0, -0.8 * lean, 0.8 * lean),
            neck=(0.0, -1.0 * lean, 1.5 * lean),
            head=(4.0 * lean, -6.0 * lean, 8.0 * lean),
            ear_l=(0.0, -2.0 * lean, -9.0 * lean),
            ear_r=(0.0, -2.0 * lean, 9.0 * lean),
            arm_l=(0.0, 0.0, 2.0 * lean),
            arm_r=(0.0, 0.0, -2.0 * lean),
            **tpose(0.72, math.pi * 0.20),
            blink=0.90,
        )),
        (0.85, P(
            spine=(1.8 * lean, -2.4 * lean, 1.8 * lean),
            chest=(0.0, -1.0 * lean, 1.0 * lean),
            neck=(0.0, -1.2 * lean, 1.8 * lean),
            head=(5.0 * lean, -6.0 * lean, 9.0 * lean),
            ear_l=(0.0, -2.2 * lean, -10.0 * lean),
            ear_r=(0.0, -2.2 * lean, 10.0 * lean),
            arm_l=(0.0, 0.0, 2.5 * lean),
            arm_r=(0.0, 0.0, -2.5 * lean),
            **tpose(1.0, math.pi * 0.45),
            blink=1.0,
        )),
        (1.25, P(
            spine=(1.6 * lean, -2.2 * lean, 1.6 * lean),
            chest=(0.0, -0.9 * lean, 0.9 * lean),
            neck=(0.0, -1.1 * lean, 1.6 * lean),
            head=(5.0 * lean, -5.0 * lean, 8.0 * lean),
            ear_l=(0.0, -2.0 * lean, -9.5 * lean),
            ear_r=(0.0, -2.0 * lean, 9.5 * lean),
            arm_l=(0.0, 0.0, 2.2 * lean),
            arm_r=(0.0, 0.0, -2.2 * lean),
            **tpose(0.95, math.pi * 0.70),
            blink=1.0,
        )),
        (1.55, P(
            spine=(1.2 * lean, -1.8 * lean, 1.2 * lean),
            chest=(0.0, -0.7 * lean, 0.7 * lean),
            neck=(0.0, -0.9 * lean, 1.2 * lean),
            head=(4.0 * lean, -4.0 * lean, 7.0 * lean),
            ear_l=(0.0, -1.8 * lean, -8.0 * lean),
            ear_r=(0.0, -1.8 * lean, 8.0 * lean),
            arm_l=(0.0, 0.0, 1.8 * lean),
            arm_r=(0.0, 0.0, -1.8 * lean),
            **tpose(0.75, math.pi * 0.95),
            blink=0.92,
        )),
        (1.78, P(
            spine=(0.6 * lean, -0.9 * lean, 0.6 * lean),
            neck=(0.0, -0.4 * lean, 0.6 * lean),
            head=(2.0 * lean, -2.0 * lean, 3.0 * lean),
            ear_l=(0.0, -0.8 * lean, -4.0 * lean),
            ear_r=(0.0, -0.8 * lean, 4.0 * lean),
            **tpose(0.35, math.pi * 1.15),
            blink=0.40,
        )),
        (2.0, P()),
    ]
    return keyed(keys)


CLIPS = {
    "greet": greet,
    "look_around": look_around,
    "groom": groom,
    "stretch": stretch,
    "walk": walk,
    "petting": petting,
}


# ---------------------------------------------------------------- GLB writer

def detect_stage(path):
    lowered = str(path).lower()
    if "remaja" in lowered:
        return 2
    if "dewasa" in lowered:
        return 3
    return 1


def build_clip(js, binary, hips_rest, name, duration, pose_fn, loop):
    frames = round(duration * FPS)
    times = [i * duration / frames for i in range(frames + 1)]
    poses = []
    for frame in range(frames + 1):
        t = 0.0 if (loop and frame == frames) else times[frame]
        pose = share_head_motion(pose_fn(t))
        pose["rot"]["Root"] = (0.0, 0.0, 0.0)
        rotations = {}
        for joint in JOINTS:
            value = qeuler(pose["rot"][joint])
            if not all(math.isfinite(component) for component in value):
                raise ValueError(f"{name}.{joint}: non-finite rotation at t={t:.3f}")
            rotations[joint] = value
        blink = max(0.0, min(1.0, float(pose["blink"])))
        poses.append((rotations, blink))

    nodes = {node["name"]: i for i, node in enumerate(js["nodes"]) if node.get("name")}
    for joint in JOINTS:
        if joint not in nodes:
            raise ValueError(f"missing joint node {joint!r}")
    for target in ("Blink_L", "Blink_R", "Hips", "Chest"):
        if target not in nodes:
            raise ValueError(f"missing target node {target!r}")

    channels = []
    samplers = []

    def add_channel(node, path, values, kind):
        source = add_accessor(js, binary, [(t,) for t in times], "SCALAR", minmax=True)
        output = add_accessor(js, binary, values, kind)
        samplers.append({"input": source, "output": output,
                         "interpolation": "LINEAR"})
        channels.append({"sampler": len(samplers) - 1,
                         "target": {"node": nodes[node], "path": path}})

    for joint in JOINTS:
        add_channel(joint, "rotation", [pose[0][joint] for pose in poses], "VEC4")
    add_channel("Hips", "translation",
                [tuple(float(v) for v in hips_rest)] * len(times), "VEC3")
    add_channel("Chest", "scale", [(1.0, 1.0, 1.0)] * len(times), "VEC3")
    add_channel("Blink_L", "weights", [(pose[1],) for pose in poses], "SCALAR")
    add_channel("Blink_R", "weights", [(pose[1],) for pose in poses], "SCALAR")
    return {"name": name, "samplers": samplers, "channels": channels}


def backup_original(path, root):
    root.mkdir(parents=True, exist_ok=True)
    destination = root / path.name
    if destination.exists():
        stamp = time.strftime("%Y%m%d_%H%M%S")
        destination = root / f"{path.stem}_{stamp}{path.suffix}"
        counter = 2
        while destination.exists():
            destination = root / f"{path.stem}_{stamp}_{counter}{path.suffix}"
            counter += 1
    shutil.copy2(path, destination)
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    backup_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
    if source_hash != backup_hash:
        raise RuntimeError(f"backup verification failed for {path}")
    return destination


def append_clips(path):
    js, binary = load_glb(path)
    animations = js.get("animations", [])
    names = [animation.get("name") for animation in animations]
    if names != list(LEGACY):
        raise SystemExit(
            f"{path}: expected the six repaired legacy clips in order, found {names}; "
            f"restore the original backup before running this script"
        )

    stage = detect_stage(path)
    hips_rest = rest_translation(js)["Hips"]
    before = path.stat().st_size
    for name, duration in LIFE:
        clip = build_clip(
            js, binary, hips_rest, name, duration, CLIPS[name](stage),
            loop=name in LOOPS,
        )
        js["animations"].append(clip)
    js["buffers"][0]["byteLength"] = len(binary)

    temporary = path.with_name(path.name + ".tmp")
    try:
        write_glb(js, binary, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    after = path.stat().st_size
    return stage, before, after, len(binary), len(js["animations"])


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*", type=Path,
                        help="GLBs to append to (default: three stage assets)")
    args = parser.parse_args(argv)
    paths = args.files or [ASSETS / name for name in FILES]
    for path in paths:
        if not path.is_file():
            raise SystemExit(f"missing input {path}")

    backup_root = Path(tempfile.gettempdir()) / "momo_life_backup"
    print(f"backup: {backup_root}")
    backups = {}
    for path in paths:
        backups[path] = backup_original(path, backup_root)
        print(f"  {path.name} -> {backups[path].name}")

    for path in paths:
        stage, before, after, bin_size, count = append_clips(path)
        print(f"{path}: stage {stage}, {count} animations, "
              f"{before} -> {after} bytes (delta {after - before}), bin {bin_size}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
