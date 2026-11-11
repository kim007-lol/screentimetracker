"""Rebuild Momo's GLB animations with full-body, state-aware motion.

Why this exists
---------------
The delivered GLBs had six clips whose translation channels were authored as
deltas (Hips starting at 0,0,0) but stored as absolute node transforms. That
sank the skeleton half a unit, cropped the body out of the camera frame, and
made the character look stiff because most joints never moved.

This script replaces every clip with a rest-correct, full-body performance:
root, hips, spine, chest, neck, head, ears, arms, forearms, paws, legs, feet and
the four tail joints all get tracks in every clip so crossfades can never leave
a limb stuck in a previous pose. Eye blinks are added by a separate script.

Usage:
    python tools/momo_animate.py mobile/assets/3d/momo_bayi.glb out.glb

The writer appends new accessors to the existing BIN chunk and leaves the old,
unused animation accessors in place. That keeps the mesh, skin, textures and UVs
byte-for-byte untouched.
"""

from __future__ import annotations

import json
import math
import struct
import sys
from typing import Callable

FPS = 30
JOINTS = [
    "Root", "Hips", "Spine", "Chest", "Neck", "Head", "Ear_L", "Ear_R",
    "Arm_L", "Forearm_L", "Paw_L", "Arm_R", "Forearm_R", "Paw_R",
    "Leg_L", "Foot_L", "Leg_R", "Foot_R", "Tail_1", "Tail_2", "Tail_3",
    "Tail_Tip",
]
SHORT = {
    "root": "Root", "hips_rot": "Hips", "spine": "Spine", "chest": "Chest",
    "neck": "Neck", "head": "Head", "ear_l": "Ear_L", "ear_r": "Ear_R",
    "arm_l": "Arm_L", "forearm_l": "Forearm_L", "paw_l": "Paw_L",
    "arm_r": "Arm_R", "forearm_r": "Forearm_R", "paw_r": "Paw_R",
    "leg_l": "Leg_L", "foot_l": "Foot_L", "leg_r": "Leg_R", "foot_r": "Foot_R",
    "tail1": "Tail_1", "tail2": "Tail_2", "tail3": "Tail_3", "tail_tip": "Tail_Tip",
}
# Extra pose keys used by the eyelid/blink pass.
EXTRA = {"blink", "blink_l", "blink_r"}


def rest_translation(gltf: dict) -> dict[str, tuple[float, float, float]]:
    return {
        n["name"]: tuple(n.get("translation", (0.0, 0.0, 0.0)))
        for n in gltf["nodes"] if n.get("name")
    }


# ---------------------------------------------------------------- math helpers

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
    """Quaternion from degrees around local X, then Y, then Z."""
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


def bump(t, center, width):
    return math.exp(-((t - center) / width) ** 2)


def window(t, start, end, edge=0.28):
    return smoothstep(start, start + edge, t) * (1.0 - smoothstep(end - edge, end, t))


def twitch(t, center, amplitude):
    d = t - center
    if abs(d) > 0.55:
        return 0.0
    return amplitude * math.exp(-((d / 0.105) ** 2)) * math.sin(2 * math.pi * d / 0.17)


# ---------------------------------------------------------------- pose helpers

def P(hips=(0.0, 0.0, 0.0), chest_s=(1.0, 1.0, 1.0), blink=0.0, **rots):
    rot = {j: (0.0, 0.0, 0.0) for j in JOINTS}
    for k, v in rots.items():
        if k not in SHORT:
            raise KeyError(k)
        rot[SHORT[k]] = v
    return {"rot": rot, "hips": hips, "chest_s": chest_s, "blink": blink}


def lerp(a, b, u):
    return a + (b - a) * u


