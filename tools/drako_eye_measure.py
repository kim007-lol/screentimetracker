"""Measure one canonical Drako eye per side, straight off the mesh.

Why this replaces the rect/colour pipeline
------------------------------------------
`drako_eye_refit.py` paints into a hand-picked atlas rectangle, so a wrong rect
paints an almond on the neck and the two eyes are only as symmetric as the two
rects happen to be.  The adult shipped that way: one big round eye, one small
thin one, and the palette in that script is a blue anime eye sampled from
`card_ref_face.png`, which is not Drako - `docs/docs-assets-chr/
paket-drako-3d-final/drako_dewasa.png` shows amber, half-lidded almonds.

Here the eye is derived from the mesh instead:

1. the original texture's pupil is found in the flat-lit render (a near-black
   blob inside a pale ring), ray-cast once to get the world centre;
2. every loop triangle within a radius of that centre, facing outward, is
   classified by the atlas colour at its UV centroid - eye paint vs body red;
3. the frame is anatomy, not statistics: the head's vertical is world +Z, and
   projecting it into the tangent plane at the eye normal gives the direction a
   lid has to sweep; `right = up x n` oriented outward.  The paint's own
   principal axis is measured *in* that frame as a cross-check (`pca_tilt`),
   never as its definition - for a near-round eye the minor axis of a circle is
   noise, and taking it for `up` authored the lid sideways across the eye, which
   is why a blink never closed it.  The triangle set is classified with the
   eye's own paint class (amber iris / dark pupil / white sclera), not the
   adult's pale `CREAM` cut: the repainted teen iris is saturated (chroma 0.54)
   and CREAM rejects it, so the flood ran out into the belly patch that touches
   the lower rim and the world cap trimmed the whole eye down to a sliver of
   skin around it.
4. one side is mirrored onto the other so both eyes share one canonical frame,
   centre |x|, height and width - the UV sheet is not mirror-symmetric, so a
   single canvas warped through each side's own affine is the only way to get
   identical eyes;
5. the per-side affine eye-space -> atlas-pixel is fitted robustly from those
   same triangles, and the triangles are exported in atlas space so the painter
   can restrict itself to texels the eye actually owns, and refuse texels a
   distant part of the sheet also uses.
6. the aperture is measured a second time, in an orthographic render taken along
   that side's own normal: the non-red component that holds the pupil, opened
   past the width of the texture's scale cracks, is the eye the viewer sees.  Its
   outline and the mesh points under it are what the eyelid card is authored
   from and what the blink gates grade; the atlas footprint above is kept for the
   affine fit and as a cross-check only.  An atlas is a painting, not a shape
   map: on the baby its eye drawing is clipped across several UV islands, so the
   footprint is a patchwork band that covers 14 % of the amber a viewer sees.
   Every gate that graded that band agreed with the card and the blink still hid
   only part of the eye.

Run it on the ORIGINAL glb (the eye paint is intact there); the repaint never
moves an eye, so the same numbers drive the repainted atlas.

  blender -b --factory-startup --python-exit-code 1 --python \
      tools/drako_eye_measure.py -- <glb> <out.json> [tag] \
      [--res=1024] [--ratio=1.62] [--radius=0.075] [--outdir=<dir>] \
      [--aperture-open-mm=1.2,2.2,3.5,5.5] [--aperture-stride=8]
"""
import bpy
import json
import math
import os
import sys

import numpy as np
from mathutils import Matrix, Vector
from bpy_extras.object_utils import world_to_camera_view

argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
pos = [a for a in args if not a.startswith("--")]
opts = dict((a[2:].split("=", 1) + [None])[:2] for a in args if a.startswith("--"))
if len(pos) < 2:
    raise SystemExit(__doc__)
glb = os.path.abspath(pos[0])
out_json = os.path.abspath(pos[1])
tag = pos[2] if len(pos) > 2 else os.path.splitext(os.path.basename(glb))[0]
RES = int(opts.get("res") or 1024)
TARGET_RATIO = float(opts.get("ratio") or 1.62)
RADIUS = float(opts.get("radius") or 0.075)
outdir = os.path.abspath(opts.get("outdir") or os.path.dirname(out_json))
os.makedirs(outdir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.fps = 30          # before import, or keys re-quantise to 24 fps
bpy.ops.import_scene.gltf(filepath=glb)

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
body = None
cards = {}
for ob in bpy.data.objects:
    if ob.type != "MESH":
        continue
    has_arm = any(m.type == "ARMATURE" and m.object == arm for m in ob.modifiers)
    srgb = any(sl.material and sl.material.use_nodes and
               any(n.type == "TEX_IMAGE" and n.image and
                   n.image.colorspace_settings.name == "sRGB"
                   for n in sl.material.node_tree.nodes)
               for sl in ob.material_slots)
    if has_arm and (ob.name == "DrakoMesh" or (srgb and body is None)):
        body = ob
    elif has_arm:
        cards[ob.name] = ob
if body is None:
    raise SystemExit("NO_SKINNED_SRGB_MESH")
print("BODY %s polys=%d   card meshes=%s" % (body.name, len(body.data.polygons),
                                             list(cards)))

# The lid cards in bind space.  The blink author needs to know how far the card
# that exists today sits from the eye it has to cover.
card_info = {}
for name, ob in cards.items():
    R3c = np.array(ob.matrix_world.to_3x3())
    tc = np.array(ob.matrix_world.translation)
    vb = np.empty(len(ob.data.vertices) * 3, np.float32)
    ob.data.vertices.foreach_get("co", vb)
    CP = vb.reshape(-1, 3).astype(np.float64) @ R3c.T + tc
    groups = {}
    for v in ob.data.vertices:
        for gw in v.groups:
            if gw.weight >= 0.5:
                groups.setdefault(ob.vertex_groups[gw.group].name, []).append(v.index)
    for gname, idx in groups.items():
        A = CP[np.array(idx)]
        card_info[gname] = {"mesh": name, "verts": int(len(idx)),
                            "centre": [round(float(x), 5) for x in A.mean(0)],
                            "min": [round(float(x), 5) for x in A.min(0)],
                            "max": [round(float(x), 5) for x in A.max(0)]}
        print("CARD %-8s verts=%-5d centre %s min %s max %s"
              % (gname, len(idx), card_info[gname]["centre"],
                 card_info[gname]["min"], card_info[gname]["max"]))

for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
for ob in list(bpy.data.objects):
    if ob.type != "MESH" or ob is body:
        continue
    bpy.data.objects.remove(ob, do_unlink=True)
for nm in [m.name for m in body.modifiers if m.type == "ARMATURE"]:
    body.modifiers.remove(body.modifiers[nm])
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()

mw = body.matrix_world
uvl = body.data.uv_layers.active
if not uvl:
    raise SystemExit("NO_UV_LAYER")
uvbuf = np.empty(len(body.data.uv_layers.active.data) * 2, np.float32)
uvl.data.foreach_get("uv", uvbuf)
uvl_arr = uvbuf.reshape(-1, 2)

body.data.calc_loop_triangles()
lt = body.data.loop_triangles
F = len(lt)
# MeshLoopTriangle exposes vertex_indices / uv_indices / cent / normal as python
# properties only, so this one pass is a python loop.  161k triangles costs a few
# seconds and then everything below is vectorised.
tri_v = np.empty((F, 3), np.int64)
tri_l = np.empty((F, 3), np.int64)
tri_p = np.empty(F, np.int64)
tri_c = np.empty((F, 3), np.float64)
tri_n = np.empty((F, 3), np.float64)
for i, t_ in enumerate(lt):
    tri_v[i] = t_.vertices
    tri_l[i] = t_.loops
    tri_p[i] = t_.polygon_index
    tri_c[i] = t_.center
    tri_n[i] = t_.normal
tri_uv = uvl_arr[tri_l]                              # F,3,2
co = np.empty(len(body.data.vertices) * 3, np.float32)
body.data.vertices.foreach_get("co", co)
V = co.reshape(-1, 3).astype(np.float64)
R3 = np.array(mw.to_3x3())
t = np.array(mw.translation)
tri_w = tri_c @ R3.T + t                             # world centroids
vert_w = V @ R3.T + t
tri_nw = tri_n @ R3.T
tri_nw /= np.maximum(np.linalg.norm(tri_nw, axis=1, keepdims=True), 1e-9)
print("TRIANGLES %d  world x[%.3f,%.3f] y[%.3f,%.3f] z[%.3f,%.3f]"
      % (F, tri_w[:, 0].min(), tri_w[:, 0].max(), tri_w[:, 1].min(),
         tri_w[:, 1].max(), tri_w[:, 2].min(), tri_w[:, 2].max()))

# ------------------------------------------------------------------ head mask
head_g = set(g.index for g in body.vertex_groups
             if g.name in ("Head", "Horn_L", "Horn_R"))
head_v = np.zeros(len(body.data.vertices), bool)
for v in body.data.vertices:
    s = 0.0
    for gw in v.groups:
        if gw.group in head_g:
            s += gw.weight
    if s >= 0.5:
        head_v[v.index] = True
hp = vert_w[head_v]
lo, hi = hp.min(0), hp.max(0)
span = float((hi - lo).max())
tgt = Vector((float((lo + hi)[0] / 2), float(lo[1] + 0.30 * (hi[1] - lo[1])),
              float(lo[2] + 0.40 * (hi[2] - lo[2]))))
print("HEAD world min %s max %s span %.3f" % (np.round(lo, 4).tolist(),
                                              np.round(hi, 4).tolist(), span))

# ---------------------------------------------------------------- face camera
scene.render.resolution_x = RES
scene.render.resolution_y = RES
cd = bpy.data.cameras.new("EyeCam")
cd.sensor_fit = "VERTICAL"
cd.angle = 0.4538
cd.clip_start = 0.01
cd.clip_end = 100.0
cam = bpy.data.objects.new("EyeCam", cd)
scene.collection.objects.link(cam)
scene.camera = cam
off = Vector((0.0, -1.0, 0.05)).normalized()
cam.location = tgt + off * span * 2.6
cam.rotation_euler = (-off).to_track_quat("-Z", "Y").to_euler()
bpy.context.view_layer.update()
vis_h = 2.0 * (span * 2.6) * math.tan(cd.angle / 2.0)
px_per_m = RES / vis_h
print("CAM %.3f m visible %.3f m -> %.0f render px per metre"
      % (span * 2.6, vis_h, px_per_m))

scene.render.engine = "BLENDER_WORKBENCH"
scene.display.shading.light = "FLAT"
scene.display.shading.color_type = "TEXTURE"
scene.display.shading.show_cavity = False
scene.view_settings.view_transform = "Standard"
shot_path = os.path.join(outdir, "%s_flat.png" % tag)
scene.render.filepath = shot_path
bpy.ops.render.render(write_still=True)
dg = bpy.context.evaluated_depsgraph_get()

shot = bpy.data.images.load(shot_path, check_existing=False)
SW, SH = shot.size
sbuf = np.empty(SW * SH * 4, np.float32)
shot.pixels.foreach_get(sbuf)
shot_px = sbuf.reshape(SH, SW, 4)[::-1].copy()       # row 0 is the TOP

tex = None
for slot in body.material_slots:
    m = slot.material
    if m and m.use_nodes:
        for nd in m.node_tree.nodes:
            if nd.type == "TEX_IMAGE" and nd.image and \
                    nd.image.colorspace_settings.name == "sRGB":
                tex = nd.image
if tex is None:
    raise SystemExit("NO_SRGB_TEXTURE")
TW, TH = tex.size
tbuf = np.empty(TW * TH * 4, np.float32)
tex.pixels.foreach_get(tbuf)
# `Image.pixels` stores row 0 at the BOTTOM of the image, while every atlas
# coordinate this tool produces - tri_apx, own_tri, the fitted affine, the
# reported atlas_box - is a TOP-origin row, because that is the convention the
# glTF runtime uses and the one the eye-symmetrise copy was verified against to
# 0.2 px.  Indexing the buffer with those coordinates therefore read the
# vertically mirrored texel.  This flip is the fix, and it is not cosmetic:
# until it, every colour decision below graded pixels that are not on the eye.
# The teen left eye's box is rows 1074-1173 and its mirror is 875-974, which is
# red scale and a cream blob - so the paint grade kept triangles for being amber
# because their *mirror* was amber, and the dark quartile that produces LID_SIDE
# picked a direction from the same wrong rows (which is why the right side
# reported up_dev 131 deg and was dropped from the canonical frame).
# tools/qa_rig/tmp_sheet_row_probe.py measures it: the buffer correlates with the
# file read upside down to 0.00000 mean absolute deviation, and with the file
# read normally to 0.19977.
sheet = np.ascontiguousarray(tbuf.reshape(TH, TW, 4)[::-1])   # row 0 is the TOP
tri_uvc = tri_uv.mean(axis=1)                         # uv at each centroid
tri_apx = np.column_stack([tri_uvc[:, 0] * TW, (1.0 - tri_uvc[:, 1]) * TH])
print("ATLAS %s %dx%d" % (tex.name, TW, TH))


def atlas_eye_paint(C):
    """The eye-paint class applied to atlas texels, in one place.

    The same three tests the render-side EYEPAINT class uses (amber iris, dark
    pupil and lash, pale sclera), written for the atlas so the footprint can be
    graded by the paint the triangles actually sample.  Both the grade and the
    row-order gate below call this, so they can never disagree.
    """
    C = np.asarray(C, np.float64)
    r, g, b = C[..., 0], C[..., 1], C[..., 2]
    return (((r > 0.45) & (g >= 0.26) & (g <= 0.62) & (b < 0.42) & (r - b > 0.20))
            | (C.max(-1) < 0.30) | (C.min(-1) > 0.78))


def atlas_px(rows, cols):
    """Texels at top-origin atlas pixel coordinates, clamped to the sheet."""
    return sheet[np.clip(np.round(rows).astype(int), 0, TH - 1),
                 np.clip(np.round(cols).astype(int), 0, TW - 1), :3]


def ray_uv(px, py):
    tt = math.tan(cd.angle / 2.0)
    nx = (px + 0.5) / RES * 2.0 - 1.0
    ny = 1.0 - (py + 0.5) / RES * 2.0
    d = (cam.matrix_world.to_3x3() @ Vector((nx * tt, ny * tt, -1.0))).normalized()
    res, loc, n, idx, obj, mat = scene.ray_cast(dg, cam.matrix_world.translation, d)
    if not res or obj != body:
        return None
    return np.array(tuple(loc), np.float64), idx


# ------------------------------------------------------- pupil seed in render
def paint_masks(px_):
    """The rendered-colour classes, for one top-origin RGBA render buffer.

    Factored out so the aperture pass grades its own orthographic render with
    byte-for-byte the same thresholds as the face render.  Two copies of this
    palette is exactly how the paint grade and the atlas grade drifted apart
    before; there is one definition and every render is judged by it.
    """
    R_, G_, B_ = px_[..., 0], px_[..., 1], px_[..., 2]
    mx = px_[..., :3].max(axis=2)
    mn = px_[..., :3].min(axis=2)
    solid = px_[..., 3] > 0.5
    # The painted eye is pale and *unsaturated*; the body skin is a saturated red
    # (MAXC-MINC ~ 0.41 at value 0.50).  A chroma cut separates the two on both
    # sides, where an RGB distance to a locally sampled skin median does not - the
    # right pupil sat 0.001 under such a cut and its component came back empty.
    # CREAM is the adult's palette and it is wrong for the repainted teen, which
    # is where the whole eye frame went sideways.  Measured off the base colour
    # atlas (image 1 of remaja_headyaw.glb, the one Material_0 uses as
    # baseColorTexture): the iris is rgb(197,93,59) - MAXC 0.77, chroma 0.54 - so
    # (MAXC-MINC) < 0.38 *rejects the iris*, and the flood that should have been
    # the eye ran out into the cream belly patch that touches the eye's lower rim.
    # The 50 mm world cap then trimmed that back to a diagonal sliver of skin
    # around the aperture: 97 triangles on the left, 63 on the right, where the
    # paint names 554 and 412.  A PCA of a sliver invented an `up` 90.1 and 51.9
    # degrees off the eye, and the lid pass authored a card *across* a round eye -
    # which is why a blink never closed it.  This class is the eye itself:
    #   body red   rgb(153,17,17)..rgb(204,34,34)  g <= 0.14  -> excluded by g >= 0.26
    #   amber iris rgb(197,93,59)                   g  0.37, b 0.23
    #   dark pupil rgb(34,17,0) and the lash line   MAXC < 0.30
    #   white ring rgb(238,236,230)                 MINC > 0.78
    #   cream belly rgb(204,187,119)/rgb(238,204,153) g >= 0.73, b 0.47 -> excluded
    # The g <= 0.62 ceiling is what keeps the belly out; the b < 0.42 ceiling keeps
    # the white ring in without letting pale skin through.
    amber = solid & (R_ > 0.45) & (G_ >= 0.26) & (G_ <= 0.62) & (B_ < 0.42) & (R_ - B_ > 0.20)
    dark = solid & (mx < 0.30)
    white = solid & (mn > 0.78)
    return {"solid": solid, "dark": dark,
            "pale": solid & (mx > 0.50) & (B_ > 0.28),      # sclera / cream, not red
            "cream": solid & (mx > 0.55) & ((mx - mn) < 0.38),
            "amber": amber, "white": white, "eyepaint": amber | dark | white}


_M = paint_masks(shot_px)
SOLID, DARK = _M["solid"], _M["dark"]
PALE, CREAM = _M["pale"], _M["cream"]
AMBER, WHITE, EYEPAINT = _M["amber"], _M["white"], _M["eyepaint"]


def integral(mask):
    p = np.zeros((SH + 1, SW + 1), np.float64)
    p[1:, 1:] = np.cumsum(np.cumsum(mask.astype(np.float64), axis=0), axis=1)
    return p


def box_sum(ii, cx, cy, r):
    x0 = int(max(cx - r, 0)); x1 = int(min(cx + r, SW))
    y0 = int(max(cy - r, 0)); y1 = int(min(cy + r, SH))
    return ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]


