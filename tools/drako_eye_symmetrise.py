"""Copy Drako's good eye island onto the side whose paint is damaged.

Why this exists
---------------
The teen's two atlas eye islands are not the same drawing.  Cropped straight out
of `1_Image_0` of `remaja_headyaw.glb`:

* the left island is a complete round eye - dark upper lash crescent, white
  sclera ring, amber iris, black pupil with two catchlights;
* the right island is the same parts scrambled: the iris is a crescent pinned to
  the lower-left, the pupil sits off-centre, a white scratch is dragged across
  the dark mass, and a gold streak runs out of the eye into the surrounding
  scales.

`drako_eye_measure.py` now proves it numerically instead of visually: on the
right side its paint flood finds 6017 px against 12093 on the left, the aperture
comes out 1.40:1 instead of 1.00:1, the darkest quartile sits 110 degrees off
the lid direction, and the iris flood collapses to 4 px.  It flags the side
`LID_SIDE_111deg` and drops it from the canonical frame.  The lid pass then
grades the right card against that side's own broken footprint and reports
`R_BLINK_HIDES_ONLY_72.9_PCT` - correctly, because the region it is measuring is
not an eye.

The fix belongs in the atlas, not in the gates.  `drako_eye_map.py` already
states the principle - both eyes have to come from *one* drawing, because the
body is a single continuous UV sheet and the two eyes sit in different places on
it, so no rect and no colour rule can produce a matched pair.  That tool draws a
new eye from a palette tuned for the adult's almond, which is a different
question: here the left eye is already the look the user accepted, and the right
one simply is not it.

So this tool does the minimum: it resamples the trusted island into the
canonical eye space through that side's measured affine, and writes it out again
through the *other* side's affine.  The canonical frame is a mirror frame (`right`
points outward on each side), so one drawing lands mirror-symmetric on the two
eyes by construction.  Nothing is invented and nothing outside the destination
island changes.

What the copy is allowed to touch
---------------------------------
A canonical ellipse alone is not the eye.  The atlas is one continuous sheet, so
the texels around the drawn aperture belong to the scales of the same UV island,
and a copy bounded only by the ellipse carries the source's skin ring onto the
destination: the repaired eye then sits inside a smooth red halo that cuts across
the scale pattern (seen on the teen's right eye, 2026-11-05).  The measure pass
already knows better - `local_triangles` is the exact set of atlas triangles the
destination eye's own faces sample - so that footprint, not the ellipse, bounds
both the paste and the old-paint inpaint.  The ellipse stays as a guard: it is
what recognises the source drawing, and a destination footprint that does not fit
inside a slightly inflated ellipse is refused as a measurement that grabbed the
whole socket.  The footprint only exists in the current measure report, so a
report without it is refused rather than silently falling back to the ellipse.

Run it with the system interpreter (cv2 lives there, not in Blender):

    python tools/drako_eye_symmetrise.py \
        --measure=tools/qa_rig/.../remaja_headyaw_eye2.json \
        --atlas=<dir>/1_Image_0.jpg --out=<dir2>/1_Image_0.jpg \
        --from=L --to=R --tag=remaja --outdir=<dir2>

The atlas is then put back with `tools/drako_texture_reapply.py`, and the
measure pass is re-run: the repaired side has to measure like its partner or the
paint is not finished.
"""
import argparse
import json
import os

import cv2
import numpy as np


def as3(m):
    """2x3 affine -> 3x3 homogeneous."""
    return np.vstack([np.asarray(m, np.float64), [0.0, 0.0, 1.0]])


def canvas_to_atlas(M, u0, v0, s):
    """canvas pixel (i, j) -> atlas pixel, for a canvas of u0 + i/s .. v0 + j/s.

    This is also the matrix cv2.warpAffine wants when the CANVAS is the source and
    the atlas the destination: OpenCV's plain (non WARP_INVERSE_MAP) matrix is the
    src -> dst map, and it inverts it internally to gather.  Handing it the inverse
    instead scatters the drawing to the mirror position - which is invisible on a
    side whose UV frame is axis-aligned and a ~80 deg rotation on one whose frame
    is not.  See tools/qa_rig/tmp_warp_convention.py for the probe that settles it.
    """
    grid = np.array([[1.0 / s, 0.0, u0], [0.0, 1.0 / s, v0], [0.0, 0.0, 1.0]])
    return (as3(M) @ grid)[:2]


def atlas_to_canvas(M, u0, v0, s):
    """atlas pixel -> canvas pixel: the matrix for warping the atlas INTO a canvas."""
    grid = np.array([[s, 0.0, -s * u0], [0.0, s, -s * v0], [0.0, 0.0, 1.0]])
    return (grid @ np.linalg.inv(as3(M)))[:2]