def lerp_pose(a, b, u):
    u = u * u * (3 - 2 * u)
    return {
        "rot": {j: tuple(lerp(a["rot"][j][i], b["rot"][j][i], u) for i in range(3)) for j in JOINTS},
        "hips": tuple(lerp(a["hips"][i], b["hips"][i], u) for i in range(3)),
        "chest_s": tuple(lerp(a["chest_s"][i], b["chest_s"][i], u) for i in range(3)),
        "blink": lerp(a["blink"], b["blink"], u),
    }


def keyed(keys):
    def pose(t):
        if t <= keys[0][0]:
            return keys[0][1]
        for (t0, p0), (t1, p1) in zip(keys, keys[1:]):
            if t <= t1:
                return lerp_pose(p0, p1, (t - t0) / (t1 - t0))
        return keys[-1][1]
    return pose


# ---------------------------------------------------------------- stage flavour

STAGE = {
    1: dict(breathe=0.020, sway=1.7, look=6.5, tail=(9, 15, 21, 27), tail_cycles=2,
            wave_arm=26, wave_paw=18, ear_twitch=14, hop=1.0),
    2: dict(breathe=0.024, sway=2.4, look=8.5, tail=(12, 18, 25, 33), tail_cycles=3,
            wave_arm=34, wave_paw=24, ear_twitch=18, hop=1.15),
    3: dict(breathe=0.017, sway=1.2, look=4.5, tail=(7, 11, 15, 20), tail_cycles=2,
            wave_arm=24, wave_paw=15, ear_twitch=10, hop=0.9),
}


def idle_fresh(stage: int, duration=8.0) -> Callable[[float], dict]:
    s = STAGE[stage]

    def pose(t):
        th = 2 * math.pi * t / duration
        breath = math.sin(2 * th)
        sway = math.sin(th)
        tail_ph = 2 * math.pi * s["tail_cycles"] * t / duration
        look = math.sin(th + 0.35)
        head_x = 1.7 * math.sin(2 * th + 0.9) + 0.9 * math.sin(th - 0.2)
        head_y = s["look"] * look
        head_z = 1.1 * math.sin(th - 0.7)
        ear_l = twitch(t, 1.9, s["ear_twitch"])
        ear_r = twitch(t, 5.35, s["ear_twitch"])
        wave = window(t, 3.1, 4.75)
        wave_beat = math.sin(2 * math.pi * 2.4 * (t - 3.1))
        paw_beat = math.sin(2 * math.pi * 3.1 * (t - 3.15))
        tail = s["tail"]
        return P(
            hips=(0.0028 * sway, 0.0035 * breath, 0.0),
            chest_s=(1 + s["breathe"] * breath,
                     1 + s["breathe"] * 1.35 * breath,
                     1 + s["breathe"] * breath),
            spine=(0.5 * breath, 0.35 * sway, -0.65 * sway),
            chest=(0.0, 0.2 * sway, 0.25 * sway),
            neck=(-0.35 * head_x, -0.4 * head_y, -0.3 * head_z),
            head=(head_x, head_y, head_z),
            ear_l=(-0.4 * breath, 0.0, -1.4 * sway + ear_l),
            ear_r=(0.4 * breath, 0.0, 1.4 * sway + ear_r + 5.0 * wave),
            arm_l=(1.4 * math.sin(2 * th + math.pi), 0.0, -1.0 * sway),
            forearm_l=(0.8 * math.sin(2 * th + math.pi - 0.4), 0.0, 0.8),
            paw_l=(0.0, 0.0, 0.6 * math.sin(th)),
            arm_r=(1.4 * math.sin(2 * th) - 2.0 * wave, 0.0,
                   1.0 * sway + 0.45 * s["wave_arm"] * wave + 2.0 * wave * wave_beat),
            forearm_r=(0.8 * math.sin(2 * th - 0.4), 0.0, 4.0 * wave),
            paw_r=(0.0, 0.0, 0.35 * s["wave_paw"] * wave * paw_beat),
            leg_l=(0.0, 0.0, -0.45 * sway),
            foot_l=(0.0, 0.0, 0.35 * sway),
            leg_r=(0.0, 0.0, 0.45 * sway),
            foot_r=(0.0, 0.0, -0.35 * sway),
            tail1=(-1.0 + 1.5 * breath, tail[0] * math.sin(tail_ph), 0.0),
            tail2=(-2.0 + 2.0 * breath, tail[1] * math.sin(tail_ph - 0.5), 0.0),
            tail3=(-3.0 + 2.5 * breath, tail[2] * math.sin(tail_ph - 1.0), 0.0),
            tail_tip=(-3.5 + 3.0 * breath, tail[3] * math.sin(tail_ph - 1.5), 0.0),
            blink=0.0,
        )
    return pose


