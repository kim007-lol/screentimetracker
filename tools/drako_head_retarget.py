#!/usr/bin/env python3
"""Turn Drako's authored sideways head roll into a head turn (yaw).

Delivered Drako clips rotate Head/Neck almost entirely around the bone-local
Y axis. On this rig local Y maps to the glTF forward axis, so the skull rolls
sideways: with the oversized bayi head that reads as the neck swinging the
head ("meleot") instead of the dog looking around.

This pass rewrites only the Head (and optionally Neck) rotation_quaternion
curves of every action. It decomposes each key into the bone-local XYZ Euler
used by tools/drako_animate.py and remaps

    pitch (local X) : unchanged
    roll  (local Y) : roll * --head-roll-keep
    yaw   (local Z) : yaw + roll * --head-yaw-gain

Key times and LINEAR interpolation are preserved, translation/scale curves and
all other bones are untouched, and the transform is pointwise so looping clips
still end on their first pose.

Run:
  blender -b --factory-startup -P tools/drako_head_retarget.py -- \
      src.glb out.glb [--head-yaw-gain 1.0] [--head-roll-keep 0.12] \
      [--neck-yaw-gain 0.0] [--neck-roll-keep 1.0]
"""

from __future__ import annotations

import math
import os
import sys

import bpy
from mathutils import Euler, Matrix, Quaternion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_export                                              # noqa: E402

argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
if len(args) < 2:
    raise SystemExit(
        "usage: drako_head_retarget.py -- src.glb out.glb "
        "[--head-yaw-gain 1.0] [--head-roll-keep 0.12] "
        "[--neck-yaw-gain 0.0] [--neck-roll-keep 1.0]"
    )

src, out = os.path.abspath(args[0]), os.path.abspath(args[1])
OPTS = {
    "head-yaw-gain": 1.0,
    "head-roll-keep": 0.12,
    "neck-yaw-gain": 0.0,
    "neck-roll-keep": 1.0,
}
i = 2
while i < len(args):
    key = args[i].lstrip("-")
    if key not in OPTS:
        raise SystemExit("unknown option: " + args[i])
    OPTS[key] = float(args[i + 1])
    i += 2

PLAN = {
    "Head": (OPTS["head-roll-keep"], OPTS["head-yaw-gain"]),
    "Neck": (OPTS["neck-roll-keep"], OPTS["neck-yaw-gain"]),
}

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
glb_export.import_glb(src)          # 30 fps grid before any key time is read

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
if arm.animation_data:
    for track in arm.animation_data.nla_tracks:
        track.mute = True
    arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)


def channel_bag(act):
    try:
        slot = act.slots[0]
        strip = act.layers[0].strips[0]
        return strip.channelbag(slot)
    except Exception:
        return None


def snap_key_times():
    """Normalize importer float noise onto the asset's 30 Hz frame grid.

    glTF stores seconds as float32: 125/30 s imports as frame 124.999992.
    Without snapping, the exporter samples 0..124 and silently drops the
    final key (a real regression on dewasa sleep). The delivered clips are
    authored one key per frame, so only near-integer times are touched.
    """
    total = 0
    for act in bpy.data.actions:
        cb = channel_bag(act)
        if cb is None:
            continue
        moved_action = 0
        for fc in cb.fcurves:
            moved = 0
            for kp in fc.keyframe_points:
                t = round(kp.co.x)
                if abs(kp.co.x - t) < 1e-3:
                    if kp.co.x != t:
                        kp.co.x = float(t)
                        moved += 1
            if moved:
                fc.update()
                moved_action += moved
        if moved_action:
            print("SNAP_KEY_TIMES %-16s points=%d" % (act.name, moved_action))
            total += moved_action
    print("SNAP_KEY_TIMES_TOTAL", total)


snap_key_times()


def curves_for(act, bone):
    cb = channel_bag(act)
    if cb is None:
        return None
    path = 'pose.bones["%s"].rotation_quaternion' % bone
    curves = [None] * 4
    for fc in cb.fcurves:
        if fc.data_path == path and 0 <= fc.array_index < 4:
            curves[fc.array_index] = fc
    if any(fc is None for fc in curves):
        return None
    return curves


