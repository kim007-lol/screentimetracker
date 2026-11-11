"""Add a seamless "living" layer to Drako's idle loops.

The delivered adult idle variants are nearly frozen: several move only the
head or a single tail segment by a few degrees, so a 6-12 s hold looks like a
still image even though the clip is playing. This pass keeps every existing
key (posture, head/wing/tail motion, blink curves) and adds a small additive
motion on top:

- tail sway around the bone's local Y (horizontal, verified to move the tip
  ~28 cm per 20 deg) plus a gentle lift around local X
- soft wing flutter with opposite signs left/right
- barely-there breathing on spine, chest, neck, and head

All added sines complete an integer number of cycles per clip, so the first
and last frames receive identical values and looping stays seamless. Curves
are re-sampled at 30 fps; values are quaternion-signed continuously.

Run:
  blender -b --factory-startup -P tools/drako_idle_alive.py -- <src.glb> <out.glb>
"""
import bpy
import sys
import os
import math
from mathutils import Matrix, Quaternion

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_export                                              # noqa: E402

argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
if len(args) < 2:
    raise SystemExit("usage: drako_idle_alive.py -- src.glb out.glb")
src, out = (os.path.abspath(a) for a in args[:2])
stage = os.path.basename(src).replace("drako_", "").replace(".glb", "")

TAIL = ["Tail_1", "Tail_2", "Tail_3", "Tail_Tip"]
TARGETS = TAIL + [
    "Wing_L", "Wing_L_Tip", "Wing_R", "Wing_R_Tip",
    "Head", "Neck", "Chest", "Spine",
]

# Horizontal wag (local Y) per tail segment, degrees. Bayi/remaja already have
# lively fresh variants, so the boost focuses on tired/critical where the
# delivered clips go nearly still. The adult is weak everywhere.
TAIL_Y = {
    "bayi": {
        "fresh": (1.0, 1.6, 2.2, 2.8),
        "tired": (2.0, 2.8, 3.6, 4.4),
        "critical": (1.5, 2.0, 2.5, 3.0),
    },
    "remaja": {
        "fresh": (1.0, 1.6, 2.2, 2.8),
        "tired": (1.8, 2.6, 3.4, 4.2),
        "critical": (1.5, 2.0, 2.5, 3.0),
    },
    "dewasa": {
        "fresh": (3.2, 4.6, 6.0, 7.4),
        "tired": (3.5, 5.0, 6.5, 8.0),
        "critical": (2.6, 3.5, 4.4, 5.3),
    },
}[stage]
TAIL_GAIN = 1.75 if stage == "dewasa" else 1.0

# Lift (local X), degrees. Two cycles for fresh, one for the low moods.
TAIL_X = {
    "fresh": (0.4, 0.6, 0.8, 1.0),
    "tired": (0.3, 0.5, 0.7, 0.9),
    "critical": (0.3, 0.4, 0.5, 0.6),
}
WING_Z = {"fresh": 1.5, "tired": 1.0, "critical": 0.8}
HEAD_X = {"fresh": 0.9, "tired": 0.7, "critical": 0.5}
CHEST_X = {"fresh": 0.55, "tired": 0.5, "critical": 0.35}
NECK_X = 0.35
SPINE_X = 0.3


def mood_of(name):
    if not name.startswith("idle_"):
        return None
    if name.startswith("idle_fresh"):
        return "fresh"
    if name.startswith("idle_tired"):
        return "tired"
    if name.startswith("idle_critical"):
        return "critical"
    return None


def set_action(act):
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = act
    try:
        if act.slots:
            ad.action_slot = act.slots[0]
    except Exception:
        pass