def idle_tired(stage: int, duration=8.0) -> Callable[[float], dict]:
    s = STAGE[stage]

    def pose(t):
        th = 2 * math.pi * t / duration
        breath = math.sin(2 * th)
        sigh = window(t, 4.9, 6.0)
        sway = math.sin(th)
        ear_l = twitch(t, 3.3, s["ear_twitch"] * 0.35)
        ear_r = twitch(t, 6.6, s["ear_twitch"] * 0.3)
        tail_ph = 2 * math.pi * 2 * t / duration
        return P(
            hips=(0.0018 * sway, -0.026 + 0.003 * breath, 0.0),
            chest_s=(1 - 0.008 + 0.011 * breath,
                     1 - 0.012 + 0.015 * breath,
                     1 - 0.008 + 0.011 * breath),
            spine=(6.0 + 1.2 * breath - 0.8 * sigh, 0.2 * sway, -1.1 * sway),
            chest=(0.6 * breath, 0.0, 0.3 * sway),
            neck=(4.5 - 1.2 * sigh, -1.2 * sway, -0.5 * sway),
            head=(11.0 + 2.0 * math.sin(2 * th - 0.5) - 6.0 * sigh,
                  3.2 * math.sin(th + 0.4), 1.2 * math.sin(th - 0.5)),
            ear_l=(-1.0 * breath, 0.0, -13.0 - 1.2 * sway + ear_l + 4.0 * sigh),
            ear_r=(1.0 * breath, 0.0, 13.0 + 1.2 * sway + ear_r - 4.0 * sigh),
            arm_l=(0.8 * math.sin(2 * th + 0.4), 0.0, 4.0),
            forearm_l=(0.0, 0.0, -6.0),
            paw_l=(0.0, 0.0, 1.2 * breath),
            arm_r=(0.8 * math.sin(2 * th + math.pi + 0.4), 0.0, -4.0),
            forearm_r=(0.0, 0.0, 6.0),
            paw_r=(0.0, 0.0, -1.2 * breath),
            leg_l=(0.0, 0.0, -0.3 * sway),
            foot_l=(0.0, 0.0, 0.2 * sway),
            leg_r=(0.0, 0.0, 0.3 * sway),
            foot_r=(0.0, 0.0, -0.2 * sway),
            tail1=(-11.0, 4.0 * math.sin(tail_ph), 0.0),
            tail2=(-9.0, 6.0 * math.sin(tail_ph - 0.45), 0.0),
            tail3=(-7.0, 8.0 * math.sin(tail_ph - 0.9), 0.0),
            tail_tip=(-4.0, 10.0 * math.sin(tail_ph - 1.35), 0.0),
            blink=0.55,
        )
    return pose


