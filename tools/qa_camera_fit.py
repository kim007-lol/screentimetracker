#!/usr/bin/env python3
"""Measure model-viewer framing occupancy for a GLB at candidate radii.

Run with Blender:
  blender -b --python tools/qa_camera_fit.py -- <glb> <theta_deg> <phi_deg> <target_x> <target_y> <target_z> <aspect> <fov_deg> <r1,r2,...>

Uses the same orbit convention as model-viewer (Y-up source, +Z front).
Prints the maximum normalized horizontal/vertical extent across all clips and
sampled frames. NDC > 1 means the silhouette would be clipped.
"""
import bpy
import sys
import os
import math
from mathutils import Vector, Euler

argv = sys.argv
args = argv[argv.index("--") + 1 :] if "--" in argv else []
if len(args) < 9:
    print("usage: blender -b --python qa_camera_fit.py -- <glb> <theta> <phi> <tx> <ty> <tz> <aspect> <fov> <radii>")
    raise SystemExit(2)

glb_path = os.path.abspath(args[0])
theta = math.radians(float(args[1]))
phi = math.radians(float(args[2]))
target = Vector(tuple(float(x) for x in args[3:6]))
aspect = float(args[6])
fov = math.radians(float(args[7]))
radii = [float(x) for x in args[8].split(",")]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 24
bpy.ops.import_scene.gltf(filepath=glb_path)

arm = next((o for o in bpy.data.objects if o.type == "ARMATURE"), None)
if arm is None:
    raise SystemExit("no armature")
meshes = [
    o for o in bpy.data.objects
    if o.type == "MESH" and any(m.type == "ARMATURE" and m.object == arm for m in o.modifiers)
]
# glTF import maps source +Y to Blender +Z and source +Z to Blender -Y.
target_b = Vector((target.x, -target.z, target.y))
front = Vector((math.sin(theta), -math.cos(theta), 0.0))
up = Vector((0.0, 0.0, 1.0))
flat = front
up_axis = up

if arm.animation_data:
    for track in arm.animation_data.nla_tracks:
        track.mute = True
    arm.animation_data.action = None

tracks = {t.name for t in arm.animation_data.nla_tracks} if arm.animation_data else set()
actions = [a for a in bpy.data.actions if a.name in tracks] or list(bpy.data.actions)
print("ACTIONS", len(actions))


def set_action(action):
    ad = arm.animation_data_create()
    ad.action = action
    try:
        if hasattr(ad, "action_slot") and action.slots:
            ad.action_slot = action.slots[0]
    except Exception as exc:
        print("slot assign failed", exc)


depsgraph = bpy.context.evaluated_depsgraph_get()
# Collect world-space vertices for all samples once. Sampling every 6th frame
# keeps the run bounded while covering fast wing flaps.
samples = []
for action in actions:
    set_action(action)
    fr = action.frame_range
    steps = sorted({round(fr[0] + (fr[1] - fr[0]) * f) for f in (0, .2, .4, .6, .8, 1)})
    for f in steps:
        scene.frame_set(f)
        depsgraph.update()
        pts = []
        for m in meshes:
            ev = m.evaluated_get(depsgraph)
            vm = ev.to_mesh()
            mw = ev.matrix_world
            pts.extend(mw @ v.co for v in vm.vertices)
            ev.to_mesh_clear()
        samples.append((action.name, f, pts))

print("SAMPLES", len(samples), "VERTS", len(samples[0][2]))

for r in radii:
    cam_loc = target_b + Vector((
        math.sin(phi) * math.sin(theta),
        -math.sin(phi) * math.cos(theta),
        math.cos(phi),
    )) * r
    cam_dir = (target_b - cam_loc).normalized()
    # Camera basis: right, up, forward (look direction).
    right = cam_dir.cross(up_axis).normalized()
    if right.length < 1e-6:
        right = Vector((1, 0, 0))
    cam_up = right.cross(cam_dir).normalized()
    tx = math.tan(fov / 2) * aspect
    ty = math.tan(fov / 2)
    mx = my = 0.0
    worst = None
    for name, f, pts in samples:
        for p in pts:
            d = p - cam_loc
            z = d.dot(cam_dir)
            if z <= 0.01:
                continue
            nx = abs(d.dot(right) / (z * tx))
            ny = abs(d.dot(cam_up) / (z * ty))
            if nx > mx:
                mx, worst = nx, (name, f, "x")
            if ny > my:
                my, worst = ny, (name, f, "y")
    print(
        f"RADIUS {r:.3f} max_x={mx:.3f} max_y={my:.3f} "
        f"worst={worst} fit={'YES' if mx <= 1 and my <= 1 else 'CROP'}"
    )
print("DONE")
