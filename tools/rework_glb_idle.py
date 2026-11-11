"""Replace full-body idle/tap clips with localized motion, in place.

The GLB already stores every animation channel with one output accessor per
channel. This script rewrites those float buffers (same count, same layout)
so no JSON or file structure changes are needed:

- posture from each clip's first keyframe is kept (mood lean, droopy ears,
  lowered hips, tail curve)
- Chest.scale is frozen at 1 and Hips.translation stays static, removing the
  whole-body "breathing"/bounce that deformed the face
- only ears, tail, eyelids, one paw and a tiny head tilt move
- celebrate stays untouched

Run: python tools/rework_glb_idle.py mobile/assets/3d/*.glb
"""

import json
import math
import os
import shutil
import struct
import sys
import tempfile

COMPONENT = {5126: ("f", 4)}
NCOMP = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}

CLIPS = ("idle_fresh", "idle_tired", "idle_critical", "sleep", "tap_reaction")


def load(path):
    with open(path, "rb") as f:
        data = bytearray(f.read())
    magic, version, length = struct.unpack_from("<III", data, 0)
    assert magic == 0x46546C67, "not a GLB"
    off = 12
    js = None
    bin_offset = None
    bin_len = 0
    while off < length:
        clen, ctype = struct.unpack_from("<II", data, off)
        if ctype == 0x4E4F534A:
            js = json.loads(bytes(data[off + 8: off + 8 + clen]).decode("utf-8"))
        elif ctype == 0x004E4942:
            bin_offset = off + 8
            bin_len = clen
        off += 8 + clen
    assert js is not None and bin_offset is not None
    return data, js, bin_offset, bin_len


def accessor_values(js, data, bin_offset, index):
    acc = js["accessors"][index]
    bv = js["bufferViews"][acc["bufferView"]]
    fmt, size = COMPONENT[acc["componentType"]]
    ncomp = NCOMP[acc["type"]]
    start = bin_offset + bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride", size * ncomp)
    out = []
    for i in range(acc["count"]):
        vals = struct.unpack_from("<" + fmt * ncomp, data, start + i * stride)
        out.append(vals[0] if ncomp == 1 else vals)
    return out, start, stride, ncomp


def write_accessor(js, data, bin_offset, index, values):
    acc = js["accessors"][index]
    bv = js["bufferViews"][acc["bufferView"]]
    fmt, size = COMPONENT[acc["componentType"]]
    ncomp = NCOMP[acc["type"]]
    assert len(values) == acc["count"]
    start = bin_offset + bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride", size * ncomp)
    for i, value in enumerate(values):
        if ncomp == 1:
            struct.pack_into("<" + fmt, data, start + i * stride, float(value))
        else:
            assert len(value) == ncomp
            struct.pack_into("<" + fmt * ncomp, data, start + i * stride,
                             *(float(v) for v in value))


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def qnormalize(q):
    n = math.sqrt(sum(v * v for v in q)) or 1.0
    return tuple(v / n for v in q)


def qaxis(axis, degrees):
    angle = math.radians(degrees) * 0.5
    s = math.sin(angle)
    x, y, z = axis
    return qnormalize((x * s, y * s, z * s, math.cos(angle)))


def smoothstep(a, b, t):
    if a == b:
        return 1.0 if t >= b else 0.0
    x = max(0.0, min(1.0, (t - a) / (b - a)))
    return x * x * (3.0 - 2.0 * x)


def bump(t, start, peak, end):
    if t <= start or t >= end:
        return 0.0
    if t < peak:
        return smoothstep(start, peak, t)
    return 1.0 - smoothstep(peak, end, t)


def blink_pulse(t, center, width=0.42):
    if t <= center - width or t >= center + width:
        return 0.0
    x = (t - (center - width)) / (2 * width)
    return 0.5 - 0.5 * math.cos(2 * math.pi * x)


TAIL_AMP = {
    "idle_fresh": (3.0, 5.0, 7.0, 9.0),
    "idle_tired": (1.5, 2.5, 3.5, 4.5),
    "idle_critical": (0.8, 1.5, 2.0, 2.5),
    "sleep": (0.5, 0.8, 1.2, 1.5),
    "tap_reaction": (0.0, 0.0, 0.0, 0.0),
}
TAIL_PERIOD = {
    "idle_fresh": 4.0, "idle_tired": 8.0, "idle_critical": 8.0,
    "sleep": 8.0, "tap_reaction": 1.0,
}
TAIL_PHASE = (0.0, 0.6, 1.2, 1.8)

BLINK = {
    "idle_fresh": (0.0, (1.5, 5.7)),
    "idle_tired": (0.52, (2.4, 6.4)),
    "idle_critical": (0.30, (1.2, 2.45)),
    "sleep": (1.0, ()),
    "tap_reaction": (0.0, ()),
}