def find_pupil(bx, by, win, rise):
    """The pupil: the thickest near-black region inside the search box.

    The anchor used to be "the darkest pixel that sits in a pale ring", which is
    a description of the *adult's* eye - a dark pupil in a white sclera.  The
    repainted teen puts a saturated amber iris around the pupil and a white
    sclera crescent off to the outer side, so the ring is highest where the lash
    line meets the sclera and the detector anchored there instead: the left eye
    came out 31 mm above the pupil the viewer sees, and the right eye found a
    four-pixel dark speck on its rim.

    Thickness is the property that does not move with the palette.  A pupil is a
    filled disc, so a square of side 2*THICK centred anywhere inside it is
    entirely dark; a lash line, a brow shadow, the mouth line and the jaw shadow
    are arcs and the same square across their width is only partly dark.  The
    pale ring survives as a minority tie-break (it is genuinely informative on
    the adult) and a mild pull toward the bone keeps the search on the eye.
    """
    ii = integral(PALE)
    iid = integral(DARK)
    ccx, ccy = bx, by - rise
    x0, x1 = int(max(ccx - win, 0)), int(min(ccx + win, SW))
    y0, y1 = int(max(ccy - win, 0)), int(min(ccy + win, SH))
    ys, xs = np.nonzero(DARK[y0:y1, x0:x1])
    if len(xs) == 0:
        return None
    THICK = max(6, int(round(RES * 0.014)))
    disc = float((2 * THICK) ** 2)
    scored = []
    for cx, cy in zip(xs + x0, ys + y0):
        if box_sum(iid, cx, cy, 2) < 6.0:
            continue                                  # a 1 px antialias gap
        thick = box_sum(iid, cx, cy, THICK) / disc
        ring = (box_sum(ii, cx, cy, 16) - box_sum(ii, cx, cy, 4)) / \
            float(4 * (16 * 16 - 4 * 4))
        near = math.hypot(cx - ccx, cy - ccy)
        scored.append((thick + 0.25 * ring - 0.0008 * near, float(thick),
                       float(ring), int(cx), int(cy)))
    if not scored:
        return None
    scored.sort(reverse=True)
    for s in scored[:3]:
        print("      cand (%d,%d) thick=%.3f pale_ring=%.4f score=%.4f"
              % (s[3], s[4], s[1], s[2], s[0]))
    return (scored[0][3], scored[0][4]), scored[0][2]


def grow(mask, sx, sy, limit, reach):
    """8-connected component of `mask` inside a window around (sx, sy)."""
    h, w = mask.shape
    if not mask[sy, sx]:
        return []
    seen = np.zeros((h, w), bool)
    out = []
    stack = [(sy, sx)]
    seen[sy, sx] = True
    while stack:
        y, x = stack.pop()
        out.append((y, x))
        if len(out) > limit:
            break
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx_ = y + dy, x + dx
                if abs(ny - sy) > reach or abs(nx_ - sx) > reach:
                    continue
                if 0 <= ny < h and 0 <= nx_ < w and mask[ny, nx_] and not seen[ny, nx_]:
                    seen[ny, nx_] = True
                    stack.append((ny, nx_))
    return out


def _window_sum(m, r):
    """(2r+1)^2 box sum around every pixel, with the frame padded by False.

    The unpadded version of this counted only the in-bounds part of a border
    window and then compared it against the *full* kernel area, so no border
    pixel ever eroded - and its dilation complement therefore painted a ring of
    `True` around the whole frame.  That ring is not cosmetic: the aperture grid
    sampled it, cast rays at u = +-228 mm, and a 198 mm eye came out with a
    456 mm footprint that no card could clear.  Padding makes "outside" mean
    "not in the mask", which is what a morphological operator on an image is
    supposed to mean.
    """
    h, w = m.shape
    p = np.zeros((h + 2 * r, w + 2 * r), np.float64)
    p[r:r + h, r:r + w] = m
    H, W = p.shape
    ii = np.zeros((H + 1, W + 1), np.float64)
    ii[1:, 1:] = np.cumsum(np.cumsum(p, axis=0), axis=1)
    k = 2 * r + 1
    return (ii[k:, k:] - ii[:-k, k:] - ii[k:, :-k] + ii[:-k, :-k])