def key_times(curves):
    """Shared key times; falls back to the union when components differ."""
    times = []
    for fc in curves:
        for kp in fc.keyframe_points:
            times.append(round(kp.co.x, 6))
    times = sorted(set(times))
    counts = {len(fc.keyframe_points) for fc in curves}
    if len(counts) == 1 and all(
        abs(a - b) < 1e-4
        for fc in curves[1:]
        for a, b in zip(
            (kp.co.x for kp in fc.keyframe_points),
            (kp.co.x for kp in curves[0].keyframe_points),
        )
    ):
        return [kp.co.x for kp in curves[0].keyframe_points], False
    return times, True


def process(act, bone, roll_keep, yaw_gain):
    curves = curves_for(act, bone)
    if curves is None:
        return None
    times, merged = key_times(curves)
    if len(times) < 2:
        return None
    prev = None
    prev_euler = None
    q_first = None
    q_last = None
    quats = []
    stats = {"roll": 0.0, "yaw": 0.0, "roll_new": 0.0, "yaw_new": 0.0}
    for t in times:
        q = Quaternion(tuple(fc.evaluate(t) for fc in curves))
        if q.magnitude < 1e-8:
            q = Quaternion((1.0, 0.0, 0.0, 0.0))
        q.normalize()
        if prev is not None and q.dot(prev) < 0.0:
            q.negate()
        if prev is None:
            q_first = q.copy()
        q_last = q.copy()
        e = q.to_euler("XYZ", prev_euler) if prev_euler is not None else q.to_euler("XYZ")
        prev_euler = e
        x, y, z = e.x, e.y, e.z
        x2, y2, z2 = x, y * roll_keep, z + yaw_gain * y
        quats.append(Euler((x2, y2, z2), "XYZ").to_quaternion())
        stats["roll"] = max(stats["roll"], abs(math.degrees(y)))
        stats["yaw"] = max(stats["yaw"], abs(math.degrees(z)))
        stats["roll_new"] = max(stats["roll_new"], abs(math.degrees(y2)))
        stats["yaw_new"] = max(stats["yaw_new"], abs(math.degrees(z2)))
        prev = q

    # The delivered loops start and end on the same pose; keep that exact after
    # remapping so idle repeats cannot pop by a fraction of a degree.
    closed = False
    if len(quats) >= 2 and q_first is not None and q_last is not None:
        a, b = q_first.copy(), q_last.copy()
        if a.dot(b) < 0.0:
            b.negate()
        if max(abs(a[k] - b[k]) for k in range(4)) < 2e-5:
            quats[-1] = quats[0].copy()
            closed = True
    loop_err = 0.0
    if len(quats) >= 2:
        a, b = quats[0].copy(), quats[-1].copy()
        if a.dot(b) < 0.0:
            b.negate()
        loop_err = max(abs(a[k] - b[k]) for k in range(4))

    for k in range(4):
        fc = curves[k]
        fc.keyframe_points.clear()
        for t, q in zip(times, quats):
            kp = fc.keyframe_points.insert(t, q[k], options={"FAST"})
            kp.interpolation = "LINEAR"
        fc.update()
    return stats, len(times), merged, loop_err, closed


print("RETARGET_SRC", src)
print("RETARGET_PARAMS head_keep=%.2f head_gain=%.2f neck_keep=%.2f neck_gain=%.2f"
      % (PLAN["Head"][0], PLAN["Head"][1], PLAN["Neck"][0], PLAN["Neck"][1]))

actions = sorted(bpy.data.actions, key=lambda a: a.name)
done = 0
for act in actions:
    changed = False
    for bone, (roll_keep, yaw_gain) in PLAN.items():
        if abs(roll_keep - 1.0) < 1e-9 and abs(yaw_gain) < 1e-9:
            continue
        result = process(act, bone, roll_keep, yaw_gain)
        if result is None:
            continue
        changed = True
        st, n, merged, loop_err, closed = result
        print(
            "RETARGET %-16s %-4s keys=%3d roll %5.1f->%5.1f yaw %5.1f->%5.1f "
            "loopErr=%.2e%s%s"
            % (act.name, bone, n, st["roll"], st["roll_new"],
               st["yaw"], st["yaw_new"], loop_err,
               " CLOSED" if closed else "", " MERGED_TIMES" if merged else "")
        )
    if changed:
        done += 1

# The retarget is pointwise, so a clip that ended on its opening pose still does;
# the shared exporter checks that against the source file and snaps every key back
# onto the 30 fps grid so a round trip cannot eat the closing frame.
glb_export.export_glb(out, src=src, arm=arm, tag="RETARGET",
                      reset_pose=True, unassign_action=True)
print("RETARGET actions=%d/%d" % (done, len(actions)))
