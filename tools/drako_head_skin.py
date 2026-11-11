#!/usr/bin/env python3
"""Rig Drako's head skin to the Head bone and put the pivot at the head base.

The imported Drako rigs bind most of the visible head skin to Chest/Neck: the
baby's face is Chest, its skull Neck; the teen's whole head is Neck. Only a
small cap is Head. Any Head-turn clip therefore twists a cap while the face
stays put, and the neck-merge workaround just swung the skull with the neck.

This tool fixes the skin instead of the clips:
  * a smooth z-mask above the neck ring moves every movable influence of the
    head skin onto Head (horns stay on Horn_L/R, which are Head children);
  * a vertex is only skipped when a wing, leg, paw, tail, root, or hips bone
    really owns it - as the strongest influence or with more than
    `--protect-max` (default 0.15) of its weight.  Small stray ties (the baby's
    face carries 0.3%-1.1% `Wing_L` all over the left side) are kept in place
    while the rest of the vertex moves to Head, so the mask slab still cannot
    drag a wing base but no longer leaves a lagging band inside the skull;
  * the Head rest pivot moves down to the head base, so pitch/roll turn the
    head around the neck instead of around a point inside/above the skull;
  * the Neck pivot can be lowered to the visible neck base (baby only);
  * the eyelid bones are reparented to Head (rest matrices preserved), so the
    blink cards follow the face;
  * horn rest matrices are restored so the horns do not move at rest.

`SKULL_ABOVE_MASK` at the end of the run is the guard: after the transfer no
vertex above `--z1` may still answer to Chest/Neck/Spine, because a welded
neighbour that does answer to Head will tear away from it as soon as a clip
rotates the skull.

No animation curve is edited: every clip still rotates the same bones by the
same angles, but now the head geometry is bound to Head and the pivots sit at
the neck.  Run:

  blender -b --python tools/drako_head_skin.py -- \
      src.glb out.glb --z0 0.682 --z1 0.782 --head-pivot 0.762 [--neck-pivot 0.72] \
      [--protect-max 0.15] [--mask-axis y|neck|corner] [--f0 F0 --f1 F1]

Which coordinate the band is measured in is not a detail, it is the difference
between a fix and a smear.  The baby stands upright, so a height slab cuts the
skull off above the jaw and `--mask-axis y` (Blender world Z, which is glTF world
Y) is what its proven `--z0 0.6819 --z1 0.7819` band is made of.  The teen and the
adult do not: the teen's snout points forward *and down*, so its lagging jaw
vertices sit at y 0.938-1.046 - inside the same height band the upper neck skin
occupies - and the adult is a horizontal quadruped whose whole body spans y
-0.398..0.540 while its head sits out at z 0.83, where a height slab captures
37% of the body.  `--mask-axis neck` measures the band as metres along the
Chest->Head bone axis instead, which is the direction the head actually sits on
for both of them, and `--mask-axis corner` converts only where a vertex clears
BOTH the height band (--z0/--z1) and a forward band (--f0/--f1, glTF +Z), which
is what the teen needs because its jaw and its nape are at the same height.
`tools/qa_rig/tmp_face_ties.py` prints every candidate coordinate per asset, the
collateral each band would capture, and a corner sweep; the values used here come
from it.
"""
import bpy
import sys
import os
import math
import statistics
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_export                                              # noqa: E402

argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []


def pop_opt(name, cast=float):
    if name not in args:
        return None
    i = args.index(name)
    val = cast(args[i + 1])
    del args[i:i + 2]
    return val


if len(args) < 2:
    raise SystemExit("usage: drako_head_skin.py -- src.glb out.glb --z0 Z0 --z1 Z1 "
                     "[--head-pivot Z] [--neck-pivot Z] [--mask-axis y|neck|corner] "
                     "[--f0 F0 --f1 F1]")
src, out = (os.path.abspath(a) for a in args[:2])
z0 = pop_opt("--z0")
z1 = pop_opt("--z1")
head_pivot_z = pop_opt("--head-pivot")
neck_pivot_z = pop_opt("--neck-pivot")
mask_axis = pop_opt("--mask-axis", str) or "y"
if mask_axis not in ("y", "neck", "corner"):
    raise SystemExit("--mask-axis must be y, neck or corner, got %r" % mask_axis)
