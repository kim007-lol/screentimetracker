#!/usr/bin/env python3
"""Render every animation clip of a GLB to PNG frames for visual QA.

Run with Blender:
  blender -b --python tools/qa_render_glb.py -- <glb> <outdir> [frames]

Read-only with respect to the GLB. Uses Blender's glTF importer and Workbench.
"""
import bpy
import sys
import os
import math
from mathutils import Vector

argv = sys.argv
if "--" in argv:
    args = argv[argv.index("--") + 1 :]
else:
    args = []
if len(args) < 2:
    print("usage: blender -b --python qa_render_glb.py -- <glb> <outdir> [frames]")
    raise SystemExit(2)
glb_path = os.path.abspath(args[0])
out_dir = os.path.abspath(args[1])
fracs = [float(x) for x in args[2].split(",")] if len(args) > 2 else [0.0, 0.33, 0.66, 1.0]
os.makedirs(out_dir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24
scene.render.engine = "BLENDER_WORKBENCH"
scene.render.resolution_x = 320
scene.render.resolution_y = 320
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.display.shading.light = "STUDIO"
scene.display.shading.studio_light = "paint.sl"
scene.display.shading.color_type = "TEXTURE"
scene.display.shading.show_shadows = True
scene.display.shading.show_cavity = True
scene.display.shading.cavity_type = "BOTH"
scene.display.shading.curvature_ridge_factor = 1.2
scene.display.shading.curvature_valley_factor = 1.2
scene.display.shading.background_type = "VIEWPORT"
scene.display.shading.background_color = (0.16, 0.17, 0.19)
scene.view_settings.view_transform = "Standard"
bpy.ops.import_scene.gltf(filepath=glb_path)

# Remove helper geometry that is not part of the skinned model.
arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if arm is None:
    raise SystemExit("no armature imported")
meshes = [
    o
    for o in bpy.data.objects
    if o.type == "MESH" and any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)
]
for o in list(bpy.data.objects):
    if o.type == "MESH" and o not in meshes:
        bpy.data.objects.remove(o, do_unlink=True)
print("RIG", arm.name, "bones", len(arm.data.bones), "meshes", [m.name for m in meshes])

if arm.animation_data:
    for track in arm.animation_data.nla_tracks:
        track.mute = True
    arm.animation_data.action = None

actions = sorted([a for a in bpy.data.actions if a.users > 0 or True], key=lambda a: a.name)
# Keep only the imported clip actions (the glTF importer names them exactly).
actions = [a for a in bpy.data.actions if a.name in {t.name for t in (arm.animation_data.nla_tracks if arm.animation_data else [])}]
if not actions:
    actions = sorted(bpy.data.actions, key=lambda a: a.name)
print("ACTIONS", [a.name for a in actions])

# Compute animated world bounds at a few sampled frames for camera framing.
depsgraph = bpy.context.evaluated_depsgraph_get()
lo = Vector((1e9, 1e9, 1e9))
hi = Vector((-1e9, -1e9, -1e9))


def accumulate_bounds(frame):
    scene.frame_set(frame)
    depsgraph.update()
    for m in meshes:
        ev = m.evaluated_get(depsgraph)
        vm = ev.to_mesh()
        mw = ev.matrix_world
        for v in vm.vertices:
            w = mw @ v.co
            for i in range(3):
                lo[i] = min(lo[i], w[i])
                hi[i] = max(hi[i], w[i])
        ev.to_mesh_clear()


def set_action(action):
    ad = arm.animation_data_create()
    ad.action = action
    # Blender 4.4+ slotted actions require an explicit slot when assigned.
    try:
        if hasattr(ad, "action_slot") and action.slots:
            ad.action_slot = action.slots[0]
    except Exception as exc:
        print("slot assign failed", exc)


for action in actions:
    set_action(action)
    fr = action.frame_range
    for f in (fr[0], (fr[0] + fr[1]) / 2, fr[1]):
        accumulate_bounds(round(f))
    print("SAMPLED", action.name, tuple(fr))

center = (lo + hi) / 2
size = max(hi.x - lo.x, hi.y - lo.y, hi.z - lo.z)
print("BOUNDS", tuple(lo), tuple(hi), "center", tuple(center), "size", size)

cam_data = bpy.data.cameras.new("QACam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = size * 1.18
cam = bpy.data.objects.new("QACam", cam_data)
scene.collection.objects.link(cam)
direction = Vector((1.35, -2.4, 0.65)).normalized()
cam.location = center + direction * (size * 4.0 + 1.0)
cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
scene.camera = cam

# Ground reference at the lowest animated point.
bpy.ops.mesh.primitive_plane_add(size=size * 8, location=(center.x, center.y, lo.z - 0.005))
plane = bpy.context.active_object
plane.name = "QAGround"
mat = bpy.data.materials.new("QAGroundMat")
mat.diffuse_color = (0.32, 0.34, 0.37, 1.0)
plane.data.materials.append(mat)

# Render one frame per requested fraction of the clip.
for action in actions:
    set_action(action)
    fr = action.frame_range
    duration = fr[1] - fr[0]
    for idx, frac in enumerate(fracs):
        scene.frame_set(round(fr[0] + duration * frac))
        depsgraph.update()
        scene.render.filepath = os.path.join(out_dir, f"{action.name}__{idx}.png")
        bpy.ops.render.render(write_still=True)
    print("RENDERED", action.name)
print("DONE", out_dir)