def xphoto_mask_means_keep():
    """Does this OpenCV's xphoto FSR read the mask as the area to KEEP?

    The documented convention is "non-zero pixels indicate the area that needs
    to be inpainted", and the OpenCV 5.0.0 wheel used here does the opposite:
    on a flat test sheet the marked square is preserved and everything else is
    rebuilt from it.  Shipping the documented mask therefore inpainted the
    *skin around* the eye from the eye's own palette while leaving the damaged
    paint untouched - the dark wedge and the olive smear seen at the repaired
    eye's corner on 2026-11-05.  Detect the convention on a throwaway 64x64
    canvas instead of hardcoding an inversion that would break on a fixed
    build.
    """
    src = np.zeros((64, 64, 3), np.uint8)
    src[:] = (0, 0, 200)
    src[20:44, 20:44] = (0, 200, 0)
    m = np.zeros((64, 64), np.uint8)
    m[20:44, 20:44] = 255
    dst = src.copy()
    cv2.xphoto.inpaint(src, m, dst, cv2.xphoto.INPAINT_FSR_FAST)
    # Correct semantics rebuild the marked square (it becomes red); the inverted
    # build keeps it green.  Compare against the marked colour, not against a
    # hardcoded red, so a different reconstruction still reads as "filled".
    kept = np.abs(dst[32, 32].astype(np.int16) -
                  src[32, 32].astype(np.int16)).max() < 20
    return bool(kept)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure", required=True,
                    help="a drako_eye_measure.py report (needs canonical + affines)")
    ap.add_argument("--atlas", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--from", dest="src_side", default="L")
    ap.add_argument("--to", dest="dst_side", default="R")
    ap.add_argument("--tag", default="eye")
    ap.add_argument("--margin", type=float, default=1.28,
                    help="the painted ellipse, as a multiple of the measured half "
                         "sizes, is what gets copied; everything outside it stays "
                         "byte-for-byte as it was")
    ap.add_argument("--pad-mm", type=float, default=6.0,
                    help="canvas padding around the ellipse, in metres x 1000")
    ap.add_argument("--ring-mm", type=float, default=10.0,
                    help="width of the trusted eye's own skin ring, carried with "
                         "the drawing so the repaired eye sits in the same soft "
                         "shadow and scales as its partner instead of in an "
                         "inpainted ring; 0 pastes the drawing alone")
    ap.add_argument("--ring-feather-mm", dest="ring_feather_mm", type=float,
                    default=5.0,
                    help="width of the fade from that ring into the destination's "
                         "skin, in millimetres")
    ap.add_argument("--quality", type=int, default=95)
    ap.add_argument("--inpaint", choices=("fsr-fast", "fsr-best", "telea"),
                    default="fsr-fast",
                    help="how the old drawing is rebuilt under the new one.  The "
                         "visible part of that mask is the ring of skin around the "
                         "drawing, so frequency-selective reconstruction (default) "
                         "rebuilds scales from the intact surroundings; Telea only "
                         "averages them into a colour smear and is kept for "
                         "comparison")
    ap.add_argument("--outdir", default=None)
    args = ap.parse_args()

    rep = json.load(open(args.measure, encoding="utf-8"))
    canon = rep.get("canonical") or {}
    recs = {r["side"]: r for r in rep["eyes"] if r.get("side")}
    for side in (args.src_side, args.dst_side):
        if side not in recs:
            raise SystemExit("NO_EYE_RECORD %s in %s" % (side, args.measure))
    used = list(canon.get("sides_used") or [s for s in recs])
    if args.src_side not in used:
        raise SystemExit("SOURCE_SIDE_NOT_TRUSTWORTHY %s (canonical frame came "
                         "from %s) - copying from a refused eye would copy the "
                         "damage instead of repairing it"
                         % (args.src_side, ",".join(used)))
    src, dst = recs[args.src_side], recs[args.dst_side]
    for r in (src, dst):
        if not r.get("affine_eye_to_atlas"):
            raise SystemExit("NO_AFFINE_%s - re-run drako_eye_measure.py" % r["side"])

    atlas = cv2.imread(args.atlas, cv2.IMREAD_COLOR)
    if atlas is None:
        raise SystemExit("CANNOT_READ_ATLAS %s" % args.atlas)
    AH, AW = atlas.shape[:2]
    TW, TH = rep["atlas"]
    if (AW, AH) != (TW, TH):
        raise SystemExit("ATLAS_SIZE_MISMATCH file=%dx%d json=%dx%d"
                         % (AW, AH, TW, TH))
    fimg = atlas.astype(np.float64) / 255.0

    Ms = as3(src["affine_eye_to_atlas"])[:2]
    Md = as3(dst["affine_eye_to_atlas"])[:2]

    # The destination's own eye faces, in atlas pixels, from the measure report.
    # This is what the copy may touch; the ellipse below is only the guard that
    # recognises the source drawing and sizes the canvas.
    if not dst.get("paint_graded", False):
        raise SystemExit("DEST_FOOTPRINT_NOT_GRADED %s - the measure pass kept "
                         "the whole socket because its paint grade dropped, so "
                         "its triangles are not the eye and a copy bounded by "
                         "them would paint the scales; re-measure, do not paste"
                         % args.dst_side)
    dst_tris = dst.get("local_triangles") or []
    if len(dst_tris) < 20:
        raise SystemExit("NO_DEST_FOOTPRINT %s has %d local triangles - the "
                         "report predates the face scoping or the eye flood "
                         "failed; without the destination's own faces the only "
                         "bound would be the ellipse, which is exactly the skin "
                         "halo this tool now refuses" % (args.dst_side,
                                                        len(dst_tris)))
    footprint = np.zeros((AH, AW), np.uint8)
    for tri in dst_tris:
        cv2.fillPoly(footprint, [np.array(tri, np.int32).reshape(-1, 1, 2)], 255)
    # A 2 px dilation covers bilinear bleed at the face seams; it is 2 atlas px,
    # i.e. ~2.4 mm of surface on the teen, not a skin ring.
    footprint = cv2.dilate(footprint, np.ones((5, 5), np.uint8))
    fp_px = int((footprint > 0).sum())

    hw, hh = float(canon["half_w"]), float(canon["half_h"])
    off = [float(v) for v in (canon.get("almond_off") or [0.0, 0.0, 0.0])][:2]
    pad = args.pad_mm / 1000.0
    # The source drawing, segmented in ATLAS pixels.  Doing this on the 1000 px/m
    # canonical canvas looked equivalent and was not: the canvas upsamples the
    # teen's sheet 1.5x, and CLOSE 5x5 there bridged the one-or-two atlas-px gap
    # between the eye's lash and the pale lid's rim.  The component then swallowed
    # the whole lid and its outline (13175 canvas px against 4972 atlas px,
    # measured 2026-11-05), the ring around it carried lid paint onto the other
    # side, and the render showed a cream/red smear where the lid had been.  In
    # atlas space the trusted eye is one clean component: 99.5% of it lies inside
    # its own measured face footprint, and the lid is a different component.
    a_r, a_g, a_b = fimg[..., 2], fimg[..., 1], fimg[..., 0]
    a_max, a_min = fimg.max(2), fimg.min(2)
    apaint = (((a_r > 0.45) & (a_g >= 0.26) & (a_g <= 0.62) & (a_b < 0.42) &
               (a_r - a_b > 0.20)) |
              (a_max < 0.30) |
              (a_min > 0.78))
    want_src = Ms[:2] @ np.array([off[0], off[1], 1.0])
    ys_a, xs_a = np.nonzero(apaint)
    if len(xs_a) == 0:
        raise SystemExit("SOURCE_CANVAS_HAS_NO_EYE_PAINT - %s's atlas has no "
                         "eye-paint texel at all, so there is nothing to copy"
                         % args.src_side)
    src_anchor = int(np.argmin((xs_a - want_src[0]) ** 2 +
                               (ys_a - want_src[1]) ** 2))
    src_anchor_off = float(np.hypot(xs_a[src_anchor] - want_src[0],
                                    ys_a[src_anchor] - want_src[1]))
    if src_anchor_off > 12.0:
        raise SystemExit("SOURCE_PUPIL_NOT_IN_PAINT - the source affine puts the "
                         "pupil at (%.1f,%.1f) but the nearest eye paint is %.1f "
                         "px away; the report and the atlas are out of step, so "
                         "nothing was written"
                         % (want_src[0], want_src[1], src_anchor_off))
    n_sa, lab_sa = cv2.connectedComponents(apaint.astype(np.uint8))
    draw_a = (lab_sa == lab_sa[ys_a[src_anchor], xs_a[src_anchor]]).astype(np.uint8) * 255
    n_draw_a = int((draw_a > 0).sum())
    # The trusted eye is ~5000 atlas px on the teen; an order of magnitude either
    # way means the class found a scale crack or the whole sheet.
    if n_draw_a < 200 or n_draw_a > 40000:
        raise SystemExit("SOURCE_DRAWING_NOT_AN_EYE - the component holding %s's "
                         "pupil is %d atlas px (an eye is ~5000), so the paint "
                         "class merged it with the scales; nothing was written"
                         % (args.src_side, n_draw_a))
    # One atlas pixel takes the antialiased rim of the lash into the copy; the
    # destination feather is a canvas pixel, i.e. smaller than this.
    draw_a = cv2.dilate(draw_a, np.ones((3, 3), np.uint8))

    # Canvas bounds come from the drawing's own extent, mapped back to canonical
    # metres, so the read pass cannot clip it.  The old bounds were sized from
    # the almond ellipse, which is a guard, not the drawing: the trusted lash
    # reaches past it, and a 20 mm growth loop was needed to stop pasting a cut
    # lash (the straight BORDER_REPLICATE seam seen on the teen, 2026-11-05).
    ys_da, xs_da = np.nonzero(draw_a)
    inv_s = np.linalg.inv(as3(Ms))
    can = (np.column_stack([xs_da, ys_da, np.ones(len(xs_da))]) @ inv_s.T)[:, :2]
    cu0, cu1 = float(can[:, 0].min()), float(can[:, 0].max())
    cv0, cv1 = float(can[:, 1].min()), float(can[:, 1].max())
    # Ring and feather are painted outside the drawing and are canonical
    # millimetres, so they grow the bounds directly.
    grow = ((args.ring_mm + 2.0 * args.ring_feather_mm) / 1000.0
            if args.ring_mm > 0.0 else 0.0)
    u0 = min(cu0 - grow - pad, off[0] - hw * args.margin - pad)
    u1 = max(cu1 + grow + pad, off[0] + hw * args.margin + pad)
    v0 = min(cv0 - grow - pad, off[1] - hh * args.margin - pad)
    v1 = max(cv1 + grow + pad, off[1] + hh * args.margin + pad)
    # The footprint can reach past the canonical ellipse (its 3D window is
    # 1.55x the aperture), so the canvas has to contain it in canonical metres
    # or the write pass would sample BORDER_CONSTANT for part of the eye.
    invd = np.linalg.inv(as3(Md))
    fv = np.array(dst_tris, np.float64).reshape(-1, 2)
    fc = (np.column_stack([fv, np.ones(len(fv))]) @ invd.T)[:, :2]
    fu0, fu1 = float(fc[:, 0].min()), float(fc[:, 0].max())
    fvv0, fvv1 = float(fc[:, 1].min()), float(fc[:, 1].max())
    u0, u1 = min(u0, fu0 - pad), max(u1, fu1 + pad)
    v0, v1 = min(v0, fvv0 - pad), max(v1, fvv1 + pad)
    # A footprint that does not fit a 1.8x inflated ellipse is not an eye: the
    # 3D footprint window is 1.55x the measured half sizes, so anything beyond
    # 1.8x means the flood grabbed the socket or the neck.
    over = max(abs(fu0 - off[0]), abs(fu1 - off[0])) / max(hw, 1e-9)
    over_v = max(abs(fvv0 - off[1]), abs(fvv1 - off[1])) / max(hh, 1e-9)
    if over > 1.8 or over_v > 1.8:
        raise SystemExit("FOOTPRINT_TOO_BIG %s spans %.2fx%.2f of the canonical "
                         "half sizes (limit 1.8) - the triangles are not the "
                         "eye, so nothing was written"
                         % (args.dst_side, over, over_v))
    # One canvas pixel per millimetre of the eye: the islands are ~90 px across a
    # ~0.11 m aperture, so 1000 px/m renders the copy at about the destination's
    # own texel density without oversampling the whole sheet.
    s = 1000.0
    W, H = int(round((u1 - u0) * s)) + 1, int(round((v1 - v0) * s)) + 1

    # The ellipse is only the guard: it sizes nothing now and is what the source
    # paint test recognises.  The copy itself is the drawing component.
    mask_cv = np.zeros((H, W), np.uint8)
    cv2.ellipse(mask_cv,
                (int(round((off[0] - u0) * s)), int(round((off[1] - v0) * s))),
                (int(round(hw * args.margin * s)),
                 int(round(hh * args.margin * s))),
                0.0, 0, 360, 255, -1)

    # cv2.warpAffine's matrix runs source -> destination, so the read pass
    # wants atlas->canvas and the write pass wants canvas->atlas.
    canvas = cv2.warpAffine(fimg, atlas_to_canvas(Ms, u0, v0, s), (W, H),
                            flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_REPLICATE)
    # The copy is the atlas component itself, warped in, not a re-segmentation of
    # this canvas.  Pasting the ellipse carried the source's skin ring (the teen's
    # right-eye halo); re-segmenting the upsampled canvas swallowed the pale lid
    # (see the atlas-space note above).  The component is already bounded by the
    # drawing's own paint, so what lands is exactly what was recognised.
    draw = cv2.warpAffine(draw_a, atlas_to_canvas(Ms, u0, v0, s), (W, H),
                          flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT)
    draw = (draw > 127).astype(np.uint8) * 255
    if int((draw > 0).sum()) < 200:
        raise SystemExit("SOURCE_DRAWING_EMPTY - %s's atlas component warped to "
                         "%d canvas px; the source island cannot be recognised, "
                         "so nothing was written"
                         % (args.src_side, int((draw > 0).sum())))
    ys_d, xs_d = np.nonzero(draw)
    if (xs_d.min() <= 2 or ys_d.min() <= 2 or
            xs_d.max() >= W - 3 or ys_d.max() >= H - 3):
        raise SystemExit("SOURCE_DRAWING_CLIPPED - the drawing still touches the "
                         "canvas border even though the bounds were computed from "
                         "its own extent; the affine and this canvas disagree, so "
                         "nothing was written")
    print("SRC_DRAWING atlas=%d canvas=%d of %d (%.1f%%)"
          % (n_draw_a, int((draw > 0).sum()), W * H,
             100.0 * (draw > 0).sum() / (W * H)))

    # A warp can be perfectly well-formed and still be pointed at the wrong patch
    # of skin, so the thing being copied has to be *recognised* before it is
    # copied: the trusted ellipse has to be holding iris and pupil pigment.
    sel = canvas[mask_cv > 127].reshape(-1, 3)
    smax = sel.max(1)
    # cv2 reads BGR, so channel 2 is red - the same order the measure pass's
    # AMBER mask uses.
    amber = float(((sel[:, 2] > 0.45) & (sel[:, 1] >= 0.26) & (sel[:, 1] <= 0.62) &
                   (sel[:, 0] < 0.42) & (sel[:, 2] - sel[:, 0] > 0.20)).mean())
    dark = float((smax < 0.30).mean())
    print("SRC_PAINT inside the trusted ellipse: amber=%.3f dark=%.3f of %d px"
          % (amber, dark, len(sel)))
    if amber < 0.05 or dark < 0.05:
        raise SystemExit("SOURCE_CANVAS_HAS_NO_EYE_PAINT (amber=%.3f dark=%.3f) - "
                         "the read pass is not looking at %s's eye; the report and "
                         "the atlas are out of step, so copying would smear skin "
                         "onto %s" % (amber, dark, args.src_side, args.dst_side))

    # The drawing alone is not the whole eye *look*: the trusted island carries
    # its own surround - the soft lash shadow, the scales above, the cream lid
    # below - and that ring is real dragon skin, not an average.  Carrying it is
    # what stops the repaired eye from sitting in an inpainted patch: inpainting
    # cannot rebuild a scale, so any visible fill next to the drawing reads as a
    # smear.  The ring is faded into the destination over --ring-feather-mm and
    # composited under the drawing; the drawing itself stays byte-exact.
    ring_c = np.zeros((H, W), np.uint8)
    if args.ring_mm > 0.0:
        rpx = int(round(args.ring_mm))  # canvas is 1000 px/m, so 1 px = 1 mm
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * rpx + 1, 2 * rpx + 1))
        grown = cv2.dilate(draw, k)
        ring_c = cv2.bitwise_and(grown, cv2.bitwise_not(draw))
        ring_c = cv2.GaussianBlur(ring_c, (0, 0),
                                  max(0.8, args.ring_feather_mm / 2.5))
        print("SRC_RING %d mm, feather %.1f mm -> %d canvas px"
              % (args.ring_mm, args.ring_feather_mm, int((ring_c > 51).sum())))

    ell_dst = cv2.warpAffine(mask_cv, canvas_to_atlas(Md, u0, v0, s), (AW, AH),
                             flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    placed = cv2.warpAffine(canvas, canvas_to_atlas(Md, u0, v0, s), (AW, AH),
                            flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)

    # Where the drawing has to land, computed straight from the destination
    # affine rather than from the warp, so a matrix handed to cv2 the wrong way
    # round is caught here instead of shipping as a rotated eye.  The check uses
    # the ellipse warp, not the footprint, because it tests the matrix.
    want = Md[:2] @ np.array([off[0], off[1], 1.0])
    got = np.array([np.nonzero(ell_dst > 51)[1].mean(),
                    np.nonzero(ell_dst > 51)[0].mean()], np.float64)
    if len(np.nonzero(ell_dst > 51)[1]) == 0 or float(np.hypot(*(got - want))) > 8.0:
        raise SystemExit("LANDING_POINT_OFF by %.1f px (mask centroid %s, the "
                         "destination affine says %s) - the warp and the measured "
                         "atlas frame disagree about where this eye is, so nothing "
                         "was written" % (float(np.hypot(*(got - want))),
                                          np.round(got, 1).tolist(),
                                          np.round(want, 1).tolist()))
    print("LANDING mask centroid=(%.1f,%.1f) affine says=(%.1f,%.1f) off=%.1f px"
          % (got[0], got[1], want[0], want[1], float(np.hypot(*(got - want)))))

    # The atlas is one continuous sheet, so a rect around the eye is not the eye:
    # the measure pass reports the faces that merely *border* the paint box, and on
    # the teen right side 232 of them sit >0.10 m away in the model - other islands
    # whose texels this copy would otherwise stamp.  Their own UV triangles are
    # rasterised and cut out of the mask, so the repair can only ever touch the
    # surface that actually carries this eye.
    foreign = np.zeros((AH, AW), np.uint8)
    for tri in (dst.get("foreign_triangles") or []):
        cv2.fillPoly(foreign, [np.array(tri, np.int32).reshape(-1, 1, 2)], 255)
    foreign = cv2.dilate(foreign, np.ones((3, 3), np.uint8))
    # What the copy replaces: the source drawing, wherever it lands on the
    # destination's sheet, and nowhere else.  It is deliberately NOT clipped by
    # the destination footprint: on the damaged side that footprint is measured
    # from the damage (the broken teen eye is smaller and shifted outward), so
    # clipping to it would shave the repaired eye to the shape of the old wrong
    # one.  The footprint is reported below as a cross-check instead.
    draw_dst = cv2.warpAffine(draw, canvas_to_atlas(Md, u0, v0, s), (AW, AH),
                              flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    draw_dst = (draw_dst > 127).astype(np.uint8) * 255
    paste = cv2.bitwise_and(draw_dst, cv2.bitwise_not(foreign))
    # Feather the seam one pixel; it is an antialias on skin, not a skin ring.
    paste = cv2.GaussianBlur(paste, (3, 3), 0.0)

    ring_dst = np.zeros((AH, AW), np.uint8)
    if args.ring_mm > 0.0:
        ring_dst = cv2.warpAffine(ring_c, canvas_to_atlas(Md, u0, v0, s), (AW, AH),
                                  flags=cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_CONSTANT)
        ring_dst[foreign > 0] = 0
        ring_px = int((ring_dst > 51).sum())
        print("RING %s px=%d on the destination (spill on foreign cut)"
              % (args.dst_side, ring_px))
        if ring_px < 100:
            raise SystemExit("RING_EMPTY - the trusted ring lands on %d px of the "
                             "destination atlas; the affines disagree, so nothing "
                             "was written" % ring_px)
    covered = int(((paste > 51) & (footprint > 0)).sum())
    spill = int(((draw_dst > 51) & (foreign > 0)).sum())
    print("FOOTPRINT %s tris=%d px=%d  drawing lands=%d px (covers %.0f%% of the "
          "footprint)  foreign_px=%d"
          % (args.dst_side, len(dst_tris), fp_px, int((draw_dst > 0).sum()),
             100.0 * covered / max(1, fp_px), spill))
    if fp_px < 200:
        raise SystemExit("FOOTPRINT_EMPTY %s rasterised to %d px - the report's "
                         "triangles are not where the atlas is, so nothing was "
                         "written" % (args.dst_side, fp_px))
    if covered < 0.35 * fp_px:
        raise SystemExit("DRAWING_MISSES_THE_EYE %s - the drawing lands on %.0f%% "
                         "of the destination's own eye faces; the affines and the "
                         "footprint disagree, so nothing was written"
                         % (args.dst_side, 100.0 * covered / max(1, fp_px)))

    # The old paint has to go before the new one arrives: the teen right island
    # carries a white scratch and an amber tail that dribbles down the cheek, and
    # compositing on top of them would leave them ringing the repaired eye.  The
    # removal is the measure pass's eye-paint class - never a free ellipse (its
    # dark scale cracks were what got smoothed into the red halo) and not every
    # dark texel in the atlas box either.  The smooth-skin guard is deliberately
    # absent: at this point the old lash is itself a saturated red-brown and the
    # guard would protect the very damage being repaired.
    mx, mn = fimg.max(2), fimg.min(2)
    fr, fg, fb = fimg[..., 2], fimg[..., 1], fimg[..., 0]
    eye_paint = (((fr > 0.45) & (fg >= 0.26) & (fg <= 0.62) & (fb < 0.42) &
                  (fr - fb > 0.20)) |
                 (mx < 0.30) |
                 (mn > 0.78))
    # The graded footprint is measured from the damage, so on this side it is
    # smaller than the drawing that made it: 442 of the old drawing's 7064 px sit
    # up to 25 atlas px outside it (measured on the teen, 2026-11-05), and those
    # are exactly the scratch end and the amber tail that stayed visible beside
    # the repaired eye.  The old drawing as a whole is the eye-paint component
    # that holds the destination's own pupil; nothing else on the sheet is
    # connected to it, while the red scale crevices that share the paint class
    # are separate components and stay untouched.
    old_paint = np.zeros((AH, AW), np.uint8)
    halo = np.zeros((AH, AW), np.uint8)
    ys_p, xs_p = np.nonzero(eye_paint)
    if len(xs_p):
        anchor = int(np.argmin((xs_p - want[0]) ** 2 + (ys_p - want[1]) ** 2))
        anchor_off = float(np.hypot(xs_p[anchor] - want[0],
                                    ys_p[anchor] - want[1]))
        if anchor_off > 12.0:
            raise SystemExit("DEST_PUPIL_NOT_IN_PAINT - the destination affine "
                             "puts the pupil at (%.1f,%.1f) but the nearest eye "
                             "paint is %.1f px away; the report, the atlas and "
                             "the damage disagree, so nothing was written"
                             % (want[0], want[1], anchor_off))
        n_ep, lab_ep = cv2.connectedComponents(eye_paint.astype(np.uint8))
        old_paint = (lab_ep == lab_ep[ys_p[anchor], xs_p[anchor]]).astype(np.uint8) * 255
        # A grid can merge the drawing into a scale crack it touches; the eye is
        # ~100 atlas px across, so anything past 4x that is a leak, not a lash.
        if int((old_paint > 0).sum()) > 40000:
            raise SystemExit("OLD_PAINT_LEAKED - the component holding the "
                             "destination pupil is %d px (an eye is ~7000), so "
                             "the paint class has merged it with the scales; "
                             "inpainting that would smooth skin, so nothing was "
                             "written" % int((old_paint > 0).sum()))
        # One pixel of dilation takes the drawing's antialiased rim with it; the
        # paste is composited on top, so it only affects texels the new eye does
        # not cover.
        old_paint = cv2.dilate(old_paint, np.ones((3, 3), np.uint8))
        # The old drawing's own rim is a soft dark red-brown that neither the
        # dark class (max < 0.30), the amber class (green < 0.26) nor the pale
        # class holds.  It is what stayed visible as a maroon hook on the cheek
        # below the repaired eye after the first FSR run (teen, 2026-11-05).
        # Take that class only where it touches the old drawing - a 3 px band
        # around it - so scale crevices elsewhere on the sheet stay untouched.
        maroon = (mx >= 0.22) & (mx < 0.52) & (fg < 0.26) & (fb < 0.36) & (fr > 0.26)
        near = cv2.dilate(old_paint, np.ones((7, 7), np.uint8))
        halo = (maroon & (near > 0)).astype(np.uint8) * 255
        touch = cv2.dilate(old_paint, np.ones((3, 3), np.uint8)) > 0
        if int((halo > 0).sum()):
            n_h, lab_h = cv2.connectedComponents(halo)
            keep = np.unique(lab_h[(halo > 0) & touch])
            keep = keep[keep > 0]
            halo = np.isin(lab_h, keep).astype(np.uint8) * 255
        else:
            n_h = 0
        if int((halo > 0).sum()):
            print("OLD_PAINT_RIM maroon px=%d in %d component(s) touching the "
                  "drawing" % (int((halo > 0).sum()), len(np.unique(
                      lab_h[(halo > 0)])) if n_h else 0))
    removed_outside = int(((old_paint > 0) & (footprint == 0)).sum())
    # How far the old drawing reaches beyond the new one, i.e. how wide a ring has
    # to be before the only thing left visible is inpainted skin.  This is the
    # number that sizes --ring-mm, so it is printed rather than guessed.
    if int((old_paint > 0).sum()) and int((paste > 51).sum()):
        reach = cv2.distanceTransform((paste <= 51).astype(np.uint8), cv2.DIST_L2, 5)
        dd = reach[old_paint > 0]
        print("OLD_PAINT reach beyond the drawing: p50 %.1f p90 %.1f p99 %.1f "
              "max %.1f px (destination ppm %.0f)"
              % (np.percentile(dd, 50), np.percentile(dd, 90),
                 np.percentile(dd, 99), dd.max(), dst["px_per_atlas_metre"][0]))
    # The inpaint mask is the whole old drawing, including the part the new eye
    # will cover.  Leaving the covered part out (an earlier `paste <= 51` term)
    # kept the old iris as inpaint *source*: TELEA bled its amber into the ring
    # where the old tail had been, and the render showed a gold swirl under the
    # repaired eye (teen, 2026-11-05).  The composite below overwrites the masked
    # area wherever the new drawing is opaque, so masking it costs nothing.
    hard = ((eye_paint & (footprint > 0)) | (old_paint > 0)) & (foreign == 0)
    hard = hard.astype(np.uint8) * 255
    # The old drawing's soft rim has to be rebuilt, but it must not widen the
    # *ring gate*: hard_f is a blur of hard and decides where the SOURCE's
    # lower-lid line is allowed to land, so adding the rim there made the dark
    # hook below the repaired eye thicker and longer (teen D8 run, 2026-11-05).
    # Keep the gate on the original removal mask and hand the inpaint a wider
    # mask (`fill`) that also covers the rim.
    fill = hard | halo
    print("REMOVE old_drawing=%d px (%d of them outside the graded footprint) "
          "hard=%d px  rim=%d px  fill=%d px  foreign_kept=%d px"
          % (int((old_paint > 0).sum()), removed_outside, int((hard > 0).sum()),
             int((halo > 0).sum()), int((fill > 0).sum()),
             int(((old_paint > 0) & (foreign > 0)).sum())))
    # The ring exists to replace the part of the old drawing the new one does
    # not cover - nowhere else.  An ungated ring around the whole drawing also
    # painted the source's pale lid onto the destination's lid (the teen's
    # right-eye cream smear, 2026-11-05).  The gate is the removal mask,
    # blurred so the ring fades into the destination exactly where the damage
    # does; the drawing itself stays opaque on top.
    hard_f = cv2.GaussianBlur(hard, (0, 0), 1.5).astype(np.float64) / 255.0
    ring_a = ring_dst.astype(np.float64) / 255.0 * hard_f
    # 0..1 float, one channel: the composite below is a lerp, and a uint8 mask
    # would make `1.0 - mask` go negative.  The drawing stays fully opaque; the
    # ring is alpha there only where the drawing is not.
    wa = np.maximum(paste.astype(np.float64) / 255.0, ring_a)[..., None]
    box = np.argwhere((wa[..., 0] > 0.02) | (fill > 0))
    if len(box) == 0:
        raise SystemExit("EMPTY_DESTINATION_MASK - the destination affine maps the "
                         "eye outside the atlas; the report and the atlas disagree")
    y0, x0 = box[:, 0].min(), box[:, 1].min()
    y1, x1 = box[:, 0].max() + 1, box[:, 1].max() + 1
    region = (np.clip(fimg[y0:y1, x0:x1], 0, 1) * 255.0 + 0.5).astype(np.uint8)
    # The fill reads the sheet WITHOUT the new drawing.  Compositing the drawing
    # first was tried: the nearest known pixels then are its own dark lash, and
    # Telea dragged that black down the lid in streaks (seen on the teen,
    # 2026-11-05).  The old order at least averages skin; the visible leftover is
    # then narrowed by the ring, which is gated to the removal mask.
    hard_c = fill[y0:y1, x0:x1]
    if args.inpaint == "telea":
        base = cv2.inpaint(region, hard_c, 4, cv2.INPAINT_TELEA).astype(np.float64) / 255.0
    else:
        # Frequency-selective reconstruction, not Telea: the visible part of this
        # mask is the ring of skin around the new drawing, and FSR rebuilds the
        # scale pattern from the intact surroundings instead of averaging them
        # into a colour smear (which read as a pale ragged band beside the
        # repaired eye).  xphoto fills `dst` in place and returns None - but the
        # 5.0.0 build inverts the mask (see xphoto_mask_means_keep), so the mask
        # handed over depends on what this interpreter actually implements.
        keep = xphoto_mask_means_keep()
        xm = (255 - hard_c) if keep else hard_c
        base = region.copy()
        alg = (cv2.xphoto.INPAINT_FSR_BEST if args.inpaint == "fsr-best"
               else cv2.xphoto.INPAINT_FSR_FAST)
        cv2.xphoto.inpaint(region, xm, base, alg)
        base = base.astype(np.float64) / 255.0
        print("INPAINT xphoto mask=%s (build keeps non-zero: %s)"
              % ("keep" if keep else "fill", keep))
    comp = base * (1.0 - wa[y0:y1, x0:x1]) + \
        placed[y0:y1, x0:x1] * wa[y0:y1, x0:x1]
    out = fimg.copy()
    out[y0:y1, x0:x1] = comp
    out8 = np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)

    changed = int((np.abs(out8[y0:y1, x0:x1].astype(np.int16) -
                          atlas[y0:y1, x0:x1].astype(np.int16)).max(2) > 6).sum())
    print("COPY %s -> %s  canvas=%dx%d ellipse=%.4f x %.4f m at (%+.4f,%+.4f) "
          "box=[%d,%d,%d,%d] changed_px=%d of %d  footprint_px=%d"
          % (args.src_side, args.dst_side, W, H, 2 * hw * args.margin,
             2 * hh * args.margin, off[0], off[1], x0, y0, x1, y1, changed,
             (y1 - y0) * (x1 - x0), fp_px))
    print("SRC  %s atlas_box=%s ppm=%s rms=%.2f px" % (src["side"],
          [round(v, 1) for v in src["atlas_box"]], src["px_per_atlas_metre"],
          src["fit_rms_px"]))
    print("DST  %s atlas_box=%s ppm=%s rms=%.2f px  frame_bad=%s" % (dst["side"],
          [round(v, 1) for v in dst["atlas_box"]], dst["px_per_atlas_metre"],
          dst["fit_rms_px"], dst.get("frame_bad")))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    cv2.imwrite(args.out, out8, [cv2.IMWRITE_JPEG_QUALITY, args.quality])
    print("WROTE %s" % args.out)

    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
        z = max(1, 340 // max(1, y1 - y0))
        for nm, img in (("before", atlas), ("after", out8)):
            c = img[y0:y1, x0:x1]
            c = cv2.resize(c, (c.shape[1] * z, c.shape[0] * z),
                           interpolation=cv2.INTER_NEAREST)
            cv2.imwrite(os.path.join(args.outdir, "%s_%s_eye_%s.png"
                                     % (args.tag, nm, args.dst_side)), c)
        cn = (canvas * 255.0).astype(np.uint8)
        cn = cn * (draw[..., None] > 127)
        cv2.imwrite(os.path.join(args.outdir, "%s_canvas_%s.png"
                                 % (args.tag, args.src_side)),
                    cv2.resize(cn, (cn.shape[1] * 2, cn.shape[0] * 2),
                               interpolation=cv2.INTER_NEAREST))
        for nm, m in (("mask_draw", draw), ("mask_ring", ring_c),
                      ("mask_paste", paste), ("mask_hard", hard),
                      ("mask_fill", fill), ("mask_footprint", footprint)):
            cv2.imwrite(os.path.join(args.outdir, "%s_%s.png" % (args.tag, nm)), m)
        wc = (canvas * 255.0).astype(np.uint8)
        cv2.imwrite(os.path.join(args.outdir, "%s_canvas_rgb_%s.png"
                                 % (args.tag, args.src_side)), wc)
        print("WROTE tiles to %s" % args.outdir)


if __name__ == "__main__":
    main()
