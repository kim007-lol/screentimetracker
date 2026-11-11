#!/usr/bin/env python3
"""Make Drako's head move as one unit around the neck base.

Problem: the face skin is weighted mostly to Neck (all stages), the skull and
horns to Head. Clips rotate Head further than Neck, so the skull/horns twist
away from the face and the head tears instead of turning.

Fix: for every action, fold the Head local rotation into Neck
    Neck' = Neck * (R_rel * Head * R_rel^-1),  Head' = identity
where R_rel is the Head rest orientation relative to Neck (identity here).
The Head bone's world orientation is preserved, but every vertex weighted to
Neck or Head now shares the Neck skinning transform, so the whole head is rigid
around the neck base and the neck visibly bends with it.

The two eyelid bones are reparented to Neck for every stage so the blink cards
follow the face instead of the chest (baby) or the now-static Head (adult).

Run:
  blender -b --python tools/drako_head_merge.py -- <src.glb> <out.glb>
"""
import bpy
import sys
import os
import math
from mathutils import Quaternion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_export                                              # noqa: E402

argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
if len(args) < 2:
    raise SystemExit("usage: drako_head_merge.py -- src.glb out.glb")
src, out = (os.path.abspath(a) for a in args[:2])

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
glb_export.import_glb(src)          # 30 fps grid before any key time is read

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
if arm.animation_data:
    for t in arm.animation_data.nla_tracks:
        t.mute = True
    arm.animation_data.action = None

root_delta = -(arm.matrix_world @ arm.data.bones["Root"].head_local)
print("ROOT_AUTHORED_AT", tuple(round(v, 6) for v in root_delta))

# Rest-space relation between Head and Neck. Must be a pure rotation; identity
# on these rigs, but keep the general conjugation so re-running stays exact.
q_neck_rest = arm.data.bones["Neck"].matrix_local.to_quaternion()
q_head_rest = arm.data.bones["Head"].matrix_local.to_quaternion()
q_rel = q_neck_rest.inverted() @ q_head_rest
print("REST_REL angle_deg", round(math.degrees(q_rel.angle), 6))


def channelbag(act):
    if not act.slots or not act.layers:
        raise SystemExit(f"action {act.name} has no slot/layer")
    slot = act.slots[0]
    strip = act.layers[0].strips[0]
    cb = strip.channelbag(slot)
    if cb is None:
        cb = strip.channelbags.new(slot)
    return cb


def rot_curves(cb, bone):
    path = f'pose.bones["{bone}"].rotation_quaternion'
    curves = {fc.array_index: fc for fc in cb.fcurves if fc.data_path == path}
    if set(curves) != {0, 1, 2, 3}:
        raise SystemExit(f"missing rotation curves for {bone}: {sorted(curves)}")
    return [curves[i] for i in range(4)]


def read_quats(curves):
    counts = {len(fc.keyframe_points) for fc in curves}
    times = [tuple(round(k.co.x, 4) for k in fc.keyframe_points) for fc in curves]
    if len(counts) != 1 or len(set(times)) != 1:
        raise SystemExit(f"quaternion curves misaligned: counts={counts}")
    out = []
    for i, kp in enumerate(curves[0].keyframe_points):
        out.append(Quaternion((curves[0].keyframe_points[i].co.y,
                               curves[1].keyframe_points[i].co.y,
                               curves[2].keyframe_points[i].co.y,
                               curves[3].keyframe_points[i].co.y)).normalized())
    return [k.co.x for k in curves[0].keyframe_points], out


def write_quats(curves, times, quats):
    for idx, fc in enumerate(curves):
        if len(fc.keyframe_points) != len(times):
            raise SystemExit("key count changed while writing")
        for kp, q in zip(fc.keyframe_points, quats):
            kp.co.y = q[idx]
            kp.handle_left.y = q[idx]
            kp.handle_right.y = q[idx]
        fc.update()


# glTF stores key times as float32 seconds; importing at 30 fps can land the
# last key on 124.99999 instead of 125, and the exporter then samples one
# frame too few. Snap near-integer key times so every clip keeps its exact
# frame count and duration.
for act in bpy.data.actions:
    snapped = 0
    for fc in channelbag(act).fcurves:
        for kp in fc.keyframe_points:
            r = round(kp.co.x)
            if abs(kp.co.x - r) <= 1e-3:
                dx = r - kp.co.x
                kp.co.x = r
                kp.handle_left.x += dx
                kp.handle_right.x += dx
                snapped += 1
        fc.update()
    if snapped:
        print("SNAPPED_TIMES %-18s points=%d" % (act.name, snapped))

report = []
for act in bpy.data.actions:
    cb = channelbag(act)
    neck = rot_curves(cb, "Neck")
    head = rot_curves(cb, "Head")
    ntimes, nquats = read_quats(neck)
    htimes, hquats = read_quats(head)
    if len(ntimes) != len(htimes) or any(abs(a - b) > 1e-4 for a, b in zip(ntimes, htimes)):
        raise SystemExit(f"Neck/Head key times differ in {act.name}")
    merged = []
    max_angle = 0.0
    for qn, qh in zip(nquats, hquats):
        extra = q_rel @ qh @ q_rel.inverted()
        q = (qn @ extra).normalized()
        merged.append(q)
        max_angle = max(max_angle, math.degrees(qh.angle))
    for i in range(1, len(merged)):
        if merged[i].dot(merged[i - 1]) < 0.0:
            merged[i].negate()
    write_quats(neck, ntimes, merged)
    write_quats(head, htimes, [Quaternion((1.0, 0.0, 0.0, 0.0)) for _ in htimes])
    report.append((act.name, len(merged), max_angle, math.degrees(merged[0].angle), math.degrees(merged[-1].angle)))

for name, keys, max_head, first, last in report:
    print("MERGED %-18s keys=%3d head_max=%5.2f neck_end=%5.2f/%5.2f" % (name, keys, max_head, first, last))

# Reparent both lid bones to Neck, preserving their rest world (armature-space)
# transform and all local animation channels.
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones
neck_eb = eb["Neck"]
for side in ("L", "R"):
    b = eb[f"Lid_{side}"]
    old_parent = b.parent.name if b.parent else None
    m = b.matrix.copy()
    b.parent = neck_eb
    b.use_connect = False
    b.matrix = m
    print("LID_PARENT", f"Lid_{side}", old_parent, "->", b.parent.name)
bpy.ops.object.mode_set(mode="OBJECT")

# Confirm the rest transforms did not move.
for side in ("L", "R"):
    b = arm.data.bones[f"Lid_{side}"]
    print("LID_REST", f"Lid_{side}", tuple(round(v, 5) for v in b.head_local),
          tuple(round(v, 5) for v in b.tail_local), "parent", b.parent.name)

# Keep the imported armature object transform: the bundled GLBs place the
# DrakoSkin node at (0.1117, 0.5568, 0.1046) in glTF space. Zeroing it sinks
# the whole pet by ~0.56 m in the app.
print("ARM_KEEP", tuple(round(v, 6) for v in arm.location))
if arm.animation_data:
    arm.animation_data.action = None
bpy.context.view_layer.update()

# The merged rig must come out at the same clip lengths it went in: the shared
# exporter takes the frame-count baseline from `src`, snaps every key back onto the
# 30 fps grid, and fails instead of writing a shortened clip.
glb_export.export_glb(out, src=src, arm=arm, tag="HEAD_MERGE")
print("HEAD_MERGE actions=%d" % len(report))