def idle_critical(stage: int, duration=3.0) -> Callable[[float], dict]:
    s = STAGE[stage]

    def pose(t):
        th = 2 * math.pi * t / duration
        tremor = math.sin(2 * math.pi * 6 * t / duration)
        fast = math.sin(2 * math.pi * 10 * t / duration)
        breath = math.sin(2 * math.pi * 4 * t / duration)
        return P(
            hips=(0.0012 * tremor, -0.034 + 0.0015 * breath, 0.0),
            chest_s=(1 - 0.012 + 0.005 * breath,
                     1 - 0.016 + 0.007 * breath,
                     1 - 0.012 + 0.005 * breath),
            spine=(8.5 + 0.6 * tremor, 0.0, 1.0 * tremor),
            neck=(7.0 + 0.4 * tremor, 0.0, 0.8 * tremor),
            head=(14.0 + 1.0 * tremor, 1.8 * math.sin(th), 1.6 * tremor),
            ear_l=(0.0, 0.0, -15.0 + 2.5 * tremor),
            ear_r=(0.0, 0.0, 15.0 - 2.5 * tremor),
            arm_l=(0.0, 0.0, 8.0 + 1.0 * tremor),
            forearm_l=(0.0, 0.0, -8.0),
            paw_l=(0.0, 0.0, 1.5 * tremor),
            arm_r=(0.0, 0.0, -8.0 - 1.0 * tremor),
            forearm_r=(0.0, 0.0, 8.0),
            paw_r=(0.0, 0.0, -1.5 * tremor),
            leg_l=(0.0, 0.0, -0.4 * tremor),
            leg_r=(0.0, 0.0, 0.4 * tremor),
            tail1=(-15.0, 3.0 * math.sin(2 * math.pi * 2 * t / duration), 0.0),
            tail2=(-12.0, 4.0 * math.sin(2 * math.pi * 2 * t / duration - 0.5), 0.0),
            tail3=(-9.0, 5.0 * math.sin(2 * math.pi * 2 * t / duration - 1.0) + 2.0 * fast, 0.0),
            tail_tip=(-5.0, 3.0 * fast, 0.0),
            blink=0.32,
        )
    return pose


def sleep(stage: int, duration=8.0) -> Callable[[float], dict]:
    def pose(t):
        th = 2 * math.pi * t / duration
        breath = math.sin(2 * th)
        ear = twitch(t, 6.4, 6.0)
        return P(
            hips=(0.0, -0.043 + 0.0035 * breath, 0.0),
            chest_s=(1 - 0.012 + 0.016 * breath,
                     1 - 0.02 + 0.024 * breath,
                     1 - 0.012 + 0.016 * breath),
            spine=(10.5 + 1.0 * breath, 0.0, -0.6 * math.sin(th)),
            neck=(7.0, 0.0, 0.4 * math.sin(th)),
            head=(19.0 + 1.5 * breath, 1.5 * math.sin(th - 0.4), 4.0),
            ear_l=(0.0, 0.0, -20.0 + ear),
            ear_r=(0.0, 0.0, 20.0),
            arm_l=(0.0, 0.0, 10.0),
            forearm_l=(0.0, 0.0, -9.0),
            paw_l=(0.0, 0.0, 2.0),
            arm_r=(0.0, 0.0, -10.0),
            forearm_r=(0.0, 0.0, 9.0),
            paw_r=(0.0, 0.0, -2.0),
            leg_l=(0.0, 0.0, -1.0),
            leg_r=(0.0, 0.0, 1.0),
            tail1=(-10.0, 20.0 + 1.5 * math.sin(th), 0.0),
            tail2=(-9.0, 29.0 + 1.5 * math.sin(th - 0.35), 0.0),
            tail3=(-7.0, 25.0 + 1.5 * math.sin(th - 0.7), 0.0),
            tail_tip=(-4.0, 17.0 + 1.5 * math.sin(th - 1.0), 0.0),
            blink=1.0,
        )
    return pose


