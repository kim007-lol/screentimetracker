"""Repair Momo's head rig and add animated eyelids.

Two problems with the delivered chibi GLBs:

1. The auto-rigger bound the eyes, muzzle and cheek tufts to Arm/Chest/Neck
   instead of Head. Head motion therefore left the face behind, and waving an
   arm distorted the face. The face is blended onto Neck (the real head pivot
   for these chibis) with a smooth spatial falloff; Head keeps a little of its
   rotation for ear/skull secondary motion.
2. The eyes are painted into the face texture, so they can never close. Each
   eye gets a small non-skinned lid mesh (fur dome + dark lash strip) parented
   to the Neck joint. The lid is a glTF morph target: base shape = open crease
   hugging the brow, target shape = dome covering the measured eye. Every clip
   animates the mesh `weights` channel, so the lid slides down instead of
   collapsing into a flat plane.

Usage:
    python tools/momo_rig.py in.glb out.glb
"""

from __future__ import annotations

import json
import math
import struct
import sys
from collections import Counter

import numpy as np

from momo_animate import add_accessor, load_glb, write_glb, smoothstep

# ------------------------------------------------------------------ eye data
# Eye centres, outward normals and visible opening sizes measured by
# raycasting the rendered irises through the model-viewer camera.
EYES = {
    "bayi": {
        "L": dict(c=(-0.3111, 0.2689, 0.4727), n=(-0.238, -0.019, 0.971),
                  w=0.215, h=0.212),
        "R": dict(c=(0.0822, 0.2639, 0.4648), n=(0.233, 0.015, 0.972),
                  w=0.210, h=0.214),
        "face": dict(c=(-0.06, 0.29, 0.44), r=(0.42, 0.34, 0.25)),
        "fur": (0.950, 0.800, 0.580),
    },
    "remaja": {
        "L": dict(c=(-0.2730, 0.5323, 0.4600), n=(-0.223, 0.174, 0.959),
                  w=0.102, h=0.124, yoff=0.052),
        "R": dict(c=(-0.0722, 0.5309, 0.4596), n=(0.275, 0.205, 0.939),
                  w=0.102, h=0.124, yoff=0.052),
        "face": dict(c=(-0.17, 0.50, 0.32), r=(0.30, 0.22, 0.26)),
        "fur": (0.930, 0.790, 0.580),
    },
    "dewasa": {
        "L": dict(c=(-0.0317, 0.4840, 0.2643), n=(-0.304, 0.059, 0.951),
                  w=0.118, h=0.075),
        "R": dict(c=(0.1572, 0.4825, 0.2631), n=(0.249, 0.165, 0.954),
                  w=0.125, h=0.077),
        "face": dict(c=(0.06, 0.45, 0.24), r=(0.26, 0.19, 0.22)),
        "fur": (0.840, 0.513, 0.266),
    },
}

# Spatial selection of face components per stage (bind space).
FACE_BOX = {
    "bayi": dict(x=(-0.44, 0.31), y=(0.02, 0.62), z=(0.29, 9.0)),
    "remaja": dict(x=(-0.47, 0.16), y=(0.30, 0.80), z=(0.14, 9.0)),
    "dewasa": dict(x=(-0.22, 0.33), y=(0.30, 0.75), z=(0.20, 9.0)),
}
EAR_BONES = {"Ear_L", "Ear_R"}
# Some skull-back tufts sit behind the face plane but must follow the head.
FACE_EXTRA = {
    "dewasa": dict(x=(-0.22, 0.33), y=(0.44, 0.75), z=(0.10, 0.20)),
}

NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
CTYPE = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2),
         5125: ("I", 4), 5126: ("f", 4)}


