#!/usr/bin/env python3
"""Repaint Drako's baked atlas so the face reads as a dragon, not a puppy.

The delivered Drako meshes share one 2048 base-color atlas.  Two things make the
in-app pet read as a dog: the painted eyes carry a wide white sclera crescent
around a muddy brown iris with a round pupil, and the red skin is a flat,
smooth plastic with no scale structure.  The reference card (`drako_bayi_card.png`)
reads as a dragon because of its scales and its gold, dark-rimmed eyes.

This pass edits the extracted atlas only (no mesh, no UV, no rig):

  eyes     the amber iris is the anchor, and its convex hull is the eyeball;
           inside that hull the iris is warmed toward gold and the pupil is
           deepened, while the gold ring and the star sparkles keep their own
           colour; outside it the wide white sclera crescent shrinks to the
           hairline sliver the reference card shows and the rest becomes dark lid
  skin     procedural scale field multiplied onto red-skin pixels only, on a
           jittered and warped lattice so it reads as skin and not as a knit,
           faded out over the bare eyelid and brow

Run:
  python tools/drako_face_repaint.py <in_dir> <out_dir> [--scales 0.18]
                                      [--cell 14] [--jitter 0.26] [--warp 0.34]
                                      [--groove-w 1.2] [--shadow-w 0.7]

`in_dir` holds the textures dumped from the GLB (`*_Image_0.jpg` base colour,
`*_Image_1.jpg` metallic-rough, `*_Image_2.jpg` normal).  The base colour is
rewritten into `out_dir`; the other two maps are copied unchanged.
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil

import cv2
import numpy as np


# ---------------------------------------------------------------- colour masks
def split_masks(bgr: np.ndarray):
    """Classify atlas pixels into the families the repaint needs."""
    img = bgr.astype(np.int16)
    b, g, r = img[..., 0], img[..., 1], img[..., 2]
    mx = img.max(axis=2)
    mn = img.min(axis=2)

    dark = (mx < 78)
    # painted sclera / sparkle: near-white, low saturation
    white = (mn > 178) & ((mx - mn) < 46)
    # red skin (the body colour, including its baked shading)
    red = (r > 60) & (r - g > 42) & (g - b < 30) & (mx < 232)
    # gold / cream (horns, belly, flame markings) - never scaled
    gold = (r > 150) & (g > 105) & (r - b > 60) & ~red
    # brown iris: mid-value, warm, clearly darker than the gold parts
    iris = (r > 74) & (r < 214) & (r - g > 22) & (g - b > 8) & ~red & ~gold
    return dark, white, red, gold, iris


# ---------------------------------------------------------------- eye repaint
IRIS_DEEP = np.array([9, 40, 120], np.float32)     # BGR  burnt amber rim
IRIS_MID = np.array([26, 96, 186], np.float32)      # BGR  amber
IRIS_LIGHT = np.array([64, 172, 236], np.float32)   # BGR  gold inner
RING_DARK = np.array([12, 26, 46], np.float32)      # BGR  dark warm lid


def eye_frame(pts: np.ndarray):
    """Principal-axis frame of a point cloud: (origin, major, minor, hw, hh).

    cv2.fitEllipse's angle convention is not usable here - the atlases pack the
    same eye at several different UV rotations.  The eigenvectors of the eyeball
    outline are unambiguous: `major` is the long axis of the almond and `minor`
    the short one.
    """
    mean = pts.mean(axis=0)
    d = pts - mean
    val, vec = np.linalg.eigh(np.cov(d.T))
    order = np.argsort(val)[::-1]
    major, minor = vec[:, order[0]], vec[:, order[1]]
    u, v = d @ major, d @ minor
    return (mean, major, minor,
            max(float(np.abs(u).max()), 1.0), max(float(np.abs(v).max()), 1.0))


def find_eyes(bgr, verbose: bool = False):
    """Locate every painted eye as a (hull, frame) pair.

    The amber *iris* family is the anchor, not the white island.  In this art
    style the sclera crescent, the sparkles and the lid highlights all come from
    the same near-white family, so an anchor built on white cannot tell an eye
    from a star drawn inside the pupil - and the atlas packs duplicated UV
    islands, so the crescent of one eye often touches the lash of another.  Iris
    colour only exists inside an eye, and its convex hull is the eyeball.

    A blob only counts as an eye when it has white in its window (every painted
    eye here carries a highlight) and either a dark pupil mass inside the hull or
    an sclera band outside it.  Measured on the shipped atlases this separates
    cleanly: the seven real eye islands all have white and dark in the hull, and
    every amber *body shading* blob - same colour family, but sitting against red
    skin - has neither.
    """
    h, w = bgr.shape[:2]
    dark, white, red, gold, iris = split_masks(bgr)
    seed = cv2.dilate(iris.astype(np.uint8), np.ones((5, 5), np.uint8), 1)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(seed, 8)
    eyes = []
    for i in range(1, n):
        comp = lab == i
        pts = np.column_stack(np.nonzero(comp & iris)[::-1]).reshape(-1, 2)
        if pts.shape[0] < 400:
            continue
        hull_pts = cv2.convexHull(pts.reshape(-1, 1, 2).astype(np.float32))
        if hull_pts.shape[0] < 6:
            continue
        hull = np.zeros((h, w), np.uint8)
        cv2.fillConvexPoly(hull, hull_pts.astype(np.int32), 1)
        hull = hull > 0
        win = cv2.dilate(comp.astype(np.uint8), np.ones((15, 15), np.uint8), 1) > 0
        wi = int((white & hull).sum())
        wo = int((white & ~hull & win).sum())
        di = int((dark & hull).sum())
        if wi + wo < 40:
            continue
        if di < 150 and wo < 120:
            continue
        fr_ = eye_frame(pts.astype(np.float32))
        if min(fr_[3], fr_[4]) < 4 or max(fr_[3], fr_[4]) > 4.5 * min(fr_[3], fr_[4]):
            continue
        eyes.append((wo + wi + di, hull, fr_))
        if verbose:
            print("  eye @(%4d,%4d) hull=%5d sclera_out=%5d sparkle_in=%5d"
                  " pupil=%5d axes=%.0fx%.0f"
                  % (fr_[0][0], fr_[0][1], int(hull.sum()), wo, wi, di,
                     fr_[3] * 2, fr_[4] * 2))
    eyes.sort(key=lambda t: -t[0])
    return [(hu, fm) for _, hu, fm in eyes], (dark, white, red, gold, iris)


def eye_sclera(white, hull):
    """White islands that wrap the outside of the eyeball: the sclera crescents.

    A component that is mostly *inside* the hull is a sparkle or a lid highlight
    and must keep its pixels.
    """
    h, w = white.shape
    n, lab, st, _ = cv2.connectedComponentsWithStats(white.astype(np.uint8), 8)
    edge = cv2.dilate(hull.astype(np.uint8), np.ones((11, 11), np.uint8), 1) > 0
    sclera = np.zeros((h, w), bool)
    for j in range(1, n):
        if st[j][4] < 40:
            continue
        comp = lab == j
        if int((comp & hull).sum()) > 0.5 * int(comp.sum()):
            continue                      # sparkle: inside the eyeball
        if int((comp & edge).sum()) < 15:
            continue                      # not touching this eye
        sclera |= comp
    return sclera


def paint_eye(bgr, hull, frame, dark, white, iris, gold, keep_band=3.0,
              lift=1.0) -> int:
    """Warm one painted iris toward the reference card's gold and lid its sclera.

    The shipped atlas already paints a gold ring, a round pupil and star
    sparkles; what makes the pet read as a dog is the wide white sclera crescent
    and the dull, blue-leaning amber.  So this pass does not re-draw the iris -
    replacing it flattened the sparkles and turned the ring muddy, which measured
    worse against the card.  It shifts the existing `iris` family up in red and
    green and down in blue, glows it toward the pupil, and leaves every `gold`
    and white island (the stars and the corner highlight) exactly as authored.

    The hull is a convex fit, so it overshoots the eyeball at the corners where
    the cream muzzle and the gold teardrop marking sit; the blue-channel guard
    keeps those out of the painted set.
    """
    h, w = bgr.shape[:2]
    org, major, minor, hw, hh = frame

    ys, xs = np.nonzero(hull & iris)
    if xs.size < 120:
        return 0
    dx = xs.astype(np.float32) - org[0]
    dy = ys.astype(np.float32) - org[1]
    u = (dx * major[0] + dy * major[1]) / hw
    v = (dx * minor[0] + dy * minor[1]) / hh
    rho = np.sqrt(u * u + v * v)
    idx = (ys.astype(np.int64) * w + xs.astype(np.int64))
    px = bgr.reshape(-1, 3)[idx].astype(np.float32)

    is_cream = px[:, 0] > 120                 # pale marking the hull overshoots into
    push = px.copy()
    push[:, 2] = px[:, 2] * 1.10 + 14.0       # R
    push[:, 1] = px[:, 1] * 1.16 + 8.0        # G
    push[:, 0] = px[:, 0] * 0.78              # B down: amber -> gold
    glow = 1.0 + 0.16 * np.clip(1.0 - rho, 0.0, 1.0) - 0.14 * np.clip(rho - 0.82, 0.0, 0.18) / 0.18
    push *= glow[:, None]
    out = px * (1.0 - lift) + push * lift

    sel = ~is_cream
    bgr.reshape(-1, 3)[idx[sel]] = np.clip(out[sel], 0, 255).astype(np.uint8)

    # --- the pupil keeps its round shape; the reference card has a round pupil
    #     too, so the "dog" read comes from the wide white sclera and the muddy
    #     iris, not from the pupil.  Deepen it for contrast against the gold.
    dys, dxs = np.nonzero(hull & dark)
    if dxs.size:
        didx = dys.astype(np.int64) * w + dxs.astype(np.int64)
        pd = bgr.reshape(-1, 3)[didx].astype(np.float32)
        bgr.reshape(-1, 3)[didx] = np.minimum(pd, RING_DARK[None, :]).astype(np.uint8)

    # --- the wide white sclera crescent is what makes the eye read as a puppy.
    #     Keep only the hairline that hugs the eyeball - the reference shows a
    #     dragon eye with a sliver of white at the corner - and turn the rest of
    #     the crescent into the dark lid.
    sclera = eye_sclera(white, hull)
    dist = cv2.distanceTransform((~hull).astype(np.uint8), cv2.DIST_L2, 3)
    lid = sclera & (dist > keep_band)
    bgr[lid] = RING_DARK
    return int(int(sel.sum()) + dxs.size + int(lid.sum()))


def repaint_eyes(bgr: np.ndarray, verbose: bool = True, keep_band: float = 3.0,
                 lift: float = 1.0, halo_px: float = 30.0):
    """Find every painted eye from its amber iris and recolour it.

    Returns `(islands, pixels, halo)`; `halo` is the eyeball union dilated by
    `halo_px`, i.e. the skin that must stay *smooth*.  The card shows bare lid and
    brow around the eye and only scales out on the cheek - without this the scale
    field marches straight into the eye socket, which is half of why the repaint
    still read as a manufactured pattern.
    """
    eyes, (dark, white, red, gold, iris) = find_eyes(bgr, verbose=verbose)
    touched = 0
    found = 0
    halo = np.zeros(bgr.shape[:2], np.uint8)
    for hull, frame in eyes:
        n_px = paint_eye(bgr, hull, frame, dark, white, iris, gold, keep_band, lift)
        if n_px == 0:
            continue
        found += 1
        touched += n_px
        halo = cv2.bitwise_or(halo, (hull * 255).astype(np.uint8))
        if verbose:
            print("  EYE #%02d at (%.0f,%.0f) touched=%d"
                  % (found, frame[0][0], frame[0][1], n_px))
    if halo.any():
        k = int(halo_px) * 2 + 1
        halo = cv2.dilate(halo, np.ones((k, k), np.uint8), 1)
    print("EYES_REPAINTED islands=%d pixels=%d halo=%d"
          % (found, touched, int((halo > 0).sum())))
    return found, touched, halo
# ------------------------------------------------------------------ scale pass
def _lattice_noise(row, col):
    """Deterministic [0,1) hash for each lattice cell, three decorrelated channels.

    float64 is not pedantry: the sin-hash needs a full-precision argument, and at
    the small cell sizes that read as dragon scales a 2048 atlas spans ~150 rows
    and columns.  In float32 neighbouring cells alias onto the same value and the
    jitter collapses back into a repeating brick.
    """
    r = np.asarray(row, np.float64)
    c = np.asarray(col, np.float64)
    out = []
    for a, b, d in ((127.1, 311.7, 74.7),
                    (269.5, 183.3, 246.1),
                    (419.2, 371.9, 97.3)):
        x = np.sin(r * a + c * b + d) * 43758.5453
        out.append((x - np.floor(x)).astype(np.float32))
    return out[0], out[1], out[2]


def scale_field(shape, cell: float, row_ratio: float = 0.70,
                radius_ratio: float = 0.62, band_ratio: float = 0.11,
                tilt_deg: float = -8.0, jitter: float = 0.26,
                size_jitter: float = 0.30, warp: float = 0.34):
    """Overlapping dragon scales as a (groove, face, shadow) triple in 0..1.

    An iso-distance band on a lattice cannot work here: the distance to the
    *nearest* lattice point only spans the inscribed radius of its Voronoi cell,
    so a band placed at a plausible scale radius is never reached (featureless),
    and a band placed within reach traces the cell walls (a honeycomb).  Equal
    radius caps are no better - their creases are perpendicular bisectors, again
    straight lines.

    So the scale is drawn parametrically.  Row `k` occupies the band
    `[k*sy, (k+1)*sy)` with columns staggered by half a pitch, and its disc
    centre sits on the band's top edge.  `row_ratio/2 < radius_ratio < row_ratio`
    (`0.35 < 0.62 < 0.70`) makes the arc `hypot(lx, ly) = R` cross every column
    strictly inside that band: it is the free lower edge of the scale, it meets
    the neighbouring column's arc exactly at the column seam (|lx| = sx/2 gives
    the same `ly`), and it never touches a row seam.  That is the scalloped
    silhouette real overlapping scales have.

    groove  - the crisp dark line on that free edge
    face    - the scale's own curvature, bright at the crown, falling to the edge
    shadow  - contact darkening below each free edge, including the overlap line
              where the scale is tucked under the row above (measured from the
              staggered row `k-1`, hence the half-pitch `lx_prev`)

    A pure lattice is the failure mode this art style shows up as: perfectly equal
    discs on perfectly straight rows read as knitted fabric or a waffle, not as
    skin.  Two things break it, both driven from the same cell hash so the field
    stays deterministic and tile-free:

    `jitter`/`size_jitter` - each scale's centre wanders inside its cell and its
        radius varies, so edges no longer meet in lockstep at the column seams.
    `warp`                 - a low-frequency domain warp bends the rows and
        columns themselves, which is what makes the field look like it is wrapped
        around a body rather than printed on a plane.

    The row-above lookup re-derives its own stagger, its own nearest column and
    its own jittered radius, so the overlap shadow still rides the real edge of
    the neighbour instead of an idealised one.
    """
    h, w = shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    a = np.deg2rad(tilt_deg)
    ca, sa = np.float32(np.cos(a)), np.float32(np.sin(a))
    px = (xx - w * 0.5) * ca + (yy - h * 0.5) * sa
    py = -(xx - w * 0.5) * sa + (yy - h * 0.5) * ca
    del xx, yy

    sx = np.float32(cell)
    sy = np.float32(cell * row_ratio)
    R = np.float32(cell * radius_ratio)
    band = R * band_ratio
    fall = np.float32(cell * 0.20)

    if warp > 0.0:
        amp = np.float32(cell * warp)
        # two incommensurate wavelengths: no repeat box inside the atlas
        px = px + amp * np.sin(py * (2.0 * np.pi / (cell * 11.3)) + 0.7)
        py = py + amp * np.sin(px * (2.0 * np.pi / (cell * 13.7)) + 2.1)

    k = np.floor(py / sy)
    off = np.mod(k, 2.0) * (sx * 0.5)
    n = np.round((px - off) / sx)
    j1, j2, j3 = _lattice_noise(k, n)
    lx = px - (n * sx + off + (j1 - 0.5) * jitter * sx)
    ly = py - (k * sy + (j2 - 0.5) * jitter * sy)              # inside the band
    Rc = R * (1.0 + (j3 - 0.5) * size_jitter)

    # The scale that tucks over this one lives in the staggered row k-1, so it
    # has its own column offset and its own jitter.  `over` is the signed depth
    # below that neighbour's free edge: the same quantity the ideal lattice wrote
    # as `ly + sy - arc_prev`, now measured against the neighbour it really is.
    kp = k - 1.0
    off_p = np.mod(kp, 2.0) * (sx * 0.5)
    n_p = np.round((px - off_p) / sx)
    p1, p2, p3 = _lattice_noise(kp, n_p)
    lx_p = px - (n_p * sx + off_p + (p1 - 0.5) * jitter * sx)
    Rc_p = R * (1.0 + (p3 - 0.5) * size_jitter)
    over = py - (kp * sy + (p2 - 0.5) * jitter * sy) \
        - np.sqrt(np.maximum(Rc_p * Rc_p - lx_p * lx_p, 1e-4))
    del px, py, k, off, n, j1, j2, j3, kp, off_p, n_p, p1, p2, p3, lx_p, Rc_p

    arc = np.sqrt(np.maximum(Rc * Rc - lx * lx, 1e-4))         # free-edge height
    groove = np.exp(-(((np.sqrt(lx * lx + ly * ly) - Rc) / band) ** 2))
    below = ly - arc                                           # past this edge
    shadow = np.maximum(np.exp(-np.clip(below, 0.0, 1e9) / fall) * (below > 0),
                        np.exp(-np.clip(over, 0.0, 1e9) / fall))
    u = np.clip(ly / arc, 0.0, 1.0)                            # 0 crown .. 1 edge
    face = 1.0 - 0.80 * u ** 1.8
    return (groove.astype(np.float32), face.astype(np.float32),
            shadow.astype(np.float32))



def scale_shade(shape, cell: float, strength: float, face_w: float = 1.15,
                groove_w: float = 1.70, shadow_w: float = 1.10,
                offset: float = 0.55, **field_kw):
    """Multiplicative luminance field for one scale pass (shared by preview).

    The three weights are exposed because the *balance* between them is what
    decides whether the pass reads as skin or as a waffle: the card's scales are
    domes with a soft seam, so a heavy `groove_w`/`shadow_w` against a light
    `face_w` draws hard dark crescents on a flat base, which is the knit look.
    """
    groove, face, shadow = scale_field(shape, cell, **field_kw)
    shade = 1.0 + strength * (face_w * (face - offset)
                              - groove_w * groove - shadow_w * shadow)
    return np.clip(shade, 0.55, 1.25).astype(np.float32)


def normalize_shade(shade, mask, lo=0.55, hi=1.35):
    """Rescale a shade field so its mean over `mask` is 1.0, then clip."""
    mean = float(shade[mask].mean()) if mask.any() else 0.0
    if mean > 1e-3:
        shade = np.clip(shade / mean, lo, hi).astype(np.float32)
    return shade


def add_scales(bgr: np.ndarray, red: np.ndarray, cell: float, strength: float,
               normalize: bool = True, smooth: np.ndarray | None = None,
               feather: float = 18.0, **field_kw):
    shade = scale_shade(bgr.shape[:2], cell, strength, **field_kw)
    mask = (cv2.dilate(red.astype(np.uint8), np.ones((3, 3), np.uint8), 1) > 0)
    if smooth is not None and smooth.any():
        # Feathered bare skin: relief fades to nothing over the eyelid and brow.
        bare = cv2.GaussianBlur(smooth.astype(np.float32) / 255.0, (0, 0), feather)
        shade = 1.0 + (shade - 1.0) * np.clip(1.0 - bare * 1.06, 0.0, 1.0)
    if normalize:
        # The scale pass must add relief, not darken the pet.
        shade = normalize_shade(shade, mask)
    out = bgr.astype(np.float32)
    for c in range(3):
        out[..., c][mask] = np.clip(out[..., c][mask] * shade[mask], 0, 255)
    print("SCALES cell=%.1f strength=%.2f red_pixels=%d mean_shade=%.3f min=%.3f max=%.3f"
          % (cell, strength, int(mask.sum()), float(shade[mask].mean()),
             float(shade[mask].min()), float(shade[mask].max())))
    return out.astype(np.uint8)


# ------------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("in_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--scales", type=float, default=0.22)
    ap.add_argument("--cell", type=float, default=20.0)
    ap.add_argument("--rows", type=float, default=0.70)
    ap.add_argument("--rim", type=float, default=0.62)
    ap.add_argument("--band", type=float, default=0.11)
    ap.add_argument("--tilt", type=float, default=-8.0)
    ap.add_argument("--jitter", type=float, default=0.26,
                    help="scale centre wander, as a fraction of the cell pitch")
    ap.add_argument("--size-jitter", type=float, default=0.30,
                    help="scale radius variation, as a fraction of the radius")
    ap.add_argument("--warp", type=float, default=0.34,
                    help="row/column bend, as a fraction of the cell pitch")
    ap.add_argument("--face-w", type=float, default=1.15)
    ap.add_argument("--groove-w", type=float, default=1.70)
    ap.add_argument("--shadow-w", type=float, default=1.10)
    ap.add_argument("--sclera-band", type=float, default=3.0)
    ap.add_argument("--halo", type=float, default=30.0,
                    help="bare-skin radius kept smooth around each eye, in texels")
    ap.add_argument("--feather", type=float, default=18.0,
                    help="sigma of the fade from bare skin back into scales")
    ap.add_argument("--lift", type=float, default=1.0,
                    help="0..1 blend of the iris warm-up (0 keeps the painted iris)")
    ap.add_argument("--no-scales", action="store_true")
    ap.add_argument("--no-eyes", action="store_true")
    ap.add_argument("--quality", type=int, default=95)
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    bases = sorted(glob.glob(os.path.join(args.in_dir, "*Image_0.jpg")))
    if not bases:
        raise SystemExit("no base colour texture (*_Image_0.jpg) in " + args.in_dir)
    src = bases[0]
    bgr = cv2.imread(src, cv2.IMREAD_COLOR)
    if bgr is None:
        raise SystemExit("cannot read " + src)
    print("BASE", src, bgr.shape[1], "x", bgr.shape[0])

    _, _, red, _, iris = split_masks(bgr)
    halo = None
    if not args.no_eyes:
        _, _, halo = repaint_eyes(bgr, keep_band=args.sclera_band, lift=args.lift,
                                  halo_px=args.halo)
    if (halo is None or not halo.any()) and args.halo > 0 and not args.no_scales:
        # No eyeball to protect - the dewasa atlas carries no white at all, so
        # `find_eyes` correctly finds nothing there.  Fall back to the amber iris
        # family, which does exist, so the socket still stays bare.
        seed = cv2.dilate(iris.astype(np.uint8), np.ones((15, 15), np.uint8), 1)
        halo = cv2.GaussianBlur(seed, (0, 0), max(args.halo * 0.5, 1.0))
        print("HALO from iris instead of hulls")
    if not args.no_scales:
        bgr = add_scales(bgr, red, args.cell, args.scales, smooth=halo,
                         feather=args.feather, row_ratio=args.rows,
                         radius_ratio=args.rim, band_ratio=args.band,
                         tilt_deg=args.tilt, jitter=args.jitter,
                         size_jitter=args.size_jitter, warp=args.warp,
                         face_w=args.face_w, groove_w=args.groove_w,
                         shadow_w=args.shadow_w)

    out = os.path.join(args.out_dir, os.path.basename(src))
    cv2.imwrite(out, bgr, [cv2.IMWRITE_JPEG_QUALITY, args.quality])
    print("WROTE", out, os.path.getsize(out))
    for other in sorted(glob.glob(os.path.join(args.in_dir, "*Image_[12].jpg"))):
        dst = os.path.join(args.out_dir, os.path.basename(other))
        if not os.path.exists(dst):
            shutil.copy2(other, dst)
            print("COPY", dst)


if __name__ == "__main__":
    main()