def _erode(m, r):
    """Binary erosion with a (2r+1)^2 square; the frame counts as outside."""
    k = 2 * r + 1
    return _window_sum(m, r) >= k * k


def _dilate(m, r):
    """Binary dilation: any neighbour in `m`.  `~_erode(~m)` is NOT the same
    operator once the frame is padded - it would grow the mask at the border."""
    return _window_sum(m, r) >= 1


def _label_runs(mask):
    """8-connected component labelling by row runs.  Blender ships no scipy.

    Returns (labels, count, sizes): labels is int32 with 0 = background and
    1..count = components, sizes[b] is the pixel count of label b.
    """
    H, W = mask.shape
    labels = np.zeros((H, W), np.int32)
    runs = []
    parent = []

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    prev = []
    for y in range(H):
        row = np.concatenate(([False], mask[y], [False]))
        d = np.diff(row.view(np.int8))
        starts = np.nonzero(d == 1)[0]
        ends = np.nonzero(d == -1)[0] - 1
        cur = []
        for s, e in zip(starts.tolist(), ends.tolist()):
            idx = len(parent)
            parent.append(idx)
            runs.append((y, int(s), int(e)))
            cur.append(idx)
        i = j = 0
        while i < len(prev) and j < len(cur):
            ps, pe = runs[prev[i]][1], runs[prev[i]][2]
            cs, ce = runs[cur[j]][1], runs[cur[j]][2]
            # Runs on consecutive rows are 8-connected when they overlap or
            # sit one column apart.
            if ps <= ce + 1 and cs <= pe + 1:
                ra, rb = find(prev[i]), find(cur[j])
                if ra != rb:
                    parent[rb] = ra
            if pe < ce:
                i += 1
            else:
                j += 1
        prev = cur
    root_id = {}
    for idx, (y, s, e) in enumerate(runs):
        r = find(idx)
        lab = root_id.get(r)
        if lab is None:
            lab = len(root_id) + 1
            root_id[r] = lab
        labels[y, s:e + 1] = lab
    sizes = np.bincount(labels.ravel(), minlength=len(root_id) + 1)
    return labels, len(root_id), sizes


def fill_holes(mask):
    """Pixels of ~mask that `mask` encloses completely.

    A complement component that touches the render frame is open - it is the
    background or a crevice that runs off the head.  Every other complement
    component is a hole walled in by the mask.  Run-length union-find because
    Blender's Python has no scipy; 8-connectivity, like the probe that proved
    the adult sclera is enclosed by the eye's own dark rim.
    """
    labels, n, sizes = _label_runs(~mask)
    open_lab = set(labels[0].tolist()) | set(labels[-1].tolist()) | \
        set(labels[:, 0].tolist()) | set(labels[:, -1].tolist())
    keep = np.ones(n + 1, bool)
    keep[0] = False
    for lab in open_lab:
        if lab:
            keep[lab] = False
    return keep[labels], int(keep.sum() - 1)


# ------------------------------------------------------------- aperture pass
# Every gate below this point used to agree with the atom because all of them
# graded the same `face_indices`: the triangles the atlas flood kept.  On the
# baby that set is a *patchwork band* across the eye - the atlas is a projection
# bake whose islands clip the eye drawing into cream/horn/flame pieces - so the
# card was authored to the band's hull and the blink hid only the part of the
# eye the band covers.  A gold-pixel ray cast put that at 13.8 % (L) and 10.7 %
# (R) of the visible amber.  Nothing derived from the atlas can fix that; the
# aperture has to be measured where the viewer sees it: in a render taken along
# the eye's own normal.
#
# Painting cannot bound that render either.  The eye's own brown arcs sit outside
# every palette class, and the texture's black scale cracks cross the red and
# touch the eye rim, so a flood in any paint class leaks out of the aperture
# within two or three pixels and never comes back.  The boundary that does hold
# is face/eye: red scales and the pale yellow muzzle on one side, every eye
# colour on the other.  Open the non-face mask with a square larger than the
# widest crack - that deletes the thin cracks and keeps the eye - take the
# component that holds the pupil, dilate it back by the rim the erosion shaved,
# and walk its outline.  The skin test is a *chroma ratio*, not `g < 0.10`: the
# texture's own body red is rgb(153,17,17)..rgb(204,34,34), whose g reaches
# 0.133, so the absolute cut classed half the scales as "not skin" and the
# component swallowed them.  The muzzle needs its own clause: it is pale and
# low-chroma like the sclera, and only its yellow cast tells them apart.
AP_OPEN_MM = [float(x) for x in
              (opts.get("aperture-open-mm") or "1.2,2.2,3.5,5.5").split(",")]
AP_STRIDE = int(opts.get("aperture-stride") or 8)


