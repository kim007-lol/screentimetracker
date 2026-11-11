#!/usr/bin/env python3
"""Swap repainted atlas textures into a Drako GLB through a Blender round-trip.

The repaint happens outside Blender (tools/drako_face_repaint.py edits the
extracted JPEGs).  This pass only re-attaches them: the imported image
datablocks are replaced by the new files, every material node that used the old
image is pointed at the replacement, and the GLB is exported again.

Nothing about the rig is touched - no mesh, no skin, no weights, no clip curve.
The glTF exporter is called with the same flags the eyelid/retarget passes use,
and `export_image_format="AUTO"` copies the JPEG bytes verbatim instead of
re-encoding to PNG, so the asset size stays comparable.

The scene frame rate MUST be 30 fps before the import: the glTF importer maps
keyframe seconds onto integer scene frames, so at Blender's 24 fps default every
clip gets re-sampled onto a 24 fps grid (walk's 43 keys at 1/30 s collapse to 34
keys at 1/24 s and the duration shifts by a third of a second).  That ordering is
no longer this file's business - `glb_export.import_glb` sets the rate and every
Drako pass imports through it, which is the only reason a new pass cannot forget
it again.

Run:
  blender -b --factory-startup -P tools/drako_texture_reapply.py -- \
      src.glb out.glb <basecolor.jpg> [<metalrough.jpg> <normal.jpg>]
"""

from __future__ import annotations

import os
import re
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_export                                              # noqa: E402

argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
if len(args) < 3:
    raise SystemExit("usage: drako_texture_reapply.py -- src.glb out.glb basecolor.jpg [mr.jpg normal.jpg]")

src, out = os.path.abspath(args[0]), os.path.abspath(args[1])
replacements = [os.path.abspath(p) for p in args[2:]]

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
glb_export.import_glb(src)          # 30 fps grid before any key time is read

# The atlas files are named Image_0 (base colour), Image_1 (metallic-roughness),
# Image_2 (normal) in the order the exporter wrote them.
BASE_SRGB = 0
by_name = {im.name: im for im in bpy.data.images}
print("IMPORTED_IMAGES", sorted(by_name))


def find_slot(slot):
    """The image datablock that carries this semantic atlas slot.

    `drako_texture_extract.py` names its files `<bufferView index>_Image_N.jpg`
    because the index prefix is what the exporter writes into the datablock name
    too - a GLB that has been round-tripped once already arrives with
    `1_Image_0`, not `Image_0`.  Matching the bare name only found the first
    generation of assets and then silently reported MISSING_IMAGE_SLOT, so the
    lookup takes the canonical `Image_N` token wherever it sits.
    """
    want = "Image_%d" % slot
    if want in by_name:
        return by_name[want]
    cands = [n for n in by_name
             if re.sub(r"\.\d+$", "", n).split("_")[-2:] == ["Image", str(slot)]]
    if len(cands) == 1:
        return by_name[cands[0]]
    if len(cands) > 1:
        print("AMBIGUOUS_IMAGE_SLOT", want, "->", sorted(cands))
    return None


SWAP = []
for slot, path in enumerate(replacements):
    old = find_slot(slot)
    if old is None:
        print("MISSING_IMAGE_SLOT", "Image_%d" % slot, "-> available", sorted(by_name))
        continue
    img = bpy.data.images.load(path, check_existing=False)
    want = "Image_%d" % slot
    img.name = want + "_repainted"
    img.colorspace_settings.name = "sRGB" if slot == BASE_SRGB else "Non-Color"
    img.file_format = "JPEG"
    SWAP.append((old, img))
    print("LOAD", want, "<-", os.path.basename(path), img.size[:], img.colorspace_settings.name)

if not SWAP:
    raise SystemExit("no image slot matched; refusing to export an unchanged GLB")

users = 0
for mat in bpy.data.materials:
    if not mat.use_nodes:
        continue
    for node in mat.node_tree.nodes:
        if node.type != "TEX_IMAGE":
            continue
        for old, new in SWAP:
            if node.image == old:
                node.image = new
                users += 1
print("NODE_REASSIGNMENTS", users)

# Textures only - the animation must leave the file exactly as it came in, so the
# source GLB is the frame-count baseline and the shared exporter snaps every key
# back onto the 30 fps grid before writing (see tools/loop_keys.py).
glb_export.export_glb(out, src=src, tag="TEXTURE",
                      extra_flags={"export_image_format": "AUTO"})
print("src %d bytes" % os.path.getsize(src))