def tap_reaction(stage: int) -> Callable[[float], dict]:
    s = STAGE[stage]
    keys = [
        (0.0, P()),
        (0.12, P(hips=(0, -0.028, 0), chest_s=(0.985, 0.975, 0.985),
                 spine=(3.5, 0, 0), neck=(2.0, 0, 0), head=(4.0, 0, 0),
                 ear_l=(0, 0, -9), ear_r=(0, 0, 9),
                 arm_l=(0, 0, 6), arm_r=(0, 0, -6),
                 tail1=(-8, 0, 0), tail2=(-6, 0, 0), tail3=(-4, 0, 0),
                 blink=0.75)),
        (0.30, P(hips=(0, 0.078 * s["hop"], 0), chest_s=(1.055, 1.07, 1.055),
                 spine=(-2.0, 0, 0), neck=(-2.0, 0, 1.0), head=(-6.0, 2.0, -3.0),
                 ear_l=(0, 0, 10), ear_r=(0, 0, -10),
                 arm_l=(0, 0, -8), forearm_l=(0, 0, -3), paw_l=(0, 0, -4),
                 arm_r=(0, 0, 8), forearm_r=(0, 0, 3), paw_r=(0, 0, 4),
                 leg_l=(0, 0, -2), leg_r=(0, 0, 2),
                 tail1=(2, 15, 0), tail2=(2, 20, 0), tail3=(0, 24, 0), tail_tip=(0, 20, 0),
                 blink=0.0)),
        (0.47, P(hips=(0, -0.020, 0), chest_s=(0.972, 0.962, 0.972),
                 spine=(2.5, 0, 0), neck=(1.5, 0, 0), head=(3.5, -1.0, 1.5),
                 ear_l=(0, 0, -5), ear_r=(0, 0, 5),
                 arm_l=(0, 0, 4), arm_r=(0, 0, -4),
                 tail1=(-4, -8, 0), tail2=(-3, -10, 0), tail3=(-2, -12, 0),
                 blink=0.55)),
        (0.64, P(hips=(0, 0.012, 0), chest_s=(1.018, 1.024, 1.018),
                 spine=(-0.8, 0, 0), head=(-1.2, 0.5, -0.5),
                 ear_l=(0, 0, 3), ear_r=(0, 0, -3),
                 tail1=(0, 4, 0), tail2=(0, 5, 0), tail3=(0, 6, 0),
                 blink=0.15)),
        (0.82, P(hips=(0, -0.003, 0), chest_s=(0.996, 0.994, 0.996),
                 tail1=(0, -1.5, 0), tail2=(0, -2, 0), tail3=(0, -2.5, 0))),
        (1.0, P()),
    ]
    return keyed(keys)


def celebrate(stage: int) -> Callable[[float], dict]:
    s = STAGE[stage]
    keys = [
        (0.0, P()),
        (0.16, P(hips=(0, -0.035, 0), chest_s=(0.98, 0.97, 0.98),
                 spine=(4, 0, 0), head=(5, 0, 0), ear_l=(0, 0, -8), ear_r=(0, 0, 8),
                 arm_l=(0, 0, 4), arm_r=(0, 0, -4),
                 blink=0.6)),
        (0.42, P(hips=(0, 0.11 * s["hop"], 0), chest_s=(1.06, 1.075, 1.06),
                 root=(0, 78, 0), spine=(-3, 0, 0), head=(-8, 6, -4),
                 ear_l=(0, 0, 14), ear_r=(0, 0, -14),
                 arm_l=(0, 0, -13), forearm_l=(0, 0, -5), paw_l=(0, 0, -6),
                 arm_r=(0, 0, 13), forearm_r=(0, 0, 5), paw_r=(0, 0, 6),
                 leg_l=(0, 0, -3), leg_r=(0, 0, 3),
                 tail1=(4, 20, 0), tail2=(4, 26, 0), tail3=(2, 30, 0), tail_tip=(0, 24, 0),
                 blink=0.0)),
        (0.70, P(hips=(0, -0.015, 0), chest_s=(0.98, 0.97, 0.98),
                 root=(0, 160, 0), head=(2, 0, 3),
                 ear_l=(0, 0, 8), ear_r=(0, 0, -8),
                 arm_l=(0, 0, -6), arm_r=(0, 0, 6),
                 tail1=(-3, -10, 0), tail2=(-3, -14, 0), tail3=(-2, -18, 0),
                 blink=0.5)),
        (0.98, P(hips=(0, 0.10 * s["hop"], 0), chest_s=(1.05, 1.065, 1.05),
                 root=(0, 240, 0), spine=(-2, 0, 0), head=(-6, -4, 4),
                 ear_l=(0, 0, 14), ear_r=(0, 0, -14),
                 arm_l=(0, 0, -12), forearm_l=(0, 0, -4),
                 arm_r=(0, 0, 12), forearm_r=(0, 0, 4),
                 tail1=(4, -20, 0), tail2=(4, -26, 0), tail3=(2, -30, 0),
                 blink=0.0)),
        (1.28, P(hips=(0, -0.018, 0), chest_s=(0.975, 0.965, 0.975),
                 root=(0, 320, 0), head=(3, 0, 0),
                 tail1=(-2, 8, 0), tail2=(-2, 10, 0), tail3=(-1, 12, 0),
                 blink=0.35)),
        (1.58, P(hips=(0, 0.012, 0), chest_s=(1.02, 1.025, 1.02),
                 root=(0, 360, 0), head=(-1.5, 2, -1),
                 ear_l=(0, 0, 4), ear_r=(0, 0, -4),
                 tail1=(0, -4, 0), tail2=(0, -5, 0), tail3=(0, -6, 0),
                 blink=0.0)),
        (2.0, P(root=(0, 360, 0))),
    ]
    return keyed(keys)