def aperture_pass(side, c, f_right, f_up, f_n, pupil_world, half_w, half_h,
                  paint_box=None):
    """The visible eye, from an orthographic render along its own normal.

    Returns the outline in the eye frame, the world points on the mesh inside
    it, and the body faces under them.  The card is authored from these points,
    so its hull, its window and the gates that judge it are the eye the viewer
    sees instead of the atlas island the flood kept.
    """
    rad = max(0.055, 2.6 * max(float(half_w), float(half_h)))
    cd2 = bpy.data.cameras.new("ApCam")
    cd2.type = "ORTHO"
    cd2.ortho_scale = 2.0 * rad
    cd2.clip_start = 0.005
    cd2.clip_end = 50.0
    cobj = bpy.data.objects.new("ApCam", cd2)
    scene.collection.objects.link(cobj)
    R3a = Matrix((tuple(f_right), tuple(f_up), tuple(f_n))).transposed()
    cobj.matrix_world = (Matrix.Translation(Vector(tuple(c)) +
                                            Vector(tuple(f_n)) * 1.0) @
                         R3a.to_4x4())
    scene.camera = cobj
    prev_bg = tuple(scene.display.shading.background_color)
    scene.display.shading.background_color = (1.0, 0.0, 1.0)
    # The aperture is the *body's* visible eye: every mesh that is not the body was
    # removed before any measurement (see the import block at the top), so this
    # render cannot include a lid card.  What it shows is what the viewer sees of
    # the eye itself - the cards are impostors and must be authored to this, not
    # the other way round.
    png = os.path.join(outdir, "%s_aperture_%s.png" % (tag, side))
    scene.render.filepath = png
    bpy.ops.render.render(write_still=True)
    scene.camera = cam
    scene.display.shading.background_color = prev_bg
    bpy.data.objects.remove(cobj, do_unlink=True)
    bpy.data.cameras.remove(cd2)

    aimg = bpy.data.images.load(png, check_existing=False)
    W2, H2 = aimg.size
    abuf = np.empty(W2 * H2 * 4, np.float32)
    aimg.pixels.foreach_get(abuf)
    px = abuf.reshape(H2, W2, 4)[::-1].copy()
    bpy.data.images.remove(aimg)
    ppm = W2 / (2.0 * rad)                        # render px per metre

    AM = paint_masks(px)
    bg = AM["solid"] & (px[..., 0] > 0.9) & (px[..., 1] < 0.1) & (px[..., 2] > 0.9)
    solid = AM["solid"] & ~bg
    R_, G_, B_ = px[..., 0], px[..., 1], px[..., 2]
    mx = px[..., :3].max(axis=2)
    mn = px[..., :3].min(axis=2)
    skin = solid & (R_ > 0.28) & (G_ < 0.30 * R_) & (B_ < 0.30 * R_)
    # This side's own painted corners in render pixels.  Half a pixel of slack
    # against rounding; the box already carries its own margin, so this cannot
    # widen the eye beyond the paint.
    in_paint = np.zeros((H2, W2), bool)
    if paint_box is not None:
        u0, v0, u1, v1 = [float(q) for q in paint_box]
        x0 = (u0 / rad + 1.0) * 0.5 * W2 - 0.5
        x1 = (u1 / rad + 1.0) * 0.5 * W2 - 0.5
        y0 = (1.0 - v1 / rad) * 0.5 * H2 - 0.5      # row 0 is max v
        y1 = (1.0 - v0 / rad) * 0.5 * H2 - 0.5
        x0, x1, y0, y1 = x0 - 0.5, x1 + 0.5, y0 - 0.5, y1 + 0.5
        xcol = np.arange(W2)[None, :]
        yrow = np.arange(H2)[:, None]
        in_paint = ((xcol >= x0) & (xcol <= x1) &
                    (yrow >= y0) & (yrow <= y1))
    # Paleness is never the eye on its own.  The adult's cream sclera, the
    # teen's cream jaw and the lid's warm highlight are all pale pixels; the
    # adult highlight reaches G-B 0.17 and the teen muzzle 0.24, so no hue cut
    # separates them.  Tested both ways: deleting pale from the face class
    # deleted the adult's eye and handed the component to the nose 280 px away;
    # keeping pale everywhere let the teen component walk out through the
    # muzzle to the render frame (APERTURE_L_HITS_THE_FRAME).  So pale stays in
    # the face class, and the adult sclera joins the eye only through topology:
    # it is cream walled in by the eye's own dark rim and amber iris, i.e. an
    # enclosed hole of the not-skin mask.  Fill those holes, but only inside
    # this side's own paint box.  The adult left side also has an enclosed pale
    # patch ~14 mm outboard of the eye (bare scales ringed by black cracks); a
    # global fill joins it and widens the aperture to u=+0.0278 against paint
    # +0.0135, and the card then reaches the brow.  A hole inside the painted
    # box is eye; a hole outside it is face.
    face_pale = (solid & (mx > 0.50) & ((mx - mn) < 0.38) &
                 ((G_ - B_) > 0.12))
    skin = skin | face_pale
    notskin = solid & ~skin
    if paint_box is not None:
        holes, nhole = fill_holes(notskin)
        nfilled = int((holes & in_paint).sum())
        notskin = notskin | (holes & in_paint)
        pale_all = solid & (mx > 0.50) & ((mx - mn) < 0.38) & ((G_ - B_) > 0.12)
        print("APERTURE_PAINT %s pale_in=%d pale_out=%d holes=%d comps=%d "
              "filled=%d box=%s"
              % (side, int((pale_all & in_paint).sum()),
                 int((pale_all & ~in_paint).sum()), int(holes.sum()), nhole,
                 nfilled, np.round(np.array(paint_box), 4).tolist()))

    pw = np.array(tuple(pupil_world), np.float64) - np.array(tuple(c), np.float64)
    pu = float(pw @ np.array(tuple(f_right)))
    pv = float(pw @ np.array(tuple(f_up)))
    sx = int(round((pu / rad + 1.0) * 0.5 * W2 - 0.5))
    sy = int(round((1.0 - pv / rad) * 0.5 * H2 - 0.5))
    sx = int(np.clip(sx, 0, W2 - 1))
    sy = int(np.clip(sy, 0, H2 - 1))

    cands = []
    for mm in AP_OPEN_MM:
        r = max(1, int(round(mm * ppm / 1000.0)))
        core = _erode(notskin, r)
        if not core[sy, sx]:
            wy, wx = np.nonzero(core)
            if len(wx) == 0:
                continue
            k = int(np.argmin((wx - sx) ** 2 + (wy - sy) ** 2))
            seed = (int(wy[k]), int(wx[k]))
        else:
            seed = (sy, sx)
        comp = grow(core, seed[1], seed[0], W2 * H2, W2)
        if len(comp) < 40:
            continue
        cands.append((mm, r, comp))
    if not cands:
        raise SystemExit("APERTURE_%s_NO_BLOB - the pupil is not inside any "
                         "non-red component of the eye render; the skin test or "
                         "the render is wrong" % side)
    areas = np.array([len(c[2]) for c in cands], np.float64)
    med = float(np.median(areas))
    stable = [i for i, a in enumerate(areas) if abs(a - med) <= 0.06 * med]
    mm, r, comp = cands[stable[0] if stable else int(np.argmin(np.abs(areas - med)))]
    ys = np.array([q[0] for q in comp])
    xs = np.array([q[1] for q in comp])
    blob = np.zeros((H2, W2), bool)
    blob[ys, xs] = True
    blob = _dilate(blob, r + 1)
    if (blob[0, :].any() or blob[-1, :].any() or
            blob[:, 0].any() or blob[:, -1].any()):
        raise SystemExit(
            "APERTURE_%s_HITS_THE_FRAME - the non-red component reaches the edge of "
            "the %.0f mm render window, so its outline is the frame and not the eye. "
            "The window is scaled off half_w/half_h; a frame touching blob means "
            "the measurement's frame is wrong or the skin test let the head in."
            % (side, 1e3 * rad))
    bys, bxs = np.nonzero(blob)
    cy0, cx0 = float(bys.mean()), float(bxs.mean())

    # The outline: a radius every half degree from the component's own centroid.
    # Three consecutive outside pixels, so a one-pixel notch in the rim does not
    # end the ray early.
    ang = np.linspace(0.0, 2.0 * math.pi, 720, endpoint=False)
    rr = np.full(len(ang), np.nan)
    for i, th in enumerate(ang):
        ct, st = math.cos(th), math.sin(th)
        out = 0
        for step in range(4, int(0.96 * rad * ppm)):
            xx = int(round(cx0 + ct * step))
            yy = int(round(cy0 - st * step))
            if not (0 <= xx < W2 and 0 <= yy < H2):
                break
            if blob[yy, xx]:
                out = 0
            else:
                out += 1
                if out >= 3:
                    rr[i] = (step - 2) / ppm
                    break
    if not np.isfinite(rr).all():
        raise SystemExit(
            "APERTURE_%s_OPEN_AT_THE_FRAME - %d of %d rays never leave the "
            "non-red component inside the %.0f mm window; the eye is clipped by "
            "the render or the component escaped through the skin"
            % (side, int((~np.isfinite(rr)).sum()), len(rr), 1e3 * rad))
    uu = rr * np.cos(ang)
    vv = rr * np.sin(ang)
    cu, cv = cx0 / ppm - rad, rad - cy0 / ppm      # centroid in the eye frame
    box = [float(uu.min()) + cu, float(vv.min()) + cv,
           float(uu.max()) + cu, float(vv.max()) + cv]

    # The aperture must hold the eye paint the viewer can name and sit on its
    # own paint.  It cannot hold every painted *corner*: the atlas eye-paint
    # class counts dark texels as paint because the pupil is black, and the
    # texture's black scale cracks are the same class, so painted corners sit on
    # cracks 6-7 mm outside the eye.  Graded that way, the adult right eye was
    # refused for not swallowing 2,303 dark crack pixels, while 0 of its 22,397
    # amber iris pixels inside its own box fell outside the aperture.  The gate
    # is stated on the amber - iris, lash rim, gold ring - which no scale
    # colour matches: every substantial amber component inside the side's own
    # paint box has to be in the aperture, the aperture's box centre has to lie
    # on the paint, and the two boxes have to overlap.  A render that latched
    # onto the nose held none of the box's amber, sat 30 mm below the paint,
    # and overlapped 0 %.
    if paint_box is not None:
        amber_box = AM["amber"] & in_paint
        # A painted-corner box overstates the eye - it is a bounding box of
        # texels, not an outline - and the teen's UV island wraps round the
        # snout, so amber that is not the eye lands inside it: a warm scale
        # patch 73 mm from the pupil (1,254 px) and, at the box corner, a
        # 162 px speck beside the muzzle.  The thin amber lower-lash rim is
        # the opposite case: it *is* the eye, but it is 1-2 px wide, so the
        # morphological opening that deletes the scale cracks shaves it and
        # the dilation cannot reach back across the pale anti-alias band -
        # the lid's own 5.5 mm skirt is what covers that rim at a blink.
        # What a viewer names as the eye is the iris disc: the amber within
        # seven tenths of the eye's minor radius of the pupil.  Grade exactly
        # that - measured on the teen, 0.8 of the minor radius pulls the
        # shaved lash rim back into the graded set (305 px) while 0.7 grades
        # 16,693 px of iris with none of it outside the aperture; on the adult
        # and the baby the whole in-box amber already sat inside the aperture,
        # so the zone only narrows what is graded, never widens it.  A render
        # latched onto the nose holds none of the zone's amber at all.
        yy3, xx3 = np.mgrid[0:H2, 0:W2]
        zone = np.hypot(xx3 - sx, yy3 - sy) <= 0.7 * min(half_w, half_h) * ppm
        amber_eye = amber_box & zone
        miss = amber_eye & ~blob
        print("APERTURE_AMBER %s in_box=%d zone=%d miss=%d"
              % (side, int(amber_box.sum()), int(amber_eye.sum()),
                 int(miss.sum())))
        ap_cx = 0.5 * (box[0] + box[2])
        ap_cy = 0.5 * (box[1] + box[3])
        on_paint = (paint_box[0] - 0.002 <= ap_cx <= paint_box[2] + 0.002 and
                    paint_box[1] - 0.002 <= ap_cy <= paint_box[3] + 0.002)
        ix = max(0.0, min(box[2], paint_box[2]) - max(box[0], paint_box[0]))
        iy = max(0.0, min(box[3], paint_box[3]) - max(box[1], paint_box[1]))
        ov = ix * iy / max(1e-9, (paint_box[2] - paint_box[0]) *
                           (paint_box[3] - paint_box[1]))
        if (int(miss.sum()) > max(16, int(0.002 * amber_eye.sum())) or
                not on_paint or ov < 0.5):
            raise SystemExit(
                "APERTURE_DOES_NOT_HOLD_THE_EYE_%s - %d of the %d amber iris "
                "pixels inside this side's paint box are outside the measured "
                "aperture, its box centre (%+.4f,%+.4f) %s the paint box "
                "u=[%+.4f,%+.4f] v=[%+.4f,%+.4f], and it overlaps %.0f%% of the "
                "paint. A correct aperture holds the amber it can see and sits "
                "on its paint; this one is somewhere else. Fix the measurement, "
                "not the gate."
                % (side, int(miss.sum()), int(amber_eye.sum()), ap_cx, ap_cy,
                   "lies on" if on_paint else "is off",
                   paint_box[0], paint_box[2], paint_box[1], paint_box[3],
                   100.0 * ov))

    # World points on the surface: the outline (so the hull is the eye's own rim)
    # plus a grid inside it (so the gates see the whole lid, not just its edge).
    yy2, xx2 = np.mgrid[0:H2:AP_STRIDE, 0:W2:AP_STRIDE]
    keep = blob[yy2, xx2]
    gx = np.concatenate([xx2[keep], np.round(cx0 + np.cos(ang) * rr * ppm)])
    gy = np.concatenate([yy2[keep], np.round(cy0 - np.sin(ang) * rr * ppm)])
    gx = np.clip(gx.astype(np.int64), 0, W2 - 1)
    gy = np.clip(gy.astype(np.int64), 0, H2 - 1)
    hits, faces, miss = [], set(), 0
    n_vec = Vector(tuple(f_n))
    dg2 = bpy.context.evaluated_depsgraph_get()
    for x, y in zip(gx.tolist(), gy.tolist()):
        u = ((x + 0.5) / W2 - 0.5) * 2.0 * rad
        v = (0.5 - (y + 0.5) / H2) * 2.0 * rad
        o = (Vector(tuple(c)) + Vector(tuple(f_right)) * u +
             Vector(tuple(f_up)) * v + n_vec * 0.30)
        res, loc, nrm, idx, obj, mat = scene.ray_cast(dg2, o, -n_vec)
        if res and obj == body:
            hits.append(tuple(loc))
            faces.add(int(idx))
        else:
            miss += 1
    if len(hits) < 40:
        raise SystemExit("APERTURE_%s_TOO_FEW_HITS %d/%d - the render and the "
                         "mesh disagree about where the eye is"
                         % (side, len(hits), len(gx)))
    return {"rad": rad, "ppm": ppm, "blob_px": int(blob.sum()),
            "open_mm": mm, "open_px": r,
            "centre_uv": [round(cu, 5), round(cv, 5)],
            "box": [round(v_, 5) for v_ in box],
            "hull": [[round(float(cu + a * math.cos(t)), 5),
                      round(float(cv + a * math.sin(t)), 5)]
                     for a, t in zip(rr, ang)],
            "points": np.array(hits, np.float64),
            "faces": sorted(faces), "miss": miss,
            "png": os.path.basename(png),
            "rays": [int(np.isfinite(rr).sum()), len(rr)]}


# ------------------------------------------------------- per-side measurement
# The pupil used to be searched only at the lid bone's own render pixel, which is
# correct exactly when that bone sits on the eye.  In the shipped teen it does
# not: Lid_R's head is 0.12 m off-axis, so its box misses the real eye by ~8 px,
# latches onto a cream blob on the cheek and dies at TOO_FEW_TRIANGLES, leaving a
# one-record report that the card author refuses.  This camera looks straight at
# x = 0 from -Y with no roll, so the face is symmetric about the image centre and
# a pupil already proven on one side pins the other.  Try the bone first (that is
# the adult's baseline), then the mirror of whatever the other side found.
def bone_pixel(bone_name):
    b = arm.data.bones.get(bone_name)
    if b is None:
        return None
    c = (arm.matrix_world @ b.head_local + arm.matrix_world @ b.tail_local) / 2
    ndc = world_to_camera_view(scene, cam, c + Vector((0.0, -0.006, 0.0)))
    return ndc.x * RES, (1.0 - ndc.y) * RES


