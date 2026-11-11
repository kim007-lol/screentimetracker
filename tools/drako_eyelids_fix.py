"""Rebuild a Drako eyelid card so the blink actually covers the painted eye.

Why this exists
---------------
`tools/drako_eyelids.py` authored one card per eye from a measured eye frame and
compressed it to 1/REST_DIV along the lid bone, so the clip's `scale.y = 30`
stretches it down over the eye.  On the adult that card never appears: it is
0.043 m wide over a painted eye that is 0.064 m along its own axis, its bone axis
tilts backward (+0.055 / +0.123 world Y per unit of sweep, where the working baby
bone tilts forward at -0.029), and its fixed 0.008 dome is far less than the way
the snout falls away below the eye.  `tools/qa_rig/tmp_lid_pose.py` measured the
stretched card landing under the eyeball (blink-frame z 0.202-0.250 against paint
at 0.224-0.292) - which is why the adult never appears to blink.  The frame it
was built from came from `tools/qa_pet/bind_dewasa_eyes.json`, whose eye centre
sits 0.28 m behind the real one.

What this does
--------------
It re-authors the card from the painted eye itself.  Two ways of finding that
eye exist, and only one of them is trustworthy:

* the eye_measure report the tool is handed carries the mesh faces
  `drako_eye_measure.py` proved belong to the eye - the set selected by world
  position *and* facing *and* atlas position *and* the almond ellipse - and the
  canonical frame it measured from them (normal, tilt, width, height, relief).
  This is the mode the adult is authored in.
* a stage/rect file has no faces to name, so the region is grown by face
  adjacency from a seed face until the neighbour stops carrying iris/sclera
  colour.  That colour flood is a trap: on the adult the mask matched 61180 of
  161608 faces - the whole red body - so the "island" was 2.4x the eye and the
  card was built on a meaningless frame.  The mode prints itself, so a rect file
  sneaking into a card run is visible in the log.

The card is a smooth plate standing off the eye plane by more than the eye's own
relief - not a shrink-wrap of the head, which is what buried the previous adult
card.  It is then checked twice: once by the algebra (does the plate span and
stand in front of the painted almond) and once for real, by posing the lid bones
to the blink peak the curves actually use and ray-casting the eye surface along
its own normal to see whether the *deformed* card hides it.  The posed check is
the one that matters - a bone whose roll maps scale-Y onto the wrong axis passes
the algebra and blinks into the air.  `LID_FIX` prints, per eye, how much of the
painted eye the closed plate covers, how much of it the plate stands in front of,
and how much of it the posed blink actually hides, so an invisible blink fails
here instead of in a render.

The lid bones keep their names, their parent and the same 1/REST_DIV
compression, so all 25 clips and their existing blink keys are reused as they
are.  `--sync-lids` additionally copies the left lid's blink keys onto the right
lid, in every clip, so both eyes close together.  Nothing else is touched.

Run:
  blender -b --factory-startup --python-exit-code 1 --python \
      tools/drako_eyelids_fix.py -- <src.glb> <eyes.json> <out.glb> \
      --stage dewasa [--sync-lids] [--report fix.json]
"""
import argparse
import json
import os
import sys

import bpy
from mathutils import Matrix, Vector

import numpy as np


def _tools_dir():
    """This file's own directory, however Blender was pointed at it."""
    for cand in (os.environ.get("QA_TOOLS_DIR"),
                 os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else None,
                 os.path.abspath("tools")):
        if cand and os.path.isfile(os.path.join(cand, "lid_curves.py")):
            return os.path.abspath(cand)
    raise SystemExit("CANNOT_FIND lid_curves.py - run this script from the project root")


sys.path.insert(0, _tools_dir())
import glb_export                                                  # noqa: E402
import lid_curves                                               # noqa: E402

# ------------------------------------------------------------------- arguments
argv = sys.argv
tail = argv[argv.index("--") + 1:] if "--" in argv else []
if tail and tail[0] == "--":
    tail = tail[1:]
if len(tail) < 3:
    raise SystemExit("usage: drako_eyelids_fix.py -- src.glb eyes.json out.glb [opts]")

ap = argparse.ArgumentParser(prog="drako_eyelids_fix")
ap.add_argument("src")
ap.add_argument("eyes",
                help="eye description: either a drako_eye_measure.py report (it "
                     "carries face_indices, and the card is authored from those "
                     "faces) or a stage/rect list for the colour-flood island")
ap.add_argument("out")
ap.add_argument("--stage", default=None)
ap.add_argument("--sync-lids", dest="sync_lids", action="store_true",
                help="copy Lid_L's blink keys onto Lid_R in every clip, so the two "
                     "eyes close together (the shipped curves lag 0.7 frames)")
ap.add_argument("--cover-margin", dest="cover_margin", type=float, default=1.02,
                help="how far past the painted eye's own box the closed card has to"
                     " reach; the card is sized off the paint, not off the almond"
                     " ellipse the detector selected with")
ap.add_argument("--min-cover", dest="min_cover", type=float, default=99.0,
                help="fail unless this percent of the painted eye is spanned by the card")
ap.add_argument("--min-fronted", dest="min_fronted", type=float, default=99.0,
                help="fail unless the card stands in front of this percent of it")
ap.add_argument("--min-hidden", dest="min_hidden", type=float, default=99.0,
                help="fail unless the posed blink hides this percent of it")
ap.add_argument("--max-rest-hidden", dest="max_rest_hidden", type=float, default=2.0,
                help="fail if the blink peak hides it but the rest pose covers more "
                     "than this percent - the pet would ship with half-shut eyes")
ap.add_argument("--max-rig-dev-mm", dest="max_rig_dev_mm", type=float, default=1.5,
                help="how far the posed card may sit from the plate the coverage was "
                     "computed on, in millimetres")
ap.add_argument("--probe-margin", dest="probe_margin", type=float, default=0.02,
                help="safety distance the blink ray starts in front of the plate at "
                     "each eye vertex, in metres")
ap.add_argument("--allow-invisible", dest="allow_invisible", action="store_true",
                help="export even when the checks below fail (experiments only)")
ap.add_argument("--atlas", type=int, default=2048)
ap.add_argument("--atlas-image", dest="atlas_image", default=None,
                help="colour atlas (Image_0) - required to bound the island by the "
                     "painted eye instead of by the requested rect")
ap.add_argument("--rest-div", dest="rest_div", type=float, default=30.0,
                help="must match REST_DIV of the blink curves (scale.y peak)")
ap.add_argument("--clear", type=float, default=0.0035,
                help="how far proud of the head surface the card rides, in metres")
ap.add_argument("--max-clear", dest="max_clear", type=float, default=0.012,
                help="the most extra ride, on top of --clear, this lid is allowed to"
                     " float to out-rank the skin the smooth fit refused to copy, in"
                     " metres; the need is measured, and exceeding this budget is a"
                     " refusal rather than a silent clip - 0 pins the lid to --clear"
                     " and lets a scute bury it")
ap.add_argument("--offset", type=float, default=0.0,
                help="lid plate stand-off along the eye normal; 0 = auto, i.e. the "
                     "measured relief of the painted eye plus --clear")
ap.add_argument("--patch-degree", dest="patch_degree", type=int, default=2,
                help="degree of the polynomial the plate conforms to over the"
                     " card: 2 is the original six-term patch; 3 follows the"
                     " socket with a lower stand-off and is the honest way to"
                     " lower --max-clear pressure, since raising --clear instead"
                     " parks the whole lid out in front of the eyeball")
ap.add_argument("--rest-sink", dest="rest_sink", type=float, default=0.004,
                help="how far the card's skirt - the canvas outside the measured eye -"
                     " sinks into the skin, in metres. The bind pose is the card"
                     " flattened along the bone axis, and flattening leaves depth"
                     " normal to the face untouched, so every millimetre the skirt"
                     " rides proud of the brow is a shelf there at rest; that shelf"
                     " is the blade that read as a gash above the eye. Sinking the"
                     " skirt is the closed lid ending at a lid margin")
ap.add_argument("--taper", type=float, default=0.006,
                help="width of the smooth step from the eye footprint (proud, w=1)"
                     " to the sunk skirt (w=0), in metres")
ap.add_argument("--rest-proud", dest="rest_proud", type=float, default=0.002,
                help="how far a vertex of the bind pose may stand in front of the"
                     " skin, in metres; further than this is a visible band or blade"
                     " at rest and is refused")
ap.add_argument("--dome", type=float, default=0.004,
                help="how far the plate corners recede from that stand-off, metres")
ap.add_argument("--curve", type=float, default=0.03,
                help="how far the plate's lower edge bows down at its middle, "
                     "as a fraction of eye height")

ap.add_argument("--rows", type=int, default=14)
ap.add_argument("--cols", type=int, default=24)
ap.add_argument("--span-top", dest="span_top", type=float, default=1.12,
                help="the card's upper arm, as a multiplier on the measured upper"
                     " arm of the painted eye (its highest vertex or paint-box edge,"
                     " whichever reaches further) after --cover-margin. It used to"
                     " be a fraction of a nominal eye height, which over- and"
                     " under-reached by tens of millimetres depending on the stage")
ap.add_argument("--span-bottom", dest="span_bottom", type=float, default=1.05,
                help="the card's lower arm, as a multiplier on the measured lower"
                     " arm of the painted eye (see --span-top). Above ~1.2 the lid"
                     " hangs below the eye over the cheek and the conform has to"
                     " ride skull the eye is not on")
ap.add_argument("--wide", type=float, default=1.06,
                help="both lateral arms of the card, as a multiplier on the measured"
                     " lateral arms of the painted eye (see --span-top); the card is"
                     " still asymmetric because the arms are measured per side")
ap.add_argument("--tall", type=float, default=1.0, help="card height / eye height")
ap.add_argument("--lash", type=float, default=0.10,
                help="lash band depth below the card, as a fraction of eye height")
ap.add_argument("--grow", type=float, default=8.0,
                help="UV growth margin outside the eye rect, in atlas pixels")
ap.add_argument("--min-face-uv", dest="min_face_uv", type=float, default=1.0,
                help="reject a rect whose connected island has fewer faces than this")
ap.add_argument("--no-mirror", dest="no_mirror", action="store_true",
                help="measure each eye frame separately instead of mirroring one")
ap.add_argument("--report", default=None)
a = ap.parse_args(tail)

src, out = os.path.abspath(a.src), os.path.abspath(a.out)
stage = a.stage or os.path.basename(src).replace("drako_", "").replace(".glb", "")
spec = json.load(open(os.path.abspath(a.eyes), encoding="utf-8"))
rows_spec = spec if isinstance(spec, list) else (spec.get("eyes") or [spec])
# The description says how the eye was found.  An eye_measure report carries the
# mesh faces the eye is made of; a refit file carries an atlas rect and nothing
# else, so the region has to be grown out of it by colour.
mode = "measure" if rows_spec and all(r.get("face_indices") for r in rows_spec) else "island"
rects = None
if mode == "measure":
    if spec.get("tag") and spec["tag"] != stage:
        raise SystemExit("MEASURE_REPORT_TAG %s != stage %s - the card would be built "
                         "on another stage's eye" % (spec["tag"], stage))
    print("MODE measure - %s (%s, %d eye records, glb=%s, %s body faces)"
          % (os.path.basename(a.eyes), spec.get("tag"), len(rows_spec),
             spec.get("glb"), spec.get("n_body_faces")))
else:
    entry = next((it for it in rows_spec if it.get("stage", stage) == stage), None)
    if entry is None:
        raise SystemExit(f"NO_STAGE {stage} in {a.eyes}")
    rects = entry.get("rects")
    if not rects:
        raise SystemExit("NO_RECTS in %s and no face_indices either - this file describes "
                         "neither the eye nor where it is" % a.eyes)
    if len(rects) != 2:
        raise SystemExit("need exactly 2 eye rects, got %d" % len(rects))
    print("MODE island - %s rects=%s (the colour flood bounds the region; on the adult "
          "it matched 61180 of 161608 faces)" % (stage, rects))

REST_DIV = a.rest_div
# How deep the bind speck must sit below the local skin before it is hidden from
# more than one direction.  The rest gate casts along the eye's own normal, but
# the face has volume: a speck 2.5 mm under the *lower rim* still peeks out when
# the viewer looks from the front, and it renders as a dark red hook on the
# cheek.  Sinking it this much deeper costs nothing at the peak - a 30x uniform
# bone scale restores the authored disc exactly wherever the head sits.
REST_HIDE_MARGIN = 0.006

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
glb_export.import_glb(src)          # 30 fps grid before any key time is read

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
lids_old = bpy.data.objects.get("DrakoEyelids")
if lids_old is None:
    raise SystemExit("NO_EYELIDS mesh - run drako_eyelids.py first")
for bn in ("Lid_L", "Lid_R"):
    if bn not in arm.data.bones:
        raise SystemExit("NO_BONE " + bn)

body = None
for o in bpy.data.objects:
    if o.type == "MESH" and o != lids_old and any(
            m.type == "ARMATURE" and m.object == arm for m in o.modifiers):
        body = o
        break
if body is None:
    raise SystemExit("NO_BODY")

# Bind pose: the cards and the eye islands are authored against the bind surface.
for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
bpy.context.view_layer.update()

# Drop the armature modifiers: Mesh.vertices are bind positions while the
# importer leaves the armature posed at frame 1, so any UV / ray-cast work has
# to ignore the pose or every measurement is taken on a moved surface.
for ob in (body, lids_old):
    for name in [m.name for m in ob.modifiers if m.type == "ARMATURE"]:
        ob.modifiers.remove(ob.modifiers[name])
bpy.context.view_layer.update()

arm_mw = arm.matrix_world.copy()
arm_inv = arm_mw.inverted()
body_mw = body.matrix_world.copy()
body_nrm = body_mw.to_3x3().inverted().transposed()


def to_arm(p):
    return arm_inv @ Vector(p)


# ------------------------------------------------------- painted eye islands
#
# Everything below is measured in one basis - bind world - because the card, the
# bone and the eyeball have to be compared in it.  The older scripts read the eye
# from a per-vertex UV lookup and a bounding rect; that basis is wrong twice over:
# a seam vertex carries the UV of whichever face claimed it first, and an adult
# rect also catches a tail of neck texels, so the "eye island" it measured was a
# 0.7 m shell reaching the chest.  Here the region is a *connected* set of faces
# grown from the face whose UV centroid sits on the proven painted centre, kept
# only while the neighbour still carries eye paint.
uvl = body.data.uv_layers.active
if not uvl:
    raise SystemExit("BODY_HAS_NO_UV")

nface = len(body.data.polygons)
fuv = np.zeros((nface, 2), np.float64)                  # UV centroid per face
for poly in body.data.polygons:
    su = sv = 0.0
    for li in poly.loop_indices:
        su += uvl.data[li].uv[0]
        sv += uvl.data[li].uv[1]
    k = float(len(poly.loop_indices))
    fuv[poly.index] = (su / k, sv / k)