# ---------------------------------------------------------------- GLB plumbing

def load_glb(path):
    raw = open(path, "rb").read()
    magic, version, _ = struct.unpack("<III", raw[:12])
    if magic != 0x46546C67 or version != 2:
        raise ValueError("not a glTF 2.0 binary")
    off = 12
    js = None
    binary = b""
    while off < len(raw):
        clen, ctype = struct.unpack("<II", raw[off:off + 8])
        off += 8
        data = raw[off:off + clen]
        off += clen
        if ctype == 0x4E4F534A:
            js = json.loads(data.decode("utf-8"))
        elif ctype == 0x004E4942:
            binary = bytearray(data)
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
    n = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}[kind]
    if len(binary) % 4:
        binary.extend(b"\x00" * (4 - len(binary) % 4))
    offset = len(binary)
    for v in values:
        binary.extend(struct.pack("<" + "f" * n, *v))
    view = {"buffer": 0, "byteOffset": offset, "byteLength": len(values) * n * 4}
    js["bufferViews"].append(view)
    acc = {"bufferView": len(js["bufferViews"]) - 1, "componentType": 5126,
           "count": len(values), "type": kind}
    if minmax:
        acc["min"] = [min(v[i] for v in values) for i in range(n)]
        acc["max"] = [max(v[i] for v in values) for i in range(n)]
    js["accessors"].append(acc)
    return len(js["accessors"]) - 1


def share_head_motion(pose):
    """Drive the face with Neck; keep a little local Head motion for ears/skull.

    The auto-rig pivots Head near the top of the skull, so a full Head rotation
    would swing the whole face around the crown. The face is weighted to Neck
    instead, which is the real head pivot for these chibis.
    """
    hx, hy, hz = pose["rot"]["Head"]
    nx, ny, nz = pose["rot"]["Neck"]
    pose["rot"]["Neck"] = (nx + 0.78 * hx, ny + 0.78 * hy, nz + 0.78 * hz)
    pose["rot"]["Head"] = (0.22 * hx, 0.22 * hy, 0.22 * hz)
    return pose