def rotation_delta(clip, name, t, duration):
    delta = (0.0, 0.0, 0.0, 1.0)

    def add(axis, degrees):
        nonlocal delta
        if abs(degrees) > 1e-6:
            delta = qmul(delta, qaxis(axis, degrees))

    if name.startswith("Tail_"):
        index = {"Tail_1": 0, "Tail_2": 1, "Tail_3": 2, "Tail_Tip": 3}[name]
        phase = TAIL_PHASE[index]
        angle = TAIL_AMP[clip][index] * math.sin(
            2 * math.pi * (t / TAIL_PERIOD[clip]) + phase
        )
        add((0, 1, 0), angle)
        return delta
    if name in ("Ear_L", "Ear_R"):
        sign = -1.0 if name == "Ear_L" else -1.0
        if clip == "idle_fresh":
            center = 1.9 if name == "Ear_L" else 5.3
            add((0, 0, sign), 9.0 * bump(t, center - 0.22, center, center + 0.3))
        elif clip == "idle_tired":
            center = 5.7
            add((0, 0, sign), 2.5 * bump(t, center - 0.3, center, center + 0.4))
        elif clip == "idle_critical":
            center = 2.8
            add((0, 0, sign), 1.5 * bump(t, center - 0.2, center, center + 0.25))
        elif clip == "sleep":
            if name == "Ear_L":
                center = 6.4
                add((0, 0, 1), 2.0 * bump(t, center - 0.3, center, center + 0.4))
        elif clip == "tap_reaction":
            add((0, 0, 1 if name == "Ear_L" else -1),
                8.0 * bump(t, 0.03, 0.3, 0.94))
        return delta
    if name == "Arm_R":
        if clip == "idle_fresh":
            add((0, 0, 1), 5.0 * bump(t, 2.2, 3.6, 5.0))
        elif clip == "idle_tired":
            add((0, 0, 1), 1.5 * bump(t, 4.6, 6.0, 7.4))
        elif clip == "idle_critical":
            add((0, 0, 1), 0.8 * bump(t, 1.0, 1.5, 2.0))
        elif clip == "tap_reaction":
            add((0, 0, 1), 22.0 * bump(t, 0.03, 0.3, 0.94))
        return delta
    if name == "Forearm_R":
        if clip == "idle_fresh":
            add((0, 0, 1), 4.0 * bump(t, 2.4, 3.8, 5.2))
        elif clip == "idle_tired":
            add((0, 0, 1), 1.0 * bump(t, 4.8, 6.2, 7.6))
        elif clip == "tap_reaction":
            add((0, 0, 1), 10.0 * bump(t, 0.05, 0.32, 0.95))
        return delta
    if name == "Paw_R":
        if clip == "idle_fresh":
            add((0, 0, 1), 8.0 * bump(t, 2.5, 3.8, 5.2))
        elif clip == "idle_tired":
            add((0, 0, 1), 1.0 * bump(t, 4.9, 6.3, 7.7))
        elif clip == "tap_reaction":
            add((0, 0, 1), 14.0 * bump(t, 0.06, 0.34, 0.96))
        return delta
    if name == "Head":
        if clip == "idle_fresh":
            add((0, 1, 0), 0.7 * math.sin(2 * math.pi * t / duration))
            add((1, 0, 0), 0.2 * math.sin(4 * math.pi * t / duration))
        elif clip == "idle_tired":
            add((0, 1, 0), 0.35 * math.sin(2 * math.pi * t / duration))
        elif clip == "sleep":
            add((1, 0, 0), 0.3 * math.sin(2 * math.pi * t / duration))
        elif clip == "tap_reaction":
            add((1, 0, 0), 1.5 * bump(t, 0.03, 0.3, 0.9))
        return delta
    return delta


def rework(path):
    data, js, bin_offset, bin_len = load(path)
    nodes = js["nodes"]
    named = {i: n.get("name", f"<{i}>") for i, n in enumerate(nodes)}
    changed = []
    for animation in js.get("animations", []):
        clip = animation.get("name")
        if clip not in CLIPS:
            continue
        channels = animation["channels"]
        times, _, _, _ = accessor_values(
            js, data, bin_offset,
            animation["samplers"][channels[0]["sampler"]]["input"],
        )
        if not times:
            continue
        duration = times[-1] - times[0]
        for channel in channels:
            target = channel["target"]
            name = named.get(target.get("node"), "")
            path_ = target["path"]
            sam = animation["samplers"][channel["sampler"]]
            out_index = sam["output"]
            values, _, _, ncomp = accessor_values(js, data, bin_offset, out_index)
            if path_ == "rotation":
                posture = values[0]
                new = []
                for t in times:
                    q = qmul(posture, rotation_delta(clip, name, t, duration))
                    new.append(qnormalize(q))
                write_accessor(js, data, bin_offset, out_index, new)
            elif path_ == "translation":
                # Keep the mood crouch, freeze the bounce.
                posture = values[0]
                write_accessor(js, data, bin_offset, out_index, [posture] * len(times))
            elif path_ == "scale":
                # No torso squash: it deformed the face through skin weights.
                write_accessor(js, data, bin_offset, out_index, [(1.0, 1.0, 1.0)] * len(times))
            elif path_ == "weights":
                base, centers = BLINK[clip]
                new = []
                for t in times:
                    weight = base
                    for center in centers:
                        weight = max(weight, base + (1.0 - base) * blink_pulse(t, center))
                    if clip == "tap_reaction":
                        weight = max(weight, 0.9 * blink_pulse(t, 0.3, 0.24))
                    new.append(min(1.0, max(0.0, weight)))
                write_accessor(js, data, bin_offset, out_index, new)
            else:
                raise SystemExit(f"unexpected path {path_}")
        changed.append(clip)
    if not changed:
        raise SystemExit(f"{path}: no target clips found")
    with open(path, "wb") as f:
        f.write(data)
    return changed, bin_len, os.path.getsize(path)


def main(paths):
    backup_root = os.path.join(tempfile.gettempdir(), "momo_glb_backup")
    os.makedirs(backup_root, exist_ok=True)
    for path in paths:
        backup = os.path.join(backup_root, os.path.basename(path))
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        clips, bin_len, size = rework(path)
        print(f"{path}: {', '.join(clips)} (bin={bin_len}, size={size})")
    print(f"backups: {backup_root}")


if __name__ == "__main__":
    main(sys.argv[1:])