raw = np.empty(len(body.data.vertices) * 3, np.float32)
body.data.vertices.foreach_get("co", raw)
pos = np.array([tuple(body_mw @ Vector(c)) for c in raw.reshape(-1, 3).astype(np.float64)],
               np.float64)
fpx = fuv[:, 0] * a.atlas                    # face UV centroid, atlas pixel space
fpy = (1.0 - fuv[:, 1]) * a.atlas

# ------------------------------------------------- painted-eye colour lookup
# The rect only says roughly where an eye is, and the body is one continuous UV
# sheet, so a box-bounded "island" is just the box: it measured a 60 px square of
# scales around a 30 px almond and built a lid twice the size of the eye.
# Sampling the colour atlas at every face centre makes the region stop where the
# paint stops, so the card covers the eye that is actually drawn.
eye_face = None
if mode == "measure":
    print("ATLAS_MASK off - the report names the eye faces directly")
elif a.atlas_image:
    path = os.path.abspath(a.atlas_image)
    if not os.path.exists(path):
        raise SystemExit("NO_ATLAS_IMAGE " + path)
    img = bpy.data.images.load(path)
    # Read the stored texels, not Blender's linearised copy: Image.pixels hands
    # back scene-linear floats for an sRGB image, which halves every threshold
    # and left one face of the almond matching instead of sixty.
    img.colorspace_settings.name = "Non-Color"
    W, H = img.size
    buf = np.empty(W * H * 4, np.float32)
    img.pixels.foreach_get(buf)
    sheet = np.ascontiguousarray(buf.reshape(H, W, 4)[::-1])
    bpy.data.images.remove(img)
    fx = np.clip((fuv[:, 0] * W).astype(np.int64), 0, W - 1)
    fy = np.clip(((1.0 - fuv[:, 1]) * H).astype(np.int64), 0, H - 1)
    # `Image.pixels` puts row 0 at the BOTTOM of the image, while (1 - v) is a
    # TOP-origin row - so the buffer is flipped above rather than the index
    # changed, and every other atlas coordinate in this pipeline stays in the
    # one convention the runtime uses.  drako_eye_measure.py carried the same
    # inversion and graded the mirrored texels for two rounds; the probe is
    # tools/qa_rig/tmp_sheet_row_probe.py and the gate is ROW_ORDER in the
    # measure pass.
    rgb = sheet[fy, fx, :3].astype(np.float64)
    hi, lo = rgb.max(axis=1), rgb.min(axis=1)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    ivory = (hi - lo < 0.18) & (hi > 0.50)                 # sclera wedge
    gold = (r > 0.50) & (g > 0.26) & (r - b > 0.28) & (g - b > 0.08)   # iris rings
    eye_face = ivory | gold
    print("ATLAS_MASK %s %dx%d eye_faces=%d of %d"
          % (os.path.basename(path), W, H, int(eye_face.sum()), nface))
else:
    print("ATLAS_MASK off - the island is bounded by the rect only")

edge_faces = {}                                         # (v0,v1) -> faces
face_edges = []
if mode == "island":
    for poly in body.data.polygons:
        vs = poly.vertices
        e = []
        for k in range(len(vs)):
            u, w = vs[k], vs[(k + 1) % len(vs)]
            key = (u, w) if u < w else (w, u)
            e.append(key)
            edge_faces.setdefault(key, []).append(poly.index)
        face_edges.append(e)

anchors = {s: np.array(tuple(arm_mw @ arm.data.bones["Lid_" + s].head_local), np.float64)
           for s in ("L", "R")}


def island(rect):
    """(face indices, vertex indices) of one painted eye."""
    x0, y0, x1, y1 = rect[:4]
    cx, cy = (float(rect[4]), float(rect[5])) if len(rect) >= 6 else ((x0 + x1) / 2.0,
                                                                      (y0 + y1) / 2.0)
    u_lo, u_hi = (x0 - a.grow) / a.atlas, (x1 + 1 + a.grow) / a.atlas
    v_hi, v_lo = 1.0 - (y0 - a.grow) / a.atlas, 1.0 - (y1 + 1 + a.grow) / a.atlas
    inside = ((fuv[:, 0] >= u_lo) & (fuv[:, 0] <= u_hi)
              & (fuv[:, 1] <= v_hi) & (fuv[:, 1] >= v_lo))
    allowed = inside if eye_face is None else (inside & eye_face)
    dist = np.hypot(fpx - cx, fpy - cy)
    dist[~allowed] = np.inf
    seed = int(np.argmin(dist))
    if not np.isfinite(dist[seed]):
        raise SystemExit("NO_PAINTED_FACE_IN rect=%s centre=%s (colour mask found nothing)"
                         % (rect[:4], (cx, cy)))
    seen, stack, faces = {seed}, [seed], []
    while stack:
        f = stack.pop()
        faces.append(f)
        for key in face_edges[f]:
            for g in edge_faces[key]:
                if g not in seen and allowed[g]:
                    seen.add(g)
                    stack.append(g)
    verts = sorted({v for f in faces for v in body.data.polygons[f].vertices})
    return faces, verts


def measure(rect):
    """Tangent frame of one painted eye, straight from its own skin surface."""
    x0, y0, x1, y1 = rect[:4]
    faces, verts = island(rect)
    if len(faces) < a.min_face_uv or len(verts) < 8:
        raise SystemExit("ISLAND_TOO_SMALL rect=%s faces=%d verts=%d"
                         % (rect[:4], len(faces), len(verts)))
    p = pos[verts]
    c = p.mean(axis=0)

    # Outward direction = area-weighted normal of the island, not the smallest
    # PCA axis: a slanted, curved almond tips that axis tens of degrees off the
    # skin, and a lid authored on it sweeps into the head instead of over it.
    acc = np.zeros(3)
    for f in faces:
        poly = body.data.polygons[f]
        acc += poly.area * np.array(tuple(body_nrm @ Vector(poly.normal)))
    n = Vector(acc)
    if n.length < 1e-9:
        raise SystemExit("DEGENERATE_ISLAND_NORMAL " + str(rect[:4]))
    n = n.normalized()
    if n.y > 0.0:                       # the face looks at -Y
        n = -n

    # The almond's own tilt comes from PCA *inside* that tangent plane.
    t1 = Vector((0.0, 0.0, 1.0)) - n * n.z
    if t1.length < 1e-4:
        t1 = Vector((1.0, 0.0, 0.0)) - n * n.x
    t1 = t1.normalized()
    t2 = n.cross(t1).normalized()
    basis = np.array([tuple(t1), tuple(t2)], np.float64).T      # 3x2
    q = (p - c) @ basis
    val, vec = np.linalg.eigh(np.cov(q.T))
    a_major, a_minor = basis @ vec[:, int(np.argmax(val))], basis @ vec[:, int(np.argmin(val))]
    up = Vector(a_minor)
    if up.z < 0.0:
        up = -up
    up = (up - up.dot(n) * n).normalized()
    right = up.cross(n).normalized()
    up = n.cross(right).normalized()    # keep the frame exactly orthonormal

    lp = (p - c) @ np.array([tuple(right), tuple(up), tuple(n)], np.float64).T
    upper, lower = lp[:, 1] > 0.0, lp[:, 1] < 0.0
    recede = 0.0
    if upper.any() and lower.any():
        # positive = the brow sits further out than the cheek, i.e. the skin
        # falls away going down; the lid sweep has to lean forward by that much
        # or it buries itself in the head.
        recede = float(lp[upper][:, 2].mean() - lp[lower][:, 2].mean())
    return {"rect": list(rect[:6]), "faces": len(faces), "verts": len(verts),
            "centre": c, "n": n, "up": up, "right": right, "points": p, "lp": lp,
            "half_w": float(np.percentile(np.abs(lp[:, 0]), 97)),
            "half_h": float(np.percentile(np.abs(lp[:, 1]), 97)),
            # The colour flood has no separate almond, so the island *is* the paint:
            # the same four numbers the card is sized from, and the same frame
            # `mirror_frame` canonicalises.
            "paint_centre": c,
            "paint_half_w": float(np.percentile(np.abs(lp[:, 0]), 97)),
            "paint_half_h": float(np.percentile(np.abs(lp[:, 1]), 97)),
            "paint_box": [float(lp[:, 0].min()), float(lp[:, 1].min()),
                          float(lp[:, 0].max()), float(lp[:, 1].max())],
            "full_w": float(np.abs(lp[:, 0]).max()),
            "full_h": float(np.abs(lp[:, 1]).max()),
            "depth": [float(lp[:, 2].min()), float(lp[:, 2].max())],
            # Frontmost paint on the eye, measured along its own normal: the lid
            # has to stand off the eye plane by at least this or it intersects the
            # eyeball it is supposed to hide.
            "relief": float(np.percentile(lp[:, 2], 98)),
            "recede": recede,
            # Atlas box the island actually reached, in pixels, and whether it
            # is pressed against the requested rect - a clipped island measures
            # a truncated almond and gives a lid that is short on one side.
            "uv_box": [round(float(np.min(fpx[faces])), 1), round(float(np.min(fpy[faces])), 1),
                       round(float(np.max(fpx[faces])), 1), round(float(np.max(fpy[faces])), 1)],
            "clipped": bool(np.min(fpx[faces]) <= x0 + 0.5 or np.max(fpx[faces]) >= x1 - 0.5
                            or np.min(fpy[faces]) <= y0 + 0.5 or np.max(fpy[faces]) >= y1 - 0.5),
            "sigma": [round(float(v), 6) for v in np.sort(val)[::-1]]}


