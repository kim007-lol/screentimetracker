"""Add skinned eyelid cards and lid bones to a Drako GLB.

The source Drako mesh has the eyes painted into its single texture; there is no
eyelid geometry, morph target, or blink clip. This builder adds two tiny screen
shutter cards (skin strip + lash line per eye) that sit at the top of each eye
in the bind pose. Scaling the lid bone along its length (local Y) stretches the
card down over the eye. The cards are invisible slivers when open.

The run is a full Blender round-trip: all 25 actions are re-baked at 30 fps,
which also removes the sparse 13-key stepping of the source clips.

Run:
  blender -b --python tools/drako_eyelids.py -- <src.glb> <eyes.json> <out.glb>
"""
import bpy
import sys
import os
import json
import math
from mathutils import Vector, Matrix

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_export                                              # noqa: E402

argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
if len(args) < 3:
    raise SystemExit("usage: drako_eyelids.py -- src.glb eyes.json out.glb")
src, eyes_path, out = (os.path.abspath(a) for a in args[:3])
stage = os.path.basename(src).replace("drako_", "").replace(".glb", "")
eyes = json.load(open(eyes_path, encoding="utf-8"))["eyes"]

# The source auto-rig binds each stage's face to a different bone (baby: Chest,
# teen: Neck, adult: Head). The lid bones must be children of the bone that
# actually drives the face, otherwise head/neck clips leave the lids behind.
FACE_BONE = {"bayi": "Chest", "remaja": "Neck", "dewasa": "Head"}[stage]

# Linear-space scale colours sampled from each stage's red scales (converted
# from the sRGB texture sample at the eye so the lid matches the face).
SKIN = {
    "bayi": (0.20, 0.002, 0.005, 1.0),
    "remaja": (0.36, 0.011, 0.013, 1.0),
    "dewasa": (0.17, 0.0045, 0.0048, 1.0),
}[stage]
LASH = (0.018, 0.0025, 0.002, 1.0)

REST_DIV = 30.0          # full stretch factor; rest height = eyeH / REST_DIV
OFFSET_N = {"bayi": 0.008, "remaja": 0.007, "dewasa": 0.003}[stage]
DOME = {"bayi": 0.030, "remaja": 0.028, "dewasa": 0.008}[stage]  # outward bulge at eye centre
LASH_FRAC = 0.05          # lash band, as a fraction of eye height at full stretch
CURVE = 0.03              # bottom centre drops this fraction of eye height

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
glb_export.import_glb(src)          # 30 fps grid before any key time is read

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
src_mesh = None
for o in list(bpy.data.objects):
    if o.type == "MESH":
        skinned = any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)
        if not skinned:
            bpy.data.objects.remove(o, do_unlink=True)
        else:
            src_mesh = o
if src_mesh is None:
    raise SystemExit("no skinned mesh")
if "Lid_L" in arm.data.bones:
    raise SystemExit("eyelids already present")
if arm.animation_data:
    for t in arm.animation_data.nla_tracks:
        t.mute = True
    arm.animation_data.action = None

# Build in the bind pose: the eye frames were measured against the bind
# surface (bind_eye_frames.py resets every pose bone first), so this probe runs
# against exactly the surface the cards will be skinned onto.
for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()

head_bone = arm.data.bones["Head"]
if head_bone.name not in {b.name for b in arm.data.bones}:
    raise SystemExit("no Head bone")

arm_mw = arm.matrix_world.copy()
arm_inv = arm_mw.inverted()
# The source GLB positions its Root node at the origin while the bind Root
# sits lower. Blender's exporter writes rest nodes, so restore that authored
# offset on the armature object; otherwise every clip sinks ~0.56 m.
root_delta = -(arm_mw @ arm.data.bones["Root"].head_local)


def to_arm(p):
    return arm_inv @ Vector(p)