def measure_side(bone_name, seed):
    """Measure one eye from `seed` = (bx, by, win, rise, label).

    Returns the record, or None when this seed does not yield a measurable eye.
    """
    bx, by, win, rise, slabel = seed
    b = arm.data.bones.get(bone_name)
    side = bone_name[-1]
    sx = -1.0 if side == "L" else 1.0
    if b is None:
        print("NO_BONE", bone_name)
        return None
    bone_c = (arm.matrix_world @ b.head_local + arm.matrix_world @ b.tail_local) / 2
    ndc = world_to_camera_view(scene, cam, bone_c + Vector((0.0, -0.006, 0.0)))
    pbx, pby = ndc.x * RES, (1.0 - ndc.y) * RES
    print("BONE %s head %s centre %s pixel (%.0f,%.0f)"
          % (bone_name, np.round(tuple(arm.matrix_world @ b.head_local), 4).tolist(),
             np.round(tuple(bone_c), 4).tolist(), pbx, pby))
    print("  SEED %s pixel (%.0f,%.0f) win=%d rise=%d"
          % (slabel, bx, by, win, rise))
    got = find_pupil(bx, by, win, rise)
    if not got:
        print("  NO_PUPIL_BLOB near seed %s" % slabel)
        return None
    (cx, cy), pale = got
    hit = ray_uv(cx, cy)
    if hit is None:
        print("  NO_HIT at the pupil pixel")
        return None
    centre, fidx = hit
    pu0 = tri_uv[fidx].mean(0)
    pax = np.array([pu0[0] * TW, (1.0 - pu0[1]) * TH], np.float64)
    print("  PUPIL (%d,%d) pale=%.4f world %s tri %d atlas_px %s"
          % (cx, cy, pale, np.round(centre, 4).tolist(), fidx,
             np.round(pax, 1).tolist()))

    # --------------------------------------------------------- row-order gate
    # An atlas read at the mirrored row still *looks* like a measurement: it
    # prints plausible colours, the thresholds still fire, and every decision
    # made from them grades texels that are not on the eye.  That is exactly the
    # bug this gate exists to refuse, and it cost the blink twice - the paint
    # grade kept gold scales because their mirror was amber, and the dark
    # quartile that names the lid side pointed 131 degrees away.
    #
    # The test needs no external truth.  The pupil's own atlas pixel is the
    # darkest thing the paint pass drew, so the triangles that land near it must
    # be eye paint.  Read them directly and again at the vertical mirror, and
    # require the direct read to hold the larger share.  If the mirror wins, the
    # sheet and the coordinates disagree and nothing below can be trusted.
    near = np.linalg.norm(tri_apx - pax, axis=1) <= 60.0
    if int(near.sum()) < 12:
        raise SystemExit("ROW_ORDER_GATE_HAS_NO_NEIGHBOURHOOD - only %d triangles "
                         "sample within 60 px of the pupil's atlas pixel, so the "
                         "orientation cannot be proven; the UV island and the "
                         "pupil hit disagree" % int(near.sum()))
    cols_ = tri_apx[near][:, 0]
    rows_ = tri_apx[near][:, 1]
    share_direct = float(atlas_eye_paint(atlas_px(rows_, cols_)).mean())
    share_mirror = float(atlas_eye_paint(atlas_px(TH - 1 - rows_, cols_)).mean())
    print("  ROW_ORDER eye-paint share direct=%.3f mirror=%.3f over %d tris"
          % (share_direct, share_mirror, int(near.sum())))
    if share_mirror > share_direct:
        raise SystemExit(
            "ATLAS_ROW_ORDER_INVERTED - the texels around the pupil read as eye "
            "paint %.3f of the time at their vertical mirror and only %.3f of the "
            "time where their UVs say they are. `Image.pixels` row order and this "
            "tool's top-origin atlas coordinates disagree; fix the sheet, not the "
            "thresholds." % (share_mirror, share_direct))

    n0 = tri_nw[fidx].copy()
    if n0[1] > 0:
        n0 = -n0
    n0 = n0 / np.linalg.norm(n0)

    # Flood the eye's own paint class, not CREAM.  The window has to reach the
    # far rim of the aperture, so it is derived from --radius in metres through
    # the camera's measured px/m rather than from a fixed fraction of the image.
    REACH = int(max(RADIUS * px_per_m + 8.0, RES * 0.06))
    rr = np.hypot(np.arange(SH)[:, None] - cy, np.arange(SW)[None, :] - cx)
    seed = (cx, cy) if EYEPAINT[cy, cx] else None
    if seed is None:
        wy, wx = np.nonzero(EYEPAINT & (rr <= 45))
        if len(wx) == 0:
            print("  NO_EYEPAINT_NEAR_PUPIL")
            return None
        k = int(np.argmin((wx - cx) ** 2 + (wy - cy) ** 2))
        seed = (int(wx[k]), int(wy[k]))
    comp = grow(EYEPAINT, seed[0], seed[1], 40000, REACH)
    # Re-centre the flood on the blob it actually found.  The window is a box
    # around its seed, so a seed sitting on the lash line clips the far rim and
    # drags the measured centre back toward the seed - the teen left eye came out
    # 31 mm above the eye the viewer sees.  Growing from the blob's own centroid
    # converges in two or three passes, because each pass can only add rim.
    for _ in range(3):
        if len(comp) < 40:
            break
        my = int(round(np.mean([p[0] for p in comp])))
        mx = int(round(np.mean([p[1] for p in comp])))
        if not EYEPAINT[my, mx]:
            break
        again = grow(EYEPAINT, my, mx, 40000, REACH)
        if len(again) <= len(comp) + 4:
            break
        comp = again
    print("  EYEPAINT px=%d seed=%s comp=%d reach=%d"
          % (int(EYEPAINT.sum()), seed, len(comp), REACH))
    if len(comp) < 40:
        print("  REGION_TOO_SMALL")
        return None
    pts, tris, miss = [], [], 0
    for (y, x) in comp:
        g = ray_uv(int(x), int(y))
        if g is None:
            miss += 1
            continue
        pts.append(g[0])
        tris.append(g[1])
    if len(pts) < 40:
        print("  TOO_FEW_HITS")
        return None
    pts = np.array(pts, np.float64)
    tris = np.array(tris, np.int64)
    # The world cap is symmetric about the blob's own centre.  Measuring it from
    # the pupil pixel was the same clipping bias one stage later: it cut the far
    # rim off the aperture and moved the centre it was supposed to bound.
    c = pts.mean(axis=0)
    sel = np.ones(len(pts), bool)
    for _ in range(4):
        sel = np.linalg.norm(pts - c, axis=1) <= RADIUS
        if int(sel.sum()) < 40:
            print("  TOO_FEW_HITS")
            return None
        newc = pts[sel].mean(axis=0)
        moved = float(np.linalg.norm(newc - c))
        c = newc
        if moved < 5e-4:
            break
    W0 = pts[sel]
    t0 = set(tris[sel].tolist())
    print("  CAST %d pts keep=%d tris=%d miss=%d clipped=%d centre %s"
          % (len(pts), len(W0), len(t0), miss, int((~sel).sum()),
             np.round(c, 4).tolist()))

    sel0 = np.array(sorted(t0), np.int64)
    n = Vector(tri_nw[sel0].mean(axis=0))
    if n.y > 0:
        n = -n
    n = n.normalized()

    def plane_frame(P):
        """An upright frame in the tangent plane at n, plus the paint's own tilt.

        `up` is anatomy, not statistics.  It used to be the *minor* axis of the
        covariance of whatever triangles the colour flood happened to keep, and
        that is what broke the blink: for a round eye the minor axis of a near
        circle is noise, and for the sliver the old CREAM flood actually kept it
        is the sliver's own short direction - which is why the report printed
        own_up_dev 90.1 and 51.9 degrees and a card authored sideways across an
        eye that is 88 mm round.  The head's vertical is world +Z; projecting it
        into the tangent plane gives the direction a lid has to sweep, and the
        elongation of the paint is then a measurement *in* that frame instead of
        the definition of it.
        """
        t1 = Vector((0.0, 0.0, 1.0)) - n * n.z
        if t1.length < 1e-4:
            t1 = Vector((1.0, 0.0, 0.0)) - n * n.x
        u_ = t1.normalized()
        r_ = u_.cross(n).normalized()
        if r_.x * sx < 0:
            r_ = -r_
        a = np.array([tuple(r_), tuple(u_), tuple(n)], np.float64).T
        lp = (P - c) @ a
        val, vec = np.linalg.eigh(np.cov(lp[:, :2].T))
        major = vec[:, int(np.argmax(val))]
        return (r_, u_, a, lp,
                float(np.degrees(math.atan2(major[1], major[0]))),
                float(np.sqrt(max(val[1], 1e-12)) / max(np.sqrt(max(val[0], 1e-12)), 1e-9)))

    right, up, ax0, lp0, pca_tilt_deg, pca_flat = plane_frame(W0)
    print("  PAINT_FRAME right %s up %s pca_tilt=%+.1f deg pca_axes_ratio=%.2f"
          % (np.round(tuple(right), 3).tolist(), np.round(tuple(up), 3).tolist(),
             pca_tilt_deg, pca_flat))
    hw = float(np.percentile(np.abs(lp0[:, 0]), 96))
    hh = float(np.percentile(np.abs(lp0[:, 1]), 96))
    ratio = hw / max(hh, 1e-6)
    print("  EYE_PAINT centre %s right %s up %s W=%.4f H=%.4f ratio=%.2f"
          % (np.round(c, 4).tolist(), np.round(tuple(right), 3).tolist(),
             np.round(tuple(up), 3).tolist(), 2 * hw, 2 * hh, ratio))

    # The iris centroid is not the aperture centroid: the pupil sits toward the
    # snout, so the paint centroid drifts out toward the corner and a canvas
    # centred on it cuts across the iris (visible in <tag>_markers.png).  Anchor
    # the paint on the iris itself and keep the offset alongside it.
    iris = [(y, x) for (y, x) in grow(DARK, cx, cy, 40000, 20)
            if (y - cy) ** 2 + (x - cx) ** 2 <= 400]
    IW = []
    for (y, x) in iris:
        g = ray_uv(int(x), int(y))
        if g is not None and float(np.linalg.norm(g[0] - centre)) <= 0.020:
            IW.append(g[0])
    ci = np.array(IW, np.float64).mean(0) if len(IW) >= 12 else centre.copy()
    off = (c - ci) @ ax0
    print("  IRIS px=%d centre %s almond_offset=(%+.4f,%+.4f) m"
          % (len(iris), np.round(ci, 4).tolist(), off[0], off[1]))

    # The footprint is the aperture *and* its lash line, which a flood in the
    # render cannot always reach: an ellipse in the upright frame, bounded by
    # world distance, facing, atlas locality - and now by the paint itself, so
    # it can never run off onto the neck, the mane or the red scales that ring
    # the eye.  The colour test is the same class the flood used, applied to the
    # atlas texel each triangle actually samples.
    lp_all = (tri_w - c) @ ax0
    # Locality about the *measured eye centre*, with slack: the ellipse below is
    # what actually shapes the footprint.  Bounding it about the pupil pixel
    # inherited that pixel's error into the triangle set.
    m_w = np.linalg.norm(tri_w - c, axis=1) <= 1.35 * RADIUS
    m_f = (tri_nw @ np.array(tuple(n))) >= 0.15
    m_a = np.linalg.norm(tri_apx - pax, axis=1) <= 150.0
    m_e = (lp_all[:, 0] / (1.55 * hw)) ** 2 + (lp_all[:, 1] / (1.55 * hh)) ** 2 <= 1.0
    CC = atlas_px(tri_apx[:, 1], tri_apx[:, 0])
    m_p = atlas_eye_paint(CC)
    geo = m_w & m_f & m_a & m_e
    n_geo = int(geo.sum())
    sel = np.nonzero(geo & m_p)[0]
    graded = True
    # 60 triangles was a sample-size guess taken from the 120 mm teen eye.  The
    # adult's painted aperture is 37 mm across and its whole 1.55x ellipse holds
    # only ~105 triangles, so a correctly graded adult eye lands at 54-59; the
    # old absolute cut downgraded it to raw geometry, and the socket's dark
    # scales then dominated the dark quartile and refused the frame as
    # LID_SIDE_82deg.  Sample size is only a proxy for "the paint class found the
    # eye"; when the paint covers most of the footprint the fraction proves that
    # directly.  A palette that really misses (the old adult brown before the
    # repaint) still collapses to a handful and falls back.
    if len(sel) < 30 or len(sel) < 0.5 * n_geo:
        graded = False
        sel = np.nonzero(geo)[0]
    print("  FOOTPRINT world %d +facing %d +atlas %d +ellipse %d +paint %d"
          " (%.0f%% of the ellipse)%s"
          % (int(m_w.sum()), int((m_w & m_f).sum()),
             int((m_w & m_f & m_a).sum()), n_geo,
             int((geo & m_p).sum()),
             100.0 * int((geo & m_p).sum()) / max(n_geo, 1),
             "" if graded else "  (paint grade dropped, kept geometry)"))
    if len(sel) < 30:
        print("  TOO_FEW_TRIANGLES")
        return None
    H = tri_w[sel]
    C = atlas_px(tri_apx[sel][:, 1], tri_apx[sel][:, 0])
    lp = (H - c) @ ax0
    pw = float(np.percentile(np.abs(lp[:, 0]), 96))
    ph = float(np.percentile(np.abs(lp[:, 1]), 96))
    lpi = (H - ci) @ ax0                              # footprint about the iris
    # The box has to reach the footprint's own rim, not stop at the triangle
    # centroids: the lid card spans the faces' vertices, and on a coarse mesh (the
    # baby's 160 mm eye carries ~20 mm triangles) a centroid box sits 10-15 mm
    # inside the rim and refuses a correct frame.  But taking every corner of a
    # painted triangle overshoots by the same radius - the corner itself can be
    # out on the scales.  So the box is built from the corners whose *own texel*
    # is eye paint, with a centroid fallback for a triangle whose middle samples
    # paint but whose corners do not.  On the teen the old all-corner box reached
    # 161 mm where the paint ends at 89 mm, and the aperture gate refused an
    # aperture the render proves is the eye.
    vv = vert_w[tri_v[sel]]
    foot_radius = float(np.linalg.norm(
        (vv - tri_w[sel][:, None, :]) @ ax0, axis=2).max())
    CCv = atlas_px((1.0 - tri_uv[sel][:, :, 1]) * TH, tri_uv[sel][:, :, 0] * TW)
    vpm = atlas_eye_paint(CCv)
    pts = np.where(vpm.any(axis=1)[:, None, None], vv,
                   tri_w[sel][:, None, :].repeat(3, axis=1))
    lpv = ((pts - ci) @ ax0)[vpm] if vpm.any() else lp
    pbox = [float(lpv[:, 0].min()) - 0.0015, float(lpv[:, 1].min()) - 0.0015,
            float(lpv[:, 0].max()) + 0.0015, float(lpv[:, 1].max()) + 0.0015]
    print("  FOOT_RADIUS %.4f m (%d footprint tris) painted-corner box [%+.4f,"
          " %+.4f, %+.4f, %+.4f] (%d corners)"
          % (foot_radius, len(sel), pbox[0], pbox[1], pbox[2], pbox[3],
             int(vpm.sum())))
    lum = C.mean(1)
    dark = lp[np.argsort(lum)[:max(4, len(lum) // 4)]].mean(0)
    dn = np.linalg.norm(dark[:2])
    up_dev = math.degrees(math.acos(max(-1.0, min(1.0, dark[1] / dn)))) if dn > 1e-6 else 0.0
    bad = []
    if float(up.z) < 0.70:
        bad.append("UP_NOT_VERTICAL(%.2f)" % float(up.z))
    if abs(float(up.y)) > 0.45:
        bad.append("UP_LEANS_FORE_BACK(%.2f)" % float(up.y))
    # The old gate demanded 1.05 <= ratio <= 3.2 because it believed a dragon
    # eye is a horizontal almond.  The atlas says otherwise: the painted teen
    # aperture measures 0.97:1 on the left and 1.04:1 on the right, i.e. round.
    # A ratio near 1 is now the expected answer, so this only refuses a frame
    # that is impossible - taller than wide by more than 2:1, or an 8:1 band -
    # both of which mean the flood grabbed something that is not an eye.
    if not (0.5 <= ratio <= 8.0):
        bad.append("RATIO_%.2f" % ratio)
    if up_dev > 75.0 and dn >= 0.008:
        # Only a pupil that actually sits off-centre is a lid-side signal.  On a
        # round eye the dark quartile averages to the centre, |dark| collapses to
        # a millimetre, and acos of that is pure noise - refusing on it would
        # reject a correct measurement for the wrong reason.
        bad.append("LID_SIDE_%.0fdeg" % up_dev)
    # The paint's major axis is only a check on the frame when the paint actually
    # *has* a major axis.  A near-round aperture (axes ratio under 1.5) has no
    # preferred direction, so its tilt is noise; refusing on it would reject a
    # correct measurement for the wrong reason.  The axis is unoriented, so fold
    # it into 0..90 degrees away from the horizontal before judging it.
    tilt_from_horizontal = abs(pca_tilt_deg) % 180.0
    tilt_from_horizontal = min(tilt_from_horizontal, 180.0 - tilt_from_horizontal)
    if pca_flat >= 1.5 and tilt_from_horizontal > 45.0:
        bad.append("PAINT_TILT_%.0fdeg_x%.2f" % (tilt_from_horizontal, pca_flat))
    if not graded:
        bad.append("PAINT_GRADE_DROPPED")
    print("  EYE centre %s right %s up %s n %s open W=%.4f H=%.4f ratio=%.2f"
          " paint W=%.4f H=%.4f dark=(%.4f,%.4f) up_dev=%.1f deg tilt=%.1f"
          " (raw %+.1f, axes %.2f)%s"
          % (np.round(c, 4).tolist(), np.round(tuple(right), 3).tolist(),
             np.round(tuple(up), 3).tolist(), np.round(tuple(n), 3).tolist(),
             2 * hw, 2 * hh, ratio, 2 * pw, 2 * ph,
             dark[0], dark[1], up_dev, tilt_from_horizontal, pca_tilt_deg, pca_flat,
             ("  BAD " + " ".join(bad)) if bad else "  OK"))
    print("  PAINT_BOX(iris) [%.4f, %.4f, %.4f, %.4f] m  (%.4f x %.4f)"
          % (pbox[0], pbox[1], pbox[2], pbox[3],
             pbox[2] - pbox[0], pbox[3] - pbox[1]))
    return {"side": side, "bone": bone_name,
            "bone_head": tuple(arm.matrix_world @ b.head_local),
            "pupil_pixel": (cx, cy), "pale": pale, "c": ci, "almond_c": c,
            "pupil_world": np.array(tuple(centre), np.float64),
            "n": n, "off": off, "pbox": pbox,
            # World-space *painted* corners of the footprint: the canonical paint
            # box has to be built from them about the *canonical* centre, not
            # by unioning per-side boxes that are each centred on that side's
            # own iris (the baby's two irises sit 28 mm apart in z, which
            # shifted the shared box off the R footprint entirely).
            "foot_w": pts[vpm] if vpm.any() else H,
            "foot_radius": foot_radius,
            "up": up, "right": right, "hw": hw, "hh": hh, "ratio": ratio,
            "pw": pw, "ph": ph, "up_dev": up_dev,
            "pca_tilt": pca_tilt_deg, "pca_flat": pca_flat, "graded": graded,
            "tri": sel, "uv": tri_uv[sel], "col": C, "bad": bad}


found = {}
missing = set()
for attempt in (1, 2):
    for bone_name in ("Lid_L", "Lid_R"):
        side = bone_name[-1]
        if side in found or side in missing:
            continue
        seeds = []
        if attempt == 1:
            bp = bone_pixel(bone_name)
            if bp is not None:
                seeds.append((bp[0], bp[1], int(RES * 0.085), int(RES * 0.062),
                              "BONE"))
            else:
                print("NO_BONE", bone_name)
                missing.add(side)
        # Mirror the *world* pupil of the side already measured and re-project it,
        # rather than flipping the pixel about the image centre: the camera target
        # is the head bbox centre, and the head is not mirror-symmetric, so a
        # pixel flip would inherit that bias.  With the bone seed lifted by
        # RISE (a bone sits under the eye it names) the mirrored seed needs no
        # lift at all - it already is the pupil.
        other = found.get("R" if side == "L" else "L")
        if other is not None:
            pw = Vector(tuple(other["pupil_world"]))
            mp = Vector((-pw.x, pw.y, pw.z))
            nd = world_to_camera_view(scene, cam, mp)
            print("MIRROR %s from %s pupil world %s -> %s"
                  % (bone_name, other["bone"], np.round(tuple(pw), 4).tolist(),
                     np.round(tuple(mp), 4).tolist()))
            seeds.append((nd.x * RES, (1.0 - nd.y) * RES, int(RES * 0.05), 0,
                          "MIRROR_%s" % other["side"]))
        for seed in seeds:
            rec = measure_side(bone_name, seed)
            if rec is not None:
                found[side] = rec
                break

eyes = [found[s] for s in ("L", "R") if s in found]
if len(eyes) != 2:
    print("ONLY_%d_EYES_MEASURED - the report will carry what was found" % len(eyes))

# ------------------------------------------------------------------ canonical
canonical = None
if eyes:
    # Only sides that passed their own gates may contribute to the shared frame.
    # Averaging in a side whose paint is damaged moves the *good* eye: on the
    # teen the right iris centroid came out 34 mm off the mirror of the left one
    # because that eye's paint has a red band across it, and the mean dragged the
    # canonical centre 15 mm outward - a lid sized and placed for a position
    # neither eye occupies.  If both sides fail, keep both and let the reported
    # flags say so; refusing to measure anything is worse than a flagged frame.
    good = [e for e in eyes if not e["bad"]] or eyes
    # Prefer a side that passed its own gates, then one whose footprint really
    # was paint-graded, then the larger sample.  The old tie-break pulled toward
    # whichever eye looked most like a 1.62:1 almond, which for a round eye
    # rewards the *contaminated* measurement - the side where the flood leaked
    # into skin and stretched the frame.
    best = max(good, key=lambda e: (e["graded"], len(e["tri"])))
    bx_ = -1.0 if best["side"] == "L" else 1.0
    n_can = Vector(best["n"])
    if bx_ < 0:
        n_can = Vector((-n_can.x, n_can.y, n_can.z))
    up_can = Vector(best["up"])
    if bx_ < 0:
        up_can = Vector((-up_can.x, up_can.y, up_can.z))
    right_can = Vector(best["right"])
    if bx_ < 0:
        right_can = Vector((-right_can.x, right_can.y, right_can.z))
    if n_can.y > 0:
        n_can = -n_can
    n_can = n_can.normalized()
    up_can = (up_can - up_can.dot(n_can) * n_can).normalized()
    if up_can.z < 0:
        up_can = -up_can
    right_can = up_can.cross(n_can).normalized()
    # The card is sized by the aperture, not by a stylistic almond ratio.  The
    # old rule stretched half_w to half_h * TARGET_RATIO and left half_h alone,
    # so a round eye (measured 0.97:1 left, 1.04:1 right) got a 1.62:1 canvas
    # that was wide enough but far too short - the top and bottom rims stayed
    # visible straight through a closed lid.  Both axes now come from the paint
    # footprint, and each takes the larger of the trustworthy eyes because the
    # lid pass drives both cards from this one canonical frame.
    pw = max(e["pw"] for e in good)
    ph = max(e["ph"] for e in good)
    hw = max(pw, max(e["hw"] for e in good))
    hh = max(ph, max(e["hh"] for e in good))
    cx = float(np.mean([abs(e["c"][0]) for e in good]))
    cy = float(np.mean([e["c"][1] for e in good]))
    cz = float(np.mean([e["c"][2] for e in good]))
    # The shared paint box has to be measured about the *canonical* centre in
    # each side's own outward frame - the same frame the lid pass will project
    # the card's vertices into.  Unioning the per-side boxes as they were came
    # out wrong twice: those boxes are about each side's own iris, and they are
    # built from centroids rather than the painted corners, so the baby's 20 mm
    # triangles put 30 of 198 footprint vertices outside their own box and a
    # correct frame was refused.  `foot_w` now carries the painted corners only.
    pbox = None
    side_box = {}
    # Both boxes come out of one loop in the one frame the aperture render uses.
    # The union stays the *sizing* input and may only be built from sides that
    # passed their own gates.  The per-side box is the coverage reference and has
    # to exist even for a dropped side: the teen's right eye is flagged for its
    # paint's tilt, and comparing its render against the *left* eye's box asked
    # the right eye to reproduce a footprint that was never measured on it - a
    # 9 mm hood at the top and a 16 mm eye corner at the bottom, both real
    # asymmetry.  A gate may only demand that an eye contains its own paint.
    for e in eyes:
        sx = -1.0 if e["side"] == "L" else 1.0
        f_n = Vector((sx * n_can.x, n_can.y, n_can.z))
        f_up = Vector((sx * up_can.x, up_can.y, up_can.z))
        f_up = (f_up - f_up.dot(f_n) * f_n).normalized()
        if f_up.z < 0:
            f_up = -f_up
        f_r = Vector((sx * right_can.x, right_can.y, right_can.z))
        f_r = (f_r - f_r.dot(f_n) * f_n - f_r.dot(f_up) * f_up).normalized()
        c_side = np.array((sx * cx, cy, cz), np.float64)
        lpv = (e["foot_w"] - c_side) @ np.array(
            [tuple(f_r), tuple(f_up)], np.float64).T
        box = [float(lpv[:, 0].min()) - 0.0015,
               float(lpv[:, 1].min()) - 0.0015,
               float(lpv[:, 0].max()) + 0.0015,
               float(lpv[:, 1].max()) + 0.0015]
        side_box[e["side"]] = box
        if e in good:
            pbox = box if pbox is None else [
                min(pbox[0], box[0]), min(pbox[1], box[1]),
                max(pbox[2], box[2]), max(pbox[3], box[3])]
    canonical = {"from": best["side"],
                 "n": [round(float(v), 5) for v in n_can],
                 "up": [round(float(v), 5) for v in up_can],
                 "right": [round(float(v), 5) for v in right_can],
                 "almond_off": [round(float(v), 5) for v in best["off"]],
                 "paint_box": [round(float(v), 5) for v in pbox],
                 "paint_box_sides": {k: [round(float(v), 5) for v in b]
                                     for k, b in side_box.items()},
                 "sides_used": [e["side"] for e in good],
                 "sides_dropped": [e["side"] + ":" + ",".join(e["bad"])
                                   for e in eyes if e["bad"]],
                 "centre_abs_x": round(cx, 5),
                 "centre_y": round(cy, 5),
                 "centre_z": round(cz, 5),
                 "half_w": round(float(hw), 5), "half_h": round(float(hh), 5),
                 "paint_half_w": round(float(pw), 5),
                 "paint_half_h": round(float(ph), 5),
                 "measured_half_w": round(float(best["hw"]), 5),
                 "measured_half_h": round(float(best["hh"]), 5),
                 "measured_ratio": round(float(best["ratio"]), 2),
                 "sizing": "paint footprint (trustworthy sides, larger axis)",
                 "target_ratio": TARGET_RATIO,
                 "paint_tilt_deg": round(float(best["pca_tilt"]), 1),
                 "paint_axes_ratio": round(float(best["pca_flat"]), 3),
                 "paint_graded": bool(best["graded"]),
                 "bad": list(best["bad"])}
    print("CANON from=%s used=%s dropped=%s centre=(+-%.4f,%.4f,%.4f) W=%.4f H=%.4f"
          " ratio=%.2f (measured %.2f) n=%s up=%s right=%s"
          % (canonical["from"], ",".join(canonical["sides_used"]),
             ",".join(canonical["sides_dropped"]) or "none",
             canonical["centre_abs_x"], canonical["centre_y"],
             canonical["centre_z"], 2 * hw, 2 * hh, hw / max(hh, 1e-9),
             canonical["measured_ratio"], canonical["n"], canonical["up"],
             canonical["right"]))

# -------------------------------------------------------------------- report
own_tri = np.empty((F, 3, 2), np.float64)
own_tri[..., 0] = tri_uv[..., 0] * TW
own_tri[..., 1] = (1.0 - tri_uv[..., 1]) * TH
report = []
for e in eyes:
    side = e["side"]
    sx = -1.0 if side == "L" else 1.0
    if canonical:
        # A pure x-mirror of the canonical frame.  Deriving right from up x n
        # instead would hand the left side a right-handed frame and point its
        # major axis *inward*, across the snout - the two eyes are mirrors, and
        # a mirror flips handedness.
        f_n = Vector((sx * canonical["n"][0], canonical["n"][1], canonical["n"][2]))
        f_up = Vector((sx * canonical["up"][0], canonical["up"][1], canonical["up"][2]))
        f_up = (f_up - f_up.dot(f_n) * f_n).normalized()
        if f_up.z < 0:
            f_up = -f_up
        f_right = Vector((sx * canonical["right"][0], canonical["right"][1],
                          canonical["right"][2]))
        f_right = (f_right - f_right.dot(f_n) * f_n - f_right.dot(f_up) * f_up)
        f_right = f_right.normalized()
        c = np.array((sx * canonical["centre_abs_x"], canonical["centre_y"],
                      canonical["centre_z"]), np.float64)
        hw, hh = canonical["half_w"], canonical["half_h"]
        pw, ph = canonical["paint_half_w"], canonical["paint_half_h"]
        # The side's *own* painted corners, in the shared frame.  `paint_box` is
        # the union over trustworthy sides and sizes the card; it must not judge
        # a side whose paint was refused, or the gate demands one eye reproduce
        # the other's footprint.
        pb = canonical["paint_box_sides"][side]
        aoff = canonical["almond_off"]   # local coords: the mirrored frame
                                         # already carries the side flip
    else:
        f_n, f_up, f_right = e["n"], e["up"], e["right"]
        c = np.array(tuple(e["c"]), np.float64)
        hw, hh = e["hw"], e["hh"]
        pw, ph = e["pw"], e["ph"]
        pb = e["pbox"]
        aoff = e["off"]
    # The visible eye, from a render along this side's own normal.  Everything
    # below this point - the card's hull, its window, its livery, and the three
    # gates that judge the blink - is authored from these points, because the
    # atlas footprint above is not the eye: on the baby it is a patchwork band
    # that covers 14 % of the amber a viewer sees.
    ap = aperture_pass(side, c, f_right, f_up, f_n, e["pupil_world"], hw, hh,
                       paint_box=pb)
    ap_w = ap["box"][2] - ap["box"][0]
    ap_h = ap["box"][3] - ap["box"][1]
    ap_area = ap["blob_px"] / (ap["ppm"] ** 2)
    paint_area = math.pi * float(hw) * float(hh)
    print("APERTURE %s rad=%.3f m open=%.1f mm(%d px) blob=%d px = %.1f cm2 "
          "(paint ellipse %.1f cm2) centre=(%+.4f,%+.4f) W=%.4f H=%.4f rays=%d/%d "
          "miss=%d faces=%d box=%s"
          % (side, ap["rad"], ap["open_mm"], ap["open_px"], ap["blob_px"],
             1e4 * ap_area, 1e4 * paint_area, ap["centre_uv"][0],
             ap["centre_uv"][1], ap_w, ap_h, ap["rays"][0], ap["rays"][1],
             ap["miss"], len(ap["faces"]), np.round(ap["box"], 4).tolist()))
    # A visible eye contains the paint that draws *that* eye.  The coverage gate
    # lives in `aperture_pass`, where the render's own masks are in hand: it
    # needs the *amber* pixels inside this side's own box, not the painted
    # corners - see the comment there for why a corner box cannot be the judge
    # (the black-crack class lands on the scales).  What stays here is the
    # independent size check: a visible eye smaller than four fifths of the
    # atlas paint ellipse lost part of the eye, whichever gate let it through.
    if ap_area < 0.8 * paint_area:
        raise SystemExit(
            "APERTURE_SMALLER_THAN_THE_PAINT_%s - the visible non-red component "
            "measures %.1f cm2 against a %.1f cm2 paint ellipse; the aperture "
            "render lost part of the eye" % (side, 1e4 * ap_area,
                                             1e4 * paint_area))
    # centre of the visible almond = iris centre + the measured offset
    ac = c + f_right * aoff[0] + f_up * aoff[1]
    ax = np.array([tuple(f_right), tuple(f_up), tuple(f_n)], np.float64).T
    world = tri_w[e["tri"]]
    lp = (world - c) @ ax
    us = e["uv"][:, :, 0].ravel()
    vs = e["uv"][:, :, 1].ravel()
    lpp = np.repeat(lp, 3, axis=0)

    def fit(lpx, usx, vsx):
        X = np.column_stack([lpx[:, 0], lpx[:, 1], np.ones(len(lpx))])
        px, py = usx * TW, (1.0 - vsx) * TH
        solx = np.linalg.lstsq(X, px, rcond=None)[0]
        soly = np.linalg.lstsq(X, py, rcond=None)[0]
        pred = np.column_stack([X @ solx, X @ soly])
        err = np.linalg.norm(pred - np.column_stack([px, py]), axis=1)
        return solx, soly, err

    X_lp, X_us, X_vs = lpp, us, vs
    solx, soly, err = fit(X_lp, X_us, X_vs)
    for _ in range(3):
        lim = max(np.percentile(err, 90), 3.0 * np.median(err))
        keep = err <= lim
        if keep.all() or keep.sum() < 90:
            break
        X_lp, X_us, X_vs = X_lp[keep], X_us[keep], X_vs[keep]
        solx, soly, err = fit(X_lp, X_us, X_vs)
    n_used = int(len(X_lp) / 3)
    aff = [[round(float(v), 4) for v in solx], [round(float(v), 4) for v in soly]]
    rms = round(float(np.sqrt((err ** 2).mean())), 2)
    mx = round(float(err.max()), 2)
    ppm = [round(float(math.hypot(solx[0], soly[0])), 1),
           round(float(math.hypot(solx[1], soly[1])), 1)]
    print("EYE %s centre %s W=%.4f H=%.4f n=%s up=%s right=%s fit rms=%.2f px"
          " max=%.2f px ppm=%s tris=%d/%d"
          % (side, np.round(c, 4).tolist(), 2 * hw, 2 * hh,
             np.round(tuple(f_n), 3).tolist(), np.round(tuple(f_up), 3).tolist(),
             np.round(tuple(f_right), 3).tolist(), rms, mx, ppm,
             n_used, len(e["tri"])))

    # the paint footprint in atlas space, and who else uses those texels
    corners = np.array([[x, y] for x in (pb[0], pb[2])
                        for y in (pb[1], pb[3])], np.float64)
    A = np.array([[solx[0], solx[1]], [soly[0], soly[1]]], np.float64)
    bvec = np.array([solx[2], soly[2]], np.float64)
    apx = corners @ A.T + bvec
    box = [float(apx[:, 0].min()), float(apx[:, 1].min()),
           float(apx[:, 0].max()), float(apx[:, 1].max())]
    tx0, ty0, tx1, ty1 = box
    ov = ((own_tri[..., 0].max(1) >= tx0) & (own_tri[..., 0].min(1) <= tx1) &
          (own_tri[..., 1].max(1) >= ty0) & (own_tri[..., 1].min(1) <= ty1))
    overlap = np.nonzero(ov)[0]
    d = np.linalg.norm(tri_w[overlap] - c, axis=1)
    foreign = overlap[d > 0.10]
    print("  ATLAS_BOX %s covers %d tris, %d of them foreign (>0.10 m away)"
          % (np.round(box, 1).tolist(), len(overlap), len(foreign)))
    local = np.intersect1d(overlap, e["tri"])
    report.append({
        "side": side, "bone": e["bone"],
        "centre_world": [round(float(v), 5) for v in c],
        "n": [round(float(v), 5) for v in f_n],
        "up": [round(float(v), 5) for v in f_up],
        "right": [round(float(v), 5) for v in f_right],
        "half_w": round(float(hw), 5), "half_h": round(float(hh), 5),
        "paint_box_eye": [round(float(v), 5) for v in pb],
        # The visible eye, measured in a render along its own normal.  This is
        # what the card is authored from and what the blink gates grade.
        "aperture_box_eye": [round(float(v), 5) for v in ap["box"]],
        "aperture_centre_eye": [round(float(v), 5) for v in ap["centre_uv"]],
        "aperture_hull_eye": ap["hull"],
        "aperture_points": [[round(float(v), 5) for v in q] for q in ap["points"]],
        "aperture_faces": ap["faces"],
        "aperture_render": ap["png"],
        "aperture_blob_px": ap["blob_px"],
        "aperture_open_mm": ap["open_mm"],
        "aperture_rays": ap["rays"],
        "almond_centre": [round(float(v), 5) for v in ac],
        "paint_half_w": round(float(pw), 5), "paint_half_h": round(float(ph), 5),
        "own_half_w": round(float(e["hw"]), 5), "own_half_h": round(float(e["hh"]), 5),
        "own_ratio": round(float(e["ratio"]), 3),
        "own_up_dev_deg": round(float(e["up_dev"]), 1),
        # The eye is measured in an anatomical frame now; the paint's own
        # principal-axis tilt is kept as a cross-check on that frame, and
        # `frame_bad` is what the side reported before canonicalisation.  The
        # lid pass refuses a card whose side carried any flag.
        "own_pca_tilt_deg": round(float(e["pca_tilt"]), 1),
        "own_pca_axes_ratio": round(float(e["pca_flat"]), 3),
        "paint_graded": bool(e["graded"]),
        "frame_bad": list(e["bad"]),
        "relief": round(float(np.percentile(lp[:, 2], 98)), 5),
        "pupil_pixel": [int(e["pupil_pixel"][0]), int(e["pupil_pixel"][1])],
        "pupil_world": [round(float(v), 5) for v in e["pupil_world"]],
        "pale_ring": round(float(e["pale"]), 4),
        "bone_head": [round(float(v), 5) for v in e["bone_head"]],
        "lid_card": card_info.get(e["bone"]),
        "lid_card_centre_to_eye": (
            round(float(np.linalg.norm(np.array(card_info[e["bone"]]["centre"],
                                                 np.float64) - c)), 5)
            if e["bone"] in card_info else None),
        "distance_bone_to_eye": round(float(np.linalg.norm(
            c - np.array(tuple(e["bone_head"]), np.float64))), 5),
        "affine_eye_to_atlas": aff,
        "px_per_atlas_metre": ppm,
        "fit_rms_px": rms, "fit_max_px": mx,
        "n_eye_triangles": int(len(e["tri"])),
        # The body faces the painted eye actually lives on, as mesh polygon
        # indices.  An eyelid card has to be authored against that surface - the
        # atlas rect it was built from before is a box on a single continuous UV
        # sheet, and the colour flood that tried to bound it swallowed the whole
        # red body.  The triangles are the proven footprint (world + facing +
        # atlas + ellipse), so their polygons are the eye.
        "face_indices": sorted({int(tri_p[i]) for i in e["tri"]}),
        "atlas_box": [round(v, 1) for v in box],
        "foreign_triangles": [[[round(float(p[0]), 1), round(float(p[1]), 1)]
                               for p in own_tri[i]] for i in foreign[:400]],
        "local_triangles": [[[round(float(p[0]), 1), round(float(p[1]), 1)]
                             for p in own_tri[i]] for i in local[:4000]],
        "atlas_rgb_mean": [round(float(v), 3) for v in e["col"].mean(0)],
    })

# ---------------------------------------------------------------- marker shot
if report:
    rgba = shot_px.copy()
    rgba[..., 3] = 1.0

    def plot(px, py, colour):
        x, y = int(round(px)), int(round(py))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if abs(dx) + abs(dy) <= 1:
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < SW and 0 <= yy < SH:
                        rgba[yy, xx] = (colour[0], colour[1], colour[2], 1.0)

    def vis(p):
        """True when the body surface the camera sees at p is p itself."""
        o = cam.matrix_world.translation
        d = Vector(tuple(p)) - o
        res, loc, nrm, idx, obj, mat = scene.ray_cast(dg, o, d.normalized())
        return bool(res) and obj == body and (Vector(tuple(loc)) -
                                             Vector(tuple(p))).length < 0.006

    def cross(p, colour):
        """Project a world point straight at the camera.

        No normal offset here: 20 mm along the eye normal is 23 render px of
        lateral shift, which made the centre marker look like it missed the
        pupil when it did not.
        """
        nd = world_to_camera_view(scene, cam, Vector(tuple(p)))
        for d in range(-9, 10):
            plot(nd.x * RES + d, (1.0 - nd.y) * RES, colour)
            plot(nd.x * RES, (1.0 - nd.y) * RES + d, colour)

    for rec in report:
        c = np.array(rec["centre_world"], np.float64)
        rr = np.array(rec["right"], np.float64)
        uu = np.array(rec["up"], np.float64)
        hw, hh = rec["half_w"], rec["half_h"]
        pb = rec["paint_box_eye"]
        ac = np.array(rec["almond_centre"], np.float64)
        for k in range(128):
            a = 2 * math.pi * k / 128.0
            p = ac + rr * (hw * math.cos(a)) + uu * (hh * math.sin(a))
            if vis(p):
                nd = world_to_camera_view(scene, cam, Vector(tuple(p)))
                plot(nd.x * RES, (1.0 - nd.y) * RES, (1.0, 0.0, 1.0))
        for t in np.linspace(0.0, 1.0, 96):
            for (x0, y0, x1, y1) in ((pb[0], pb[1], pb[2], pb[1]),
                                     (pb[2], pb[1], pb[2], pb[3]),
                                     (pb[2], pb[3], pb[0], pb[3]),
                                     (pb[0], pb[3], pb[0], pb[1])):
                p = c + rr * (x0 + (x1 - x0) * t) + uu * (y0 + (y1 - y0) * t)
                if vis(p):
                    nd2 = world_to_camera_view(scene, cam, Vector(tuple(p)))
                    plot(nd2.x * RES, (1.0 - nd2.y) * RES, (0.6, 0.0, 1.0))
        cross(np.array(rec["pupil_world"], np.float64), (0.0, 1.0, 1.0))
        cross(c, (0.0, 1.0, 0.0))
    mimg = bpy.data.images.new("%s_markers" % tag, SW, SH, alpha=True)
    mimg.colorspace_settings.name = "Non-Color"
    # shot_px is top-down; a Blender pixel array is bottom-up, so flip back
    mimg.pixels.foreach_set(rgba[::-1].reshape(-1).astype(np.float32))
    mimg.filepath_raw = os.path.join(outdir, "%s_markers.png" % tag)
    mimg.file_format = "PNG"
    mimg.save()
    bpy.data.images.remove(mimg)
    print("WROTE %s_markers.png" % tag)

out = {"tag": tag, "glb": os.path.basename(glb), "atlas": [TW, TH], "res": RES,
       "body_mesh": body.name, "n_body_faces": len(body.data.polygons),
       "px_per_render_metre": round(px_per_m, 1),
       "head": {"min": [round(float(v), 4) for v in lo],
                "max": [round(float(v), 4) for v in hi]},
       "canonical": canonical, "eyes": report}
with open(out_json, "w") as fh:
    json.dump(out, fh, indent=1)
print("WROTE %s eyes=%d" % (out_json, len(report)))
print("DONE")
