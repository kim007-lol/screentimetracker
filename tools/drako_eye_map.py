"""Paint Drako's dragon eye onto the atlas, once per side, from the measured eye.

Why this exists
---------------
`drako_eye_refit.py` draws a rectangle of a *blue anime eye* that was sampled
out of `card_ref_face.png` - which is not Drako.  The shipped adult texture has
a pale cream crescent with a small round dark pupil: that is a puppy, and it is
a large part of why the pet reads as a dog.

The real reference is `docs/docs-assets-chr/paket-drako-3d-final/drako_dewasa.png`
- a small fierce almond, amber/gold iris that fills the eye vertically, a
vertical slit pupil set slightly toward the snout, a dark limen ring, one bright
catchlight, and a heavy dark-maroon upper lid that cuts down over the iris.

This tool paints that eye *in eye space* - one canvas, both sides - and warps
each copy onto the atlas through the affine that `drako_eye_measure.py` fitted
for that side.  Both eyes therefore come from the same drawing, which is the
only way they can be symmetric: the body is one continuous UV sheet and the two
eyes sit in different places on it, so a rect or a global colour rule can never
give a matched pair.

Run it with the system interpreter (cv2 lives there, not in Blender):

    C:/Python314/python.exe tools/drako_eye_map.py \
        --measure=tools/qa_rig/dragon_look/eye_map/dewasa_orig_eye.json \
        --atlas=<tex_out>/1_Image_0.jpg \
        --out=<tex_out2>/1_Image_0.jpg --tag=dewasa

Everything else in the atlas is copied byte-for-byte through the JPEG re-encode;
only the two masked eye islands change.
"""
import argparse
import json
import math
import os

import cv2
import numpy as np

# ----------------------------------------------------------------- palette
# sampled from the reference card (see ref_eye_a/b probes), authored as RGB so a
# person can read it; cv2 and the atlas work in BGR, so PAL below is the same
# table reversed.  Authoring straight in BGR is how the first run painted a
# blue eye on a red dragon.
PAL_RGB = {
    "sclera": (0.930, 0.858, 0.672),
    "sclera_shade": (0.735, 0.612, 0.420),
    "iris_inner": (0.905, 0.692, 0.225),
    "iris_mid": (0.780, 0.486, 0.150),
    "iris_outer": (0.520, 0.258, 0.082),
    "limen": (0.225, 0.058, 0.052),
    "pupil": (0.055, 0.026, 0.026),
    "lid": (0.168, 0.030, 0.038),
    "lid_warm": (0.420, 0.105, 0.085),
    "brow_shadow": (0.290, 0.058, 0.062),
    "catch": (1.000, 0.982, 0.910),
}
PAL = {k: np.array(v[::-1], np.float64) for k, v in PAL_RGB.items()}

CANVAS_PX_PER_MM = 12.0


def lerp(a, b, t):
    t = np.clip(t, 0.0, 1.0)[..., None]
    return a * (1.0 - t) + b * t


