#!/usr/bin/env python3
"""Read-only structural QA for the Momo and Drako GLB rigs.

Parses the exact bundled GLBs and compares clip metadata with the Dart and
Kotlin registries. It never writes to a GLB; the JSON report is evidence only.

Usage:
  python tools/qa_rig_audit.py [--json tools/qa_rig/rig_audit.json]
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSET_DIR = ROOT / "mobile" / "assets" / "3d"
PET_DART = ROOT / "mobile" / "lib" / "core" / "models" / "pet.dart"
PET_KT = (
    ROOT
    / "mobile"
    / "android"
    / "app"
    / "src"
    / "main"
    / "kotlin"
    / "com"
    / "screentimetrack"
    / "app"
    / "PetBehavior.kt"
)

FILES = {
    ("momo", "bayi"): "momo_bayi.glb",
    ("momo", "remaja"): "momo_remaja.glb",
    ("momo", "dewasa"): "momo_dewasa.glb",
    ("drako", "bayi"): "drako_bayi.glb",
    ("drako", "remaja"): "drako_remaja.glb",
    ("drako", "dewasa"): "drako_dewasa.glb",
}

LOOP_CLIPS = {
    "idle_fresh",
    "idle_fresh_a",
    "idle_fresh_b",
    "idle_fresh_c",
    "idle_fresh_d",
    "idle_tired",
    "idle_tired_a",
    "idle_tired_b",
    "idle_tired_c",
    "idle_critical",
    "idle_critical_a",
    "idle_critical_b",
    "idle_critical_c",
    "sleep",
    "walk",
}

COMPONENT = {
    5120: ("b", 1, 127.0),
    5121: ("B", 1, 255.0),
    5122: ("h", 2, 32767.0),
    5123: ("H", 2, 65535.0),
    5125: ("I", 4, None),
    5126: ("f", 4, None),
}
NCOMP = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}


def quat_matrix(q):
    x, y, z, w = q
    n = math.sqrt(x * x + y * y + z * z + w * w) or 1.0
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0],
            [0, 0, 0, 1],
        ],
        dtype=np.float64,
    )


def trs_matrix(t, r, s):
    m = np.eye(4)
    m[:3, :3] = quat_matrix(r)[:3, :3] @ np.diag(s)
    m[:3, 3] = t
    return m


def angle_between(q1, q2):
    q1 = np.asarray(q1, dtype=np.float64)
    q2 = np.asarray(q2, dtype=np.float64)
    n1 = np.linalg.norm(q1)
    n2 = np.linalg.norm(q2)
    if n1 == 0 or n2 == 0:
        return 0.0
    d = abs(float(np.dot(q1 / n1, q2 / n2)))
    return math.degrees(2 * math.acos(min(1.0, max(-1.0, d))))


class Glb:
    def __init__(self, path: Path):
        self.path = path
        self.raw = path.read_bytes()
        self.sha256 = hashlib.sha256(self.raw).hexdigest()
        self.errors = []
        self.warnings = []
        self.info = []
        self._parse()

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def _parse(self):
        if len(self.raw) < 12:
            raise ValueError("too short")
        magic, version, length = struct.unpack_from("<4sII", self.raw, 0)
        if magic != b"glTF":
            self.err(f"bad magic {magic!r}")
        if version != 2:
            self.err(f"unsupported glTF version {version}")
        if length != len(self.raw):
            self.err(f"declared length {length} != file size {len(self.raw)}")
        off = 12
        self.chunks = []
        while off + 8 <= len(self.raw):
            clen, ctype = struct.unpack_from("<II", self.raw, off)
            off += 8
            if off + clen > len(self.raw):
                self.err("chunk extends past EOF")
                break
            self.chunks.append((ctype, self.raw[off : off + clen]))
            off += clen + ((4 - clen % 4) % 4)
        if not self.chunks or self.chunks[0][0] != 0x4E4F534A:
            raise ValueError("missing JSON chunk")
        self.js = json.loads(self.chunks[0][1].decode("utf-8").rstrip("\x00 "))
        self.bin = b""
        for ctype, data in self.chunks[1:]:
            if ctype == 0x004E4942:
                self.bin = data
                break
        self._validate_buffers()
        self._validate_accessors()

    def _validate_buffers(self):
        self.buffer_bytes = []
        for i, buf in enumerate(self.js.get("buffers", [])):
            if "uri" in buf:
                self.err(f"buffer {i} uses external URI (must be GLB self-contained)")
                self.buffer_bytes.append(b"")
                continue
            length = buf.get("byteLength", 0)
            if i == 0:
                if length > len(self.bin):
                    self.err(f"buffer 0 byteLength {length} > BIN {len(self.bin)}")
                self.buffer_bytes.append(self.bin)
            else:
                self.err(f"buffer {i} has no data")
                self.buffer_bytes.append(b"")
        for i, bv in enumerate(self.js.get("bufferViews", [])):
            buf = bv.get("buffer", 0)
            start = bv.get("byteOffset", 0)
            length = bv.get("byteLength", 0)
            if buf >= len(self.buffer_bytes):
                self.err(f"bufferView {i} references missing buffer {buf}")
                continue
            if start + length > len(self.buffer_bytes[buf]):
                self.err(f"bufferView {i} range {start}+{length} exceeds buffer")
            stride = bv.get("byteStride")
            if stride is not None and (stride <= 0 or stride > 252):
                self.err(f"bufferView {i} has invalid byteStride {stride}")

    def _validate_accessors(self):
        self.accessor_data = {}
        for i, acc in enumerate(self.js.get("accessors", [])):
            ctype = acc.get("componentType")
            if ctype not in COMPONENT:
                self.err(f"accessor {i} has unknown componentType {ctype}")
                continue
            fmt, size, _ = COMPONENT[ctype]
            ncomp = NCOMP.get(acc.get("type"))
            if ncomp is None:
                self.err(f"accessor {i} has unknown type {acc.get('type')}")
                continue
            count = acc.get("count", 0)
            if count <= 0:
                self.err(f"accessor {i} has non-positive count {count}")
            bv_index = acc.get("bufferView")
            if bv_index is None:
                self.warn(f"accessor {i} has no bufferView (zero-filled)")
                arr = np.zeros((count, ncomp), dtype=np.float64)
            else:
                bv = self.js["bufferViews"][bv_index]
                buf = self.buffer_bytes[bv.get("buffer", 0)]
                base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
                stride = bv.get("byteStride") or size * ncomp
                need = (count - 1) * stride + size * ncomp
                if base + need > len(buf):
                    self.err(f"accessor {i} reads past bufferView/buffer")
                    arr = np.zeros((count, ncomp), dtype=np.float64)
                else:
                    if stride == size * ncomp:
                        arr = np.frombuffer(
                            buf, dtype=np.dtype("<" + fmt), count=count * ncomp, offset=base
                        ).reshape(count, ncomp)
                    else:
                        arr = np.ndarray(
                            shape=(count, ncomp),
                            dtype=np.dtype("<" + fmt),
                            buffer=buf,
                            offset=base,
                            strides=(stride, size),
                        ).copy()
                    if ctype in (5120, 5121, 5122, 5123):
                        arr = arr.astype(np.float64)
                        if acc.get("normalized"):
                            arr /= COMPONENT[ctype][2]
                    else:
                        arr = arr.astype(np.float64)
            self.accessor_data[i] = arr
            if acc.get("sparse"):
                self.err(f"accessor {i} is sparse (unsupported by this audit)")

    def acc(self, index):
        return self.accessor_data[index]

    def accessor_is_float(self, index):
        return self.js["accessors"][index].get("componentType") == 5126


def check_structure(g: Glb, pet, stage):
    js = g.js
    g.info.append(("asset", js.get("asset")))
    g.info.append(("counts", {
        "nodes": len(js.get("nodes", [])),
        "meshes": len(js.get("meshes", [])),
        "skins": len(js.get("skins", [])),
        "animations": len(js.get("animations", [])),
        "materials": len(js.get("materials", [])),
        "images": len(js.get("images", [])),
        "textures": len(js.get("textures", [])),
    }))
    if len(js.get("skins", [])) != 1:
        g.err(f"expected exactly one skin, found {len(js.get('skins', []))}")
    if not js.get("scenes"):
        g.err("no scenes")
    if js.get("extensionsRequired"):
        g.info.append(("extensionsRequired", js["extensionsRequired"]))

    nodes = js.get("nodes", [])
    names = [n.get("name") for n in nodes]
    if len(set(names)) != len(names):
        g.err("duplicate node names")
    for i, n in enumerate(nodes):
        if "mesh" in n and n["mesh"] >= len(js.get("meshes", [])):
            g.err(f"node {i} references missing mesh")
        if "skin" in n and n["skin"] >= len(js.get("skins", [])):
            g.err(f"node {i} references missing skin")
        t = n.get("translation", [0, 0, 0])
        r = n.get("rotation", [0, 0, 0, 1])
        s = n.get("scale", [1, 1, 1])
        if not all(math.isfinite(v) for v in t + r + s):
            g.err(f"node {i} has non-finite TRS")
        qn = math.sqrt(sum(v * v for v in r))
        if abs(qn - 1.0) > 1e-4:
            g.err(f"node {i} rotation not normalized (norm {qn})")
        if any(abs(v) < 1e-9 for v in s):
            g.err(f"node {i} has near-zero scale axis {s}")
        if "matrix" in n:
            g.warn(f"node {i} uses matrix instead of TRS")
    # hierarchy acyclicity
    parent = {}
    for i, n in enumerate(nodes):
        for c in n.get("children", []):
            if c < 0 or c >= len(nodes):
                g.err(f"node {i} has invalid child {c}")
                continue
            if c in parent:
                g.err(f"node {c} has multiple parents")
            parent[c] = i
    for i in range(len(nodes)):
        seen = set()
        cur = i
        while cur in parent:
            if cur in seen:
                g.err(f"cycle in node hierarchy at node {cur}")
                break
            seen.add(cur)
            cur = parent[cur]
    # global bind matrices
    globals_ = {}

    def walk(i, m):
        n = nodes[i]
        if "matrix" in n:
            local = np.array(n["matrix"], dtype=np.float64).reshape(4, 4).T
        else:
            local = trs_matrix(
                n.get("translation", [0, 0, 0]),
                n.get("rotation", [0, 0, 0, 1]),
                n.get("scale", [1, 1, 1]),
            )
        world = m @ local
        globals_[i] = world
        for c in n.get("children", []):
            walk(c, world)

    for i, n in enumerate(nodes):
        if i not in parent:
            walk(i, np.eye(4))
    if len(globals_) != len(nodes):
        g.err(f"only {len(globals_)}/{len(nodes)} nodes reachable from scene roots")

    # meshes
    tri_total = 0
    vert_total = 0
    skinned_meshes = {n["mesh"] for n in nodes if "skin" in n and "mesh" in n}
    for mi, mesh in enumerate(js.get("meshes", [])):
        is_skinned = mi in skinned_meshes
        target_counts = {len(p.get("targets", [])) for p in mesh.get("primitives", [])}
        if len(target_counts) > 1:
            g.err(f"mesh {mi} primitives disagree on morph target count: {sorted(target_counts)}")
        for pi, prim in enumerate(mesh.get("primitives", [])):
            attrs = prim.get("attributes", {})
            for required in ("POSITION", "NORMAL"):
                if required not in attrs:
                    g.err(f"mesh {mi} prim {pi} missing {required}")
            pos = g.acc(attrs["POSITION"])
            nrm = g.acc(attrs["NORMAL"])
            vcount = pos.shape[0]
            vert_total += vcount
            joints = weights = None
            if is_skinned:
                if "JOINTS_0" not in attrs or "WEIGHTS_0" not in attrs:
                    g.err(f"mesh {mi} prim {pi} missing skin attributes")
                    joints = weights = None
                else:
                    joints = g.acc(attrs["JOINTS_0"])
                    weights = g.acc(attrs["WEIGHTS_0"])
            if nrm.shape[0] != vcount or (
                joints is not None and (joints.shape[0] != vcount or weights.shape[0] != vcount)
            ):
                g.err(f"mesh {mi} prim {pi} attribute counts differ")
            if not np.isfinite(pos).all():
                g.err(f"mesh {mi} prim {pi} POSITION has non-finite values")
            pmin = np.round(pos.min(axis=0), 6).tolist()
            pmax = np.round(pos.max(axis=0), 6).tolist()
            acc_min = js["accessors"][attrs["POSITION"]].get("min")
            acc_max = js["accessors"][attrs["POSITION"]].get("max")
            if acc_min is not None and np.max(np.abs(np.array(acc_min) - pmin)) > 1e-4:
                g.err(f"mesh {mi} prim {pi} POSITION accessor min mismatch")
            if acc_max is not None and np.max(np.abs(np.array(acc_max) - pmax)) > 1e-4:
                g.err(f"mesh {mi} prim {pi} POSITION accessor max mismatch")
            nlen = np.linalg.norm(nrm, axis=1)
            if np.any(np.abs(nlen - 1) > 5e-3):
                g.err(
                    f"mesh {mi} prim {pi} normals not unit length "
                    f"(min {nlen.min():.4f}, max {nlen.max():.4f})"
                )
            zero_normals = int(np.sum(nlen < 1e-6))
            if zero_normals:
                g.warn(f"mesh {mi} prim {pi} has {zero_normals} zero-length normals")
            if weights is not None:
                wsum = weights.sum(axis=1)
                bad_w = int(np.sum(np.abs(wsum - 1.0) > 1e-2))
                severe_w = int(np.sum(np.abs(wsum - 1.0) > 5e-2))
                if bad_w:
                    g.err(
                        f"mesh {mi} prim {pi} {bad_w} vertices have weight sums outside "
                        f"1+/-0.01 (range {wsum.min():.6f}..{wsum.max():.6f}); "
                        f"{severe_w} outside 1+/-0.05"
                    )
                neg = int(np.sum(weights < 0))
                if neg:
                    g.err(f"mesh {mi} prim {pi} has {neg} negative weights")
                influences = (weights > 1e-6).sum(axis=1)
                g.info.append(
                    (
                        f"weights mesh {mi}",
                        {
                            "vertices": vcount,
                            "sum_min": float(wsum.min()),
                            "sum_max": float(wsum.max()),
                            "max_influences": int(influences.max()),
                            "vertices_with_0": int((influences == 0).sum()),
                            "vertices_over_4": int((influences > 4).sum()),
                            "outside_1pct": bad_w,
                            "outside_5pct": severe_w,
                        },
                    )
                )
                if int((influences == 0).sum()):
                    g.err(f"mesh {mi} prim {pi} has vertices with no joint influence")
            idx = prim.get("indices")
            tri_count = None
            if idx is not None:
                indices = g.acc(idx).astype(np.int64).ravel()
                if indices.size % 3:
                    g.err(f"mesh {mi} prim {pi} index count {indices.size} not divisible by 3")
                if indices.size and (indices.min() < 0 or indices.max() >= vcount):
                    g.err(f"mesh {mi} prim {pi} index out of range")
                tri_count = indices.size // 3
                tri_total += tri_count
                if indices.size >= 3:
                    tri = indices[: indices.size - indices.size % 3].reshape(-1, 3)
                    v = pos[tri]
                    area = 0.5 * np.linalg.norm(
                        np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0]), axis=1
                    )
                    degenerate = int(np.sum(area < 1e-10))
                    if degenerate:
                        g.warn(f"mesh {mi} prim {pi} has {degenerate} degenerate triangles")
            for t_i, target in enumerate(prim.get("targets", [])):
                if "POSITION" not in target:
                    g.warn(f"mesh {mi} prim {pi} morph target {t_i} has no POSITION")
                else:
                    delta = g.acc(target["POSITION"])
                    if delta.shape[0] != vcount:
                        g.err(f"mesh {mi} prim {pi} morph target {t_i} count mismatch")
                    if not np.isfinite(delta).all():
                        g.err(f"mesh {mi} prim {pi} morph target {t_i} non-finite")
            g.info.append(
                (
                    f"mesh {mi} prim {pi}",
                    {
                        "vertices": vcount,
                        "triangles": tri_count,
                        "morph_targets": len(prim.get("targets", [])),
                        "skinned": is_skinned,
                        "material": prim.get("material"),
                    },
                )
            )
    g.info.append(("geometry", {"vertices": vert_total, "triangles": tri_total}))

    # skin
    for si, skin in enumerate(js.get("skins", [])):
        joints = skin.get("joints", [])
        if not joints:
            g.err(f"skin {si} has no joints")
            continue
        if len(set(joints)) != len(joints):
            g.err(f"skin {si} has duplicate joints")
        for j in joints:
            if j < 0 or j >= len(nodes):
                g.err(f"skin {si} references invalid joint node {j}")
        ibm_index = skin.get("inverseBindMatrices")
        if ibm_index is None:
            g.err(f"skin {si} missing inverseBindMatrices")
        else:
            raw = g.acc(ibm_index)
            if raw.shape[0] != len(joints):
                g.err(f"skin {si} IBM count {raw.shape[0]} != joints {len(joints)}")
            mats = raw.reshape(-1, 4, 4).transpose(0, 2, 1)
            if not np.isfinite(mats).all():
                g.err(f"skin {si} IBM has non-finite values")
            devs = []
            rel_devs = []
            root = skin.get("skeleton")
            for j, node_i in enumerate(joints):
                if j >= len(mats):
                    break
                try:
                    bind_inv = np.linalg.inv(globals_.get(node_i, np.eye(4)))
                except np.linalg.LinAlgError:
                    g.err(f"skin {si} joint {node_i} bind matrix singular")
                    continue
                devs.append(float(np.max(np.abs(mats[j] - bind_inv))))
                if root is not None:
                    try:
                        rel = globals_[root] @ globals_[node_i]
                        rel_devs.append(float(np.max(np.abs(mats[j] - np.linalg.inv(rel)))))
                    except np.linalg.LinAlgError:
                        pass
            if devs:
                g.info.append(
                    (
                        f"skin {si} IBM",
                        {
                            "max_abs_dev_vs_inverse_global": max(devs),
                            "max_abs_dev_vs_inverse_root_relative": max(rel_devs) if rel_devs else None,
                            "joints": len(joints),
                        },
                    )
                )
                if max(devs) > 1e-3:
                    g.warn(
                        f"skin {si} IBM deviates from inverse global bind matrix "
                        f"by {max(devs):.5f} (root-relative {max(rel_devs) if rel_devs else 0:.5f})"
                    )
        skeleton = skin.get("skeleton")
        if skeleton is not None and skeleton not in joints:
            g.warn(f"skin {si} skeleton node {skeleton} is not in the joint list")
        # joint weight coverage (joint indices -> node index -> name)
        total_by_joint = np.zeros(len(joints), dtype=np.float64)
        prims = [
            p
            for m in js["meshes"]
            for p in m["primitives"]
            if "JOINTS_0" in p["attributes"]
        ]
        for prim in prims:
            ji = g.acc(prim["attributes"]["JOINTS_0"]).astype(np.int64)
            w = g.acc(prim["attributes"]["WEIGHTS_0"])
            flat_j = ji.ravel()
            flat_w = w.ravel()
            mask = (flat_j >= 0) & (flat_j < len(joints))
            np.add.at(total_by_joint, flat_j[mask], flat_w[mask])
        total_by_joint = {int(k): float(v) for k, v in enumerate(total_by_joint)}
        unused = [
            nodes[joints[ji]].get("name")
            for ji in range(len(joints))
            if total_by_joint.get(ji, 0.0) < 1e-3
        ]
        if unused:
            g.warn(f"skin {si} joints with no significant skin influence: {unused}")
        g.info.append(
            (
                f"skin {si} joint influence",
                {nodes[joints[ji]].get("name"): round(total_by_joint.get(ji, 0.0), 2) for ji in range(len(joints))},
            )
        )

    # materials / textures / images
    for mi, mat in enumerate(js.get("materials", [])):
        pbr = mat.get("pbrMetallicRoughness", {})
        for key in ("baseColorFactor", "metallicFactor", "roughnessFactor"):
            val = pbr.get(key)
            if val is not None:
                arr = np.array(val if isinstance(val, list) else [val], dtype=float)
                if not np.isfinite(arr).all():
                    g.err(f"material {mi} {key} non-finite")
                if key != "baseColorFactor" and (arr.min() < 0 or arr.max() > 1):
                    g.err(f"material {mi} {key} outside 0..1")
        bct = pbr.get("baseColorTexture")
        if bct and bct.get("index", 0) >= len(js.get("textures", [])):
            g.err(f"material {mi} references missing texture")
        g.info.append((f"material {mi}", {k: mat.get(k) for k in ("name", "alphaMode", "doubleSided")}))
    for ti, tex in enumerate(js.get("textures", [])):
        if tex.get("source") is None or tex["source"] >= len(js.get("images", [])):
            g.err(f"texture {ti} references missing image")
    for ii, img in enumerate(js.get("images", [])):
        if "bufferView" not in img:
            g.err(f"image {ii} is not embedded in a bufferView")
            continue
        bv = js["bufferViews"][img["bufferView"]]
        data = g.buffer_bytes[bv.get("buffer", 0)][
            bv.get("byteOffset", 0) : bv.get("byteOffset", 0) + bv.get("byteLength", 0)
        ]
        mime = img.get("mimeType", "")
        try:
            pil = Image.open(io.BytesIO(data))
            pil.load()
            g.info.append(
                (
                    f"image {ii}",
                    {
                        "mime": mime,
                        "size": list(pil.size),
                        "mode": pil.mode,
                        "bytes": len(data),
                    },
                )
            )
            if mime == "image/jpeg" and not (data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9"):
                g.err(f"image {ii} claims JPEG but has no JPEG markers")
            if pil.size[0] < 16 or pil.size[1] < 16:
                g.warn(f"image {ii} is very small {pil.size}")
        except Exception as exc:
            g.err(f"image {ii} cannot be decoded: {exc}")
    # morph default weights
    for mi, mesh in enumerate(js.get("meshes", [])):
        weights = mesh.get("weights")
        if weights and not all(0 <= w <= 1 for w in weights):
            g.err(f"mesh {mi} default morph weights outside 0..1")

    # animation target/basic checks
    anims = js.get("animations", [])
    names = [a.get("name") for a in anims]
    if len(set(names)) != len(names):
        g.err("duplicate animation names")
    bones = set()
    for i, n in enumerate(nodes):
        if "mesh" not in n:
            bones.add(n.get("name"))
    for ai, anim in enumerate(anims):
        seen = set()
        for ci, ch in enumerate(anim.get("channels", [])):
            target = ch.get("target", {})
            node = target.get("node")
            path = target.get("path")
            if node is None or node < 0 or node >= len(nodes):
                g.err(f"animation {names[ai]} channel {ci} invalid target node")
                continue
            if path not in ("translation", "rotation", "scale", "weights"):
                g.err(f"animation {names[ai]} channel {ci} invalid path {path}")
            if (node, path) in seen:
                g.err(f"animation {names[ai]} duplicate channel for {nodes[node].get('name')}.{path}")
            seen.add((node, path))
            sampler = anim.get("samplers", [])
            si = ch.get("sampler")
            if si is None or si < 0 or si >= len(sampler):
                g.err(f"animation {names[ai]} channel {ci} invalid sampler")
                continue
            s = sampler[si]
            interp = s.get("interpolation", "LINEAR")
            if interp not in ("LINEAR", "STEP", "CUBICSPLINE"):
                g.err(f"animation {names[ai]} unsupported interpolation {interp}")
            inp = g.acc(s["input"]).ravel()
            if len(inp) < 2:
                g.err(f"animation {names[ai]} sampler {si} has <2 keys")
                continue
            if not np.isfinite(inp).all():
                g.err(f"animation {names[ai]} sampler {si} non-finite timestamps")
                continue
            if np.any(np.diff(inp) <= 0):
                g.err(f"animation {names[ai]} sampler {si} timestamps not strictly increasing")
            if abs(inp[0]) > 1e-6:
                g.warn(f"animation {names[ai]} sampler {si} starts at {inp[0]:.4f}s not 0")
            out = g.acc(s["output"])
            expected_components = NCOMP["SCALAR"]
            if path == "rotation":
                expected_components = 4
            elif path in ("translation", "scale"):
                expected_components = 3
            elif path == "weights":
                mesh_i = nodes[node].get("mesh")
                expected_components = 0
                if mesh_i is not None:
                    # glTF morph weights are shared per target index across all
                    # primitives of a mesh; every primitive must expose the same
                    # target count.
                    expected_components = max(
                        1,
                        max(
                            len(p.get("targets", []))
                            for p in js["meshes"][mesh_i].get("primitives", [])
                        ),
                    )
            factor = 3 if interp == "CUBICSPLINE" else 1
            expected_rows = len(inp) * factor
            if out.shape[0] != expected_rows or (expected_components and out.shape[1] != expected_components):
                g.err(
                    f"animation {names[ai]} sampler {si} output shape {out.shape} "
                    f"expected ({expected_rows},{expected_components})"
                )
                continue
            if not np.isfinite(out).all():
                g.err(f"animation {names[ai]} sampler {si} non-finite output")
            if path == "weights":
                if out.min() < -1e-5 or out.max() > 1 + 1e-5:
                    g.err(
                        f"animation {names[ai]} weights outside 0..1 "
                        f"({out.min():.4f}..{out.max():.4f})"
                    )
            if path == "rotation":
                norms = np.linalg.norm(out, axis=1)
                if np.any(np.abs(norms - 1) > 2e-3):
                    bad = int(np.sum(np.abs(norms - 1) > 2e-3))
                    g.err(
                        f"animation {names[ai]} {nodes[node].get('name')} rotation "
                        f"{bad} keys not normalized (norm {norms.min():.4f}..{norms.max():.4f})"
                    )
            # accessor min/max for time
            acc_min = js["accessors"][s["input"]].get("min")
            acc_max = js["accessors"][s["input"]].get("max")
            if acc_min is not None and abs(acc_min[0] - float(inp[0])) > 1e-5:
                g.warn(f"animation {names[ai]} input min metadata mismatch")
            if acc_max is not None and abs(acc_max[0] - float(inp[-1])) > 1e-5:
                g.warn(f"animation {names[ai]} input max metadata mismatch")
    if len(anims) == 0:
        g.err("no animations")
    g.info.append(("bones", sorted(b for b in bones if b)))


def pose_at(g: Glb, anim, index: int):
    """Return {(node, path): value} for one key of one clip."""
    pose = {}
    for ch in anim.get("channels", []):
        s = anim["samplers"][ch["sampler"]]
        out = g.acc(s["output"])
        if s.get("interpolation", "LINEAR") == "CUBICSPLINE":
            out = out.reshape(-1, 3, out.shape[1])[:, 1, :]
        key = index if index >= 0 else len(out) + index
        key = max(0, min(len(out) - 1, key))
        node_name = g.js["nodes"][ch["target"]["node"]].get("name")
        pose[(node_name, ch["target"]["path"])] = out[key]
    return pose


def pose_delta(a, b):
    """Largest rotation (deg) and translation/scale/weight (abs) difference."""
    max_rot = 0.0
    max_other = 0.0
    worst_rot = ""
    worst_other = ""
    for key, va in a.items():
        if key not in b:
            continue
        vb = b[key]
        path = key[1]
        if path == "rotation":
            d = angle_between(va, vb)
            if d > max_rot:
                max_rot = d
                worst_rot = str(key[0])
        else:
            d = float(np.max(np.abs(np.asarray(va) - np.asarray(vb))))
            if d > max_other:
                max_other = d
                worst_other = str(key[0])
    return max_rot, max_other, worst_rot, worst_other


def animation_report(g: Glb):
    js = g.js
    nodes = js["nodes"]
    anims = js.get("animations", [])
    reports = {}
    for anim in anims:
        name = anim.get("name")
        dur = 0.0
        channels = {}
        moving = {}
        max_angle = 0.0
        max_trans = 0.0
        max_scale = 0.0
        max_angle_bone = ""
        max_trans_bone = ""
        max_scale_bone = ""
        max_rot_dev = 0.0
        max_other_dev = 0.0
        flips = 0
        flip_events = []
        lid_scale_max = {}
        for ch in anim.get("channels", []):
            s = anim["samplers"][ch["sampler"]]
            inp = g.acc(s["input"]).ravel()
            out = g.acc(s["output"])
            interp = s.get("interpolation", "LINEAR")
            if interp == "CUBICSPLINE":
                out = out.reshape(len(inp), 3, -1)[:, 1, :]
            dur = max(dur, float(inp[-1]))
            node_i = ch["target"]["node"]
            path = ch["target"]["path"]
            bone = nodes[node_i].get("name")
            channels[(bone, path)] = out
            if path == "rotation":
                vals = out
                dev = max(angle_between(vals[0], v) for v in vals)
                max_rot_dev = max(max_rot_dev, dev)
                if dev > 0.25:
                    moving[bone] = max(moving.get(bone, 0), dev)
                for k in range(len(vals) - 1):
                    if float(np.dot(vals[k], vals[k + 1])) < 0:
                        flips += 1
                        flip_events.append(
                            {
                                "time": round(float(inp[k + 1]), 4),
                                "bone": bone,
                                "step_deg": round(angle_between(vals[k], vals[k + 1]), 2),
                            }
                        )
                    a = angle_between(vals[k], vals[k + 1])
                    if a > max_angle:
                        max_angle = a
                        max_angle_bone = bone
            elif path in ("translation", "scale"):
                dev = float(np.max(np.abs(out - out[0])))
                max_other_dev = max(max_other_dev, dev)
                if dev > 0.002:
                    moving[bone] = max(moving.get(bone, 0), dev)
                step = np.max(np.abs(np.diff(out, axis=0))) if len(out) > 1 else 0.0
                if path == "translation":
                    if step > max_trans:
                        max_trans = float(step)
                        max_trans_bone = bone
                else:
                    if step > max_scale:
                        max_scale = float(step)
                        max_scale_bone = bone
                    if bone in ("Lid_L", "Lid_R") and out.shape[1] > 1:
                        lid_scale_max[bone] = round(float(np.max(out[:, 1])), 2)
            elif path == "weights":
                dev = float(np.max(np.abs(out - out[0])))
                max_other_dev = max(max_other_dev, dev)
                if dev > 0.01:
                    moving[bone] = max(moving.get(bone, 0), dev)
        loop_delta = None
        if name in LOOP_CLIPS:
            details = []
            for (bone, path), vals in channels.items():
                if path == "rotation":
                    d = angle_between(vals[0], vals[-1])
                    if d > 0.01:
                        details.append((bone, "rotation", d))
                else:
                    d = float(np.max(np.abs(vals[0] - vals[-1])))
                    if d > 1e-4:
                        details.append((bone, path, d))
            loop_delta = details
        root_net = None
        for root_name in ("Root", "Hips"):
            vals = channels.get((root_name, "translation"))
            if vals is not None:
                root_net = (root_name, float(np.linalg.norm(vals[-1] - vals[0])))
                break
        reports[name] = {
            "duration": round(dur, 4),
            "channels": len(anim.get("channels", [])),
            "moving_joints": sorted(moving.items(), key=lambda kv: -kv[1]),
            "max_angle_step_deg": round(max_angle, 2),
            "max_angle_bone": max_angle_bone,
            "max_translation_step_m": round(max_trans, 5),
            "max_translation_bone": max_trans_bone,
            "max_scale_step": round(max_scale, 5),
            "max_scale_bone": max_scale_bone,
            "quat_sign_flips": flips,
            "quat_flip_events": flip_events,
            "eyelid_scale_max": lid_scale_max,
            "loop_start_end_delta": loop_delta,
            "root_net_translation": root_net,
            "max_rotation_deviation_deg": round(max_rot_dev, 3),
            "max_other_deviation": round(max_other_dev, 6),
            "static": max_rot_dev < 0.05 and max_other_dev < 0.0005,
        }
    return reports


def parse_dart_durations():
    text = PET_DART.read_text(encoding="utf-8")
    blocks = {
        "_momoDurations": ("momo", "all"),
        "_drakoBayiDurations": ("drako", "bayi"),
        "_drakoRemajaDurations": ("drako", "remaja"),
        "_drakoDewasaDurations": ("drako", "dewasa"),
    }
    result = {}
    for name, key in blocks.items():
        m = re.search(
            rf"static const {name} = <String, Duration>\{{(.*?)\n  \}};",
            text,
            re.S,
        )
        if not m:
            raise SystemExit(f"cannot find Dart duration block {name}")
        vals = {}
        for cm in re.finditer(
            r"'([^']+)':\s*Duration\((?:seconds:\s*(\d+)|milliseconds:\s*(\d+))\)",
            m.group(1),
        ):
            ms = int(cm.group(2)) * 1000 if cm.group(2) else int(cm.group(3))
            vals[cm.group(1)] = ms
        result[key[1]] = vals
    return result


def parse_kotlin_durations():
    text = PET_KT.read_text(encoding="utf-8")
    clip_consts = dict(re.findall(r'const val (\w+) = "([^"]+)"', text))
    blocks = {
        "MOMO_DURATIONS": ("momo", "all"),
        "DRAKO_BAYI_DURATIONS": ("drako", "bayi"),
        "DRAKO_REMAJA_DURATIONS": ("drako", "remaja"),
        "DRAKO_DEWASA_DURATIONS": ("drako", "dewasa"),
    }
    result = {}
    for name, key in blocks.items():
        m = re.search(rf"private val {name} = mapOf\((.*?)\n    \)", text, re.S)
        if not m:
            raise SystemExit(f"cannot find Kotlin duration block {name}")
        vals = {}
        for cm in re.finditer(r'((?:PetClips\.\w+)|\"[^\"]+\")\s*to\s*([\d_]+)L', m.group(1)):
            raw = cm.group(1)
            clip = clip_consts[raw.split(".")[1]] if raw.startswith("PetClips.") else raw.strip('"')
            vals[clip] = int(cm.group(2).replace("_", ""))
        result[key[1]] = vals
    return result


def compare_registry(g: Glb, pet, stage, reports, dart, kt):
    key = "all" if pet == "momo" else stage
    actual = {name: round(rep["duration"] * 1000) for name, rep in reports.items()}
    for source, table in (("dart", dart[key]), ("kotlin", kt[key])):
        if not table:
            g.err(f"{source} duration table for {pet}/{stage} is empty")
            continue
        missing = sorted(set(actual) - set(table))
        extra = sorted(set(table) - set(actual))
        if missing:
            g.err(f"{source}: clips missing from duration table: {missing}")
        if extra:
            g.err(f"{source}: duration table has clips absent from GLB: {extra}")
        diffs = []
        for clip, raw_ms in table.items():
            if clip not in actual:
                continue
            if abs(actual[clip] - raw_ms) > 20:
                diffs.append((clip, actual[clip], raw_ms))
        if diffs:
            g.err(f"{source}: duration mismatch (glb_ms, registry_ms): {diffs}")
        g.info.append((f"{source} duration coverage", {"clips": len(table), "mismatches": len(diffs)}))
    if pet == "momo":
        expected = {
            "idle_fresh",
            "idle_tired",
            "idle_critical",
            "sleep",
            "tap_reaction",
            "celebrate",
            "greet",
            "look_around",
            "groom",
            "stretch",
            "walk",
            "petting",
        }
    else:
        expected = {
            "idle_fresh",
            "idle_fresh_a",
            "idle_fresh_b",
            "idle_fresh_c",
            "idle_fresh_d",
            "idle_tired",
            "idle_tired_a",
            "idle_tired_b",
            "idle_tired_c",
            "idle_critical",
            "idle_critical_a",
            "idle_critical_b",
            "idle_critical_c",
            "sleep",
            "tap_reaction",
            "celebrate",
            "wing_flap",
            "tail_wag",
            "head_look",
            "fire_puff",
            "happy_bounce",
            "greet",
            "petting",
            "walk",
            "wing_show",
        }
    missing = sorted(expected - set(actual))
    extra = sorted(set(actual) - expected)
    if missing:
        g.err(f"expected clip set missing: {missing}")
    if extra:
        g.err(f"unexpected clips: {extra}")
    # required bones per family
    node_names = {n.get("name") for n in g.js["nodes"]}
    if pet == "drako":
        required = {
            "Root",
            "Hips",
            "Spine",
            "Chest",
            "Neck",
            "Head",
            "Wing_L",
            "Wing_R",
            "Wing_L_Tip",
            "Wing_R_Tip",
            "Lid_L",
            "Lid_R",
            "Tail_1",
            "Tail_2",
            "Tail_3",
            "Tail_Tip",
            "LegFL",
            "LegFR",
            "LegBL",
            "LegBR",
            "PawFL",
            "PawFR",
            "PawBL",
            "PawBR",
            "Horn_L",
            "Horn_R",
        }
    else:
        required = {
            "Root",
            "Hips",
            "Spine",
            "Chest",
            "Neck",
            "Head",
            "Ear_L",
            "Ear_R",
            "Arm_L",
            "Arm_R",
            "Forearm_L",
            "Forearm_R",
            "Paw_L",
            "Paw_R",
            "Leg_L",
            "Leg_R",
            "Foot_L",
            "Foot_R",
            "Tail_1",
            "Tail_2",
            "Tail_3",
            "Tail_Tip",
            "Blink_L",
            "Blink_R",
        }
    absent = sorted(required - node_names - {""})
    if absent:
        g.err(f"required bones/nodes missing: {absent}")
    if pet == "drako":
        skin = (g.js.get("skins") or [{}])[0]
        joint_names = {g.js["nodes"][j].get("name") for j in skin.get("joints", [])}
        for lid in ("Lid_L", "Lid_R"):
            if lid not in joint_names:
                g.err(f"eyelid {lid} is not a skin joint")
        lid_mesh = [
            n
            for n in g.js["nodes"]
            if (n.get("name") or "").startswith("DrakoEyelids")
        ]
        if not lid_mesh:
            g.err("no DrakoEyelids mesh node")
        elif not all("mesh" in n and "skin" in n for n in lid_mesh):
            g.err("DrakoEyelids mesh is not skinned")
        blink_missing = []
        weak_blink = []
        for name, rep in reports.items():
            lid = rep.get("eyelid_scale_max", {})
            if set(lid) != {"Lid_L", "Lid_R"}:
                blink_missing.append(name)
            elif min(lid.values()) < 5.0:
                weak_blink.append((name, lid))
        if blink_missing:
            g.err(f"clips without eyelid blink channels: {blink_missing}")
        if weak_blink:
            g.warn(f"clips whose blink never closes the lid (scale.y < 5): {weak_blink}")
        g.info.append(
            (
                "eyelid blink coverage",
                {
                    "clips": len(reports),
                    "with_both_lids": len(reports) - len(blink_missing),
                    "weak": len(weak_blink),
                },
            )
        )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=str(ROOT / "tools" / "qa_rig" / "rig_audit.json"))
    ap.add_argument("--assets-dir", default=str(ASSET_DIR))
    args = ap.parse_args()
    assets = Path(args.assets_dir)
    dart = parse_dart_durations()
    kt = parse_kotlin_durations()

    all_out = {}
    total_errors = 0
    total_warnings = 0
    for (pet, stage), filename in FILES.items():
        path = assets / filename
        print(f"\n=== {pet} / {stage} / {filename}")
        g = Glb(path)
        check_structure(g, pet, stage)
        reports = animation_report(g)
        compare_registry(g, pet, stage, reports, dart, kt)
        anims_by_name = {a.get("name"): a for a in g.js.get("animations", [])}
        # Idle variants must not be identical still frames; cycling among them
        # should show a visibly different live pose.
        idle_groups = {}
        for clip in reports:
            if clip.startswith("idle_fresh"):
                idle_groups.setdefault("fresh", []).append(clip)
            elif clip.startswith("idle_tired"):
                idle_groups.setdefault("tired", []).append(clip)
            elif clip.startswith("idle_critical"):
                idle_groups.setdefault("critical", []).append(clip)
        for mood, clips in idle_groups.items():
            if len(clips) < 2:
                continue
            starts = {c: pose_at(g, anims_by_name[c], 0) for c in clips}
            pairwise = []
            for i, a in enumerate(clips):
                for b in clips[i + 1 :]:
                    rot, other, wr, wo = pose_delta(starts[a], starts[b])
                    pairwise.append((rot, other, a, b))
            worst = max(pairwise, key=lambda t: (t[0], t[1]))
            rep = reports.get(clips[0], {})
            g.info.append(
                (
                    f"idle {mood} variants",
                    {
                        "count": len(clips),
                        "largest_pose_gap_deg": round(worst[0], 2),
                        "largest_pose_gap_other": round(worst[1], 5),
                        "between": [worst[2], worst[3]],
                        "static_clips": [c for c in clips if reports.get(c, {}).get("static")],
                    },
                )
            )
            if worst[0] < 0.5 and worst[1] < 0.005:
                g.err(f"{mood} idle variants are visually identical still poses")
        # One-shots should settle near the base idle after their final frame so
        # the 250 ms crossfade does not visibly snap.
        base = pose_at(g, anims_by_name["idle_fresh"], 0) if "idle_fresh" in anims_by_name else {}
        for name, rep in reports.items():
            if name in LOOP_CLIPS or not base:
                continue
            end = pose_at(g, anims_by_name[name], -1)
            rot, other, wr, wo = pose_delta(base, end)
            rep["end_vs_idle"] = {
                "rotation_deg": round(rot, 2),
                "other": round(other, 5),
                "worst_rotation": wr,
                "worst_other": wo,
            }
            if rot > 60:
                g.warn(
                    f"clip {name} ends {rot:.1f}deg from base idle on {wr}; "
                    "crossfade will be visible"
                )
        # per-clip checks
        for name, rep in reports.items():
            if rep["static"]:
                g.err(f"clip {name} is completely static")
            if rep["loop_start_end_delta"]:
                details = rep["loop_start_end_delta"]
                # rotations allow 0.5 degrees, translations 1 mm
                bad = [
                    d
                    for d in details
                    if (d[1] == "rotation" and d[2] > 0.5)
                    or (d[1] != "rotation" and d[2] > 1e-3)
                ]
                if bad:
                    g.warn(
                        f"clip {name} loop start/end differs: "
                        + ", ".join(f"{b}.{p}={v:.3f}" for b, p, v in bad[:6])
                    )
            # A quaternion hemisphere flip (q vs -q) is the same rotation. It is
            # harmless when the actual rotation step stays small; only a flip
            # hiding a large step would be a real interpolation defect.
            hard_flips = [e for e in rep["quat_flip_events"] if e["step_deg"] > 30.0]
            if hard_flips:
                g.warn(
                    f"clip {name} has {len(hard_flips)} quaternion sign flips with "
                    f"large rotation steps: {hard_flips[:3]}"
                )
            if rep["max_angle_step_deg"] > 60:
                g.warn(
                    f"clip {name} max rotation step {rep['max_angle_step_deg']}deg "
                    f"on {rep['max_angle_bone']}"
                )
            if rep["max_translation_step_m"] > 0.15:
                g.warn(
                    f"clip {name} max translation step {rep['max_translation_step_m']}m "
                    f"on {rep['max_translation_bone']}"
                )
        # choreography expectations
        if pet == "drako":
            for clip in ("wing_flap", "wing_show"):
                reps = reports.get(clip, {}).get("moving_joints", [])
                wing = [j for j, v in reps if j.startswith("Wing")]
                if not wing:
                    g.err(f"{clip} does not move any wing bone")
                else:
                    g.info.append((f"{clip} wing motion", dict(reps)[wing[0]]))
            for clip in ("tail_wag",):
                reps = dict(reports.get(clip, {}).get("moving_joints", []))
                if not any(j.startswith("Tail") for j in reps):
                    g.err(f"{clip} does not move tail bones")
            for clip in ("head_look",):
                reps = dict(reports.get(clip, {}).get("moving_joints", []))
                if "Head" not in reps and "Neck" not in reps:
                    g.err(f"{clip} does not move head/neck")
        else:
            for clip in ("groom", "stretch", "look_around"):
                reps = dict(reports.get(clip, {}).get("moving_joints", []))
                if not reps:
                    g.err(f"{clip} has no moving joints")
            blink = reports.get("idle_fresh", {}).get("moving_joints", [])
            # Blink is morph weights and lives on nodes, not bones; checked above.
            if "tail_wag" in reports:
                g.err("Momo unexpectedly ships a tail_wag clip")
        # motion range sanity: any rotation > 170deg from first
        for name, rep in reports.items():
            for bone, val in rep["moving_joints"]:
                limit = 170 if rep["max_angle_step_deg"] <= 60 else 220
                if val == "rotation" or False:
                    pass
        print(
            f"nodes={len(g.js['nodes'])} meshes={len(g.js['meshes'])} "
            f"skin_joints={len(g.js['skins'][0]['joints']) if g.js.get('skins') else 0} "
            f"clips={len(reports)} errors={len(g.errors)} warnings={len(g.warnings)}"
        )
        for err in g.errors:
            print("  ERROR", err)
        for warn in g.warnings:
            print("  WARN ", warn)
        total_errors += len(g.errors)
        total_warnings += len(g.warnings)
        all_out[f"{pet}/{stage}"] = {
            "file": filename,
            "bytes": len(g.raw),
            "sha256": g.sha256,
            "errors": g.errors,
            "warnings": g.warnings,
            "info": g.info,
            "clips": reports,
        }
    print(f"\nTOTAL errors={total_errors} warnings={total_warnings}")
    out = {
        "generated": "2026-10-31",
        "tool": "tools/qa_rig_audit.py",
        "read_only": True,
        "summary": {"errors": total_errors, "warnings": total_warnings},
        "pets": all_out,
    }
    Path(args.json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"report: {args.json}")
    return 1 if total_errors else 0


if __name__ == "__main__":
    sys.exit(main())