f0 = pop_opt("--f0")
f1 = pop_opt("--f1")
# Materiality of a limb/wing/tail tie.  The source auto-rig leaks a 0.3%-1.1%
# Wing_L influence across the whole left half of the baby's face; treating any
# non-zero tie as a veto left 145 face and 18 crown vertices on Chest/Neck
# while their welded neighbours moved to Head.  0.15 keeps every vertex that a
# wing, leg, or tail actually owns out of the transfer.
protect_max = pop_opt("--protect-max")
if protect_max is None:
    protect_max = 0.15
if z0 is None or z1 is None or not (z0 < z1):
    raise SystemExit("missing/invalid --z0 --z1 (both required, z0 < z1)")
if mask_axis == "corner" and (f0 is None or f1 is None or not (f0 < f1)):
    raise SystemExit("--mask-axis corner needs --f0 --f1 (forward band, glTF +Z, f0 < f1)")

HORNS = {"Horn_L", "Horn_R"}
# A pure z-slab also crosses the shoulder/wing base (baby).  Any vertex that is
# even partially driven by a limb, wing, tail, or body-root bone must keep its
# weights: the head must never drag those elements.
PROTECTED = ("Wing_", "Leg", "Paw", "Tail_", "Root", "Hips")

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
glb_export.import_glb(src)          # 30 fps grid before any key time is read

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
body = bpy.data.objects["DrakoMesh"]
eyelids = bpy.data.objects["DrakoEyelids"]
if arm.animation_data:
    for t in arm.animation_data.nla_tracks:
        t.mute = True
    arm.animation_data.action = None

mw = body.matrix_world
minv = arm.matrix_world.inverted()

# --- measure the eyes (separate lid-card mesh) in world space -------------
eye_pts = [eyelids.matrix_world @ v.co for v in eyelids.data.vertices]

# --- the mask coordinate --------------------------------------------------
# `y` is Blender world Z, which is glTF world Y: the upright baby, whose proven
# band (0.6819..0.7819) is a height slab across the jaw line.  `neck` is metres
# from the Chest bone along the Chest->Head bone line: the teen's snout drops
# forward as it extends, and the adult's head sits out in front of a horizontal
# body, so for both of them a height slab either misses the jaw or captures a
# third of the chest.  Bands in this coordinate come from
# `tools/qa_rig/tmp_face_ties.py`, which reports both per asset.
if mask_axis == "y":
    def coord(p):
        return (mw @ p).z
elif mask_axis == "neck":
    _origin = arm.matrix_world @ arm.data.bones["Chest"].head_local
    _axis = (arm.matrix_world @ arm.data.bones["Head"].head_local) - _origin
    if _axis.length < 1e-6:
        raise SystemExit("--mask-axis neck needs distinct Chest and Head bone heads")
    _axis /= _axis.length
    print("MASK_AXIS neck origin=%s dir=%s |Chest->Head|=%.4f" % (
        tuple(round(v, 4) for v in _origin), tuple(round(v, 4) for v in _axis),
        (arm.matrix_world @ arm.data.bones["Head"].head_local
         - arm.matrix_world @ arm.data.bones["Chest"].head_local).length))

    def coord(p):
        return ((mw @ p) - _origin) @ _axis
else:
    # Corner mask: a vertex only counts as skull when it is BOTH high enough and
    # forward enough.  The teen's snout hangs below the skull base at the same
    # height as the back of its own neck (`tmp_face_ties.py` reports the height
    # band's 996 captured Neck vertices at median glTF z +0.62 -- behind the
    # skull -- while the lagging jaw vertices sit at z +0.84..+0.92), so a height
    # slab welds the nape to the skull and the neck stops bending.  The forward
    # coordinate is glTF +Z == Blender -Y, mapped affinely onto the height ramp so
    # the band, the guard and the MIX report all keep their z0/z1 meaning.
    _fscale = (z1 - z0) / (f1 - f0)

    def coord(p):
        w = mw @ p
        return z0 + min(w.z - z0, (-(w.y) - f0) * _fscale)

    print("MASK_AXIS corner height z0=%.4f z1=%.4f forward f0=%.4f f1=%.4f "
          "scale=%.4f (glTF +Z)" % (z0, z1, f0, f1, _fscale))


eye_c = statistics.median(coord(p) for p in eye_pts)
print("EYE_%s %.4f  mask z0=%.4f z1=%.4f band=%.4f" % (
    mask_axis.upper(), eye_c, z0, z1, z1 - z0))

# --- smooth mask and weight transfer -------------------------------------
def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


gn = {g.index: g.name for g in body.vertex_groups}
body_verts = body.data.vertices