def build_canvas(spec, params):
    """One eye, drawn in millimetres of eye space, returned as RGB + alpha.

    Eye space is the frame the measurement produced: +x runs along `right`
    (outward, away from the snout), +y along `up`.  The origin is the iris
    centre, which is NOT the middle of the cream almond - the almond sits a few
    millimetres below it (spec["almond_off"]).
    """
    a = spec["half_w"] * 1000.0                  # almond half-width, mm
    h = spec["half_h"] * 1000.0                  # almond half-height, mm
    yc = spec["almond_off"][1] * 1000.0          # almond centre, mm below iris
    pb = spec["paint_box"]
    x_lo = min(pb[0] * 1000.0, -a * 1.9) - 4.0
    x_hi = max(pb[2] * 1000.0, a * 1.9) + 4.0
    y_lo = min(pb[1] * 1000.0, yc - h * 2.0) - 4.0
    y_hi = max(pb[3] * 1000.0, yc + h * 2.0) + 4.0
    W = int((x_hi - x_lo) * CANVAS_PX_PER_MM) + 1
    H = int((y_hi - y_lo) * CANVAS_PX_PER_MM) + 1
    xs = np.linspace(x_lo, x_hi, W)
    ys = np.linspace(y_hi, y_lo, H)              # row 0 is +y (up)
    X, Y = np.meshgrid(xs, ys)

    # --- the almond: pointed at both corners, fuller toward the outer side ---
    t = np.clip((X - 0.0) / a, -1.0, 1.0)
    arc = np.power(np.clip(1.0 - t * t, 0.0, 1.0), params["pointy"])
    y_up = yc + h * arc * (1.0 + params["corner_rise"] * t)
    y_dn = yc - h * arc * (1.0 - params["corner_drop"] * t)
    inside = (Y <= y_up) & (Y >= y_dn) & (np.abs(t) < 1.0)

    rgb = np.zeros((H, W, 3), np.float64)
    alpha = np.zeros((H, W), np.float64)

    # --- sclera: cream, with the lid shadow pooling along the top ------------
    top_shade = np.clip((Y - yc) / max(h, 1e-6), -1.0, 1.0)
    sclera = lerp(PAL["sclera"], PAL["sclera_shade"],
                  np.clip(0.15 + 0.85 * top_shade, 0.0, 1.0) ** 1.4)
    rgb[:] = sclera
    alpha[:] = inside.astype(np.float64)

    # --- iris: a circle that fills the eye vertically, clipped by the lids ---
    r_i = h * params["iris_r"]
    xi = -a * params["iris_inset"]
    yi = yc + h * params["iris_rise"]
    R = np.hypot(X - xi, Y - yi)
    ir = np.clip(R / r_i, 0.0, 1.0)
    iris_col = np.where(ir[..., None] < 0.55,
                        lerp(PAL["iris_inner"], PAL["iris_mid"], ir / 0.55),
                        np.where(ir[..., None] < 0.90,
                                 lerp(PAL["iris_mid"], PAL["iris_outer"],
                                      (ir - 0.55) / 0.35),
                                 lerp(PAL["iris_outer"], PAL["limen"],
                                      (ir - 0.90) / 0.10)))
    # radial striation so the iris does not read as flat plastic
    ang = np.arctan2(Y - yi, X - xi)
    stri = 0.5 + 0.5 * np.sin(ang * params["stria_n"] + ir * 6.0)
    iris_col = iris_col * (1.0 - params["stria"] * (0.55 - 0.55 * ir) ** 2 *
                            (stri - 0.5) * 2.0)[..., None]
    in_iris = (R <= r_i) & inside
    m = in_iris[..., None]
    rgb = np.where(m, iris_col, rgb)

    # --- pupil: a vertical slit pointed at both ends, a touch toward the snout
    # The reference pupil is not an ellipse: it is a lens, so the superellipse
    # exponents are asymmetric (the y term grows faster and closes the tip).
    prx = r_i * params["pupil_rx"]
    pry = r_i * params["pupil_ry"]
    px_ = xi - r_i * params["pupil_inset"]
    py_ = yi
    Rp = (np.abs(X - px_) / prx) ** params["pupil_p"] + \
        (np.abs(Y - py_) / pry) ** params["pupil_q"]
    pup = (Rp <= 1.0) & in_iris
    rgb = np.where(pup[..., None], PAL["pupil"], rgb)
    feather_w = params["pupil_feather"]
    edge = (Rp > 1.0) & (Rp < 1.0 + feather_w) & in_iris
    rgb = np.where(edge[..., None],
                   lerp(PAL["pupil"], PAL["iris_outer"],
                        np.clip((Rp - 1.0) / feather_w, 0, 1)), rgb)

    # --- catchlight: one bright dot on the pupil's upper-inner edge, one faint
    # one lower-outer.  fa scales the intensity, so it must stay inside the
    # loop - using it after the loop would tint the whole canvas with the last
    # (faint) value.  The radius is tied to the iris, not to the slit: sizing it
    # from prx/pry stretches it into a scratch along the pupil.
    cl = np.zeros((H, W), np.float64)
    cr = r_i * 0.17
    for (fx, fy, fs, fa) in ((px_ - prx * 0.45, yi + r_i * 0.52, 1.00, 1.00),
                             (px_ + prx * 0.90, yi - r_i * 0.44, 0.62, 0.30)):
        d = np.hypot(X - fx, Y - fy) / (cr * fs)
        cl = np.maximum(cl, fa * np.clip(1.0 - d, 0.0, 1.0) ** 1.5)
    cl = cl * in_iris
    rgb = rgb * (1.0 - cl[..., None]) + PAL["catch"] * cl[..., None]

    # --- lids: the heavy dark upper line that cuts the iris, thin lower line -
    def dist_to_curve(yu):
        return np.abs(Y - yu)

    up_line = dist_to_curve(y_up)
    lw_up = h * params["lid_up"] * (0.55 + 0.45 * np.clip(t, -1, 1) * 0.5 +
                                    0.28 * np.clip(t, 0, 1))
    a_up = np.clip((lw_up - up_line) / np.maximum(lw_up * 0.55, 1e-6), 0.0, 1.0)
    a_up = a_up * np.clip(1.0 - np.abs(t) ** 1.6 * 0.35, 0.0, 1.0)   # taper
    dn_line = dist_to_curve(y_dn)
    a_dn = np.clip((h * params["lid_dn"] - dn_line) /
                   np.maximum(h * params["lid_dn"] * 0.6, 1e-6), 0.0, 1.0)
    lid_a = np.clip(a_up + a_dn * 0.55, 0.0, 1.0) * inside
    rgb = rgb * (1.0 - lid_a[..., None]) + PAL["lid"] * lid_a[..., None]

    # --- brow shadow above the eye, and a warm lid rim below ------------------
    # Both are *outside* shading: clipping the distance alone also evaluates to
    # "fully in shadow" everywhere inside the eye, which is what turned the whole
    # canvas brown in sheet_v2.  Gate each on the side of its lid line, and keep
    # the band narrow - at 30 texels across, a wide soft gradient reads as a
    # smudge on the head, not as a brow.
    br = max(h * params["brow_r"], 1e-6)
    above = np.clip((Y - y_up) / br, 0.0, 1.0)
    brow = (1.0 - above) ** 2.2 * params["brow"] * (Y > y_up)
    brow = brow * np.clip(1.0 - np.abs(t) * 0.35, 0.0, 1.0)
    rgb = rgb * (1.0 - brow[..., None]) + PAL["brow_shadow"] * brow[..., None]
    alpha = np.clip(alpha + brow * params["brow_a"], 0.0, 1.0)
    rr = max(h * params["rim_r"], 1e-6)
    below = np.clip((y_dn - Y) / rr, 0.0, 1.0)
    rim = (1.0 - below) ** 2.0 * params["rim"] * (Y < y_dn)
    rim = rim * np.clip(1.0 - np.abs(t) * 0.5, 0, 1)
    rgb = rgb * (1.0 - rim[..., None]) + PAL["lid_warm"] * rim[..., None]
    alpha = np.clip(alpha + rim * params["rim_a"], 0.0, 1.0)

    # feather the canvas edge so the composite never leaves a hard step
    alpha = cv2.GaussianBlur(alpha.astype(np.float32), (0, 0),
                             params["feather"] * CANVAS_PX_PER_MM / 2.0) \
        .astype(np.float64)
    return rgb, np.clip(alpha, 0.0, 1.0), (x_lo, y_lo, x_hi, y_hi), W, H