# Build a smooth curved grid for each eye plus a lash strip at its lower edge.
# The card is a gentle outward dome (no raycast) so it stays clean and does not
# inherit the irregular brow/cheek/horn geometry of the source head surface.
lid_plans = []
for eye, suffix in zip(eyes, ("L", "R")):
    p = Vector(eye["center"])
    n = Vector(eye["normal"]).normalized()
    right = Vector(eye["right"]).normalized()
    up = Vector(eye["up"]).normalized()
    w = float(eye["width"]) * 1.12
    h = float(eye["height"]) * 1.12
    top_y = h * 0.58
    bottom_y = -h * 0.68
    rows, cols = 16, 20
    grid = []
    for row in range(rows):
        rr = row / (rows - 1.0)
        cells = []
        for col in range(cols):
            cc = col / (cols - 1.0)
            xf = cc - 0.5
            yf = rr - 0.5
            droop = -CURVE * h * (1.0 - (xf * 2.0) ** 2)
            y = top_y + rr * (bottom_y + droop - top_y)
            # radial dome: centre bulges outward, corners recede (matches the
            # convex head), scaled so it never flips the outward normal.
            rad = (xf * 2.0) ** 2 + (yf * 2.0) ** 2
            dome = -DOME * rad
            pt = p + right * (xf * w) + up * y + n * (OFFSET_N + dome)
            cells.append(pt)
        grid.append(cells)
    top_pt = grid[0][cols // 2]
    bottom_pt = grid[rows - 1][cols // 2]
    top_n = n
    bone_dir = (bottom_pt - top_pt).normalized()
    # Full lash band at the bottom 5% of the eye, slightly proud.
    lash_top = []
    lash_bottom = []
    for col in range(cols):
        pt = grid[rows - 1][col]
        lash_top.append(pt + n * 0.0008)
        lash_bottom.append(pt + n * 0.0008 - bone_dir * (h * LASH_FRAC))
    lid_plans.append({
        "suffix": suffix,
        "grid": grid,
        "rows": rows,
        "cols": cols,
        "top": top_pt,
        "bottom": bottom_pt,
        "top_n": top_n,
        "dir": bone_dir,
        "lash_top": lash_top,
        "lash_bottom": lash_bottom,
    })

# Create the two lid bones, children of the face-driving bone.
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
edit_bones = arm.data.edit_bones
parent = edit_bones[FACE_BONE]
lid_bones = {}
for plan in lid_plans:
    suffix = plan["suffix"]
    local_n = (to_arm(plan["top"] + plan["top_n"]) - to_arm(plan["top"])).normalized()
    eb = edit_bones.new(f"Lid_{suffix}")
    eb.head = to_arm(plan["top"])
    eb.tail = to_arm(plan["bottom"])
    eb.parent = parent
    eb.use_connect = False
    eb.align_roll(local_n)
    lid_bones[suffix] = eb.name
bpy.ops.object.mode_set(mode="OBJECT")

# Materials: flat red scale lid + dark lash. They use no texture so the cards
# stay cheap and there is no UV bleed from the painted eye.
def make_material(name, color, rough):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = 0.0
    mat.diffuse_color = color
    return mat


skin_mat = make_material(f"DrakoEyelid_{stage}", SKIN, 0.50)
lash_mat = make_material(f"DrakoLash_{stage}", LASH, 0.55)


def compress(pt, head, down):
    """Collapse the point toward the bone head along the bone (local Y)."""
    rel = pt - head
    along = rel.dot(down)
    return head + rel - down * (along * (1.0 - 1.0 / REST_DIV))


verts = []
faces = []
face_mats = []
groups = {"L": [], "R": []}

for plan in lid_plans:
    suffix = plan["suffix"]
    head = plan["top"]
    down = plan["dir"]
    cols = plan["cols"]
    rows = plan["rows"]
    base = len(verts)
    for row in plan["grid"]:
        for pt in row:
            verts.append(to_arm(compress(pt, head, down)))
    for r in range(rows - 1):
        for c in range(cols - 1):
            a = base + r * cols + c
            b = a + 1
            cc = a + cols + 1
            d = a + cols
            faces.append((a, d, cc, b))
            face_mats.append(0)
    groups[suffix].extend(range(base, base + cols * rows))

    base = len(verts)
    for pt in plan["lash_top"]:
        verts.append(to_arm(compress(pt, head, down)))
    for pt in plan["lash_bottom"]:
        verts.append(to_arm(compress(pt, head, down)))
    for c in range(cols - 1):
        a = base + c
        b = a + 1
        cc = base + cols + c + 1
        d = base + cols + c
        faces.append((a, d, cc, b))
        face_mats.append(1)
    groups[suffix].extend(range(base, base + cols * 2))

mesh = bpy.data.meshes.new("DrakoEyelids")
mesh.from_pydata([tuple(v) for v in verts], [], faces)
mesh.update()
obj = bpy.data.objects.new("DrakoEyelids", mesh)
scene.collection.objects.link(obj)
mesh.materials.append(skin_mat)
mesh.materials.append(lash_mat)
for poly, mi in zip(mesh.polygons, face_mats):
    poly.material_index = mi
    poly.use_smooth = True
mesh.uv_layers.new(name="UVMap")

for bone, indices in groups.items():
    vg = obj.vertex_groups.new(name=lid_bones[bone])
    vg.add(indices, 1.0, "REPLACE")

obj.parent = arm
obj.matrix_parent_inverse = Matrix.Identity(4)
obj.matrix_world = arm_mw
mod = obj.modifiers.new("Armature", "ARMATURE")
mod.object = arm
mod.use_vertex_groups = True

# The lid cards must be visible from the front even if the source material is
# single sided; keep the new materials double sided for safety.
for mat in (skin_mat, lash_mat):
    mat.use_backface_culling = False

# --- Blink curves -----------------------------------------------------------
# Every action gets lid scale keys. The cards are compressed by 1/REST_DIV in
# bind, so scale Y = REST_DIV closes them over the painted eye. Idles blink a
# couple of times; sleep stays shut; one-shots get a single blink. Keeping
# frame 0 and the final frame open preserves the seamless loop of every clip.
# Both eyes get exactly the same frames and values.  This used to shift the
# right lid's non-rest keys 0.7 frames later "for life": the blink closes in 1.8
# frames, so the app sampled the left card shut at 30 and the right still travel-
# ing at 26.3 - one eye visibly half shut in every clip - and in `sleep`, where
# every key is a non-rest key, the offset put the right lid's keys past the
# clip's last frame and the exporter dropped them.  Asymmetry in a blink reads as
# a broken rig, not as character; tools/drako_lid_sync.py repairs assets that
# were authored with the offset.
BLINK_CLOSE = 1.8        # frames at 30 fps
BLINK_HOLD = 1.0
BLINK_OPEN = 4.0


def blink_offsets(scale=REST_DIV):
    return [
        (-(BLINK_CLOSE + 2.0), 1.0),
        (-BLINK_CLOSE, scale),
        (BLINK_HOLD, scale),
        (BLINK_OPEN, 1.0),
    ]


def lid_frames(name, start, end):
    dur = end - start
    if name == "sleep":
        return [(start, REST_DIV), (end, REST_DIV)]
    anchors = [(start, 1.0), (end, 1.0)]
    if dur < 16.0:
        fractions = [0.45]
    elif name.startswith("idle"):
        fractions = [0.30, 0.64] + ([0.84] if dur > 120.0 else [])
    else:
        fractions = [0.42]
    keys = list(anchors)
    for f in fractions:
        center = start + dur * f
        for off, value in blink_offsets():
            frame = center + off
            if start + 1.0 < frame < end - 1.0:
                keys.append((frame, value))
    return sorted(keys)


def add_lid_curves():
    added = 0
    for act in bpy.data.actions:
        start, end = (float(v) for v in act.frame_range)
        if end <= start:
            continue
        if not act.slots or not act.layers:
            raise SystemExit(f"action {act.name} has no slot/layer")
        slot = act.slots[0]
        strip = act.layers[0].strips[0]
        cb = strip.channelbag(slot)
        if cb is None:
            cb = strip.channelbags.new(slot)
        for side in ("L", "R"):
            path = f'pose.bones["Lid_{side}"].scale'
            for fc in list(cb.fcurves):
                if fc.data_path == path and fc.array_index == 1:
                    cb.fcurves.remove(fc)
            fc = cb.fcurves.new(path, index=1, group_name="Eyelids")
            for frame, value in lid_frames(act.name, start, end):
                kp = fc.keyframe_points.insert(frame, value, options={"FAST"})
                kp.interpolation = "LINEAR"
            fc.update()
            added += 1
    print(f"LID_CURVES {added} fcurves over {len(bpy.data.actions)} actions")


add_lid_curves()

# Restore the authored root position before exporting.
arm.location = root_delta
print(f"EYELIDS lid bones={lid_bones}")

# One exporter for every Drako tool: the source file is the frame-count baseline,
# so authoring lids cannot silently shorten a clip on the way out.
glb_export.export_glb(out, src=src, arm=arm, tag="EYELIDS")