def read_acc(js, binary, idx):
    acc = js["accessors"][idx]
    bv = js["bufferViews"][acc["bufferView"]]
    n = NCOMP[acc["type"]]
    fmt, size = CTYPE[acc["componentType"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or n * size
    out = np.zeros((acc["count"], n), dtype=np.float64)
    for i in range(acc["count"]):
        out[i] = struct.unpack_from("<" + fmt * n, binary, start + i * stride)
    return out


def stage_of(path):
    low = path.lower()
    if "remaja" in low:
        return "remaja"
    if "dewasa" in low:
        return "dewasa"
    return "bayi"


def components(pos, idx):
    """Connected components with vertices welded by position.

    The export duplicates vertices along UV seams, so index-only components
    split one visible surface into two. Reweighting half of it tears the fur.
    Welding identical positions keeps every visible surface in one piece.
    """
    parent = list(range(len(pos)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for tri in idx.reshape(-1, 3):
        union(tri[0], tri[1])
        union(tri[0], tri[2])
    first_at: dict[tuple[int, int, int], int] = {}
    for v in range(len(pos)):
        key = (int(round(pos[v][0] * 100000)),
               int(round(pos[v][1] * 100000)),
               int(round(pos[v][2] * 100000)))
        if key in first_at:
            union(first_at[key], v)
        else:
            first_at[key] = v

    groups: dict[int, list[int]] = {}
    for v in range(len(pos)):
        groups.setdefault(find(v), []).append(v)
    return list(groups.values())


def raycast_grid(pos, idx, eye, n, right, up, xs, ys, offset=None):
    """Depth of the face surface under every tangent-plane point, along -n.

    `xs`/`ys` are final local coordinates. Sampling at the exact final point
    matters: shaping the silhouette after sampling would slide skin behind
    the face and let the brow poke through the lid.

    `offset` moves the sampled plane to where the lid node actually sits
    (its hinge is raised to the eye top). Without it the measured surface
    belongs to a different part of the face than the vertices it shapes.

    Every ray hit is collected and the one closest to the eye plane wins:
    the muzzle and cheek tufts sit several centimetres in front of the eye,
    and the nearest hit would otherwise dome the lid out of the face.
    """
    tri = pos[idx.reshape(-1, 3)]
    e1 = tri[:, 1] - tri[:, 0]
    e2 = tri[:, 2] - tri[:, 0]
    out = np.full(xs.shape, np.nan)
    d = -np.asarray(n)
    base = np.asarray(eye) + (0.0 if offset is None else np.asarray(offset))
    for iv in range(xs.shape[0]):
        for iu in range(xs.shape[1]):
            o = (base + np.asarray(n) * 0.6
                 + right * xs[iv, iu] + up * ys[iv, iu])
            pvec = np.cross(d, e2)
            det = np.einsum("ij,ij->i", e1, pvec)
            ok = np.abs(det) > 1e-9
            inv = np.zeros_like(det)
            inv[ok] = 1.0 / det[ok]
            tvec = o - tri[:, 0]
            u = np.einsum("ij,ij->i", tvec, pvec) * inv
            qvec = np.cross(tvec, e1)
            v = np.einsum("j,ij->i", d, qvec) * inv
            t = np.einsum("ij,ij->i", e2, qvec) * inv
            hit = ok & (u >= -1e-6) & (v >= -1e-6) & (u + v <= 1 + 1e-6) & (t > 1e-6)
            if hit.any():
                depths = 0.6 - t[hit]
                near = depths[np.abs(depths) < 0.15]
                # Frontmost skin within the eye window: a raised rim or the
                # painted eyeball itself must end up behind the lid, not in
                # front of it.
                pick = near.max() if len(near) else depths[np.abs(depths).argmin()]
                out[iv, iu] = pick
    return out


def max_filter(a, radius=1):
    """Dilate depths so the skin clears thin ridges between samples."""
    out = a.copy()
    nv, nu = a.shape
    for iv in range(nv):
        for iu in range(nu):
            iv0, iv1 = max(0, iv - radius), min(nv, iv + radius + 1)
            iu0, iu1 = max(0, iu - radius), min(nu, iu + radius + 1)
            out[iv, iu] = np.nanmax(a[iv0:iv1, iu0:iu1])
    return out


def fill_depth(out):
    """Replace ray misses with the nearest measured sample."""
    if not np.isnan(out).any():
        return out
    valid = np.argwhere(~np.isnan(out))
    for iv in range(out.shape[0]):
        for iu in range(out.shape[1]):
            if np.isnan(out[iv, iu]):
                if len(valid):
                    d2 = (valid[:, 0] - iv) ** 2 + (valid[:, 1] - iu) ** 2
                    pick = valid[d2.argmin()]
                    out[iv, iu] = out[pick[0], pick[1]]
                else:
                    out[iv, iu] = 0.0
    return out


def raycast_surface(pos, idx, eye, n, right, up, w, h, nu, nv, offset=None):
    """Depth of the face surface around an eye, measured from the eye plane."""
    xs = np.zeros((nv + 1, nu + 1))
    ys = np.zeros((nv + 1, nu + 1))
    for iv in range(nv + 1):
        for iu in range(nu + 1):
            xs[iv, iu] = -w * 0.5 + w * iu / nu
            ys[iv, iu] = h * 0.5 - h * iv / nv
    out = raycast_grid(pos, idx, eye, n, right, up, xs, ys, offset)
    return np.clip(fill_depth(out), -0.035, 0.035)


def qfrom_basis(right, up, normal):
    """Quaternion for a rotation whose local X/Y/Z axes are the given vectors."""
    r = np.array(right, dtype=np.float64)
    u = np.array(up, dtype=np.float64)
    n = np.array(normal, dtype=np.float64)
    m = np.column_stack([r, u, n])  # columns are the local axes
    trace = m[0, 0] + m[1, 1] + m[2, 2]
    if trace > 0:
        s = math.sqrt(trace + 1.0) * 2
        w = 0.25 * s
        x = (m[2, 1] - m[1, 2]) / s
        y = (m[0, 2] - m[2, 0]) / s
        z = (m[1, 0] - m[0, 1]) / s
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2]) * 2
        w = (m[2, 1] - m[1, 2]) / s
        x = 0.25 * s
        y = (m[0, 1] + m[1, 0]) / s
        z = (m[0, 2] + m[2, 0]) / s
    elif m[1, 1] > m[2, 2]:
        s = math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2]) * 2
        w = (m[0, 2] - m[2, 0]) / s
        x = (m[0, 1] + m[1, 0]) / s
        y = 0.25 * s
        z = (m[1, 2] + m[2, 1]) / s
    else:
        s = math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1]) * 2
        w = (m[1, 0] - m[0, 1]) / s
        x = (m[0, 2] + m[2, 0]) / s
        y = (m[1, 2] + m[2, 1]) / s
        z = 0.25 * s
    q = np.array([x, y, z, w])
    q /= np.linalg.norm(q)
    return tuple(float(v) for v in q)