changed = 0
rigid_above = 0
max_inf = 0
pruned = 0
skipped_protected = 0
for v in body_verts:
    zw = coord(v.co)
    if zw <= z0:
        continue
    a = smoothstep((zw - z0) / (z1 - z0))
    if a <= 1e-6:
        continue
    w = {}
    for ge in v.groups:
        name = gn.get(ge.group)
        if name and ge.weight > 1e-6:
            w[name] = w.get(name, 0.0) + ge.weight
    if not w:
        continue
    prot = {name: wt for name, wt in w.items() if name.startswith(PROTECTED)}
    prot_max = max(prot.values(), default=0.0)
    # Veto only the vertices a limb, wing, tail, or body-root really owns:
    # either it is the strongest influence on the vertex, or it carries more
    # than `protect_max` of it.  A stray sub-1% tie must not veto a face
    # vertex - that is what tore the baby's skull in two.
    if prot_max >= protect_max or max(w, key=w.get) in prot:
        skipped_protected += 1
        continue
    movable = sum(wt for name, wt in w.items()
                  if name not in HORNS and name not in prot)
    if movable <= 1e-9:
        continue

    new = {}
    for name, wt in w.items():
        if name in HORNS or name in prot:
            new[name] = wt
        else:
            val = wt * (1.0 - a)
            if val > 1e-5:
                new[name] = val
    new["Head"] = new.get("Head", 0.0) + a * movable

    # glTF default keeps 4 influences; prune deterministically and renormalize.
    if len(new) > 4:
        keep = sorted(new.items(), key=lambda kv: (-kv[1], kv[0]))[:4]
        new = dict(keep)
        pruned += 1
    total = sum(new.values())
    if total <= 1e-9:
        continue
    for name, wt in new.items():
        new[name] = wt / total

    # Write only the groups that changed/survive; clear the others.
    for name in list(w):
        if name not in new:
            body.vertex_groups[name].remove([v.index])
    for name, wt in new.items():
        body.vertex_groups[name].add([v.index], wt, "REPLACE")
    changed += 1
    max_inf = max(max_inf, len(new))
    if zw >= z1 and set(new) <= (HORNS | {"Head"}):
        rigid_above += 1

print("WEIGHTS changed=%d rigid_above=%d max_influences=%d pruned=%d protected_skipped=%d (protect_max=%.3f)" % (
    changed, rigid_above, max_inf, pruned, skipped_protected, protect_max))

# Self-check: above the mask the skull must be one piece.  Anything that still
# answers to Chest/Neck/Spine up there is a seam the clips will tear open.
import collections

stragglers = collections.Counter()
for v in body_verts:
    if coord(v.co) <= z1:
        continue
    best, best_w = None, 0.0
    for ge in v.groups:
        name = gn.get(ge.group)
        if name and ge.weight > best_w:
            best, best_w = name, ge.weight
    if best and best not in ("Head",) and not best.startswith("Horn"):
        stragglers[best] += 1
print("SKULL_ABOVE_MASK non-Head-dominant=%d %s" % (
    sum(stragglers.values()), dict(stragglers)))

# Report the resulting group mix per z band.
import collections
bands = collections.defaultdict(lambda: collections.Counter())
counts = collections.Counter()
for v in body_verts:
    zw = coord(v.co)
    if not (z0 - 0.08 <= zw <= z1 + 0.12):
        continue
    key = round(zw * 20) / 20
    counts[key] += 1
    for ge in v.groups:
        if ge.weight > 0.001:
            bands[key][gn.get(ge.group)] += ge.weight
for key in sorted(counts):
    mix = ", ".join("%s %.2f" % (n, wt / counts[key]) for n, wt in bands[key].most_common(3))
    print("MIX z=%.2f n=%5d %s" % (key, counts[key], mix))

# --- rest pivots ----------------------------------------------------------
bones = arm.data.bones
old_head = bones["Head"].matrix_local.copy()
old_head_len = bones["Head"].length
old_neck = bones["Neck"].matrix_local.copy()
old_horns = {n: bones[n].matrix_local.copy() for n in ("Horn_L", "Horn_R")}
old_lids = {n: bones[n].matrix_local.copy() for n in ("Lid_L", "Lid_R")}