def sway(mood, bone, u):
    """Additive local rotation for one bone at loop fraction u in [0,1]."""
    ph = 2 * math.pi * u
    q = Quaternion((1, 0, 0, 0))
    if bone in TAIL:
        i = TAIL.index(bone)
        cycles_x = 2 if mood == "fresh" else 1
        q = (Quaternion((0, 1, 0),
                        math.radians(TAIL_Y[mood][i] * TAIL_GAIN) * math.sin(ph + i * 0.55))
             @ Quaternion((1, 0, 0),
                          math.radians(TAIL_X[mood][i] * TAIL_GAIN)
                          * math.sin(cycles_x * ph - i * 0.35 + 0.9)))
    elif bone.startswith("Wing_"):
        cycles = 2 if mood == "fresh" else 1
        tip = bone.endswith("_Tip")
        amp = WING_Z[mood] * (1.4 if tip else 1.0)
        sign = 1.0 if "_L" in bone else -1.0
        q = Quaternion((0, 0, 1), math.radians(amp * sign) * math.sin(cycles * ph))
    elif bone == "Head":
        q = (Quaternion((1, 0, 0), math.radians(HEAD_X[mood]) * math.sin(ph - 0.5))
             @ Quaternion((0, 1, 0), math.radians(0.4) * math.sin(ph * 2 + 0.7)))
    elif bone == "Neck":
        q = Quaternion((1, 0, 0), math.radians(NECK_X) * math.sin(ph - 0.3))
    elif bone == "Chest":
        q = Quaternion((1, 0, 0), math.radians(CHEST_X[mood]) * math.sin(ph))
    elif bone == "Spine":
        q = Quaternion((1, 0, 0), math.radians(SPINE_X) * math.sin(ph))
    return q


bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
glb_export.import_glb(src)          # 30 fps grid before any key time is read

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
if arm.animation_data:
    for t in arm.animation_data.nla_tracks:
        t.mute = True
    arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)

missing = [b for b in TARGETS if b not in arm.pose.bones]
if missing:
    raise SystemExit("missing bones: %s" % missing)

# Sample every idle action first, then write; modifying curves while the
# action is being evaluated by the same armature invites double application.
plans = []
for act in sorted(bpy.data.actions, key=lambda a: a.name):
    mood = mood_of(act.name)
    if mood is None:
        continue
    f0, f1 = (float(v) for v in act.frame_range)
    if f1 <= f0:
        continue
    frames = [float(f) for f in range(int(f0), int(f1) + 1)]
    if abs(frames[-1] - f1) > 1e-4:
        frames.append(f1)
    set_action(act)
    sampled = {b: [] for b in TARGETS}
    for f in frames:
        base = int(math.floor(f))
        scene.frame_set(base, subframe=f - base)
        u = (f - f0) / (f1 - f0)
        for b in TARGETS:
            q = arm.pose.bones[b].rotation_quaternion.copy() @ sway(mood, b, u)
            q.normalize()
            sampled[b].append(q)
    plans.append((act, mood, frames, sampled, f1 - f0))

arm.animation_data.action = None
for act, mood, frames, sampled, dur in plans:
    slot = act.slots[0]
    strip = act.layers[0].strips[0]
    cb = strip.channelbag(slot)
    if cb is None:
        cb = strip.channelbags.new(slot)
    for b in TARGETS:
        path = 'pose.bones["%s"].rotation_quaternion' % b
        for fc in list(cb.fcurves):
            if fc.data_path == path:
                cb.fcurves.remove(fc)
        qs = sampled[b]
        for i in range(1, len(qs)):
            if qs[i].dot(qs[i - 1]) < 0.0:
                qs[i].negate()
        for idx in range(4):
            fc = cb.fcurves.new(path, index=idx, group_name="LivingIdle")
            for f, q in zip(frames, qs):
                kp = fc.keyframe_points.insert(f, q[idx], options={"FAST"})
                kp.interpolation = "LINEAR"
            fc.update()
    print("LIVING %-16s mood=%-8s frames=%d dur=%.2fs" % (
        act.name, mood, len(frames), dur / 30.0))

# Every added sine completes an integer number of cycles, so each clip still ends
# on its opening pose; the shared exporter verifies that against the source file
# and refuses to write if the boost shortened a clip instead.
glb_export.export_glb(out, src=src, arm=arm, tag="LIVING",
                      reset_pose=True, unassign_action=True)
print("LIVING clips=%d" % len(plans))
