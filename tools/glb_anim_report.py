"""Report animation channels in the Momo GLB rigs.

Reads a GLB, prints every animation channel with node name/path, key count,
and first/last values (quaternions converted to axis/angle deltas).
Used to design localized idle clips without guessing rig data.
"""

import json
import math
import struct
import sys

COMPONENT = {5120: ("b", 1), 5121: ("B", 1), 5122: ("h", 2), 5123: ("H", 2),
             5125: ("I", 4), 5126: ("f", 4)}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def load(path):
    with open(path, "rb") as f:
        data = f.read()
    magic, version, length = struct.unpack_from("<III", data, 0)
    assert magic == 0x46546C67, "not a GLB"
    off = 12
    js = None
    bin_chunk = b""
    while off < length:
        clen, ctype = struct.unpack_from("<II", data, off)
        chunk = data[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:
            js = json.loads(chunk.decode("utf-8"))
        elif ctype == 0x004E4942:
            bin_chunk = chunk
        off += 8 + clen
    return js, bin_chunk


def accessor(js, bin_chunk, index):
    acc = js["accessors"][index]
    bv = js["bufferViews"][acc["bufferView"]]
    fmt, size = COMPONENT[acc["componentType"]]
    ncomp = NCOMP[acc["type"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride", size * ncomp)
    out = []
    for i in range(acc["count"]):
        base = start + i * stride
        vals = struct.unpack_from("<" + fmt * ncomp, bin_chunk, base)
        out.append(vals[0] if ncomp == 1 else vals)
    return out


def quat_delta(q0, q1):
    # relative quaternion q0^-1 * q1
    x0, y0, z0, w0 = q0
    x1, y1, z1, w1 = q1
    ix, iy, iz, iw = -x0, -y0, -z0, w0
    rx = iw * x1 + ix * w1 + iy * z1 - iz * y1
    ry = iw * y1 - ix * z1 + iy * w1 + iz * x1
    rz = iw * z1 + ix * y1 - iy * x1 + iz * w1
    rw = iw * w1 - ix * x1 - iy * y1 - iz * z1
    norm = math.sqrt(rx * rx + ry * ry + rz * rz + rw * rw) or 1.0
    w = max(-1.0, min(1.0, rw / norm))
    angle = 2.0 * math.degrees(math.acos(w))
    s = math.sqrt(max(0.0, 1.0 - w * w))
    if s < 1e-8:
        return angle, (0.0, 0.0, 0.0)
    return angle, (rx / s, ry / s, rz / s)


def fmt_q(q):
    angle, axis = quat_delta((0, 0, 0, 1), q)
    return f"({q[0]:.4f},{q[1]:.4f},{q[2]:.4f},{q[3]:.4f}) {angle:.2f}deg axis({axis[0]:.2f},{axis[1]:.2f},{axis[2]:.2f})"


def report(path):
    js, bin_chunk = load(path)
    nodes = js["nodes"]
    print(f"== {path}")
    print(f"nodes={len(nodes)} meshes={len(js.get('meshes', []))} skins={len(js.get('skins', []))}")
    named = {i: n.get("name", f"<{i}>") for i, n in enumerate(nodes)}
    for a in js.get("animations", []):
        print(f"\n-- animation '{a.get('name')}' channels={len(a['channels'])}")
        for ch in a["channels"]:
            tgt = ch["target"]
            node = tgt.get("node")
            path_ = tgt["path"]
            sam = a["samplers"][ch["sampler"]]
            times = accessor(js, bin_chunk, sam["input"])
            vals = accessor(js, bin_chunk, sam["output"])
            dur = times[-1] - times[0] if times else 0
            if path_ == "rotation":
                first = vals[0]
                deviations = [quat_delta(first, v)[0] for v in vals]
                max_dev = max(deviations) if deviations else 0
                last = vals[-1]
                print(f"  {named.get(node)}[{node}].rotation keys={len(vals)} dur={dur:.2f} "
                      f"first={fmt_q(first)} last={fmt_q(last)} maxdev={max_dev:.2f}deg")
            elif path_ == "translation":
                first, last = vals[0], vals[-1]
                spread = max(abs(v[i] - first[i]) for v in vals for i in range(3))
                print(f"  {named.get(node)}[{node}].translation keys={len(vals)} dur={dur:.2f} "
                      f"first=({first[0]:.4f},{first[1]:.4f},{first[2]:.4f}) "
                      f"last=({last[0]:.4f},{last[1]:.4f},{last[2]:.4f}) spread={spread:.4f}")
            elif path_ == "scale":
                first, last = vals[0], vals[-1]
                spread = max(abs(v[i] - first[i]) for v in vals for i in range(3))
                print(f"  {named.get(node)}[{node}].scale keys={len(vals)} dur={dur:.2f} "
                      f"first=({first[0]:.4f},{first[1]:.4f},{first[2]:.4f}) "
                      f"last=({last[0]:.4f},{last[1]:.4f},{last[2]:.4f}) spread={spread:.4f}")
            else:
                first, last = vals[0], vals[-1]
                if isinstance(first, tuple):
                    spread = max(abs(v[i] - first[i]) for v in vals
                                 for i in range(len(first)))
                    ftext = "(" + ",".join(f"{x:.4f}" for x in first) + ")"
                    ltext = "(" + ",".join(f"{x:.4f}" for x in last) + ")"
                else:
                    spread = max(abs(v - first) for v in vals)
                    ftext = f"{first:.4f}"
                    ltext = f"{last:.4f}"
                print(f"  {named.get(node)}[{node}].{path_} keys={len(vals)} dur={dur:.2f} "
                      f"first={ftext} last={ltext} spread={spread:.4f}")


if __name__ == "__main__":
    for p in sys.argv[1:]:
        report(p)