world_head = arm.matrix_world @ bones["Head"].head_local
if head_pivot_z is None:
    # The teen and adult pivots already sit at the neck->head joint with the
    # same 0.069-0.070 m bone spacing the proven baby uses, and their complaint
    # is skin that answers to Neck, not a rotation centre in the wrong place.
    # Moving the pivot anyway would re-aim every existing clip channel, so the
    # rest is left exactly as it is and asserted below.
    delta = Vector((0.0, 0.0, 0.0))
    print("HEAD_REST_UNCHANGED", tuple(round(v, 5) for v in world_head),
          "length", round(old_head_len, 5))
else:
    pivot_world = Vector((world_head.x, world_head.y, head_pivot_z))
    new_head_local = minv @ pivot_world
    delta = new_head_local - bones["Head"].head_local
    print("HEAD_REST_OLD", tuple(round(v, 5) for v in world_head),
          "-> new", tuple(round(v, 5) for v in pivot_world),
          "length", round(old_head_len, 5))

bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones

# Head: translate head+tail down, orientation/roll and length preserved.
head_eb = eb["Head"]
head_eb.head = head_eb.head + delta
head_eb.tail = head_eb.tail + delta

# Neck: optional pivot move (shift whole bone, length preserved).
if neck_pivot_z is not None:
    neck_pb = eb["Neck"]
    world_neck = arm.matrix_world @ bones["Neck"].head_local
    npivot_world = Vector((world_neck.x, world_neck.y, neck_pivot_z))
    ndelta = (minv @ npivot_world) - neck_pb.head
    neck_pb.head = neck_pb.head + ndelta
    neck_pb.tail = neck_pb.tail + ndelta
    print("NECK_REST_MOVED", tuple(round(v, 5) for v in world_neck),
          "->", tuple(round(v, 5) for v in npivot_world))

# Restore horn rest matrices (they are Head children; the pivot move must not
# drag the horns down) and reparent the lids to Head preserving rest matrices.
for n, m in old_horns.items():
    eb[n].matrix = m
head_eb_after = eb["Head"]
for side in ("L", "R"):
    b = eb[f"Lid_{side}"]
    old_parent = b.parent.name if b.parent else None
    m = b.matrix.copy()
    b.parent = head_eb_after
    b.use_connect = False
    b.matrix = m
    print("LID_PARENT", "Lid_" + side, old_parent, "->", b.parent.name)
bpy.ops.object.mode_set(mode="OBJECT")

# --- verify the rest state ------------------------------------------------
bones = arm.data.bones
new_head = bones["Head"].matrix_local.copy()
q_old = old_head.to_quaternion()
q_new = new_head.to_quaternion()
print("HEAD_ORIENT_DELTA_DEG %.6f" % math.degrees(q_old.rotation_difference(q_new).angle))
assert abs(bones["Head"].length - old_head_len) < 1e-5
for n in ("Horn_L", "Horn_R", "Lid_L", "Lid_R"):
    b = bones[n]
    m = b.matrix_local
    if n.startswith("Horn"):
        om = old_horns[n]
    else:
        om = old_lids[n]
    d = (m.translation - om.translation).length
    print("REST_%s head=%s delta=%.6f parent=%s" % (
        n, tuple(round(v, 5) for v in (arm.matrix_world @ b.head_local)), d,
        b.parent.name if b.parent else None))
    assert d < 1e-4, (n, d)
if neck_pivot_z is None:
    assert (bones["Neck"].matrix_local.translation - old_neck.translation).length < 1e-6
if head_pivot_z is None:
    assert (new_head.translation - old_head.translation).length < 1e-6, \
        "Head rest moved although no --head-pivot was given"

# --- snap float32 key times back onto exact frames ------------------------
# The exporter samples integer frames; without this the last key of a clip can
# land on 124.99999 and the sampled range loses a frame.  The previous rig pass
# used the same fix and kept all 25 clips at their exact durations.
def channelbag(act):
    if not act.slots or not act.layers:
        raise SystemExit(f"action {act.name} has no slot/layer")
    slot = act.slots[0]
    strip = act.layers[0].strips[0]
    cb = strip.channelbag(slot)
    if cb is None:
        cb = strip.channelbags.new(slot)
    return cb


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

# --- export (same verified settings as the previous rig pass) -------------
if arm.animation_data:
    arm.animation_data.action = None
print("ARM_KEEP", tuple(round(v, 6) for v in arm.location))
# Weights and pivots only: the shared exporter keeps every clip at the source
# file's frame count, so re-skinning can no longer eat a loop-closing key.
glb_export.export_glb(out, src=src, arm=arm, tag="HEAD_SKIN")