def read_scalars(js, binary, acc_index):
    """Read a SCALAR float accessor (the eyelid weight curves)."""
    acc = js["accessors"][acc_index]
    if acc["componentType"] != 5126 or acc["type"] != "SCALAR":
        raise ValueError(f"accessor {acc_index} is not a float SCALAR")
    view = js["bufferViews"][acc["bufferView"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride") or 4
    return [struct.unpack_from("<f", binary, start + i * stride)[0]
            for i in range(acc["count"])]


def legacy_blinks(js, binary, name):
    """Copy Blink_L/R weight curves out of the existing clip with this name.

    The body clips are re-authored here; the eyelid animation is authored by
    momo_rig and must survive the rewrite untouched, otherwise the eyes stop
    blinking (idle_fresh has no blink keys of its own).
    """
    node_names = [n.get("name") for n in js["nodes"]]
    for anim in js.get("animations", []):
        if anim.get("name") != name:
            continue
        found = {}
        for ch in anim["channels"]:
            if ch["target"]["path"] != "weights":
                continue
            node_name = node_names[ch["target"]["node"]]
            if node_name in ("Blink_L", "Blink_R"):
                sampler = anim["samplers"][ch["sampler"]]
                times = read_scalars(js, binary, sampler["input"])
                found[node_name] = (times, read_scalars(js, binary, sampler["output"]))
        return found
    raise ValueError(f"{name}: input GLB has no clip with eyelid weights; "
                     f"run momo_rig.py on the raw asset first")


def build_clip(js, binary, rest_t, name, duration, pose_fn, loop, blinks=None):
    frames = int(round(duration * FPS))
    times = [i * duration / frames for i in range(frames + 1)]
    poses = [share_head_motion(pose_fn((t % duration) if loop else t)) for t in times]
    nodes = {n["name"]: i for i, n in enumerate(js["nodes"]) if n.get("name")}
    channels = []
    samplers = []

    def add_channel(node_name, path, values, kind):
        nonlocal samplers
        src = add_accessor(js, binary, [(t,) for t in times], "SCALAR", minmax=True)
        out = add_accessor(js, binary, values, kind)
        samplers.append({"input": src, "output": out, "interpolation": "LINEAR"})
        channels.append({"sampler": len(samplers) - 1,
                         "target": {"node": nodes[node_name], "path": path}})

    for joint in JOINTS:
        quats = [qeuler(p["rot"][joint]) for p in poses]
        add_channel(joint, "rotation", quats, "VEC4")
    add_channel("Hips", "translation",
                [tuple(rest_t["Hips"][i] + p["hips"][i] for i in range(3)) for p in poses],
                "VEC3")
    add_channel("Chest", "scale", [tuple(p["chest_s"]) for p in poses], "VEC3")
    if blinks is not None:
        for side in ("Blink_L", "Blink_R"):
            src_times, values = blinks[side]
            if len(values) != len(times) or any(
                    abs(a - b) > 1e-6 for a, b in zip(src_times, times)):
                raise ValueError(f"{name}: eyelid keys no longer match the clip frames")
            add_channel(side, "weights", [(v,) for v in values], "SCALAR")
    return {"name": name, "samplers": samplers, "channels": channels}


def rebuild(path_in, path_out):
    js, binary = load_glb(path_in)
    rest_t = rest_translation(js)
    stage = 1
    base = path_in.lower()
    if "remaja" in base:
        stage = 2
    elif "dewasa" in base:
        stage = 3
    specs = [
        ("idle_fresh", 8.0, idle_fresh(stage), True),
        ("idle_tired", 8.0, idle_tired(stage), True),
        ("idle_critical", 3.0, idle_critical(stage), True),
        ("sleep", 8.0, sleep(stage), True),
        ("tap_reaction", 1.0, tap_reaction(stage), False),
        ("celebrate", 2.0, celebrate(stage), False),
    ]
    blinks = {name: legacy_blinks(js, binary, name) for name, *_ in specs}
    js["animations"] = [
        build_clip(js, binary, rest_t, name, dur, fn, loop, blinks=blinks[name])
        for name, dur, fn, loop in specs
    ]
    js["buffers"][0]["byteLength"] = len(binary)
    write_glb(js, binary, path_out)
    print(f"{path_in} -> {path_out} ({len(binary)/1e6:.2f} MB bin)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: momo_animate.py input.glb output.glb")
    rebuild(sys.argv[1], sys.argv[2])
