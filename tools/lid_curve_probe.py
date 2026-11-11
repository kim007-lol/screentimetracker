#!/usr/bin/env python3
"""Dump the blink keyframes of the lid bones straight out of a GLB.

Read-only: parses the GLB header + JSON + BIN chunks with struct/numpy, so no
glTF graph object is mutated and no Blender round-trip is needed to answer
"what value does the animator actually put on Lid_R at the blink peak?".

  python lid_curve_probe.py <glb> [clip ...]
"""
import base64
import json
import os
import struct
import sys

import numpy as np

TYPES = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
TYPE_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5124: 4, 5125: 4, 5126: 4}


def read_glb(path):
    data = open(path, "rb").read()
    magic, version, length = struct.unpack_from("<III", data, 0)
    assert magic == 0x46546C67, "not a GLB"
    off = 12
    js = None
    binv = b""
    while off < length:
        clen, ctype = struct.unpack_from("<II", data, off)
        off += 8
        chunk = data[off:off + clen]
        off += clen
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode("utf-8"))
        elif ctype == 0x004E4942:
            binv = chunk
    return js, binv


def accessor(js, binv, idx):
    a = js["accessors"][idx]
    n = TYPES[a["type"]]
    ts = TYPE_SIZE[a["componentType"]]
    if "bufferView" not in a:
        return np.zeros((a["count"], n))
    bv = js["bufferViews"][a["bufferView"]]
    base = bv.get("byteOffset", 0)
    stride = bv.get("byteStride", 0) or ts * n
    fmt = "<" + {5126: "f", 5123: "H", 5121: "B", 5125: "I", 5122: "h",
                 5124: "i"}.get(a["componentType"], "") * n
    if len(fmt) == 1:
        raise SystemExit("componentType %d unsupported" % a["componentType"])
    out = np.empty((a["count"], n), np.float64)
    for i in range(a["count"]):
        pos = base + a.get("byteOffset", 0) + i * stride
        out[i] = struct.unpack_from(fmt, binv, pos)
    return out


def main():
    path = sys.argv[1]
    want = set(sys.argv[2:]) or {"idle_fresh"}
    js, binv = read_glb(path)
    nodes = js["nodes"]
    names = {i: nd.get("name", "node%d" % i) for i, nd in enumerate(nodes)}
    fps = float(os.environ.get("QA_FPS", 30))
    print("# %s  meshes=%d animations=%d" % (path, len(js.get("meshes", [])),
                                             len(js.get("animations", []))))
    for an in js.get("animations", []):
        nm = an.get("name", "?")
        if nm not in want:
            continue
        print("== clip %s  channels=%d" % (nm, len(an["channels"])))
        for ch in an["channels"]:
            tgt = ch["target"]
            node = tgt["node"]
            if "Lid" not in names.get(node, "") or tgt["path"] != "scale":
                continue
            sm = an["samplers"][ch["sampler"]]
            t = accessor(js, binv, sm["input"]).ravel()
            out = accessor(js, binv, sm["output"])
            y = out[:, 1]
            print("  %-7s keys=%d  y-scale min=%.3f max=%.3f  interp=%s"
                  % (names[node], len(t), y.min(), y.max(),
                     sm.get("interpolation", "LINEAR")))
            hits = np.flatnonzero(y > 1.05)
            for i in hits:
                print("      f%-5d t=%-7.3f  scale=(%.3f, %.3f, %.3f)"
                      % (round(t[i] * fps), t[i], out[i, 0], out[i, 1], out[i, 2]))
            if not hits.size:
                print("      values:", np.array2string(
                    np.unique(np.round(y, 4)), max_line_width=200))
    return 0


if __name__ == "__main__":
    sys.exit(main())