def joint_world(js, joint):
    nodes = js["nodes"]
    names = {n.get("name"): i for i, n in enumerate(nodes) if n.get("name")}
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            parent[c] = i
    out = np.zeros(3)
    i = names[joint]
    while True:
        out += np.array(nodes[i].get("translation", (0.0, 0.0, 0.0)))
        if i not in parent:
            break
        i = parent[i]
    return out


# ---------------------------------------------------------------- lids

def band_geometry(w, ytop, ybot, depth, bow_top, bow_bot, nu, nv, lift):
    """Curved band hugging the face surface, top rim at the origin.

    Local +X is the eye's right, -Y hangs down the face, +Z points outward.
    `depth` is a (nv+1, nu+1) surface-depth array. The bows raise or lower
    the top and bottom edges toward the middle so the lid follows the eye's
    curved outline instead of cutting a straight bar across it.
    """
    verts = []
    for iv in range(nv + 1):
        v = iv / nv
        for iu in range(nu + 1):
            u = iu / nu
            x = (-0.5 + u) * w
            y = (ytop + (ybot - ytop) * v
                 + math.sin(math.pi * u) * (bow_top * (1.0 - v) + bow_bot * v))
            z = depth[iv, iu] + lift
            verts.append((x, y, z))
    norms = []
    for iv in range(nv + 1):
        for iu in range(nu + 1):
            iu0, iu1 = max(0, iu - 1), min(nu, iu + 1)
            iv0, iv1 = max(0, iv - 1), min(nv, iv + 1)
            dx = (verts[iv * (nu + 1) + iu1][0] - verts[iv * (nu + 1) + iu0][0]) or 1e-6
            dy = (verts[iv1 * (nu + 1) + iu][1] - verts[iv0 * (nu + 1) + iu][1]) or 1e-6
            dzdx = (verts[iv * (nu + 1) + iu1][2] - verts[iv * (nu + 1) + iu0][2]) / dx
            dzdy = (verts[iv1 * (nu + 1) + iu][2] - verts[iv0 * (nu + 1) + iu][2]) / dy
            n = np.array([-dzdx, -dzdy, 1.0])
            n /= np.linalg.norm(n)
            norms.append((float(n[0]), float(n[1]), float(n[2])))
    tris = []
    for iv in range(nv):
        for iu in range(nu):
            a = iv * (nu + 1) + iu
            b = a + 1
            c = a + nu + 1
            d = c + 1
            tris.extend([a, d, b, a, c, d])
    return verts, norms, tris