def eyes_from_measure(path):
    """The eye exactly as drako_eye_measure.py proved it: its faces and its frame.

    The colour flood above used to stand in for this and matched 61180 of 161608
    faces on the adult - the whole red body, because the body is one continuous UV
    sheet with no gap between an eye island and the scales around it.  That gave a
    frame 2.4x the eye, up-deviations of 71.5 and 0.0 degrees against a measured
    41.8 and 25.8, and a card that missed the eye it was supposed to hide.

    The report instead carries the mesh faces chosen by world position *and*
    facing *and* atlas position *and* the almond ellipse together, plus the
    canonical frame already mirrored onto both sides, so the card is built on the
    eye the app actually renders.
    """
    rep = json.load(open(os.path.abspath(path), encoding="utf-8"))
    recs = {r.get("side"): r for r in rep.get("eyes") or () if r.get("side") in ("L", "R")}
    if sorted(recs) != ["L", "R"]:
        raise SystemExit("MEASURE_REPORT_NEEDS_BOTH_EYES %s in %s"
                         % (sorted(recs), os.path.basename(path)))
    if rep.get("body_mesh") and rep["body_mesh"] != body.name:
        raise SystemExit("MEASURE_REPORT_MESH %s != %s" % (rep["body_mesh"], body.name))
    if rep.get("n_body_faces") and int(rep["n_body_faces"]) != nface:
        raise SystemExit("MEASURE_REPORT_FACES %s != %d - this report was measured on a "
                         "different mesh, so its face indices mean nothing here"
                         % (rep["n_body_faces"], nface))
    if rep.get("glb") and rep["glb"] != os.path.basename(src):
        print("MEASURE_REPORT_SRC %s, authoring %s - the face indices carry over only "
              "because the repaint changed texels and not geometry"
              % (rep["glb"], os.path.basename(src)))
    # A card is only as good as the frame it is authored from, and until now the
    # lid pass trusted whatever the measure tool handed it.  The teen's first
    # repaired report proved the cost of that: the measure tool itself printed
    # UP_NOT_VERTICAL / RATIO_0.97 for the frame it was reporting, the canonical
    # block picked the *least bad* side anyway, and the lid pass obediently
    # authored a card across a round eye - every internal gate passed and the
    # blink still hid nothing.  The frame's own verdict is now part of the
    # contract.
    can = rep.get("canonical") or {}
    if can.get("bad"):
        raise SystemExit("MEASURE_CANONICAL_BAD %s - the frame this card would be "
                         "authored from failed drako_eye_measure.py's own gates. "
                         "Repair the measurement (or the paint behind it); do not "
                         "author a lid on a refused frame." % ",".join(can["bad"]))
    if "sides_used" in can and not can["sides_used"]:
        raise SystemExit("MEASURE_CANONICAL_HAS_NO_SIDES - the measure tool kept no "
                         "trustworthy eye, so there is nothing to author from")
    if can.get("sides_dropped"):
        # Not fatal: the canonical frame is built only from the sides that passed,
        # so the card is still correct for both eyes.  What the dropped side
        # actually means is that its paint is broken in the atlas, which is an
        # asset bug to fix in its own pass.
        print("MEASURE_SIDES_DROPPED %s - canonical frame from %s only. The dropped "
              "side's paint is damaged (an atlas bug), but the card is still authored "
              "from a frame the tool accepted."
              % ("; ".join(can["sides_dropped"]), ",".join(can["sides_used"])))
    made = []
    for side in ("L", "R"):
        rec = recs[side]
        faces = sorted({int(i) for i in rec.get("face_indices") or ()})
        if not faces:
            raise SystemExit("MEASURE_REPORT_NO_FACES %s - re-run drako_eye_measure.py, "
                             "older reports did not emit face indices" % side)
        if faces[0] < 0 or faces[-1] >= nface:
            raise SystemExit("MEASURE_REPORT_FACE_OUT_OF_RANGE %s (%d..%d of %d)"
                             % (side, faces[0], faces[-1], nface))
        verts = sorted({v for f in faces for v in body.data.polygons[f].vertices})
        # The card is authored from the aperture the viewer sees, not from the
        # atlas footprint.  They are different sets, and on the baby they are
        # barely related: the atlas is a projection bake whose islands clip the
        # eye drawing into cream/horn/flame pieces, so `face_indices` covers a
        # patchwork band - 14 % of the amber pixels a viewer sees.  Every gate
        # below used to grade that band and agree with the card while the render
        # showed the eye still open.  A report without an aperture is a report
        # from the broken pipeline; refuse it rather than silently fall back.
        appts = rec.get("aperture_points") or ()
        apbox = [float(x) for x in (rec.get("aperture_box_eye") or ())]
        if len(appts) < 200 or len(apbox) != 4:
            raise SystemExit(
                "MEASURE_REPORT_NO_APERTURE_%s - this report has no visible-eye "
                "aperture (%d points). Re-run drako_eye_measure.py: a card sized "
                "and gated on an atlas footprint hides only the part of the eye "
                "that footprint happens to cover." % (side, len(appts)))
        pa = np.asarray(appts, np.float64)
        c = np.array(rec["almond_centre"], np.float64)
        n, up, right = Vector(rec["n"]), Vector(rec["up"]), Vector(rec["right"])
        ax = np.array([tuple(right), tuple(up), tuple(n)], np.float64).T
        p = pos[verts]
        lp = (p - c) @ ax
        lpa = (pa - c) @ ax
        hw, hh = float(rec["half_w"]), float(rec["half_h"])
        # The eye the viewer sees, not the margin the detector selected with: the
        # footprint reaches 1.55x the almond to keep the fit robust, and skin
        # outside the almond is not something a closed lid has to hide.
        eye = (lp[:, 0] / hw) ** 2 + (lp[:, 1] / hh) ** 2 <= a.cover_margin ** 2
        pc = np.array(rec.get("centre_world") or tuple(c), np.float64)
        pwh = float(rec.get("paint_half_w") or hw)
        pwhh = float(rec.get("paint_half_h") or hh)
        pbox = [float(x) for x in (rec.get("paint_box_eye") or [-pwh, -pwhh, pwh, pwhh])]
        # `paint_box_eye` is the paint footprint about `centre_world`, and this card
        # is built on `centre_world` too, but `lp` above is about `almond_centre` -
        # the two origins are almond_off apart (24 mm in u on the teen).  Put the
        # vertices in the box's frame before comparing them, or a correct report
        # looks like a footprint that sticks out of its own box.
        shift = (pc - c) @ ax                                  # iris <- almond
        lc = lp - shift
        # The box and the paint it describes have to agree about where they are.
        # This is the check that catches a frame mix-up on the first run instead of
        # sixty millimetres of stray lid on the first render.
        out_u = int(((lc[:, 0] < pbox[0] - 1e-4) | (lc[:, 0] > pbox[2] + 1e-4)).sum())
        out_v = int(((lc[:, 1] < pbox[1] - 1e-4) | (lc[:, 1] > pbox[3] + 1e-4)).sum())
        if out_u + out_v > 0.15 * len(lp):
            raise SystemExit(
                "PAINT_BOX_NOT_IN_THE_CARDS_FRAME %s - %d of %d eye vertices lie "
                "outside the reported paint box in the frame the card is built on "
                "(u outside %d, v outside %d; box %s, verts u=[%+.4f,%+.4f] "
                "v=[%+.4f,%+.4f]). The box is expressed about a different origin "
                "than `centre_world`, or the footprint is wider than the paint it "
                "claims; widening --cover-margin is neither of those fixes."
                % (side, out_u + out_v, len(lp), out_u, out_v,
                   np.round(pbox, 4).tolist(), lc[:, 0].min(), lc[:, 0].max(),
                   lc[:, 1].min(), lc[:, 1].max()))
        # The almond ellipse is a *measurement* margin, not the eye.  Grading the
        # lid against the 8 vertices it keeps is what let every internal gate pass
        # on a card that hid nothing: the same report names 97 faces as the painted
        # eye, and the other sixty of those vertices are exactly where the card was
        # buried under the brow.  The gate now sees all of them.
        if int(eye.sum()) < 6:
            raise SystemExit("MEASURE_ELLIPSE_HAS_%d_VERTS_%s - the report's frame and "
                             "its faces cannot both be right" % (int(eye.sum()), side))
        upper, lower = lpa[:, 1] > 0.0, lpa[:, 1] < 0.0
        recede = 0.0
        if upper.any() and lower.any():
            recede = float(lpa[upper][:, 2].mean() - lpa[lower][:, 2].mean())
        print("MEASURE_EYE %s faces=%d verts=%d almond_verts=%d almond_W=%.4f H=%.4f "
              "paint_W=%.4f H=%.4f aperture_W=%.4f H=%.4f box=%s (almond is "
              "%+.4f,%+.4f from the card origin) card-frame verts u=[%+.4f,%+.4f] "
              "v=[%+.4f,%+.4f] atlas_box=%s relief=%.4f recede=%+.4f "
              "centre->paint=%.4f m"
              % (side, len(faces), len(verts), int(eye.sum()), 2 * hw, 2 * hh,
                 2 * pwh, 2 * pwhh,
                 float(lpa[:, 0].max() - lpa[:, 0].min()),
                 float(lpa[:, 1].max() - lpa[:, 1].min()),
                 np.round(pbox, 4).tolist(), shift[0], shift[1],
                 lc[:, 0].min(), lc[:, 0].max(), lc[:, 1].min(), lc[:, 1].max(),
                 rec.get("atlas_box"),
                 float(rec["relief"]), recede, float(np.linalg.norm(pc - c))))
        made.append({
            "rect": list(rec.get("atlas_box") or [0.0, 0.0, 0.0, 0.0]),
            "faces": len(faces), "verts": len(verts), "eye_verts": int(eye.sum()),
            "centre": c, "n": n, "up": up, "right": right,
            # The card is sized, hulled and gated on the *visible* eye.  The paint
            # vertices stay in `all_points` because the atlas footprint is still
            # the honest measure of what the repaint touched, and the diagnostic
            # "of N in the region" should not pretend the aperture is one.
            "points": pa, "all_points": p, "lp": lpa,
            "paint_points": p, "aperture_points": pa,
            "half_w": hw, "half_h": hh,
            "paint_centre": pc, "paint_half_w": pwh, "paint_half_h": pwhh,
            "paint_box": pbox,
            "full_w": float(np.abs(lpa[:, 0]).max()),
            "full_h": float(np.abs(lpa[:, 1]).max()),
            "depth": [float(lpa[:, 2].min()), float(lpa[:, 2].max())],
            "relief": float(rec["relief"]),
            "recede": recede,
            "uv_box": rec.get("atlas_box"), "clipped": False,
            "side": side, "bone": rec.get("bone"),
        })
    return made


eyes = []
if mode == "measure":
    eyes = eyes_from_measure(a.eyes)
else:
    for rect in rects:
        m = measure(rect)
        m["side"] = "L" if m["centre"][0] < 0.0 else "R"     # Lid_L sits at -X
        eyes.append(m)
if sorted(e["side"] for e in eyes) != ["L", "R"]:
    raise SystemExit("BOTH_ISLANDS_SAME_SIDE %s" % [e["side"] for e in eyes])
eyes.sort(key=lambda e: e["side"])
for e in eyes:
    d = np.linalg.norm(e["centre"] - anchors[e["side"]])
    print("EYE %s rect=%s faces=%d verts=%d centre=%s W=%.4f H=%.4f depth=%s relief=%.4f"
          " recede=%+.4f n=%s up=%s | uv_box=%s%s old card head %.4f away"
          % (e["side"], e["rect"][:4], e["faces"], e["verts"],
             np.round(e["centre"], 4).tolist(), e["half_w"] * 2.0, e["half_h"] * 2.0,
             [round(v, 4) for v in e["depth"]], e["relief"], e["recede"],
             np.round(tuple(e["n"]), 3).tolist(), np.round(tuple(e["up"]), 3).tolist(),
             e["uv_box"], " CLIPPED" if e["clipped"] else "", d))


def mirror_frame(eyes):
    """One canonical eye frame, reflected onto the other side.

    The two painted islands are tessellated differently, so a frame measured per
    eye gives two lids of different size and tilt and the pet reads as
    cross-eyed.  The head is symmetric about x = 0, so the better-preserved
    island defines the frame and the other eye gets its mirror.  The mirror is
    the *measured* frame, not a re-derivation from world up: a dragon almond
    slants back over the brow, and flattening that slant onto world up would
    close the lid at a different angle from the eye it covers.
    """
    def reflect(v):
        return Vector((-v.x, v.y, v.z))

    best = max(eyes, key=lambda e: (e["faces"], e["verts"]))
    if best["side"] == "R":
        n_can, up_can = Vector(best["n"]), Vector(best["up"])
    else:
        n_can, up_can = reflect(best["n"]), reflect(best["up"])
    if n_can.y > 0.0:
        n_can = -n_can
    n_can = n_can.normalized()
    up_can = (up_can - up_can.dot(n_can) * n_can).normalized()
    if up_can.z < 0.0:
        up_can = -up_can
    right_can = up_can.cross(n_can).normalized()

    # Size from the clean island, not from the mean: the second rect can catch a
    # neighbouring brow scute whose faces point elsewhere, and averaging that in
    # shrinks the lid below the eye it has to cover.
    hw, hh = float(best["half_w"]), float(best["half_h"])
    recede = float(best["recede"])
    relief = float(best["relief"])
    # The *paint*, not the almond ellipse, sets where the lid sits and how big it
    # is.  The two are 18.5 mm apart on the teen and the paint is a third wider, so
    # a card centred and sized on the ellipse lands beside the eye the viewer sees:
    # every gate passed on it while the render showed the eyes still open.
    pwh, pwhh = float(best.get("paint_half_w", hw)), float(best.get("paint_half_h", hh))
    pbox = [float(x) for x in (best.get("paint_box") or [-pwh, -pwhh, pwh, pwhh])]
    pcx = float(np.mean([abs(e["paint_centre"][0]) for e in eyes]))
    pcy = float(np.mean([e["paint_centre"][1] for e in eyes]))
    pcz = float(np.mean([e["paint_centre"][2] for e in eyes]))
    print("CANON n=%s up=%s right=%s almond_W=%.4f H=%.4f paint_W=%.4f H=%.4f "
          "paint_box=%s |x|=%.4f"
          % (np.round(tuple(n_can), 3).tolist(), np.round(tuple(up_can), 3).tolist(),
             np.round(tuple(right_can), 3).tolist(), 2 * hw, 2 * hh, 2 * pwh, 2 * pwhh,
             np.round(pbox, 4).tolist(), pcx))
    for e in eyes:
        sx = -1.0 if e["side"] == "L" else 1.0     # Lid_L sits at -X
        f_n = Vector((sx * n_can.x, n_can.y, n_can.z))
        f_up0 = Vector((sx * up_can.x, up_can.y, up_can.z))
        f_up = (f_up0 - f_up0.dot(f_n) * f_n).normalized()
        # Compared as measured: e["up"] and f_up are both on this side, and
        # reflecting the L one - as this line used to do - put the two vectors in
        # different hemispheres and printed a deviation that was roughly twice the
        # real one on exactly the side the report was trusted for.
        own = Vector(e["up"])
        dev = float(np.degrees(np.arccos(max(-1.0, min(1.0, own.normalized().dot(f_up))))))
        e["up_can_dev"] = round(dev, 2)
        # `right` is the x-mirror of the canonical one, exactly as
        # drako_eye_measure.py emits it - not `up x n`.  Deriving it from the cross
        # product hands the left side a *right-handed* frame, which is the opposite
        # lateral axis: up x n for the mirrored pair is -(x-mirror of right_can).
        # The measure tool documents the same trap ("a mirror flips handedness").
        # With a card symmetric in u the sign did not matter, so both tools passed
        # while disagreeing; sizing the card per arm reads the paint box's two arms
        # as different numbers, and a 24 mm sign flip becomes a lid authored on the
        # wrong side of the eye.
        f_right0 = Vector((sx * right_can.x, right_can.y, right_can.z))
        f_right = (f_right0 - f_right0.dot(f_n) * f_n - f_right0.dot(f_up) * f_up).normalized()
        agree = float(f_right.dot(Vector(e["right"])))
        if agree < 0.9:
            raise SystemExit(
                "CANON_FRAME_FACES_THE_MEASURERS_OPPOSITE %s - this pass built its "
                "card frame with right=%s while the measure report that sized it says "
                "right=%s (dot %+0.2f). The two tools would put the paint box's wide "
                "arm on opposite sides of the eye."
                % (e["side"], np.round(tuple(f_right), 4).tolist(),
                   np.round(tuple(Vector(e["right"])), 4).tolist(), agree))
        e["frame"] = {"centre": np.array((sx * pcx, pcy, pcz), np.float64),
                      "n": f_n, "up": f_up, "right": f_right,
                      "half_w": hw, "half_h": hh, "recede": recede, "relief": relief,
                      "almond_centre": np.array(tuple(e["centre"]), np.float64),
                      "paint_half_w": pwh, "paint_half_h": pwhh, "paint_box": pbox}
        print("FRAME %s centre=%s paintW=%.4f paintH=%.4f almondHW=%.4f HH=%.4f"
              " relief=%.4f n=%s up=%s right=%s own up dev=%.1f deg"
              % (e["side"], np.round(e["frame"]["centre"], 4).tolist(), 2 * pwh, 2 * pwhh,
                 hw, hh, relief,
                 np.round(tuple(f_n), 3).tolist(), np.round(tuple(f_up), 3).tolist(),
                 np.round(tuple(f_right), 3).tolist(), dev))


if not a.no_mirror:
    mirror_frame(eyes)
else:
    for e in eyes:
        e["frame"] = {k: e[k] for k in ("centre", "n", "up", "right",
                                        "half_w", "half_h", "recede", "relief",
                                        "paint_centre", "paint_half_w", "paint_half_h",
                                        "paint_box")}
        e["frame"]["centre"] = e["paint_centre"]
        e["frame"]["almond_centre"] = np.array(tuple(e["centre"]), np.float64)

# ------------------------------------------------------------- card surfaces
body_inv = body_mw.inverted()
body_dir_inv = body_mw.to_3x3().inverted()


def surface_depth(pts, n, cast=0.12):
    """How far proud of its own plane the head skin sits under each grid column.

    One ray per column, fired along -n from `cast` metres in front of the eye plane
    so the first thing it meets is the outside of the skin.  A column that hits
    nothing - the card overhangs the silhouette there - comes back NaN and is
    dropped from the fit, so the lid is never authored against empty air.
    """
    nn = Vector(n).normalized()
    dloc = body_dir_inv @ (-nn)
    out = np.full(len(pts), np.nan)
    for i, p in enumerate(pts):
        pv = Vector(p)
        hit, loc, _nm, _idx = body.ray_cast(body_inv @ (pv + nn * cast), dloc)
        if hit:
            out[i] = float((body_mw @ loc - pv) @ nn)
    return out


def _design(s, t, deg=2):
    """Design matrix of the polynomial patch at normalised eye coordinates.

    `deg=2` is the original six-term patch and its column order is unchanged, so a
    degree-2 fit reproduces byte-for-byte what it used to.
    """
    s = np.asarray(s, np.float64)
    t = np.asarray(t, np.float64)
    cols = [np.ones_like(s)]
    for k in range(1, int(deg) + 1):
        cols += [s ** (k - j) * t ** j for j in range(k + 1)]
    return np.stack(cols, axis=1)