def warp_canvas(rgb, a, eye, box, ss):
    """Sample the eye-space canvas into the atlas box.

    The canvas is ~10x finer than the atlas there (a 30 mm eye is only ~56 texels
    wide), so a single-point cv2.remap would alias the thin lid line into a
    speckle.  Sampling on an ss-subdivided grid and area-averaging is the
    filtered version of the same transform.
    """
    cx0, cy0, cx1, cy1 = box
    cw, ch = cx1 - cx0, cy1 - cy0
    A = np.array(eye["affine_eye_to_atlas"], np.float64)
    Ainv = np.linalg.inv(A[:, :2])
    b = A[:, 2]
    gx = (np.arange(cw * ss) + 0.5) / ss + cx0 - 0.5
    gy = (np.arange(ch * ss) + 0.5) / ss + cy0 - 0.5
    GC, GR = np.meshgrid(gx, gy)
    P = np.stack([GC.ravel(), GR.ravel()], 0)
    E = (Ainv @ (P - b[:, None])).T.reshape(GR.shape + (2,))     # metres, eye space
    x_lo, y_lo, x_hi, y_hi, W, H = rgb["dom"]
    u = (E[..., 0] * 1000.0 - x_lo) / (x_hi - x_lo) * (W - 1)
    v = (y_hi - E[..., 1] * 1000.0) / (y_hi - y_lo) * (H - 1)
    mx = np.ascontiguousarray(u, np.float32)
    my = np.ascontiguousarray(v, np.float32)
    src = np.ascontiguousarray(rgb["img"].astype(np.float32))
    sa = np.ascontiguousarray(a.astype(np.float32))
    wr = cv2.remap(src, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    # outside the canvas the alpha is 0, so the knock-back skin shows through
    wa = cv2.remap(sa, mx, my, cv2.INTER_LINEAR,
                   borderMode=cv2.BORDER_CONSTANT, borderValue=0.0)
    wr = cv2.resize(wr, (cw, ch), interpolation=cv2.INTER_AREA).astype(np.float64)
    wa = cv2.resize(wa, (cw, ch), interpolation=cv2.INTER_AREA).astype(np.float64)
    return wr, np.clip(wa, 0.0, 1.0)


def island_mask(eye, box, ss):
    """Fraction of each atlas pixel whose surface samples the eye island."""
    cx0, cy0, cx1, cy1 = box
    cw, ch = cx1 - cx0, cy1 - cy0
    polys = [[(np.array(p) - np.array([cx0, cy0])) * ss for p in t]
             for t in eye["local_triangles"]]
    m = np.zeros((ch * ss, cw * ss), np.uint8)
    for p in polys:
        cv2.fillPoly(m, [np.round(p).astype(np.int32).reshape(-1, 1, 2)], 1)
    m = cv2.resize(m.astype(np.float32), (cw, ch),
                   interpolation=cv2.INTER_AREA).astype(np.float64)
    return cv2.GaussianBlur(m, (3, 3), 0.6).astype(np.float64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measure", required=True)
    ap.add_argument("--atlas", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tag", default="eye")
    ap.add_argument("--sides", default="L,R")
    ap.add_argument("--quality", type=int, default=95)
    ap.add_argument("--ss", type=int, default=0, help="supersample factor (0=auto)")
    ap.add_argument("--params", default=None,
                    help='JSON object overriding the canvas parameters, e.g. '
                         '{"lid_up":0.5}')
    ap.add_argument("--outdir", default=None,
                    help="where to drop the before/after tiles")
    args, _ = ap.parse_known_args()

    spec_all = json.load(open(args.measure))
    atlas = cv2.imread(args.atlas, cv2.IMREAD_COLOR).astype(np.float64) / 255.0
    AH, AW = atlas.shape[:2]
    TW, TH = spec_all["atlas"]
    if (AW, AH) != (TW, TH):
        raise SystemExit("ATLAS_SIZE_MISMATCH file=%dx%d json=%dx%d"
                         % (AW, AH, TW, TH))
    out = atlas.copy()
    # Tuned against ref_eye_a.png / ref_eye_b.png: a wedge that is tall at the
    # outer corner and drops to a point at the snout, an iris that fills the
    # aperture vertically and is cut by a heavy upper lid, and a tall narrow
    # slit pupil with one catchlight on its upper edge.
    params = dict(pointy=0.72, corner_rise=0.20, corner_drop=0.22,
                  iris_r=1.26, iris_inset=0.14, iris_rise=0.04,
                  pupil_rx=0.22, pupil_ry=0.94, pupil_inset=0.05,
                  pupil_p=1.30, pupil_q=2.60, pupil_feather=0.30,
                  stria=0.18, stria_n=22.0,
                  lid_up=0.55, lid_dn=0.12,
                  brow=0.55, brow_r=0.42, brow_a=0.60,
                  rim=0.45, rim_r=0.26, rim_a=0.50, feather=0.45)
    if args.params:
        params.update(json.loads(args.params))
    canon = spec_all["canonical"]
    tiles = []
    for eye in spec_all["eyes"]:
        side = eye["side"]
        if side not in args.sides.split(","):
            continue
        spec = {"half_w": eye["half_w"], "half_h": eye["half_h"],
                # one canonical offset for both sides: the mirrored frame already
                # carries the side flip, so the pair stays symmetric.
                "almond_off": [canon["almond_off"][0], canon["almond_off"][1], 0.0],
                "paint_box": eye["paint_box_eye"]}
        rgb, a, (x_lo, y_lo, x_hi, y_hi), W, H = build_canvas(spec, params)
        rgb = {"img": rgb, "dom": (x_lo, y_lo, x_hi, y_hi, W, H)}

        x0, y0, x1, y1 = eye["atlas_box"]
        pad = 10            # inpaint needs a ring of untouched skin to work from
        box = (max(int(x0) - pad, 0), max(int(y0) - pad, 0),
               min(int(x1) + pad, AW), min(int(y1) + pad, AH))
        scale = math.sqrt(abs(np.linalg.det(
            np.array(eye["affine_eye_to_atlas"], np.float64)[:, :2])))
        ss = args.ss or int(np.clip(round(CANVAS_PX_PER_MM * 1000.0 / scale), 2, 16))
        wr, wa = warp_canvas(rgb, a, eye, box, ss)
        m = island_mask(eye, box, ss)
        cx0, cy0, cx1, cy1 = box

        # The old paint must not leak out around the new eye.  Scale relief and
        # luminance cannot be "faded" toward skin - that leaves the ghost of the
        # old crescent ringing the new eye (seen in sheet_v2).  Instead the eye
        # paint texels are *inpainted* from the red skin around them, which is
        # what an empty eye socket looks like, and the canvas is laid over that.
        box_px = atlas[cy0:cy1, cx0:cx1]
        mx, mn = box_px.max(2), box_px.min(2)
        # skin = red-dominant, chromatic, and not bright: cream sclera, the dark
        # pupil and any amber iris all fail one of those tests and get erased.
        skin_like = (box_px[..., 2] >= box_px.max(2) - 1e-6) & ((mx - mn) > 0.18) \
            & (mx < 0.62)
        knock = ((m > 0.45) & ~skin_like).astype(np.uint8) * 255
        base = cv2.inpaint((np.clip(box_px, 0, 1) * 255.0 + 0.5).astype(np.uint8),
                           knock, 4, cv2.INPAINT_TELEA).astype(np.float64) / 255.0
        comp = base * (1.0 - wa[..., None]) + wr * wa[..., None]
        out[cy0:cy1, cx0:cx1] = box_px * (1.0 - m[..., None]) + comp * m[..., None]
        print("%s box=[%d,%d,%d,%d] canvas=%dx%d ss=%d island=%.0f px knock=%d px "
              "alpha_mean=%.3f" % (side, cx0, cy0, cx1, cy1, W, H, ss, m.sum(),
                                   int((knock > 0).sum()), wa.mean()))
        tiles.append((side, cx0, cy0, cx1, cy1, rgb["img"], a))

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    cv2.imwrite(args.out, np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8),
                [cv2.IMWRITE_JPEG_QUALITY, args.quality])
    print("WROTE %s" % args.out)
    if args.outdir:
        os.makedirs(args.outdir, exist_ok=True)
        for (side, cx0, cy0, cx1, cy1, canvas_rgb, canvas_a) in tiles:
            zoom = max(1, 340 // max(1, cy1 - cy0))
            for nm, img in (("before", atlas), ("after", out)):
                c = img[cy0:cy1, cx0:cx1]
                c = cv2.resize((c * 255).astype(np.uint8),
                               (c.shape[1] * zoom, c.shape[0] * zoom),
                               interpolation=cv2.INTER_NEAREST)
                cv2.imwrite(os.path.join(args.outdir, "%s_%s_eye_%s.png"
                                         % (args.tag, nm, side)), c)
            # the unwarped canvas, so a bad drawing can be told from a bad warp
            cn = (np.clip(canvas_rgb, 0, 1) * canvas_a[..., None] * 255) \
                .astype(np.uint8)
            cv2.imwrite(os.path.join(args.outdir, "%s_canvas_%s.png"
                                     % (args.tag, side)), cn)
        print("WROTE tiles to %s" % args.outdir)


if __name__ == "__main__":
    main()
