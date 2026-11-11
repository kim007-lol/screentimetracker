#!/usr/bin/env python3
"""Dump the three embedded JPEGs of a Drako GLB into a directory.

`tools/drako_face_repaint.py` edits extracted atlases and
`tools/drako_texture_reapply.py` puts them back, but neither one reads texture
bytes out of a GLB.  This is that missing step, so the repaint is a reproducible
three-command pipeline instead of an ad-hoc snippet.

Read-only on the GLB: it parses the binary chunk's bufferViews and writes the
image payloads out unchanged, so the JPEG bytes that come back in are the same
ones that went out (the audit relies on `Image_1`/`Image_2` being bit-identical).

Files are named `<index>_<Image_N>.jpg`, which is what the reapply pass expects
(`1_Image_0.jpg` base colour, `2_Image_1.jpg` metallic-roughness,
`0_Image_2.jpg` normal).  Note that the index prefix is the *bufferView order*,
not the semantic order - pairing by the canonical `Image_N` name is what matters.

Run:
  python tools/drako_texture_extract.py <in.glb> <out_dir>
"""

from __future__ import annotations

import argparse
import json
import os
import re
import struct

CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942


def parse_glb(path):
    with open(path, "rb") as fh:
        data = fh.read()
    magic, version, total = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2:
        raise SystemExit("%s is not a glTF 2.0 binary" % path)
    if total != len(data):
        raise SystemExit("%s declares %d bytes but is %d" % (path, total, len(data)))
    off = 12
    json_chunk = None
    bin_chunk = b""
    while off + 8 <= len(data):
        length, kind = struct.unpack_from("<II", data, off)
        off += 8
        body = data[off:off + length]
        off += length
        if kind == CHUNK_JSON:
            json_chunk = json.loads(body.rstrip(b"\x20").decode("utf-8"))
        elif kind == CHUNK_BIN:
            bin_chunk = body
    if json_chunk is None:
        raise SystemExit("%s has no JSON chunk" % path)
    return json_chunk, bin_chunk


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("glb")
    ap.add_argument("out_dir")
    args = ap.parse_args()

    glb = os.path.abspath(args.glb)
    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    gltf, blob = parse_glb(glb)
    written = []
    for i, image in enumerate(gltf.get("images", [])):
        bv = gltf["bufferViews"][image["bufferView"]]
        start = bv.get("byteOffset", 0)
        payload = blob[start:start + bv["byteLength"]]
        name = image.get("name") or "image_%d" % i
        # Strip any existing index prefix so re-running on a re-exported asset
        # does not stack prefixes (0_1_Image_0.jpg).
        canon = re.sub(r"^\d+_", "", name)
        mime = image.get("mimeType", "image/jpeg")
        ext = ".jpg" if mime == "image/jpeg" else "." + mime.split("/")[-1]
        fname = "%d_%s%s" % (i, canon, ext)
        with open(os.path.join(out_dir, fname), "wb") as fh:
            fh.write(payload)
        written.append((canon, fname, len(payload)))

    if len(written) != 3:
        print("WARNING expected 3 embedded images, found %d" % len(written))
    for canon, fname, size in written:
        print("WROTE %-10s %-14s %9d bytes" % (canon, fname, size))
    print("EXTRACT_DONE %s -> %s (%d files)" % (os.path.basename(glb), out_dir, len(written)))


if __name__ == "__main__":
    main()