def fit_patch(u, v, d, eyeW, eyeH, deg=2):
    """Smooth quadratic through the sampled skin, with the scutes thrown away.

    A lid is a lid, not a shrink-wrap.  Copying every brow scute and horn seam into
    the plate is what made an earlier conform attempt read as a second forehead, and
    it is also why this function was originally refused - but a *flat* plate at a
    fixed stand-off loses the other way: the measured skin over the teen's eye runs
    from -11 mm to +42 mm off the eye plane, so a plate parked at +27.6 mm is in
    front of the eyeball and behind the brow at the same time, which is exactly the
    blink that renders as nothing.  A six-term patch carries the bulge the eye
    actually sits in and nothing finer.

    Samples are weighted toward the eye centre, where the plate has to be right and
    the fit is only allowed to extrapolate gently at the border, and the residual is
    reweighted twice against its own median deviation so a ray that caught an
    overhanging horn cannot tilt the whole surface.

    `deg` is the degree of the polynomial, not a smoothness knob.  A six-term patch
    over a card that is 158 x 140 mm cannot carry the globe the eye actually is: the
    residual of the degree-2 fit on the teen was p50 4 mm / p98 19 mm, which forced
    the whole plate to ride 15 mm off the head to clear one brow seam - a lid that
    hovers is a lid that does not hide.  Raising the degree follows the socket with
    fewer millimetres of stand-off; raising `--clear` to the same effect is the same
    lie told more expensively.

    """
    u = np.asarray(u, np.float64)
    v = np.asarray(v, np.float64)
    d = np.asarray(d, np.float64)
    m = np.isfinite(d)
    n_terms = (int(deg) + 1) * (int(deg) + 2) // 2
    if int(m.sum()) < 3 * n_terms:
        raise SystemExit("SURFACE_RAYCAST_FOUND_%d_OF_%d_COLUMNS - the body mesh gave"
                         " away under the card; a degree-%d patch needs at least %d"
                         " samples to be fitted, not interpolated"
                         % (int(m.sum()), len(d), deg, 3 * n_terms))
    su, sv, sy = u[m], v[m], d[m]
    s, t = su / eyeW, sv / eyeH
    A = _design(s, t, deg)
    rad = np.hypot(s, t)
    w = np.exp(-(rad / 0.62) ** 2) + 0.15
    coef, res, _r, _s = np.linalg.lstsq(A * w[:, None], sy * w, rcond=None)
    for _ in range(2):
        r = sy - A @ coef
        mad = 1.4826 * float(np.median(np.abs(r - np.median(r)))) + 1e-5
        keep = (np.abs(r) < 3.0 * mad).astype(float)
        if keep.sum() < 3 * n_terms:
            break
        ww = w * keep
        coef, *_ = np.linalg.lstsq(A * ww[:, None], sy * ww, rcond=None)
    # Aligned with the caller's grid, NaN where the raycast missed the head: the
    # clearance below has to know *which* column misses the skin, not just how many
    # millimetres the worst one does, because a card that overhangs the eye and a
    # card that sits on it demand completely different stand-offs.
    resid = np.full(d.shape, np.nan)
    resid[m] = d[m] - _design(u[m] / eyeW, v[m] / eyeH, deg) @ coef
    return coef, resid


def flat_plate(u, v, eyeW, top, bottom, standoff):
    """The legacy plate: one stand-off, receded toward the corners by --dome.

    Kept as one function because `build_card` authors it and `plate_field` has to
    grade against it: written twice, the two versions differed by the dome term's
    reference and the card was covered on one formula and checked on another.
    """
    rr = (np.asarray(top) - np.asarray(v)) / max(1e-6, float(top) - float(bottom))
    rad = (2.0 * np.asarray(u) / eyeW) ** 2 + (2.0 * rr - 1.0) ** 2
    return float(standoff) - a.dome * rad


def _ramp(x, lo, hi, t):
    """1 inside [lo, hi], 0 outside it by `t`, smooth in between.

    A step would crease the mesh along the eye rim; a smoothstep over a few
    millimetres is the lid margin itself, which is what the closed eye's edge is.
    """
    x = np.asarray(x, np.float64)
    t = max(float(t), 1e-6)
    up = np.clip((x - lo) / t + 1.0, 0.0, 1.0)
    dn = np.clip((hi - x) / t + 1.0, 0.0, 1.0)
    return (up * up * (3.0 - 2.0 * up)) * (dn * dn * (3.0 - 2.0 * dn))


