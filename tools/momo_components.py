"""Inspect Momo GLB mesh components near the face for rig repair.

Prints connected components with centroid, bbox, dominant joint and distance
to a per-stage eye midpoint so a human can pick face/head components that the
auto-rigger bound to Arm/Chest/Neck instead of Head.
"""

from __future__ import annotations

import json
import struct
import sys
from collections import Counter, deque

import numpy as np

EYE_MID = {
    "bayi": (-0.116, 0.283, 0.469),
    "remaja": (-0.174, 0.5258, 0.457),
    "dewasa": (0.059, 0.4671, 0.265),
}


def load(path):
    raw = open(path, "rb").read()
    off, js, binary = 12, None, b""
    while off < len(raw):
        clen, ctype = struct.unpack("<II", raw[off:off + 8])
        off += 8
        data = raw[off:off + clen]
        off += clen
        if ctype == 0x4E4F534A:
            js = json.loads(data.decode("utf-8"))
        elif ctype == 0x004E4942:
            binary = data
    return js, binary


def comp_type(n):
    return {5120: "b", 5121: "B", 5122: "h", 5123: "H", 5125: "I", 5126: "f"}[n]


NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def read_acc(js, binary, idx):
    acc = js["accessors"][idx]
    bv = js["bufferViews"][acc["bufferView"]]
    n = NCOMP[acc["type"]]
    fmt = comp_type(acc["componentType"])
    size = struct.calcsize(fmt)
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or n * size
    out = np.zeros((acc["count"], n), dtype=np.float64)
    for i in range(acc["count"]):
        vals = struct.unpack_from("<" + fmt * n, binary, start + i * stride)
        out[i] = vals
    return out


def main(path):
    js, binary = load(path)
    stage = "bayi"
    low = path.lower()
    if "remaja" in low:
        stage = "remaja"
    elif "dewasa" in low:
        stage = "dewasa"
    eye = np.array(EYE_MID[stage])

    prim = js["meshes"][0]["primitives"][0]
    attrs = prim["attributes"]
    pos = read_acc(js, binary, attrs["POSITION"])
    joints = read_acc(js, binary, attrs["JOINTS_0"]).astype(int)
    weights = read_acc(js, binary, attrs["WEIGHTS_0"])
    idx = read_acc(js, binary, prim["indices"]).astype(int).reshape(-1)

    # Build adjacency from triangles, union-find components.
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

    groups: dict[int, list[int]] = {}
    for v in range(len(pos)):
        groups.setdefault(find(v), []).append(v)

    node_names = {
        i: (n.get("name") or f"node{i}") for i, n in enumerate(js["nodes"])
    }
    skin_joints = js["skins"][0]["joints"]
    # JOINTS_0 indexes into skin.joints, not the node array.
    bone_name = {i: node_names[j] for i, j in enumerate(skin_joints)}

    rows = []
    for root, verts in groups.items():
        pts = pos[verts]
        c = pts.mean(axis=0)
        # Dominant bone by summed weight.
        wsum = weights[verts].sum(axis=0)
        bone_counts = Counter()
        for wrow, jrow in zip(weights[verts], joints[verts]):
            for w, j in zip(wrow, jrow):
                if w > 0.05:
                    bone_counts[bone_name[j]] += w
        dom = bone_counts.most_common(2)
        dist = float(np.linalg.norm(c - eye))
        rows.append((dist, len(verts), c, pts.min(axis=0), pts.max(axis=0), dom))

    rows.sort(key=lambda r: r[0])
    print(f"{stage}: {len(rows)} components, {len(pos)} verts")
    for dist, nv, c, mn, mx, dom in rows[:34]:
        names = ", ".join(f"{b}:{w:.0f}" for b, w in dom)
        print(
            f"id={root if False else ''} d={dist:.3f} nv={nv:4d} "
            f"c=({c[0]:+.3f},{c[1]:+.3f},{c[2]:+.3f}) "
            f"bb=({mn[0]:+.2f},{mn[1]:+.2f},{mn[2]:+.2f})..({mx[0]:+.2f},{mx[1]:+.2f},{mx[2]:+.2f}) "
            f"{names}"
        )
    # Need component ids: redo with ids kept.
    print("\n--- with ids ---")
    id_rows = []
    for root, verts in groups.items():
        pts = pos[verts]
        c = pts.mean(axis=0)
        bone_counts = Counter()
        for wrow, jrow in zip(weights[verts], joints[verts]):
            for w, j in zip(wrow, jrow):
                if w > 0.05:
                    bone_counts[bone_name[j]] += w
        dom = bone_counts.most_common(1)
        dist = float(np.linalg.norm(c - eye))
        id_rows.append((dist, root, len(verts), c, dom))
    id_rows.sort()
    for dist, root, nv, c, dom in id_rows[:34]:
        name = dom[0][0] if dom else "?"
        print(f"{root}\td={dist:.3f}\tnv={nv}\tc=({c[0]:+.3f},{c[1]:+.3f},{c[2]:+.3f})\t{name}")


if __name__ == "__main__":
    main(sys.argv[1])