def surface_band(pos, idx, center, n, right, up, w, ytop, ybot,
                 nu, nv, bow_top, bow_bot, lift, clip=None, absolute=False,
                 offset=None):
    """Raycast the face across a vertical band, then build the curved band.

    `absolute` keeps the sampled depth measured from the hinge plane instead
    of normalising it to the top row; a closed lid needs that so its whole
    width clears the brow ridge, which can bulge far in front of the eye.
    `clip` caps how far the band may sink behind that reference plane.
    """
    hb = ytop - ybot
    yc = 0.5 * (ytop + ybot)
    depth = raycast_surface(pos, idx, center + up * yc, n, right, up,
                            w, hb, nu, nv, offset)
    if not absolute:
        depth = depth - depth[0, nu // 2]
    if clip is not None:
        depth = np.clip(depth, -clip, clip)
    return band_geometry(w, ytop, ybot, depth, bow_top, bow_bot, nu, nv, lift)


def almond_patch(pos, idx, center, n, right, up, w, h, nu, nv,
                 y_top, y_bot, y_end, lift, puff, offset=None):
    """Closed lid: two arcs over the eye meeting in a point at each corner.

    The top arc starts above the brow line, the bottom arc is the lid margin
    (the lash sits on it), and both meet at the eye corners. Unlike a scaled
    rectangle this is a true almond, so the closed eye has no square corners.
    """
    xs = np.zeros((nv + 1, nu + 1))
    ys = np.zeros((nv + 1, nu + 1))
    for iv in range(nv + 1):
        v = iv / nv
        for iu in range(nu + 1):
            u = iu / nu
            s = math.sin(math.pi * u)
            # y_top/y_bot/y_end are absolute distances; the corner taper
            # must not rescale them again or the patch turns into a slab.
            top = y_top + (y_end - y_top) * (1.0 - s)
            bot = y_bot + (y_end - y_bot) * (1.0 - s)
            xs[iv, iu] = (-0.5 + u) * w * 1.06
            ys[iv, iu] = top + (bot - top) * v
    depth = np.clip(max_filter(fill_depth(raycast_grid(
        pos, idx, center, n, right, up, xs, ys, offset))), -0.05, 0.05)
    zs = np.zeros_like(depth)
    verts = []
    for iv in range(nv + 1):
        v = iv / nv
        for iu in range(nu + 1):
            u = iu / nu
            dome = math.sin(math.pi * v) * math.sin(math.pi * u) ** 0.6
            zs[iv, iu] = depth[iv, iu] + lift + puff * dome
            verts.append((float(xs[iv, iu]), float(ys[iv, iu]),
                          float(zs[iv, iu])))
    # Face-like normals from the depth gradient: the closed lid then shades
    # exactly like the surrounding fur instead of like a separate shell.
    norms = []
    for iv in range(nv + 1):
        for iu in range(nu + 1):
            iu0, iu1 = max(0, iu - 1), min(nu, iu + 1)
            iv0, iv1 = max(0, iv - 1), min(nv, iv + 1)
            dx = xs[iv, iu1] - xs[iv, iu0] or 1e-6
            dy = ys[iv1, iu] - ys[iv0, iu] or 1e-6
            nx = -(zs[iv, iu1] - zs[iv, iu0]) / dx
            ny = -(zs[iv1, iu] - zs[iv0, iu]) / dy
            nl = np.array([nx, ny, 1.0])
            nl /= np.linalg.norm(nl)
            nc = right * nl[0] + up * nl[1] + np.asarray(n) * nl[2]
            nc /= np.linalg.norm(nc)
            norms.append(tuple(float(c) for c in nc))
    tris = []
    for iv in range(nv):
        for iu in range(nu):
            a = iv * (nu + 1) + iu
            b = a + 1
            c = a + nu + 1
            d = c + 1
            tris.extend([a, d, b, a, c, d])
    return verts, norms, tris


def feather_alpha(nu, nv):
    """Vertex alpha: invisible against the brow, solid over the iris.

    The top crown fades into the fur, the sides vanish at the corners, and
    the bottom stays solid under the lash line.
    """
    out = []
    for iv in range(nv + 1):
        v = iv / nv
        top = smoothstep(0.0, 0.07, v)
        bot = 1.0 - 0.45 * smoothstep(0.92, 1.0, v)
        for iu in range(nu + 1):
            u = iu / nu
            side = 1.0 - smoothstep(0.18, 0.0, min(u, 1.0 - u))
            out.append(max(0.0, min(1.0, top * bot * side)))
    return out


def add_material(js, name, color, double_sided=True, blend=False):
    mat = {
        "name": name, "doubleSided": double_sided,
        "pbrMetallicRoughness": {
            "baseColorFactor": [color[0], color[1], color[2], 1.0],
            "metallicFactor": 0.0, "roughnessFactor": 0.86,
        },
    }
    if blend:
        # Vertex alpha feathers the lid into the fur; without BLEND the
        # feather is ignored and the patch reads as a pasted sticker.
        mat["alphaMode"] = "BLEND"
    js["materials"].append(mat)
    return len(js["materials"]) - 1


def add_index_accessor(js, binary, tris):
    """Uint16 index accessor for the small eyelid meshes."""
    if len(binary) % 4:
        binary.extend(b"\x00" * (4 - len(binary) % 4))
    off = len(binary)
    data = struct.pack("<" + "H" * len(tris), *tris)
    binary.extend(data)
    js["bufferViews"].append({"buffer": 0, "byteOffset": off,
                              "byteLength": len(data)})
    js["accessors"].append({
        "bufferView": len(js["bufferViews"]) - 1,
        "componentType": 5123,
        "count": len(tris),
        "type": "SCALAR",
        "min": [int(min(tris))], "max": [int(max(tris))],
    })
    return len(js["accessors"]) - 1


def add_mesh(js, binary, prim_defs):
    """Build the lid mesh; every primitive carries one morph target."""
    prims = []
    for base_v, base_n, alpha, tgt_dv, tgt_dn, tris, mat in prim_defs:
        p = add_accessor(js, binary, base_v, "VEC3", minmax=True)
        n = add_accessor(js, binary, base_n, "VEC3")
        tp = add_accessor(js, binary, tgt_dv, "VEC3")
        tn = add_accessor(js, binary, tgt_dn, "VEC3")
        ind = add_index_accessor(js, binary, tris)
        attrs = {"POSITION": p, "NORMAL": n}
        if alpha is not None:
            rgba = [(1.0, 1.0, 1.0, float(a)) for a in alpha]
            attrs["COLOR_0"] = add_accessor(js, binary, rgba, "VEC4")
        prims.append({"attributes": attrs,
                      "indices": ind, "material": mat,
                      "targets": [{"POSITION": tp, "NORMAL": tn}]})
    js["meshes"].append({"name": "Eyelids", "primitives": prims,
                         "weights": [0.0]})
    return len(js["meshes"]) - 1


def make_lids(js, binary, stage, neck_pos, pos, idx):
    cfg = EYES[stage]
    fur = add_material(js, f"LidFur_{stage}", cfg["fur"], blend=True)
    lash = add_material(js, "LidLash", (0.045, 0.018, 0.008))
    made = {}
    for side in ("L", "R"):
        eye = cfg[side]
        center = np.array(eye["c"])
        n = np.array(eye["n"])
        n /= np.linalg.norm(n)
        right = np.cross(np.array((0.0, 1.0, 0.0)), n)
        right /= np.linalg.norm(right)
        up = np.cross(n, right)
        up /= np.linalg.norm(up)
        w, h = eye["w"], eye["h"]
        yoff = eye.get("yoff", h * 0.5)
        # Where the lid node lands in model space; depths must be sampled
        # there, not at the eye centre, or the patch is shaped by skin it
        # does not actually cover.
        off = up * yoff + n * 0.0025
        open_h = max(0.035 * h, 0.008)
        nu, nv = 20, 12

        # Open: a hairline crease parked just inside the skull, so nothing
        # is painted on the brow between blinks.
        bv, _, bt = surface_band(pos, idx, center, n, right, up, w,
                                 0.0, -open_h, nu, nv, 0.06 * h, 0.06 * h,
                                 0.003, 0.006, offset=off)
        # Closed: almond lid whose margin sits at the lower eye rim.
        cv, cn, ct = almond_patch(pos, idx, center, n, right, up, w, h,
                                  nu, nv, 0.10 * h, -1.05 * h, -0.52 * h,
                                  0.004, 0.002, offset=off)
        bn = recalc_normals(bv, bt)
        dv = [(c[0] - b[0], c[1] - b[1], c[2] - b[2])
              for b, c in zip(bv, cv)]
        dn = [(c[0] - b[0], c[1] - b[1], c[2] - b[2])
              for b, c in zip(bn, cn)]
        alpha = feather_alpha(nu, nv)

        # Lash: the lid's own bottom rows. Hidden inside the face while the
        # eye is open, surfaced just in front of the margin when closed.
        first = (nv - 1) * (nu + 1)
        lbv = [(v[0], v[1], v[2] - 0.008) for v in bv[first:]]
        leb = [(v[0], v[1], v[2] + 0.003) for v in cv[first:]]
        ldv = [(c[0] - b[0], c[1] - b[1], c[2] - b[2])
               for b, c in zip(lbv, leb)]
        lbt = []
        for i in range(len(bt) // 3):
            tri = bt[i * 3:i * 3 + 3]
            if min(tri) >= first:
                lbt.extend(v - first for v in tri)
        lbn = recalc_normals(lbv, lbt)
        ldn = [(c[0] - b[0], c[1] - b[1], c[2] - b[2])
               for b, c in zip(lbn, recalc_normals(leb, lbt))]

        mesh = add_mesh(js, binary, [(bv, bn, alpha, dv, dn, bt, fur),
                                     (lbv, lbn, None, ldv, ldn, lbt, lash)])
        origin = center + off
        node = {
            "name": f"Blink_{side}",
            "mesh": mesh,
            "translation": [float(v) for v in (origin - neck_pos)],
            "rotation": list(qfrom_basis(right, up, n)),
        }
        js["nodes"].append(node)
        parent_idx = next(i for i, nd in enumerate(js["nodes"])
                          if nd.get("name") == "Neck")
        js["nodes"][parent_idx].setdefault("children", []).append(len(js["nodes"]) - 1)
        made[side] = len(js["nodes"]) - 1
    return made


def recalc_normals(verts, tris):
    """Smooth vertex normals from the final deformed shape."""
    acc = [np.zeros(3) for _ in verts]
    for i in range(0, len(tris), 3):
        a, b, c = tris[i], tris[i + 1], tris[i + 2]
        pa, pb, pc = (np.array(verts[j]) for j in (a, b, c))
        fn = np.cross(pb - pa, pc - pa)
        for j in (a, b, c):
            acc[j] += fn
    out = []
    for v in acc:
        l = np.linalg.norm(v)
        out.append(tuple(v / l) if l > 1e-9 else (0.0, 0.0, 1.0))
    return out


# ---------------------------------------------------------------- blink curves

def ev(t, c, peak=1.0, up=0.06, hold=0.02, down=0.10):
    if t < c - up or t > c + hold + down:
        return 0.0
    if t < c:
        return peak * smoothstep(c - up, c, t)
    if t <= c + hold:
        return peak
    return peak * (1.0 - smoothstep(c + hold, c + hold + down, t))


def blink_curves(stage, name, times):
    L, R = [], []
    for t in times:
        l = r = 0.0
        if name == "idle_fresh":
            base = 0.0
            for c, pk in ((1.72, 1.0), (1.94, 1.0), (6.02, 1.0), (7.36, 0.92)):
                v = ev(t, c, pk)
                base = max(base, v)
            squint = ev(t, 4.05, 0.52, up=0.20, hold=0.10, down=0.26)
            wink = ev(t, 3.45, 0.95, up=0.06, hold=0.05, down=0.10)
            l = max(base, squint)
            r = max(base, squint, wink)
        elif name == "idle_tired":
            base = 0.52
            sigh = ev(t, 5.55, 0.30, up=0.35, hold=0.25, down=0.45)
            for c, pk in ((2.35, 0.88), (6.95, 0.8)):
                base = max(base, ev(t, c, pk, up=0.10, hold=0.04, down=0.26))
            l = min(1.0, base + sigh)
            r = min(1.0, base + sigh * 0.9)
        elif name == "idle_critical":
            base = 0.30
            for c, pk in ((0.55, 0.9), (1.55, 0.55), (2.25, 0.85)):
                base = max(base, ev(t, c, pk, up=0.05, hold=0.02, down=0.11))
            l = r = base
        elif name == "sleep":
            l = r = 1.0
            flutter = ev(t, 3.3, 0.04, up=0.1, hold=0.05, down=0.2)
            l -= flutter
            r -= flutter * 0.6
        elif name == "tap_reaction":
            keys = [(0.0, 0.0), (0.10, 0.85), (0.22, 0.9), (0.34, 0.0),
                    (0.47, 0.55), (0.60, 0.2), (0.72, 0.0), (1.0, 0.0)]
            l = r = keyed_value(keys, t)
        elif name == "celebrate":
            l = keyed_value([(0.0, 0.0), (0.14, 0.55), (0.32, 0.0),
                             (1.28, 0.0), (1.42, 0.45), (1.62, 0.0),
                             (2.0, 0.0)], t)
            r = keyed_value([(0.0, 0.0), (0.14, 0.55), (0.32, 0.0),
                             (0.55, 0.0), (0.62, 0.95), (0.78, 0.95),
                             (0.90, 0.0), (1.05, 0.0), (1.12, 0.95),
                             (1.28, 0.95), (1.42, 0.45), (1.62, 0.0),
                             (2.0, 0.0)], t)
        L.append(max(0.0, min(1.0, l)))
        R.append(max(0.0, min(1.0, r)))
    return L, R


def keyed_value(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            u = u * u * (3 - 2 * u)
            return v0 + (v1 - v0) * u
    return keys[-1][1]


def add_blink_channels(js, binary, stage, lid_nodes):
    for anim in js["animations"]:
        times = read_acc(js, binary, anim["samplers"][0]["input"])[:, 0]
        L, R = blink_curves(stage, anim["name"], times)
        for side, values in (("L", L), ("R", R)):
            src = add_accessor(js, binary, [(float(t),) for t in times], "SCALAR",
                               minmax=True)
            out = add_accessor(js, binary, [(v,) for v in values], "SCALAR")
            anim["samplers"].append({"input": src, "output": out,
                                     "interpolation": "LINEAR"})
            anim["channels"].append({
                "sampler": len(anim["samplers"]) - 1,
                "target": {"node": lid_nodes[side], "path": "weights"},
            })


# ---------------------------------------------------------------- reweight


def reweight_face(js, binary, stage):
    """Blend the face onto the Neck bone with a smooth spatial falloff.

    The neck is the anatomical head pivot for these chibis; the auto-rigger
    left the eyes, muzzle and cheek tufts on Arm/Chest. A smooth field keeps
    every overlapping fur tuft moving together; no damping by the old limb
    weights, because those weights are exactly what pulled the eyes off the
    face whenever the arm moved.
    """
    prim = js["meshes"][0]["primitives"][0]
    a = prim["attributes"]
    pos = read_acc(js, binary, a["POSITION"])
    joints_acc = js["accessors"][a["JOINTS_0"]]
    weights_acc = js["accessors"][a["WEIGHTS_0"]]
    joints_bv = js["bufferViews"][joints_acc["bufferView"]]
    weights_bv = js["bufferViews"][weights_acc["bufferView"]]
    j_start = joints_bv.get("byteOffset", 0) + joints_acc.get("byteOffset", 0)
    w_start = weights_bv.get("byteOffset", 0) + weights_acc.get("byteOffset", 0)
    j_stride = joints_bv.get("byteStride") or CTYPE[joints_acc["componentType"]][1] * 4
    w_stride = weights_bv.get("byteStride") or CTYPE[weights_acc["componentType"]][1] * 4
    j_fmt = CTYPE[joints_acc["componentType"]][0]

    skin = js["skins"][0]
    neck_node = next(i for i, n in enumerate(js["nodes"]) if n.get("name") == "Neck")
    neck_slot = skin["joints"].index(neck_node)

    cfg = EYES[stage]["face"]
    c = np.array(cfg["c"], dtype=np.float64)
    r = np.array(cfg["r"], dtype=np.float64)
    joints = read_acc(js, binary, a["JOINTS_0"]).astype(int)
    weights = read_acc(js, binary, a["WEIGHTS_0"])
    moved = 0
    for v in range(len(pos)):
        q = (pos[v] - c) / r
        dist = float(np.sqrt(np.dot(q, q)))
        f = 1.0 - smoothstep(1.0, 1.28, dist)
        if f <= 0.001:
            continue
        slot_of = {int(j): w for j, w in zip(joints[v], weights[v]) if w > 0.001}
        old = np.zeros(22)
        for s, w in slot_of.items():
            if s < 22:
                old[s] = w
        old /= old.sum() or 1.0
        blended = (1.0 - f) * old
        blended[neck_slot] += f
        blended /= blended.sum()
        order = np.argsort(-blended)
        top = [(int(i), float(blended[i])) for i in order[:4] if blended[i] > 0.0005]
        sl = [t[0] for t in top] + [0] * (4 - len(top))
        wt = [t[1] for t in top] + [0.0] * (4 - len(top))
        struct.pack_into("<" + j_fmt * 4, binary, j_start + v * j_stride, *sl)
        struct.pack_into("<ffff", binary, w_start + v * w_stride, *wt)
        moved += 1
    return moved


def main(path_in, path_out):
    stage = stage_of(path_in)
    js, binary = load_glb(path_in)
    hp = joint_world(js, "Neck")
    moved = reweight_face(js, binary, stage)
    prim = js["meshes"][0]["primitives"][0]
    pos = read_acc(js, binary, prim["attributes"]["POSITION"])
    idx = read_acc(js, binary, prim["indices"]).astype(int).reshape(-1)
    lids = make_lids(js, binary, stage, hp, pos, idx)
    add_blink_channels(js, binary, stage, lids)
    js["buffers"][0]["byteLength"] = len(binary)
    write_glb(js, binary, path_out)
    print(f"{stage}: reweighted {moved} verts, lids at {lids} -> {path_out}"
          f" ({len(binary)/1e6:.2f} MB bin)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: momo_rig.py input.glb output.glb")
    main(sys.argv[1], sys.argv[2])