def _hull2(points):
    """Convex hull of the painted eye in card coordinates, CCW, or None.

    The card used to end at a *box*, and a box is what the closed lid looked
    like on screen: a red rectangle standing over the eye.  The eye's own painted
    vertices are the outline the viewer actually sees, so the lid is cut to their
    hull instead.  Monotone chain, exact on the small point set a paint island
    has.
    """
    pts = sorted(set((round(float(p[0]), 9), round(float(p[1]), 9)) for p in points))
    if len(pts) < 3:
        return None

    def cross(o, a2, b2):
        return (a2[0] - o[0]) * (b2[1] - o[1]) - (a2[1] - o[1]) * (b2[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    if len(hull) < 3:
        return None
    return np.array(hull, np.float64)


def _hull_sd(hull, u, v):
    """Signed distance to a convex CCW polygon: negative inside, positive out.

    Only used as a ramp coordinate a few millimetres either side of the eye rim,
    which is exactly where the max of the edge-plane distances is the distance to
    the nearest edge.
    """
    h = np.asarray(hull, np.float64)
    p = np.stack([np.asarray(u, np.float64).ravel(),
                  np.asarray(v, np.float64).ravel()], axis=1)
    sd = np.full(len(p), -np.inf)
    for i in range(len(h)):
        a2 = h[i]
        e = h[(i + 1) % len(h)] - a2
        nrm = np.array([e[1], -e[0]], np.float64)     # outward for CCW winding
        ln = float(np.linalg.norm(nrm))
        if ln < 1e-12:
            continue
        sd = np.maximum(sd, (p - a2) @ (nrm / ln))
    return sd.reshape(np.shape(u))


def _hull_low(hull, u):
    """Lowest v of a convex polygon on the vertical line at u, or NaN outside.

    The lash band used to hang off the card's *bottom row*, a straight line metres
    below an eye the card was sized around, so a closed lid carried a dark bar
    across the cheek.  It has to trace the painted eye's own lower rim, and that
    rim is a polygon edge, not a v = const row.
    """
    h = np.asarray(hull, np.float64)
    vs = []
    for i in range(len(h)):
        a2, b2 = h[i], h[(i + 1) % len(h)]
        if (a2[0] <= u <= b2[0]) or (b2[0] <= u <= a2[0]):
            if abs(b2[0] - a2[0]) < 1e-12:
                vs.extend([a2[1], b2[1]])
            else:
                t = (u - a2[0]) / (b2[0] - a2[0])
                vs.append(a2[1] + t * (b2[1] - a2[1]))
    return min(vs) if vs else float("nan")


def _card_grid_at(grid, u, v, u_lo, u_hi, top_y, bottom_y):
    """Bilinear read of the card's sampled skin at (u, v), card-frame coordinates.

    The authored plate *is* this grid plus the window, so the gate that grades the
    plate and the mesh the viewer sees must read the same samples; a polynomial
    that no longer authors anything would only grade a surface that is not there.
    Rows run top -> bottom on the mesh, hence the inverted v fraction.
    """
    g = np.asarray(grid, np.float64)
    rows, cols = g.shape
    u = np.asarray(u, np.float64)
    v = np.asarray(v, np.float64)
    fx = np.clip((u - u_lo) / max(u_hi - u_lo, 1e-9) * (cols - 1), 0.0, cols - 1.0)
    fy = np.clip((top_y - v) / max(top_y - bottom_y, 1e-9) * (rows - 1),
                 0.0, rows - 1.0)
    i0 = np.floor(fx).astype(int)
    j0 = np.floor(fy).astype(int)
    i1 = np.minimum(i0 + 1, cols - 1)
    j1 = np.minimum(j0 + 1, rows - 1)
    tx = fx - i0
    ty = fy - j0
    a2 = g[j0, i0]
    b2 = g[j0, i1]
    c2 = g[j1, i0]
    d2 = g[j1, i1]
    return (a2 * (1.0 - tx) + b2 * tx) * (1.0 - ty) + (c2 * (1.0 - tx) + d2 * tx) * ty


def _resample_rim(poly, step):
    """The hull walked at even spacing, with one outward normal per sample.

    A rectangular card can only meet a curved outline by cutting cells, and the
    cut is what put a sawtooth on the closed lid's lower rim: at 7 mm of column
    spacing and a 3 mm window ramp, adjacent vertices alternate between proud and
    sunk and the lash behind the edge shows through the notches.  Sampling the
    outline itself puts the vertices where the viewer looks - on the rim - and
    the normals let the lash follow the same curve.  `poly` is CCW, so (dy, -dx)
    is the outward side.
    """
    pts = []
    n = len(poly)
    for i in range(n):
        a2, b2 = poly[i], poly[(i + 1) % n]
        length = float(np.linalg.norm(b2 - a2))
        k = max(1, int(round(length / step)))
        for j in range(k):
            pts.append(a2 + (j / float(k)) * (b2 - a2))
    pts = np.array(pts, np.float64)
    nrm = np.zeros_like(pts)
    for i in range(len(pts)):
        # Average the two edges that meet here.  Using the outgoing edge alone
        # gives the normal a step at every hull vertex, which folds the 5.5 mm
        # skirt at the eye's pointed corners and makes the lash twist there; the
        # bisector is continuous and, being shorter than 1 on a sharp corner, it
        # also keeps the offset from crossing itself.
        d0 = pts[i] - pts[(i - 1) % len(pts)]
        d1 = pts[(i + 1) % len(pts)] - pts[i]
        n0 = np.array([d0[1], -d0[0]], np.float64) / max(
            float(np.linalg.norm(d0)), 1e-9)
        n1 = np.array([d1[1], -d1[0]], np.float64) / max(
            float(np.linalg.norm(d1)), 1e-9)
        v = n0 + n1
        nrm[i] = v / max(float(np.linalg.norm(v)), 1e-9)
    return pts, nrm


def lid_window(u, v, plan):
    """1 over the painted eye, 0 out on the skirt (per the plan's own outline).

    The plate has to out-rank the eye it hides; it does *not* have to hover over
    the brow and cheek it does not.  Every millimetre the skirt rides in front of
    the skin is preserved at rest, because the bind pose is the card flattened
    along the bone axis and that flattening leaves depth normal to the face
    untouched - so a skirt at +clear over the brow is a shelf at rest, and a shelf
    poking out of the brow is the blade that read as a gash on the face.  The
    window is the painted eye's own hull, not the box around it: the box corners
    are canvas the eye never reaches, and a closed lid with square corners is the
    red plate the face was wearing in the A/B render.
    """
    hull = plan.get("hull")
    if hull:
        sd = _hull_sd(hull, u, v)
        t = np.clip(1.0 - sd / max(plan["win_margin"], 1e-6), 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)
    u0, u1, v0, v1, t = plan["win"]
    return _ramp(u, u0, u1, t) * _ramp(v, v0, v1, t)


def plate_of(plan, u, v):
    """The depth the lid is authored at over (u, v), in the card's own frame.

    Two fields, because the lid has two jobs: over the paint it is the eye's own
    sampled surface plus clearance, and outside the paint it is the head's skin
    minus the sink, so the canvas disappears under the face.  The window is the only
    place they mix.  Grading a plate against one field when it was authored off two
    is how the previous round certified a lid that hovered and a rim that sagged.
    """
    if plan["conform"] == "FLAT":
        return flat_plate(u, v, plan["eyeW"], plan["top_y"], plan["bottom_y"],
                          plan["standoff"])
    # `u` is centred on the card (the hull and the window are authored in that
    # basis); the sampled grid itself spans the absolute card columns.
    plate = _card_grid_at(plan["base_grid"], u + plan["u_c"], v,
                          plan["u_lo"], plan["u_hi"],
                          plan["top_y"], plan["bottom_y"])
    skin = _card_grid_at(plan["skin_grid"], u + plan["u_c"], v,
                         plan["u_lo"], plan["u_hi"],
                         plan["top_y"], plan["bottom_y"])
    w = lid_window(u, v, plan)
    return w * (plate + plan["clear"]) + (1.0 - w) * (skin - plan["sink"])


def build_card(e):
    """Target (fully blinked) world points: a lid-shaped shell over the painted eye.

    The plate rides the fitted skin plus a clearance, so it hides the eye it is
    standing over for its whole sweep instead of only at the one column the flat
    offset happened to miss.  `--offset` still means the old thing - a flat plate at
    that stand-off - so the comparison that proved this fix stays reproducible.
    """
    fr = e["frame"]
    c, n, up, right = Vector(fr["centre"]), fr["n"], fr["up"], fr["right"]
    # Size and span from the eye the viewer sees - the aperture the measure tool
    # rendered along the eye normal - because that is what has to stop being
    # visible when the lid closes.  The atlas box is kept in the union below: a
    # painted triangle centroid is not a boundary, and the aperture is what
    # decides the shape.
    #
    # The card is sized per *arm*, not by the wider arm mirrored onto both sides.
    # The two boxes the report gives are not symmetric about the card origin: the
    # almond is 130 mm wide about its own centre, which sits 24 mm out along
    # `right` from the frame centre, so its true extent here is [-0.050, +0.098]
    # and the paint footprint reaches [-0.049, +0.108].  Taking
    # `max(|lo|, |hi|)` and applying it as +-half made a 219 mm card for a 158 mm
    # span - sixty millimetres of flat, untextured dark-red lid lying over the
    # cheek and brow beside the eye.  At rest the lid is a thin band, and a band
    # that wide is what reads on screen as a gash across the face.
    pb = fr["paint_box"]
    # One projection, used for the size, for the fit and for the gate.  `plate_field`
    # grades the same `points` about the same `centre` with the same axes, so the
    # footprint the card is authored to and the footprint it is judged against are
    # the same numbers by construction instead of by coincidence.
    axf = np.array([tuple(right), tuple(up), tuple(n)], np.float64).T
    pv = np.asarray(e["points"], np.float64)
    lv = (pv - np.array(tuple(c), np.float64)) @ axf
    # The eye the card has to cover, measured per arm: the union of the size the
    # viewer sees (the aperture's own extreme points) and the atlas box.  The box
    # is centroid-based and can trail the rim by a triangle radius, so neither may
    # be dropped: the aperture sets the shape, the box proves no painted texel is
    # left outside it.
    foot_u = (min(float(pb[0]), float(lv[:, 0].min())),
              max(float(pb[2]), float(lv[:, 0].max())))
    foot_v = (min(float(pb[1]), float(lv[:, 1].min())),
              max(float(pb[3]), float(lv[:, 1].max())))
    # The paint centroid sits inside its own footprint, so a card frame in which the
    # measured eye does not straddle the origin is not a card frame at all: it is
    # two origins mixed together, which is the mistake every previous round of this
    # file made.  Say so instead of authoring a lid off to one side of the eye.
    if not (foot_u[0] < 0.0 < foot_u[1] and foot_v[0] < 0.0 < foot_v[1]):
        raise SystemExit(
            "PAINT_FOOTPRINT_DOES_NOT_STRADDLE_THE_CARD_ORIGIN %s - the eye's "
            "vertices span u=[%+.4f,%+.4f] v=[%+.4f,%+.4f] about `centre`, so the "
            "lid would be authored entirely to one side of the eye it has to hide. "
            "`centre` and the box it is compared with must be the same origin "
            "(the paint centroid); check the frame, not the margin."
            % (e["side"], foot_u[0], foot_u[1], foot_v[0], foot_v[1]))
    # Both axes come from the same measured footprint now.  The vertical one used to
    # be `max(--span * eye height, box arm)`: a fraction of a nominal height the eye
    # does not have.  On the teen `--span-bottom 0.78` x 0.1145 m parked the card's
    # lower edge 22 mm below the lowest painted vertex, and out there the six-term
    # patch has to ride 75 mm of skull curvature, so the *corners* demanded 13.5 mm
    # of stand-off while the eye itself needed 7.7 - and a lid that hangs past the
    # eye is exactly what reads on screen as a dark band across the face.  The
    # almond ellipse left the sizing entirely: it is a detector margin centred 24 mm
    # in from the paint, and reaching it meant 48 mm of canvas over the brow.
    u_lo = foot_u[0] * a.cover_margin * a.wide
    u_hi = foot_u[1] * a.cover_margin * a.wide
    eyeW = u_hi - u_lo
    u_c = 0.5 * (u_lo + u_hi)
    # The patch basis is a *scale*, not a style choice: normalising v by a height
    # the eye does not have (the old `2 * paint_half_h`) flattens every coefficient
    # and the fitted plate spends its freedom on the wrong curvature.  The card's
    # own span is the only honest denominator.
    eyeH = (foot_v[1] - foot_v[0]) * a.tall
    top_y = foot_v[1] * a.cover_margin * a.span_top
    bottom_y = foot_v[0] * a.cover_margin * a.span_bottom
    # The eye's own outline, in the card's centred coordinates.  The window below
    # is cut to this hull, so the closed lid ends where the paint ends instead of
    # on the card's rectangular canvas.  The margin is the ramp width *outside*
    # the hull, clamped to the canvas that is actually left around it so the
    # window reaches zero before the mesh edge; otherwise the lid's border is a
    # straight cut at the card boundary.
    hull = _hull2(np.stack([lv[:, 0] - u_c, lv[:, 1]], axis=1))
    if hull is not None:
        edge = min(float(hull[:, 0].min() + 0.5 * eyeW),
                   float(0.5 * eyeW - hull[:, 0].max()),
                   float(hull[:, 1].min() - bottom_y),
                   float(top_y - hull[:, 1].max()))
        win_margin = max(0.0015, min(float(a.taper), 0.8 * edge))
    else:
        win_margin = float(a.taper)
    rows, cols = a.rows, a.cols
    us, vs = [], []
    for r in range(rows):
        rr = r / float(rows - 1)
        row_u, row_v = [], []
        for ci in range(cols):
            xf = ci / float(cols - 1) - 0.5
            # The bow was the closed lid's lower edge while the card *was* the lid.
            # It is not any more: the window cuts the lid to the eye's outline, so
            # a bowed card edge only bends the canvas that gets sunk.  Kept for
            # the flat-plate A/B, which still ends at the card's own rectangle.
            droop = 0.0
            if a.offset > 0.0:
                droop = -a.curve * eyeH * (1.0 - (xf * 2.0) ** 2)
            row_u.append(u_c + xf * eyeW)
            row_v.append(top_y + rr * (bottom_y + droop - top_y))
        us.append(row_u)
        vs.append(row_v)
    flat_u = np.array([x for row in us for x in row], np.float64)
    flat_v = np.array([x for row in vs for x in row], np.float64)
    # Everything that is a *shape* - the dome, the patch basis - is written in
    # coordinates centred on the card, so the fit cannot spend a degree of freedom
    # on the offset the card already knows it has.
    flat_du = flat_u - u_c

    surf = None
    base_grid = None
    skin_grid = None
    win_box = None
    if a.offset > 0.0:                      # the flat plate, kept for the A/B
        coef, clear, res = None, a.offset, np.array([0.0])
        depth = flat_plate(flat_du, flat_v, eyeW, top_y, bottom_y, a.offset)
        mode = "FLAT"
    else:
        plane = [np.array(tuple(c), np.float64) + right * u + up * v_up
                 for u, v_up in zip(flat_u, flat_v)]
        surf = surface_depth(plane, n)
        coef, res = fit_patch(flat_du, flat_v, surf, eyeW, eyeH, a.patch_degree)
        mode = "CONFORM"
        # ---------------------------------------------------------- the plate
        # The plate the viewer sees when the eye is shut *is* the skin the card
        # was measured against, sampled at each grid column.  It used to be a
        # quadratic through those samples plus the worst residual of that fit;
        # on the teen that put the plate 16-28 mm off the paint - a flat red board
        # hovering over the face, which is what the A/B render showed.  Copying
        # the samples makes the lid hug the socket; the fit is kept only as the
        # fallback for a column whose ray missed, and as the roughness diagnostic
        # that says how much sculpture a smooth patch would have thrown away.
        poly = _design(flat_du / eyeW, flat_v / eyeH, a.patch_degree) @ coef
        skin = np.where(np.isfinite(surf), surf, poly)
        # The lid ends on the eye's own outline, not on a box around it.
        if hull is not None:
            sd = _hull_sd(hull, flat_du, flat_v)
            t_win = np.clip(1.0 - sd / win_margin, 0.0, 1.0)
            win = t_win * t_win * (3.0 - 2.0 * t_win)
            inside = sd <= 0.0
        else:
            win_box = [foot_u[0] * a.cover_margin - u_c,
                       foot_u[1] * a.cover_margin - u_c,
                       foot_v[0] * a.cover_margin, foot_v[1] * a.cover_margin,
                       a.taper]
            win = _ramp(flat_du, win_box[0], win_box[1], win_box[4]) * \
                _ramp(flat_v, win_box[2], win_box[3], win_box[4])
            inside = np.ones(len(flat_u), bool)
        # The plate is the eye's *own* surface, carried across the card; the skirt is
        # the actual skin below it.  Reading one field for both is what made a lid
        # dive 91 mm at the lower rim: a bilinear cell that straddles the rim blends
        # the eye's depth with the cheek's, and a closed lid has no business following
        # the cheek.  So columns under the paint keep their raycast, every column
        # outside borrows the nearest painted neighbour, and the two only meet inside
        # the 1.5 mm window ramp - where the mesh wall is the lid margin itself.
        if not inside.any():
            raise SystemExit(
                "NO_RAYCAST_COLUMN_LIES_OVER_THE_PAINTED_EYE %s - the card spans the"
                " eye in u/v but none of its %d columns falls inside the measured"
                " footprint; the plate would be judged only on skirt, which is not a"
                " lid. Check --rows/--cols and the frame origin." % (e["side"], len(sd)))
        plate_base = np.where(inside, skin, 0.0)
        if (~inside).any():
            ins = np.stack([flat_du[inside], flat_v[inside]], axis=1)
            outs = np.stack([flat_du[~inside], flat_v[~inside]], axis=1)
            near = ((outs[:, None, :] - ins[None, :, :]) ** 2).sum(axis=2).argmin(axis=1)
            plate_base[~inside] = plate_base[inside][near]
        # How much stand-off the *interpolated* plate actually needs over the eye.
        # The mesh between two grid columns is a straight line through the samples,
        # so a painted vertex that sits on a bump between them can be in front of
        # the plate even when every sample is above the skin.  This is measured on
        # the same bilinear read `plate_field` uses, at the vertices the coverage
        # and blink gates count, and the clearance is raised by exactly that much.
        plate_eye = _card_grid_at(plate_base.reshape(rows, cols), lv[:, 0],
                                  lv[:, 1], u_lo, u_hi, top_y, bottom_y) + a.clear
        deficit = lv[:, 2] - plate_eye
        need = max(0.0, float(np.max(deficit)))
        kw = int(np.argmax(deficit))
        if need > a.max_clear:
            fx = (lv[kw, 0] - u_lo) / max(u_hi - u_lo, 1e-9) * (cols - 1)
            fy = (top_y - lv[kw, 1]) / max(top_y - bottom_y, 1e-9) * (rows - 1)
            i0 = int(np.clip(np.floor(fx), 0, cols - 2))
            j0 = int(np.clip(np.floor(fy), 0, rows - 2))
            pg = plate_base.reshape(rows, cols)
            sk = skin.reshape(rows, cols)
            print("DEBUG %s body=%s worst vert u=%+.4f v=%+.4f d=%+.2f fx=%.2f"
                  " fy=%.2f | inside[%d,%d..%d,%d]=%s | plate=%s | skin=%s"
                  " | stored-in %d/%d, plate_base %+.2f..%+.2f"
                  % (e["side"], body.name, lv[kw, 0], lv[kw, 1], 1e3 * lv[kw, 2],
                     fx, fy, j0, i0, j0 + 1, i0 + 1,
                     np.array2string(inside.reshape(rows, cols)[j0:j0 + 2, i0:i0 + 2]),
                     np.array2string(1e3 * pg[j0:j0 + 2, i0:i0 + 2], precision=2),
                     np.array2string(1e3 * sk[j0:j0 + 2, i0:i0 + 2], precision=2),
                     int(inside.sum()), len(inside),
                     1e3 * float(plate_base.min()), 1e3 * float(plate_base.max())))
            print("DEBUG %s full skin grid (mm, rows top->bottom, NaN='   .')"
                  % e["side"])
            for r in range(rows):
                print("  " + " ".join("%6.1f" % (1e3 * sk[r, ci]) if np.isfinite(sk[r, ci])
                                      else "     ." for ci in range(cols)))
            print("DEBUG %s card frame u=[%+.4f,%+.4f] v=[%+.4f,%+.4f] c=%s n=%s"
                  " right=%s up=%s cast plane p%d,%d=%s"
                  % (e["side"], u_lo, u_hi, bottom_y, top_y,
                     np.round(tuple(c), 4).tolist(), np.round(tuple(n), 4).tolist(),
                     np.round(tuple(right), 4).tolist(), np.round(tuple(up), 4).tolist(),
                     int(np.clip(round(fy), 0, rows - 1)),
                     int(np.clip(round(fx), 0, cols - 1)),
                     np.round(plane[int(np.clip(round(fy), 0, rows - 1)) * cols +
                                    int(np.clip(round(fx), 0, cols - 1))], 4).tolist()))
        # Which of the card's own columns have an eye under them.  The plate has
        # to out-rank the skin wherever the eye is visible; over the *skirt* - the
        # canvas outside the aperture that exists only so a closed lid has an edge -
        # a column the patch misses by a centimetre hides nothing, and demanding
        # that the whole plate float high enough to clear it is what parks the lid
        # out in front of the eyeball.  `inside` is the aperture itself, so this is
        # now the eye the viewer sees rather than a box around the atlas paint.
        in_eye = np.isfinite(surf) & inside
        if not in_eye.any():
            raise SystemExit(
                "NO_RAYCAST_COLUMN_LIES_OVER_THE_PAINTED_EYE %s - the card spans the"
                " eye in u/v but none of its %d columns falls inside the measured"
                " footprint; the plate would be judged only on skirt, which is not a"
                " lid. Check --rows/--cols and the frame origin."
                % (e["side"], len(res)))
        clear = float(a.clear + need)
        if need > a.max_clear:
            raise SystemExit(
                "CONFORM_NEEDS_%s_MM_CLEARANCE_%s - the skin between the card's own"
                " columns stands %.2f mm through the plate (worst eye vertex"
                " u=%+.4f v=%+.4f), which is more than the %.1f mm of stand-off this"
                " lid is allowed to float. The card reaches u=[%+.4f,%+.4f]"
                " v=[%+.4f,%+.4f] while the eye is u=[%+.4f,%+.4f] v=[%+.4f,%+.4f]."
                " Collect the skin more finely (--rows/--cols) or bring the card"
                " closer to the measured eye (--wide/--span-*); do not raise"
                " --max-clear to make the number go away."
                % (e["side"], round(1e3 * need, 2), 1e3 * need,
                   lv[kw, 0], lv[kw, 1], 1e3 * a.max_clear, u_lo, u_hi,
                   bottom_y, top_y, foot_u[0], foot_u[1], foot_v[0], foot_v[1]))
        base_grid = plate_base.reshape(rows, cols)
        skin_grid = skin.reshape(rows, cols)
        depth = win * (plate_base + clear) + (1.0 - win) * (skin - a.rest_sink)
        fit_lo, fit_hi = float(poly.min()), float(poly.max())
        print("SURFACE %s skin=%+6.1f..%+6.1f mm | poly %+6.1f..%+6.1f mm, what a"
              " smooth patch would miss: p50=%.2f p98=%.2f mm | interp need=%.2f mm"
              " at u=%+.4f v=%+.4f | clear=%.2f mm | plate base %+6.1f..%+6.1f mm"
              " authored %+6.1f..%+6.1f mm | window %s margin=%.2f mm | %d/%d"
              " columns hit, %d/%d under the paint"
              % (e["side"], 1e3 * float(np.nanmin(surf)), 1e3 * float(np.nanmax(surf)),
                 1e3 * fit_lo, 1e3 * fit_hi,
                 1e3 * float(np.median(np.abs(res))),
                 1e3 * float(np.percentile(np.abs(res), 98)),
                 1e3 * need, lv[kw, 0], lv[kw, 1], 1e3 * clear,
                 1e3 * float(plate_base.min()), 1e3 * float(plate_base.max()),
                 1e3 * float(depth.min()), 1e3 * float(depth.max()),
                 "hull" if hull is not None else "box", 1e3 * win_margin,
                 int(np.isfinite(surf).sum()), len(surf),
                 int(inside.sum()), len(inside)))

    plan = {"eyeH": eyeH, "eyeW": eyeW, "u_lo": u_lo, "u_hi": u_hi, "u_c": u_c,
            "foot_u": [round(foot_u[0], 4), round(foot_u[1], 4)],
            "foot_v": [round(foot_v[0], 4), round(foot_v[1], 4)],
            "top_y": top_y, "bottom_y": bottom_y,
            "coef": coef, "clear": clear, "conform": mode, "deg": a.patch_degree,
            "base_grid": base_grid, "skin_grid": skin_grid,
            "hull": None if hull is None else hull.round(6).tolist(),
            "win_margin": round(float(win_margin), 5),
            "win": [round(float(x), 5) for x in win_box] if win_box is not None else None,
            "sink": float(a.rest_sink),
            "offset": float(np.mean(depth)), "standoff": float(a.offset)}

    if a.offset > 0.0 or hull is None:
        # The flat plate A/B, and the no-hull fallback: the rectangular grid.  It
        # is kept exact so the before/after that proved the conform stays
        # reproducible, and so an eye the hull could not be built for still gets
        # a card instead of a crash.
        grid = []
        k = 0
        for r in range(rows):
            row = []
            for ci in range(cols):
                row.append(c + right * us[r][ci] + up * vs[r][ci] + n * float(depth[k]))
                k += 1
            grid.append(row)
        corners = ((np.abs(flat_du) > 0.5 * eyeW - 1e-9) |
                   (np.abs(flat_v - 0.5 * (top_y + bottom_y)) >
                    0.5 * (top_y - bottom_y) - 1e-9))
        if a.offset > 0.0:
            corner_proud = None
        else:
            cp = (depth - surf)[corners & np.isfinite(surf)]
            corner_proud = float(cp.min()) if cp.size else None
        mid = cols // 2
        head = grid[0][mid]
        direction = grid[rows - 1][mid] - head
        if direction.length < 1e-6:
            raise SystemExit("degenerate card for " + e["side"])
        direction.normalize()
        roll = (n - n.dot(direction) * direction).normalized()
        lash_depth = eyeH * a.lash
        depth_grid = np.asarray(depth, np.float64).reshape(rows, cols)
        lash_top, lash_bottom = [], []
        for ci in range(cols):
            u = us[rows - 1][ci]
            v_rim = _hull_low(hull, u - u_c) if hull is not None else float("nan")
            if not np.isfinite(v_rim):
                v_rim = bottom_y
            v_top = max(v_rim - 0.0010, bottom_y)
            v_bot = max(v_top - lash_depth, bottom_y)
            if a.offset > 0.0:
                def at(uu, vv):
                    return flat_plate(np.array([uu - u_c]), np.array([vv]), eyeW,
                                      top_y, bottom_y, a.offset)[0]
            else:
                def at(uu, vv):
                    return float(_card_grid_at(depth_grid, np.array([uu]),
                                               np.array([vv]), u_lo, u_hi,
                                               top_y, bottom_y)[0])
            lash_top.append(c + right * u + up * v_top + n * (float(at(u, v_top)) + 0.0015))
            lash_bottom.append(c + right * u + up * v_bot + n * (float(at(u, v_bot)) + 0.0015))
        plan.update({"grid": grid, "head": head, "dir": direction, "roll": roll,
                     "lash_top": lash_top, "lash_bottom": lash_bottom,
                     "corner_proud": corner_proud,
                     "target": [p for row in grid for p in row], "disc": None})
        return plan

    # ---- the closed lid's own outline --------------------------------------
    # CONFORM: a disc whose rim *is* the painted eye's hull.  The rim is proud
    # (win = 1 on sd = 0), so every painted vertex stays behind the lid, and a
    # short skirt 5.5 mm outside it sinks below the skin; the visible edge is the
    # smooth crossing between the two, not a cell grid's staircase.  The lash is
    # traced on the same samples, so it follows the rim instead of chording it.
    rim_poly, rim_nrm = _resample_rim(hull, 0.004)
    N = len(rim_poly)
    ct2 = np.array([float(hull[:, 0].mean()), float(hull[:, 1].mean())])
    K = 8
    lash_depth = min(eyeH * a.lash, 0.004)
    lash_h = 0.0015

    def at_uv(du, v):
        # `du` is card-centred (the hull and the window are authored there); the
        # frame origin is `u_c` further out along `right`.  Placing the disc at
        # `right * du` put the whole lid 31 mm inboard of the eye it has to cover
        # while every downstream check that shared the same error still agreed.
        return c + right * float(du + u_c) + up * float(v) + \
            n * float(plate_of(plan, float(du), float(v)))

    world, tags, depths = [at_uv(ct2[0], ct2[1])], ["skin"], \
        [float(plate_of(plan, ct2[0], ct2[1]))]
    ring_ids = []
    for k in range(1, K + 1):
        r = k / float(K)
        row = []
        for i in range(N):
            q = ct2 + r * (rim_poly[i] - ct2)
            row.append(len(world))
            d = float(plate_of(plan, q[0], q[1]))
            depths.append(d)
            world.append(c + right * float(q[0] + u_c) + up * float(q[1]) + n * d)
            tags.append("skin")
        ring_ids.append(row)
    skirt_ids = []
    for i in range(N):
        q = rim_poly[i] + rim_nrm[i] * 0.0055
        d = float(plate_of(plan, q[0], q[1]))
        depths.append(d)
        world.append(c + right * float(q[0] + u_c) + up * float(q[1]) + n * d)
        skirt_ids.append(len(world) - 1)
        tags.append("skin")
    skin_faces = []
    for i in range(N):
        skin_faces.append((0, ring_ids[0][(i + 1) % N], ring_ids[0][i]))
    for k in range(K - 1):
        for i in range(N):
            j = (i + 1) % N
            skin_faces.append((ring_ids[k][i], ring_ids[k][j],
                               ring_ids[k + 1][j], ring_ids[k + 1][i]))
    for i in range(N):
        j = (i + 1) % N
        skin_faces.append((ring_ids[K - 1][i], ring_ids[K - 1][j],
                           skirt_ids[j], skirt_ids[i]))
    # The lash hugs the lower arc only - the part of the rim whose outward
    # normal points down - and is sampled on the same 4 mm walk, so its top edge
    # is a continuous line on the lid's margin instead of a dashed chord.
    low = np.where(rim_nrm[:, 1] < -0.25)[0]
    arc = []
    if low.size:
        runs, start = [], 0
        for k in range(1, len(low) + 1):
            if k == len(low) or low[k] != low[k - 1] + 1:
                runs.append(low[start:k])
                start = k
        if len(runs) > 1 and runs[0][0] == 0 and runs[-1][-1] == N - 1:
            runs[0] = np.concatenate([runs[-1], runs[0]])
            runs.pop()
        arc = list(max(runs, key=len))
    lash_faces = []
    if len(arc) >= 2:
        top_ids, bot_ids = [], []
        for k, i in enumerate(arc):
            # The band lies *inside* the rim, not across it: a proud ribbon that
            # reaches the silhouette pokes past the lid at the pointed corners
            # and reads as a black claw on the cheek.  Inset the top edge by a
            # fraction of a millimetre, run the bottom edge inward, and fade the
            # width to nothing over the first and last three samples so the lash
            # line dies out at the corners instead of ending in a cut.
            taper = min(1.0, min(k, len(arc) - 1 - k) / 3.0)
            quv = rim_poly[i] - rim_nrm[i] * 0.0008
            bv = rim_poly[i] - rim_nrm[i] * (0.0008 + lash_depth * taper)
            for q in (quv, bv):
                d = float(plate_of(plan, q[0], q[1])) + lash_h
                depths.append(d)
                world.append(c + right * float(q[0] + u_c) + up * float(q[1]) + n * d)
                tags.append("lash")
            top_ids.append(len(world) - 2)
            bot_ids.append(len(world) - 1)
        for k in range(len(arc) - 1):
            lash_faces.append((top_ids[k], top_ids[k + 1],
                               bot_ids[k + 1], bot_ids[k]))
    nvec = np.array(tuple(n), np.float64)

    def _fnorm(f):
        p0 = np.array(tuple(world[f[0]]), np.float64)
        p1 = np.array(tuple(world[f[1]]), np.float64)
        p2 = np.array(tuple(world[f[2]]), np.float64)
        return np.cross(p1 - p0, p2 - p0)

    if skin_faces and float(_fnorm(skin_faces[0]) @ nvec) < 0.0:
        skin_faces = [tuple(reversed(f)) for f in skin_faces]
        lash_faces = [tuple(reversed(f)) for f in lash_faces]
    top_i = int(np.argmax(rim_poly[:, 1]))
    bot_i = int(np.argmin(rim_poly[:, 1]))
    head = c + right * float(ct2[0] + u_c) + up * float(ct2[1]) + \
        n * (float(plate_of(plan, ct2[0], ct2[1])) - clear - a.rest_sink)
    direction = (at_uv(rim_poly[bot_i][0], rim_poly[bot_i][1]) -
                 at_uv(rim_poly[top_i][0], rim_poly[top_i][1]))
    if direction.length < 1e-6:
        raise SystemExit("degenerate lid disc for " + e["side"])
    direction.normalize()
    roll = (n - n.dot(direction) * direction).normalized()
    plan.update({"head": head, "dir": direction, "roll": roll,
                 "lash_depth": lash_depth, "rim_pts": int(N), "rings": K,
                 "corner_proud": None,
                 "disc": {"world": world, "tags": tags,
                          "faces": skin_faces, "lash_faces": lash_faces},
                 "target": world, "offset": float(np.mean(depths))})

    # ---- settle the rest speck ---------------------------------------------
    # The bind is the whole card compressed 1/REST_DIV on all three axes, so at
    # rest it is still a ~6 mm speck, not a point: its depth spread is only
    # (d_max-d_min)/30, but the skin under those same few millimetres can fall
    # away by far more.  Anchored at the disc centre - which rides `clear` above
    # the eye - the cloud's shoulder can therefore stand in front of the brow
    # even though the centre is sunk.  The peak is algebraically independent of
    # where the head sits (a 30x uniform bone scale restores every vertex
    # exactly), so settle the head until the whole speck reports behind the skin
    # instead of hoping the chosen centre happened to be a hollow.
    latv = direction.cross(roll).normalized()
    obasis = np.array([tuple(direction), tuple(roll), tuple(latv)],
                      np.float64).T

    def bind_cloud(hh):
        out = []
        for p in world:
            q = np.array(tuple(p), np.float64) - hh
            out.append(hh + obasis @ ((q @ obasis) / REST_DIV))
        return np.array(out, np.float64)

    hh = np.array(tuple(head), np.float64)
    settle = 0.0
    for _ in range(4):
        cloud = bind_cloud(hh)
        dd = surface_depth(cloud, nvec, cast=0.25)
        ok = np.isfinite(dd)
        if not ok.any():
            break
        worst = float(np.max(-dd[ok]))
        if worst <= -REST_HIDE_MARGIN:
            break
        step = worst + REST_HIDE_MARGIN + 0.0010
        hh = hh - nvec * step
        settle += step
    head = Vector(hh)
    plan["head"] = head
    print("REST_SETTLE %s head sunk an extra %.2f mm so the bind speck clears"
          " the skin" % (e["side"], 1e3 * settle))
    print("DISC %s rim=%d samples (%.2f mm), rings=%d, skirt=5.5 mm,"
          " lash=%d samples x %.2f mm, verts=%d"
          % (e["side"], N, 1e3 * float(np.mean(np.linalg.norm(
              rim_poly - np.roll(rim_poly, 1, axis=0), axis=1))),
             K, len(arc), 1e3 * lash_depth, len(world)))
    return plan


plans = [build_card(e) for e in eyes]

# The whole bug class is here: a lid bone that leans backward drives its card
# into the head as it stretches, and the blink is invisible.  Prove the opposite
# instead of hoping - cover every painted eye face and check the closed plate
# stands in front of it - and say so before exporting.
def plate_field(e, plan):
    """(u, v, d, plate) of every painted eye vertex in the card's own frame.

    u/v are lateral and vertical from the eye centre, d is how far the vertex
    itself stands in front of the eye plane, and plate is the depth the lid was
    actually authored at over that vertex: the fitted skin plus its clearance, or
    the flat stand-off receded by the dome term when `--offset` asked for a plate.
    Both checks below need the same field, so it is computed once here rather than
    re-derived per check; that is also what lets the ray-cast start in front of the
    plate instead of in front of the eye.
    """
    fr = e["frame"]
    ax = np.array([tuple(fr["right"]), tuple(fr["up"]), tuple(fr["n"])], np.float64).T
    loc = (e["points"] - np.array(tuple(fr["centre"]), np.float64)) @ ax
    u, v, d = loc[:, 0], loc[:, 1], loc[:, 2]
    # The plate is authored in coordinates centred on the card, which is not the
    # frame centre any more now that the card is sized per arm; grade in the same
    # coordinates the design basis uses or the two disagree by the card offset.
    du = u - plan["u_c"]
    plate = plate_of(plan, du, v)
    return u, v, d, plate


def coverage(e, plan):
    u, v, d, plate = plate_field(e, plan)
    fr = e["frame"]
    # The card's own edges, not the knobs that were considered for them: `--wide`
    # and the paint box both compete for the size, and grading against the loser
    # either invents canvas that was never authored or ignores canvas that was.
    lat_lo, lat_hi = plan["u_lo"], plan["u_hi"]
    top_lim, bot_lim = plan["top_y"], plan["bottom_y"]
    inside = (u <= lat_hi) & (u >= lat_lo) & (v <= top_lim) & (v >= bot_lim)
    fronted = inside & (plate >= d)
    buried_sel = inside & (plate < d)
    bury_detail = []
    if buried_sel.any():
        # Where a plate sinks tells you which knob is the right one: buried at the
        # card's lateral extremes means it is too big for the head it has to ride
        # (--wide / the paint box), buried inside the almond means the conform
        # itself is wrong (--clear / the fit).  Print the almond-relative position
        # of the worst ones so that choice is made from evidence, not from a hunch.
        bhw = max(float(fr["half_w"]), 1e-6)
        bhh = max(float(fr["half_h"]), 1e-6)
        # half_w/half_h are the almond's radii about the *almond* centre, while u/v
        # here are about the card origin, which the report puts wherever the paint
        # centroid is - 24 mm away on the teen.  Ratio one by the other and every
        # vertex reads as sitting further out than it does.
        axf = np.array([tuple(fr["right"]), tuple(fr["up"]), tuple(fr["n"])], np.float64).T
        aoff = ((np.array(tuple(fr["almond_centre"]), np.float64) -
                 np.array(tuple(fr["centre"]), np.float64)) @ axf)[:2]
        gap = (plate - d)[buried_sel]
        bu, bv = u[buried_sel] - aoff[0], v[buried_sel] - aoff[1]
        for k in np.argsort(gap)[:10]:
            bury_detail.append([round(float(bu[k]), 4), round(float(bv[k]), 4),
                                round(float(gap[k]), 4),
                                round(float((bu[k] / bhw) ** 2 + (bv[k] / bhh) ** 2), 2)])
    # A coverage failure has two completely different causes and they need
    # different fixes: the plate can be buried in the skin, or the eye footprint
    # can simply reach past the card.  Saying which, and by how much, is what
    # stops the next person from retuning --clear when --wide is the knob.
    return {"eye_verts": int(len(u)),
            "region_verts": int(len(e.get("all_points", e["points"]))),
            "covered_pct": round(100.0 * inside.mean(), 1),
            "fronted_pct": round(100.0 * fronted.mean(), 1),
            "worst_gap": round(float(np.max(plate[inside] - d[inside])) if inside.any() else 0.0, 4),
            "worst_bury": round(float(np.min(plate[inside] - d[inside])) if inside.any() else 0.0, 4),
            "u_span": [round(float(u.min()), 4), round(float(u.max()), 4)],
            "v_span": [round(float(v.min()), 4), round(float(v.max()), 4)],
            "card_u": [round(float(lat_lo), 4), round(float(lat_hi), 4)],
            "out_wide": int((u > lat_hi).sum() + (u < lat_lo).sum()),
            "out_high": int((v > top_lim).sum()),
            "out_low": int((v < bot_lim).sum()),
            "bury": bury_detail,
            "buried": int(buried_sel.sum())}


for e, plan in zip(eyes, plans):
    fr = e["frame"]
    cov = coverage(e, plan)
    plan["coverage"] = cov
    # What decides whether the blink is visible is the plate's distance from the
    # eye surface, not the sign of its sweep in world Y.  The old verdict read
    # "BACKWARD (SINKS INTO HEAD)" for any card whose chord had +world Y, which
    # was a fair proxy for the baby's near-upright eye and a false charge against
    # the adult, whose almond tilts 63 degrees forward over the brow so its own
    # "down" runs forward.  The honest statement is the one below: does the plate
    # stay in front of the painted eye for its whole sweep.
    print("CARD %s %s eyeW=%.4f eyeH=%.4f span=%+.4f/%+.4f top=%s dir=%s roll=%s"
          " sweep_lean=%+.4f mean_depth=%.4f recede=%+.4f cover=%s%% fronted=%s%%"
          " over %d eye verts (of %d in the region) worst_bury=%s m"
          " | card u=%s v=%s, eye spans u=%s v=%s,"
          " outside: wide=%d high=%d low=%d, buried=%d, corner_proud=%s m"
          % (e["side"], plan["conform"], plan["eyeW"], plan["eyeH"],
             plan["top_y"], plan["bottom_y"], np.round(tuple(plan["head"]), 4).tolist(),
             np.round(tuple(plan["dir"]), 4).tolist(), np.round(tuple(plan["roll"]), 4).tolist(),
             float(plan["dir"].y), plan["offset"], fr["recede"],
             cov["covered_pct"], cov["fronted_pct"], cov["eye_verts"], cov["region_verts"],
             cov["worst_bury"],
             cov["card_u"], [round(float(plan["bottom_y"]), 4),
                             round(float(plan["top_y"]), 4)],
             cov["u_span"], cov["v_span"], cov["out_wide"], cov["out_high"],
             cov["out_low"], cov["buried"],
             None if plan["corner_proud"] is None else
             round(float(plan["corner_proud"]), 4)))
    if cov["buried"]:
        print("BURIED %s worst [u, v, plate-skin, (u/hw)^2+(v/hh)^2]: %s"
              " - under 1.0 is inside the almond, so the conform is wrong; well"
              " over it is the card reaching past the eye and --wide is the knob"
              % (e["side"], cov["bury"]))

# ----------------------------------------------------- lid bones (rest pose)
# The blink only scales bone-local Y, so the bone's *direction* decides where a
# stretched card row lands while its length does not; re-aim it along the swept
# chord and re-roll it onto the surface normal so local Z is the card's own
# outward axis (the axis that carries the clearance through the stretch).
arm_rot_inv = arm_mw.to_3x3().inverted()
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
edit_bones = arm.data.edit_bones
for e, plan in zip(eyes, plans):
    eb = edit_bones["Lid_" + e["side"]]
    eb.use_connect = False
    eb.head = to_arm(plan["head"])
    eb.tail = eb.head + (arm_rot_inv @ plan["dir"]).normalized() * 0.05
    eb.align_roll(arm_rot_inv @ plan["roll"])
bpy.ops.object.mode_set(mode="OBJECT")
bpy.context.view_layer.update()

# ----------------------------------------------------------- author the mesh
def author(e, plan):
    """Bind card = target card compressed 1/REST_DIV on *all three* bone axes.

    Compressing only the sweep was the blade.  The bind pose is what the viewer
    shows between blinks, so whatever the card still spans at rest is what it
    wears on the face: a 0.17 m wide card compressed to 4 mm of sweep is a wide
    ribbon lying on the brow, and the head falls away under its lateral ends by
    tens of millimetres, so the ribbon stood 40 mm proud at the temple.  Every
    clip's blink keys are a uniform 1 -> 30 in the bone's own scale channel, so
    the bind can be compressed on X and Z as well; at rest the whole card is a
    6 mm speck at the bone head, which the sunk top row puts inside the skin, and
    at the peak it is exactly the authored plate again.
    """
    lat = plan["dir"].cross(plan["roll"]).normalized()
    basis = np.array([tuple(plan["dir"]), tuple(plan["roll"]), tuple(lat)], np.float64).T
    h = np.array(tuple(plan["head"]), np.float64)
    verts, which = [], []

    def put(p, tag):
        rel = np.array(tuple(p), np.float64) - h
        comp = rel @ basis                       # along, across, lateral
        bind = h + basis @ (comp / REST_DIV)
        verts.append(to_arm(Vector(bind)))
        which.append(tag)

    disc = plan.get("disc")
    if disc is not None:
        # The rim-aligned disc is already one ordered vertex list with its faces
        # indexed into it; keep that order exactly so the builder can reuse the
        # indices instead of re-deriving them from a grid.
        for p, tag in zip(disc["world"], disc["tags"]):
            put(p, tag)
        return verts, which

    for r, row in enumerate(plan["grid"]):
        for p in row:
            put(p, "skin")
    for p in plan["lash_top"]:
        put(p, "lash")
    for p in plan["lash_bottom"]:
        put(p, "lash")
    return verts, which


skin_mat = next((m for m in bpy.data.materials if m.name.startswith("DrakoEyelid")), None)
lash_mat = next((m for m in bpy.data.materials if m.name.startswith("DrakoLash")), None)
if skin_mat is None or lash_mat is None:
    raise SystemExit("MISSING_EYELID_MATERIALS")

bpy.data.objects.remove(lids_old, do_unlink=True)

mesh = bpy.data.meshes.new("DrakoEyelids")
faces, face_mats, groups = [], [], {"L": [], "R": []}
all_verts = []
for e, plan in zip(eyes, plans):
    vs, tags = author(e, plan)
    base = len(all_verts)
    all_verts.extend(vs)
    disc = plan.get("disc")
    if disc is not None:
        # Indices are already relative to this side's vertex block, and the
        # ordering in `author` is the disc's own; shift them by the block start.
        for f in disc["faces"]:
            faces.append(tuple(base + i for i in f))
            face_mats.append(0)
        for f in disc["lash_faces"]:
            faces.append(tuple(base + i for i in f))
            face_mats.append(1)
    else:
        rows, cols = a.rows, a.cols
        for r in range(rows - 1):
            for ci in range(cols - 1):
                x = base + r * cols + ci
                faces.append((x, x + cols, x + cols + 1, x + 1))
                face_mats.append(0)
        lb = base + rows * cols
        for ci in range(cols - 1):
            x = lb + ci
            faces.append((x, x + cols, x + cols + 1, x + 1))
            face_mats.append(1)
    groups[e["side"]].extend(range(base, base + len(vs)))

mesh.from_pydata([tuple(v) for v in all_verts], [], faces)
mesh.update()
for poly, mi in zip(mesh.polygons, face_mats):
    poly.material_index = mi
    poly.use_smooth = True
mesh.materials.append(skin_mat)
mesh.materials.append(lash_mat)
mesh.uv_layers.new(name="UVMap")

obj = bpy.data.objects.new("DrakoEyelids", mesh)
scene.collection.objects.link(obj)
for side, idx in groups.items():
    vg = obj.vertex_groups.new(name="Lid_" + side)
    vg.add(idx, 1.0, "REPLACE")
obj.parent = arm
obj.matrix_parent_inverse = Matrix.Identity(4)
obj.matrix_world = arm_mw
mod = obj.modifiers.new("Armature", "ARMATURE")
mod.object = arm
mod.use_vertex_groups = True
for m in (skin_mat, lash_mat):
    m.use_backface_culling = False

# ------------------------------------------------------------- the rest band
# The blink clips hold scale.y at 1 between blinks, so the bind pose is what the
# viewer shows whenever the pet is not mid-blink.  The bind is the authored card
# flattened along the bone axis: its sweep is divided by REST_DIV, its depth normal
# to the face is left alone.  So the plate's stand-off *is* the height of the band
# at rest, and a plate that rides `clear` over the brow leaves a shelf there - a
# shelf sticking out of the brow is the blade that read as a gash above the eye.
# --rest-sink pulls the skirt into the skin; this proves the band that is left is
# behind the skin, and says where it is not.
REST = {}
for e, plan in zip(eyes, plans):
    if plan["conform"] != "CONFORM":
        continue
    n = np.array(tuple(e["frame"]["n"]), np.float64)
    pts = np.array([tuple(arm_mw @ all_verts[i]) for i in groups[e["side"]]],
                   np.float64)
    dd = surface_depth(pts, n, cast=0.25)
    # surface_depth fires from `cast` metres in front of the point along -n and
    # reports the signed gap to the first hit: the skin is *in front of* the point
    # when the hit arrives early (positive), so the band is proud of the skin by
    # -dd.  A NaN ray means the column overhangs the silhouette altogether: the
    # point is in empty air, which is the worst case of all and must not pass.
    proud = -dd
    ok = np.isfinite(proud)
    worst = float(proud[ok].max()) if ok.any() else float("inf")
    k = int(np.argmax(np.where(ok, proud, -np.inf)))
    hidden = int((proud[ok] <= a.rest_proud).sum())
    print("REST %s band %d/%d behind the skin (<= %.1f mm proud), worst %+.2f mm at"
          " world=%s, rays that miss the head: %d"
          % (e["side"], hidden, len(proud), 1e3 * a.rest_proud, 1e3 * worst,
             np.round(pts[k], 4).tolist(), int((~ok).sum())))
    REST[e["side"]] = {"verts": int(len(proud)), "behind": hidden,
                       "allow_proud": round(1e3 * a.rest_proud, 2),
                       "worst_proud": round(1e3 * worst, 2),
                       "at": np.round(pts[k], 4).tolist(),
                       "miss": int((~ok).sum())}
    if (~ok).any() or worst > a.rest_proud:
        raise SystemExit(
            "REST_BAND_%s_MM_THROUGH_THE_SKIN_%s - the bind pose is what the"
            " viewer shows between blinks, and this band stands %.2f mm in front of"
            " the head at %s (allowed %.2f mm), so only %d of %d vertices are behind"
            " the skin and %d columns overhang the silhouette entirely. Deepen"
            " --rest-sink, widen --taper, or shrink the skirt with --wide/--span-*;"
            " do not raise --rest-proud to make the blade go away."
            % (e["side"], round(1e3 * worst, 2), 1e3 * worst,
               np.round(pts[k], 4).tolist(), 1e3 * a.rest_proud, hidden, len(proud),
               int((~ok).sum())))

# ------------------------------------------------------ the blink, posed for real
# Everything above is algebra about a plate.  What the app shows is the deformed
# mesh at the value the blink curve reaches, and the two only agree if the bone
# runs along the sweep the card was designed for and its local Y is that sweep.
# So pose the lid bones to REST_DIV - the number the curves actually hit - push
# the painted eye out along its own normal and cast back, and count what the card
# is genuinely standing in front of.  Then do it again at scale 1.0, where the
# answer has to be nothing: a card that already hides the eye in the rest pose
# ships as a pet with its eyes shut.
PROBE = 0.03


def posed_lid(scale):
    """(evaluated lid object, depsgraph, world verts) with the lids at one scale.

    Uniform, not just local Y: the bind is compressed on all three axes now, so the
    peak has to restore all three or the closed lid comes out a thirtieth as wide
    as the eye it has to cover.  The action curves are made to match below.
    """
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    for side in ("L", "R"):
        arm.pose.bones["Lid_" + side].scale = (scale, scale, scale)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    co = np.empty(len(ev.data.vertices) * 3, np.float32)
    ev.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3).astype(np.float64)
    mw = np.array(ev.matrix_world)
    return ev, dg, co @ mw[:3, :3].T + mw[:3, 3]


def is_lid(h):
    """Whether a ray hit names the lid card.

    The depsgraph hands back either the object or its evaluated copy depending on
    what it had to deform, and comparing identity against one of them silently
    reported "the blink hides nothing" while the rays were hitting the card the
    whole time.  The card is the only object named DrakoEyelids.
    """
    if h is None:
        return False
    for o in (h, getattr(h, "original", None)):
        if o is not None and o.type == "MESH" and o.name == obj.name:
            return True
    return False


def blink_check(scale_y):
    """What percent of each painted eye the posed lid cards cover, at one scale.

    The ray has to start in front of the plate it is testing, not in front of the
    eye.  A fixed PROBE measured from the eye vertex silently failed on the teen's
    right eye: that eye recesses 6.7 mm behind its own plane while the plate rides
    27.6 mm in front of it, so a 30 mm probe began 4 mm *behind* the lid and the
    cast reported the eye as uncovered when nothing was wrong with the lid.  Each
    vertex is now pushed past the plate height designed for its own column, with a
    margin, so a miss means the card genuinely does not stand over that pixel.
    """
    _ev, dg, lco = posed_lid(scale_y)
    out = {}
    for e, plan in zip(eyes, plans):
        fr = e["frame"]
        n = np.array(tuple(fr["n"]), np.float64)
        p = e["points"]
        u, v, d, plate = plate_field(e, plan)
        ax = np.array([tuple(fr["right"]), tuple(fr["up"]), tuple(fr["n"])],
                      np.float64).T
        lidloc = (lco[groups[e["side"]]] -
                  np.array(tuple(fr["centre"]), np.float64)) @ ax
        along = np.maximum(PROBE, plate - d + a.probe_margin)
        hidden, gaps, misses = 0, [], []
        for k, (pt, push) in enumerate(zip(p, along)):
            hit, loc, _n, _i, hobj, _m = scene.ray_cast(dg, Vector(pt + n * float(push)),
                                                        Vector(-n))
            if not hit or not is_lid(hobj):
                # Say *why* a miss is a miss: the nearest posed lid vertex in the
                # eye's own uv plane, and how far the lid is above the eye there.
                # A gap and a sag between vertices need opposite repairs, and the
                # raw hit name cannot tell them apart.
                duv = np.hypot(lidloc[:, 0] - u[k], lidloc[:, 1] - v[k])
                nn = int(np.argmin(duv))
                hu = np.array(plan["hull"], np.float64) if plan.get("hull") else None
                sd = (float(_hull_sd(hu, u[k] - plan["u_c"], v[k]))
                      if hu is not None else None)
                misses.append((hit, getattr(hobj, "name", None),
                               round(float(np.linalg.norm(np.array(loc, np.float64) - pt)), 4)
                               if hit else None,
                               [round(float(u[k]), 4), round(float(v[k]), 4)],
                               round(float(plate[k] - d[k]), 4),
                               round(1000.0 * float(duv[nn]), 1),
                               round(1000.0 * float(lidloc[nn, 2] - d[k]), 1),
                               None if sd is None else round(1000.0 * sd, 2)))
                continue
            hidden += 1
            gaps.append(float(np.linalg.norm(np.array(loc, np.float64) - pt)))
        if misses:
            near = np.array([m[5] for m in misses], np.float64)
            sds = np.array([m[7] for m in misses if m[7] is not None], np.float64)
            print("BLINK_DIAG %s misses=%d nearest_lid_vertex mm p50=%.1f"
                  " p90=%.1f max=%.1f | hull sd mm p50=%+.2f min=%+.2f max=%+.2f"
                  " | %.0f%% of misses outside the hull"
                  % (e["side"], len(misses), float(np.median(near)),
                     float(np.percentile(near, 90)), float(near.max()),
                     float(np.median(sds)) if sds.size else float("nan"),
                     float(sds.min()) if sds.size else float("nan"),
                     float(sds.max()) if sds.size else float("nan"),
                     100.0 * float((sds > 0).mean()) if sds.size else float("nan")))
        out[e["side"]] = {"scale": scale_y, "eye_verts": int(len(p)), "hidden": hidden,
                          "pct": round(100.0 * hidden / max(1, len(p)), 1),
                          "probe_mm": [round(1000.0 * float(along.min()), 1),
                                       round(1000.0 * float(along.max()), 1)],
                          # Millimetres, and named as such: these gaps are Blender
                          # metres (0.0042), which printed as "4 mm proud of the
                          # paint" while the number was still in metres - the unit in
                          # the label has to match the number in the value.
                          "standoff_mean_mm": round(1000.0 * float(np.mean(gaps)), 2) if gaps else None,
                          "standoff_max_mm": round(1000.0 * float(np.max(gaps)), 2) if gaps else None,
                          "first_misses": misses[:3]}
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return out


def rig_check(e, plan):
    """Does the posed mesh actually land on the plate the algebra covered?

    The curve scales a bone, the modifier deforms the card, and the two only agree
    if the bone runs along the sweep the card was designed for.  Measuring the gap
    between the deformed vertices and the grid the coverage was computed on is what
    turns "the maths says it covers" into "this file blinks".  The eye-frame bounds
    of the posed card say where it went when it did not.
    """
    _ev, _dg, lco = posed_lid(REST_DIV)
    sel = lco[groups[e["side"]]]
    # The designed target, whatever topology produced it: the grid's points on
    # the flat fallback and the disc's own vertices on CONFORM.
    grid = np.array([tuple(p) for p in plan["target"]], np.float64)
    fr = e["frame"]
    ax = np.array([tuple(fr["right"]), tuple(fr["up"]), tuple(fr["n"])], np.float64).T
    lp = (sel - np.array(tuple(fr["centre"]), np.float64)) @ ax
    dev = float(np.max(np.min(np.linalg.norm(grid[:, None, :] - sel[None, :, :], axis=2), axis=1)))
    out = {"max_dev_mm": round(1000.0 * dev, 2), "verts": int(len(sel)),
           "card_u": [round(float(lp[:, 0].min()), 4), round(float(lp[:, 0].max()), 4)],
           "card_v": [round(float(lp[:, 1].min()), 4), round(float(lp[:, 1].max()), 4)],
           "card_d": [round(float(lp[:, 2].min()), 4), round(float(lp[:, 2].max()), 4)],
           "eye_u": [round(float(e["half_w"]), 4), round(float(e["half_w"]), 4)],
           "eye_v": [round(-float(e["half_h"]), 4), round(float(e["half_h"]), 4)]}
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return out


blink_peak = blink_check(REST_DIV)
blink_rest = blink_check(1.0)
for e, plan in zip(eyes, plans):
    plan["blink_peak"] = blink_peak[e["side"]]
    plan["blink_rest"] = blink_rest[e["side"]]
    plan["rig"] = rig_check(e, plan)
    r = plan["rig"]
    print("RIG %s posed card within %s mm of the designed plate ( verts=%d)"
          " | card u=%s v=%s d=%s against eye u=+-%s v=+-%s -> %s"
          % (e["side"], r["max_dev_mm"], r["verts"], r["card_u"], r["card_v"], r["card_d"],
             r["eye_u"][0], r["eye_v"][1],
             "rig delivers the plate" if r["max_dev_mm"] <= a.max_rig_dev_mm
             else "THE POSED CARD IS NOT THE DESIGNED ONE"))
    if plan["blink_peak"]["pct"] < a.min_hidden:
        print("BLINK_MISS %s %s" % (e["side"], plan["blink_peak"]["first_misses"]))
    print("BLINK %s closed: hides %s%% of %d eye verts (lid %s-%s mm proud of the"
          " paint, probed from %s-%s mm) | rest: hides %s%% -> %s"
          % (e["side"], plan["blink_peak"]["pct"], plan["blink_peak"]["eye_verts"],
             plan["blink_peak"]["standoff_mean_mm"], plan["blink_peak"]["standoff_max_mm"],
             plan["blink_peak"]["probe_mm"][0], plan["blink_peak"]["probe_mm"][1],
             plan["blink_rest"]["pct"],
             "covers the eye at rest" if plan["blink_rest"]["pct"] > a.max_rest_hidden
             else "eye open at rest, blinks shut"))

fails = []
for e, plan in zip(eyes, plans):
    cov, bp, br, rg = plan["coverage"], plan["blink_peak"], plan["blink_rest"], plan["rig"]
    if cov["covered_pct"] < a.min_cover:
        fails.append("%s_SPANS_ONLY_%s_PCT" % (e["side"], cov["covered_pct"]))
    if cov["fronted_pct"] < a.min_fronted:
        fails.append("%s_IN_FRONT_ONLY_%s_PCT" % (e["side"], cov["fronted_pct"]))
    if rg["max_dev_mm"] > a.max_rig_dev_mm:
        fails.append("%s_POSED_CARD_%s_MM_OFF_DESIGN" % (e["side"], rg["max_dev_mm"]))
    if bp["pct"] < a.min_hidden:
        fails.append("%s_BLINK_HIDES_ONLY_%s_PCT" % (e["side"], bp["pct"]))
    if br["pct"] > a.max_rest_hidden:
        fails.append("%s_REST_COVERS_%s_PCT" % (e["side"], br["pct"]))
print("LID_VERIFY %s" % (" ".join(fails) if fails else
                         "PASS - both eyes fully covered at the blink peak, clear at rest"))
if fails and not a.allow_invisible:
    raise SystemExit("LID_VERIFY FAILED: " + " ".join(fails) +
                     " - nothing was exported; retune --wide/--span-*/--clear/--dome")

# ------------------------------------------------------------------- report
rep = {"stage": stage, "src": os.path.basename(src), "rest_div": REST_DIV,
       "mode": mode, "eyes_json": os.path.basename(a.eyes),
       "cover_margin": a.cover_margin,
       "clear": a.clear, "rows": a.rows, "cols": a.cols,
       "span": [a.span_top, a.span_bottom], "wide": a.wide, "tall": a.tall,
       "eyes": [], "verts": len(all_verts), "faces": len(faces)}
for e, plan in zip(eyes, plans):
    stretched = np.array([tuple(p) for p in plan["target"]], np.float64)
    bindv = np.array([tuple(obj.matrix_world @ v.co) for v in obj.data.vertices], np.float64)
    side = e["side"]
    sel = [i for i in groups[side]]
    fr = e["frame"]
    rep["eyes"].append({
        "side": side, "rect": e["rect"], "island_verts": e["verts"],
        "eye_verts": e.get("eye_verts", e["verts"]),
        "island_faces": e["faces"], "island_up_dev_deg": e.get("up_can_dev"),
        "island_uv_box": e["uv_box"], "island_clipped": e["clipped"],
        "island_centre": [round(float(v), 4) for v in e["centre"]],
        "island_half": [round(e["half_w"], 4), round(e["half_h"], 4)],
        "island_full": [round(e["full_w"], 4), round(e["full_h"], 4)],
        "frame_centre": [round(float(v), 4) for v in fr["centre"]],
        "frame_almond_centre": [round(float(v), 4) for v in fr["almond_centre"]],
        "frame_half": [round(fr["half_w"], 4), round(fr["half_h"], 4)],
        "paint_half": [round(fr["paint_half_w"], 4), round(fr["paint_half_h"], 4)],
        "paint_box": [round(float(v), 4) for v in fr["paint_box"]],
        "conform": plan["conform"], "plate_clear": round(plan["clear"], 4),
        "span": [round(plan["top_y"], 4), round(plan["bottom_y"], 4)],
        # The measured footprint the card was sized from, per arm, in the card's own
        # frame: without it a later reader cannot tell a lid that hugs the eye from
        # one that reaches past it, which is the difference between the gash and the
        # fix.
        "footprint_u": plan["foot_u"], "footprint_v": plan["foot_v"],
        "card_u": [round(plan["u_lo"], 4), round(plan["u_hi"], 4)],
        "corner_proud": (None if plan["corner_proud"] is None else
                         round(float(plan["corner_proud"]), 4)),
        "depth": [round(d, 4) for d in e["depth"]],
        "recede": round(fr["recede"], 4),
        "relief": round(fr["relief"], 4),
        "offset": round(plan["offset"], 4),
        "coverage": plan["coverage"],
        "rest_band": REST.get(side),
        "blink_at_peak": plan["blink_peak"],
        "blink_at_rest": plan["blink_rest"],
        "posed_vs_design": plan["rig"],
        "lean": round(float(plan["dir"].y), 4),
        "n": [round(float(v), 4) for v in fr["n"]],
        "up": [round(float(v), 4) for v in fr["up"]],
        "right": [round(float(v), 4) for v in fr["right"]],
        "bone_head": [round(float(v), 4) for v in plan["head"]],
        "bone_dir": [round(float(v), 4) for v in plan["dir"]],
        "bone_roll": [round(float(v), 4) for v in plan["roll"]],
        "blink_bounds_min": [round(float(v), 4) for v in stretched.min(axis=0)],
        "blink_bounds_max": [round(float(v), 4) for v in stretched.max(axis=0)],
        "bind_size": [round(float(v), 5) for v in (bindv[sel].max(axis=0) - bindv[sel].min(axis=0))],
    })
# ---------------------------------------------------------------- lid sync
sync = None
if a.sync_lids:
    # A card the blink cannot reach is one bug; a blink that shuts one eye and
    # leaves the other half open is another, and the shipped curves had the
    # second one: drako_eyelids.py wrote Lid_R's non-rest keys 0.7 frames after
    # Lid_L's.  The left lid is the source of truth, the right gets its keys.
    sync = lid_curves.sync_lids(bpy.data.actions)
    rep["lid_sync"] = {"clips": len(sync),
                       "changed": [s["clip"] for s in sync if s["changed"]],
                       "desynced": [s["clip"] for s in sync if not s["identical"]]}
    bad = rep["lid_sync"]["desynced"]
    for s in sync:
        print("LID_SYNC %s bags=%d changed=%s identical=%s"
              % (s["clip"], s["bags"], ",".join(s["changed"]) or "none", s["identical"]))
    print("LID_SYNC %d clips, %d repaired, %d still desynced -> %s"
          % (len(sync), len(rep["lid_sync"]["changed"]), len(bad),
             "both eyes blink together" if not bad else "STILL DESYNCED"))
    if bad:
        raise SystemExit("LID_SYNC FAILED in %s - nothing was exported" % bad)

# ------------------------------------------------------- uniform blink scale
# The bind pose is the card compressed 1/REST_DIV on all three bone axes, so the
# closed lid only grows back to the plate the coverage was measured on if the clip
# scales all three.  Every shipped clip animates local Y alone (X and Z sit at 1),
# which would land a 30x-taller card a thirtieth as wide - a red spike over one
# corner of the eye.  Mirror Y onto X and Z in every action, then prove it.
uni = [u for u in (lid_curves.uniform_scale(act) for act in bpy.data.actions)
       if u["bags"] or u["missing_y"]]
uni_bad = []
for act in bpy.data.actions:
    if not any(lid_curves.scale_curves(cb, s)
               for cb in lid_curves.channelbags(act) for s in lid_curves.LID_SIDES):
        continue
    st = lid_curves.uniform_state(act)
    if not all(st.values()):
        uni_bad.append("%s:%s" % (act.name, ",".join(
            s for s, ok in st.items() if not ok)))
for u in uni:
    if u["written"] or u["missing_y"]:
        print("LID_UNIFORM %s bags=%d wrote=%s missing_y=%s"
              % (u["clip"], u["bags"], ",".join(u["written"]) or "none",
                 ",".join(u["missing_y"]) or "none"))
rep["lid_uniform"] = {
    "clips": len(uni),
    "written": {u["clip"]: u["written"] for u in uni if u["written"]},
    "missing_y": {u["clip"]: u["missing_y"] for u in uni if u["missing_y"]},
    "not_uniform": uni_bad}
print("LID_UNIFORM %d clips with lid channels, %d repaired, not uniform: %s"
      % (len(uni), sum(1 for u in uni if u["written"]),
         ",".join(uni_bad) or "none"))
if uni_bad:
    raise SystemExit("LID_UNIFORM FAILED in %s - nothing was exported" % uni_bad)

# The exporter reads the file's bind state, not this session's probes.
print("LID_FIX " + json.dumps(rep, indent=1))
if a.report:
    with open(os.path.abspath(a.report), "w") as f:
        json.dump(rep, f, indent=2)

# So the bind state has to leave the file exactly as it arrived, and the clips have
# to leave at the lengths they came in at: both are the shared exporter's job, with
# the source GLB as the frame-count baseline (see tools/loop_keys.py).
#
# Put the body's armature modifier back first.  The exporter derives a glTF `skin`
# from that modifier, so an asset exported with it still removed writes the body as
# a rigid mesh - the adult did exactly that (DrakoMesh came out with neither `skin`
# nor `JOINTS_0`), and every key-level audit passed while the app would have shown a
# body that never follows the bones.  The vertex groups were never touched, so
# re-adding the modifier restores the original binding.
if not any(m.type == "ARMATURE" and m.object == arm for m in body.modifiers):
    rec = body.modifiers.new("Armature", "ARMATURE")
    rec.object = arm
    rec.show_viewport = rec.show_render = True
    print("LID_FIX re-attached %s to the armature before export" % body.name)

glb_export.export_glb(out, src=src, arm=arm, tag="LID_FIX", reset_pose=True)
