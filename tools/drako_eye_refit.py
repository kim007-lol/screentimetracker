#!/usr/bin/env python3
"""Re-draw the Drako eyes in the atlas to match the reference card.

The shipped adult eye is a pale cream blob with a soft dark smudge: at the app
camera it disappears into the surrounding cream markings.  The reference shows a
hard-edged almond - dark socket, ivory sclera, saturated amber iris, black
pupil, catchlight, heavy upper lid.  This tool paints that structure in place.

It does not guess where the eyes are: every rectangle comes from the proven
locator chain (bind-pose render -> bright-island detector -> ray cast -> atlas
rectangle -> atlas-paint probe).  Painting is clipped to the rectangle, so it
can never bleed into a neighbouring UV island.

  python tools/drako_eye_refit.py --atlas <dir> --eyes <json> --out <dir>

`--eyes` is a JSON list of {"stage": "...", "rects": [[x0,y0,x1,y1], ...]}.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from drako_face_repaint import eye_frame                      # noqa: E402

# BGR, sampled from docs/docs-assets-chr/paket-drako-3d-final/drako_dewasa.png
SOCKET = np.array([26, 20, 58], np.float32)     # dark maroon eye socket
LID = np.array([18, 12, 30], np.float32)        # near-black warm lid line
SCLERA = np.array([212, 228, 244], np.float32)  # warm ivory
IRIS_DEEP = np.array([22, 84, 168], np.float32)  # burnt amber outer iris
IRIS_MID = np.array([52, 158, 226], np.float32)  # golden amber
IRIS_LIGHT = np.array([110, 206, 248], np.float32)  # bright gold inner ring
PUPIL = np.array([10, 12, 22], np.float32)      # near-black
CATCH = np.array([238, 244, 250], np.float32)   # highlight


def _aa_layer(shape, draw, blur=0.8):
    """Draw into a uint8 canvas, then split it into (mask, colour) floats.

    cv2 draws anti-aliased edges into the canvas itself, so the mask is simply
    "this pixel was painted" and the colour is the canvas.  Drawing on uint8
    keeps cv2's ellipse and line behaviour identical to the rest of the pipeline.
    """
    c = np.zeros((*shape[:2], 3), np.uint8)
    draw(c)
    m = (c.max(axis=2) > 0).astype(np.float32)
    if blur > 0:
        k = int(blur * 4) | 1
        m = cv2.GaussianBlur(m, (k, k), blur)
    return m, c.astype(np.float32)


def _ell(centre, axes, angle, colour, fill=True, width=1):
    def draw(canvas):
        cv2.ellipse(canvas, (int(round(centre[0])), int(round(centre[1]))),
                    (max(1, int(round(axes[0]))), max(1, int(round(axes[1])))),
                    float(angle), 0, 360,
                    [int(round(v)) for v in colour],
                    cv2.FILLED if fill else width, cv2.LINE_AA)
    return draw


def build_eye(bgr, rect, params):
    """Paint one eye.  Returns (n_pixels_written, debug dict)."""
    h, w = bgr.shape[:2]
    x0, y0, x1, y1 = rect
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    win = bgr[y0:y1, x0:x1].astype(np.float32)
    wh, ww = win.shape[:2]
    val = win.max(axis=2) / 255.0

    # ---- anchor: the eyeball is the densest concentration of bright pixels.
    # Taking the largest bright component instead would pick up the cream cheek
    # and flame markings that touch the eye in this atlas, so seed from the
    # blurred density peak and grow only inside a small disc around it.
    cx, cy = ww / 2.0, wh / 2.0
    bright = (val > params["anchor_val"]).astype(np.float32)
    yy0, xx0 = np.mgrid[0:wh, 0:ww]
    # The locator chain proves one atlas point per eye (ray cast, then confirmed
    # by painting a marker there and rendering the head).  When that centre is
    # supplied, seed from it: a density peak can easily land on the cream cheek
    # marking that touches the eye in this atlas.
    if params.get("centre"):
        sx = int(round(params["centre"][0])) - int(rect[0])
        sy = int(round(params["centre"][1])) - int(rect[1])
        sx = int(np.clip(sx, 0, ww - 1))
        sy = int(np.clip(sy, 0, wh - 1))
    else:
        near = ((xx0 - cx) ** 2 + (yy0 - cy) ** 2) <= (params["seed_r"] * 1.9) ** 2
        dens = cv2.GaussianBlur(bright, (0, 0), 4.5) * near
        if not dens.any():
            return 0, {"skipped": "no bright pixels in rect"}
        sy, sx = np.unravel_index(int(np.argmax(dens)), dens.shape)
    disc = ((xx0 - sx) ** 2 + (yy0 - sy) ** 2) <= params["seed_r"] ** 2
    n, lab, st, _ = cv2.connectedComponentsWithStats(
        (bright * disc).astype(np.uint8), 8)
    if n <= 1:
        return 0, {"skipped": "no bright island at the seed"}
    # largest component inside the seed disc, not "the component containing the
    # seed" - the proven centre can sit on the dark pupil, which is not bright.
    seed_lab = 1 + int(np.argmax(st[1:, 4]))
    blob = (lab == seed_lab)
    if int(blob.sum()) < params["anchor_min_area"]:
        return 0, {"skipped": "anchor too small", "area": int(blob.sum())}
    pts = np.column_stack(np.nonzero(blob)[::-1]).astype(np.float32)
    origin, major, minor, hw, hh = eye_frame(pts)

    # ---- which atlas direction is the eye's own horizontal?  The PCA of the
    # cream crescent gives two orthogonal axes but cannot say which one runs
    # along the snout, so `axis` selects it and the app-camera render decides.
    if params["axis"] == "major":
        horiz, vert, sh, sv = major, minor, hw, hh
    else:
        horiz, vert, sh, sv = minor, major, hh, hw

    # ---- which way is "up" on the head?  The existing dark lid and brow shadow
    # sit on one side of the eyeball; keep that side so the new lid matches the
    # sculpt instead of painting a lower lid over the cheek.
    ring = (cv2.dilate(blob.astype(np.uint8), np.ones((9, 9), np.uint8), 1) > 0) & ~blob
    dk = (val < params["lid_dark_val"]) & ring
    up = vert.copy()
    if int(dk.sum()) >= 6:
        dp = np.column_stack(np.nonzero(dk)[::-1]).astype(np.float32) - origin
        s = float((dp @ vert).mean())
        up = vert if s > 0 else -vert
    angle = float(np.degrees(np.arctan2(horiz[1], horiz[0])))

    # The reference almond is roughly twice as wide as it is tall.  The crescent
    # PCA returns a near-round frame, so the ratio is imposed rather than
    # measured; the half-height stays anchored to the painted feature so the eye
    # cannot grow off the eyeball.
    b = float(np.clip(sv * params["grow"], params["min_b"], params["max_b"]))
    a = float(np.clip(max(sh * params["grow"], b * params["almond"]),
                      params["min_a"], params["max_a"]))
    c = (float(origin[0]), float(origin[1]))

    written = 0

    def over(draw, colour, alpha_scale=1.0, blur=0.8):
        nonlocal win
        m, col = _aa_layer(win.shape, draw, blur)
        alpha = np.clip(m, 0, 1) * alpha_scale
        win = win * (1 - alpha[..., None]) + col * alpha[..., None]
        return alpha

    # 1. socket: separates the eye from the cream markings around it
    a_socket = over(_ell(c, (a + params["socket"], b + params["socket"]),
                         angle, SOCKET), SOCKET, params["socket_alpha"])
    written += int((a_socket > 0.05).sum())

    # 2. sclera
    over(_ell(c, (a, b), angle, SCLERA), SCLERA)

    # 3. iris: the reference iris fills the almond vertically and only leaves an
    # ivory wedge at each corner, so it is sized from the half-height first.
    ib = b * params["iris_b"]
    ia = min(a * params["iris_a"], ib * params["almond"] * 0.72)
    over(_ell(c, (ia, ib), angle, IRIS_DEEP), IRIS_DEEP)
    over(_ell(c, (ia * 0.88, ib * 0.88), angle, IRIS_MID), IRIS_MID)
    # 3b. gold inner ring, brighter toward the pupil
    over(_ell(c, (ia * 0.62, ib * 0.62), angle, IRIS_LIGHT), IRIS_LIGHT, 0.9)

    # 4. pupil: round in the reference, not a slit
    pr = min(b * params["pupil_b"], ia * params["pupil_a"])
    over(_ell(c, (pr, pr), 0.0, PUPIL), PUPIL)

    # 5. catchlight: one round highlight on the brow side of the pupil.  It is
    # deliberately centred on the vertical axis - the PCA sign of `horiz` is
    # arbitrary, so any lateral offset would land on the outer corner of one eye
    # and the inner corner of the other and make the pet look wall-eyed.
    cc_ = (c[0] + up[0] * (b * 0.34), c[1] + up[1] * (b * 0.34))
    cr = max(1.0, min(a, b) * 0.24)
    over(_ell(cc_, (cr, cr), 0.0, CATCH), CATCH, 0.92)

    # 6. heavy upper lid: a thick arc on the brow side of the almond, plus a
    # thin lower rim so the eye never floats on the skin.
    outer = np.zeros(win.shape[:2], np.uint8)
    inner = np.zeros(win.shape[:2], np.uint8)
    cv2.ellipse(outer, (int(c[0]), int(c[1])), (int(a + 2), int(b + 2)),
                angle, 0, 360, 1, cv2.FILLED, cv2.LINE_AA)
    cv2.ellipse(inner, (int(c[0]), int(c[1])), (int(a - 0.5), int(b - 0.5)),
                angle, 0, 360, 1, cv2.FILLED, cv2.LINE_AA)
    band = (outer > 0) & (inner == 0)
    yy, xx = np.mgrid[0:wh, 0:ww]
    side = (xx - c[0]) * up[0] + (yy - c[1]) * up[1]
    lid = band & (side > -b * params["lid_sides"])

    def draw_lid(canvas):
        canvas[lid] = [int(round(v)) for v in LID]

    over(draw_lid, LID, params["lid_alpha"], blur=0.6)

    # ---- clip to the rect with a 1 px feather so nothing crosses islands
    edge = np.ones(win.shape[:2], np.float32)
    pad = 2
    edge[:pad, :] = 0
    edge[-pad:, :] = 0
    edge[:, :pad] = 0
    edge[:, pad * -1:] = 0
    edge = cv2.GaussianBlur(edge, (5, 5), 1.2)
    keep = np.clip(edge, 0, 1)
    orig = bgr[y0:y1, x0:x1].astype(np.float32)
    bgr[y0:y1, x0:x1] = (orig * (1 - keep[..., None])
                         + win * keep[..., None]).astype(bgr.dtype)
    return int(keep.sum()), {"centre": [round(float(c[0] + x0), 1),
                                        round(float(c[1] + y0), 1)],
                             "axes": [round(a * 2, 1), round(b * 2, 1)],
                             "angle": round(angle, 1),
                             "anchor_area": int(blob.sum())}


DEFAULTS = dict(anchor_val=0.60, anchor_min_area=24, seed_r=17.0,
                axis="major", almond=2.0, grow=1.06,
                min_a=8.0, max_a=25.0, min_b=5.0,
                max_b=12.5, socket=2.2, socket_alpha=0.80, iris_a=0.72,
                iris_b=0.95, pupil_a=0.42, pupil_b=0.48, lid_sides=0.35,
                lid_alpha=0.92, lid_dark_val=0.40)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--atlas", required=True, help="dir holding <stage>_Image_0.jpg")
    ap.add_argument("--eyes", required=True, help="JSON list of stage/rects")
    ap.add_argument("--out", required=True)
    ap.add_argument("--quality", type=int, default=95)
    for k, v in DEFAULTS.items():
        ap.add_argument("--" + k.replace("_", "-"), type=type(v), default=v)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    params = {k: getattr(a, k) for k in DEFAULTS}

    spec = json.load(open(a.eyes))
    for item in spec:
        stage = item["stage"]
        # The repaint pipeline names the atlas after its glTF index
        # ("1_Image_0.jpg"), the extract stage names it after the stage
        # ("dewasa_Image_0.jpg"); accept either so --atlas can point at either.
        hits = (glob.glob(os.path.join(a.atlas, "*%s*Image_0*" % stage))
                or glob.glob(os.path.join(a.atlas, "*Image_0*")))
        if not hits:
            print("NO ATLAS for", stage, "in", a.atlas)
            continue
        src = hits[0]
        bgr = cv2.imread(src, cv2.IMREAD_COLOR)
        print("== %s  %s  %s" % (stage, os.path.basename(src), bgr.shape))
        before = bgr.copy()
        tiles = []
        for rect in item["rects"]:
            r = list(rect[:4])
            p = dict(params)
            p["centre"] = (float(rect[4]), float(rect[5])) if len(rect) >= 6 else None
            n, dbg = build_eye(bgr, r, p)
            print("   rect %s -> %d px  %s" % (rect, n, json.dumps(dbg)))
            x0, y0, x1, y1 = r
            z = 12
            for tag, img in (("before", before), ("after", bgr)):
                s = img[max(0, y0 - 22):y1 + 22, max(0, x0 - 22):x1 + 22].copy()
                s = cv2.resize(s, (s.shape[1] * z, s.shape[0] * z),
                               interpolation=cv2.INTER_NEAREST)
                cv2.putText(s, "%s x%d y%d" % (tag, x0, y0), (6, 24),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2,
                            cv2.LINE_AA)
                tiles.append(s)
        dst = os.path.join(a.out, "%s_Image_0.jpg" % stage)
        cv2.imwrite(dst, bgr, [cv2.IMWRITE_JPEG_QUALITY, a.quality])
        if tiles:
            hh = max(t.shape[0] for t in tiles)
            tiles = [cv2.copyMakeBorder(t, 0, hh - t.shape[0], 0, 0,
                                       cv2.BORDER_CONSTANT, value=(8, 8, 8))
                     for t in tiles]
            row = np.hstack([np.hstack([tiles[i], np.full((hh, 6, 3), 8, np.uint8)])
                             for i in range(len(tiles))])
            cv2.imwrite(os.path.join(a.out, "%s_eye_before_after.png" % stage), row)
        print("   wrote", dst)


if __name__ == "__main__":
    main()
