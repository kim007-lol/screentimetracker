"""Validate the six appended Momo "life" clips in all three stage GLBs.

Contract checked per file:
  * exactly 12 animations, legacy six first, new six appended
  * each new clip has 26 channels (22 rotations + Hips.translation +
    Chest.scale + Blink_L/Blink_R weights)
  * expected durations, LINEAR interpolation, 30 fps frames 0..duration
  * Hips.translation frozen at the node rest translation
  * Chest.scale frozen at (1, 1, 1), Root.rotation identity
  * no NaN/Inf in any animation accessor
  * walk first and last keyframes identical (seamless loop)
  * optional original snapshot: legacy clip value hashes, scene structure and
    the original BIN prefix must be unchanged (content level, not file offsets)

Usage:
    python tools/validate_momo_life.py
    python tools/validate_momo_life.py --write-snapshot %TEMP%/momo_life_backup/snapshot_original
    python tools/validate_momo_life.py --snapshot %TEMP%/momo_life_backup/snapshot_original

Run --write-snapshot on the untouched GLBs, then --snapshot after generating
the new clips. The snapshot is refused if it already exists, so the original
proof cannot be silently overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

FPS = 30
FILES = ("momo_bayi.glb", "momo_remaja.glb", "momo_dewasa.glb")
ASSETS = Path(__file__).resolve().parent.parent / "mobile" / "assets" / "3d"

JOINTS = [
    "Root", "Hips", "Spine", "Chest", "Neck", "Head", "Ear_L", "Ear_R",
    "Arm_L", "Forearm_L", "Paw_L", "Arm_R", "Forearm_R", "Paw_R",
    "Leg_L", "Foot_L", "Leg_R", "Foot_R", "Tail_1", "Tail_2", "Tail_3",
    "Tail_Tip",
]
LEGACY = {
    "idle_fresh": 8.0,
    "idle_tired": 8.0,
    "idle_critical": 3.0,
    "sleep": 8.0,
    "tap_reaction": 1.0,
    "celebrate": 2.0,
}
LIFE = {
    "greet": 2.0,
    "look_around": 3.0,
    "groom": 3.2,
    "stretch": 2.6,
    "walk": 1.2,
    "petting": 2.0,
}
EXPECTED_TARGETS = {(name, "rotation") for name in JOINTS} | {
    ("Hips", "translation"),
    ("Chest", "scale"),
    ("Blink_L", "weights"),
    ("Blink_R", "weights"),
}
STRUCT_KEYS = (
    "asset", "scene", "scenes", "nodes", "meshes", "skins", "materials",
    "images", "textures", "samplers",
)
COMPONENT = {5126: ("f", 4)}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def load_glb(path: Path):
    raw = path.read_bytes()
    if len(raw) < 20:
        raise ValueError("file too short")
    magic, version, total = struct.unpack_from("<III", raw, 0)
    if magic != 0x46546C67 or version != 2:
        raise ValueError("not a glTF 2.0 binary")
    if total != len(raw):
        raise ValueError(f"header length {total} != file size {len(raw)}")
    offset = 12
    js = None
    binary = b""
    while offset < total:
        chunk_len, chunk_type = struct.unpack_from("<II", raw, offset)
        offset += 8
        chunk = raw[offset:offset + chunk_len]
        offset += chunk_len
        if chunk_type == 0x4E4F534A:
            js = json.loads(chunk.decode("utf-8"))
        elif chunk_type == 0x004E4942:
            binary = chunk
    if js is None:
        raise ValueError("missing JSON chunk")
    return js, binary


def read_accessor(js, binary, index):
    acc = js["accessors"][index]
    component = acc["componentType"]
    if component not in COMPONENT:
        raise ValueError(f"accessor {index}: unsupported componentType {component}")
    fmt, size = COMPONENT[component]
    ncomp = NCOMP[acc["type"]]
    view = js["bufferViews"][acc["bufferView"]]
    start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = view.get("byteStride", size * ncomp)
    values = []
    for i in range(acc["count"]):
        raw = struct.unpack_from("<" + fmt * ncomp, binary, start + i * stride)
        values.append(tuple(float(v) for v in raw))
    return values


def node_names(js):
    return {i: node.get("name", f"node_{i}") for i, node in enumerate(js["nodes"])}


def channel_rows(js, binary, animation):
    names = node_names(js)
    rows = []
    for channel in animation["channels"]:
        target = channel["target"]
        node = names.get(target["node"], f"node_{target['node']}")
        path = target["path"]
        sampler = animation["samplers"][channel["sampler"]]
        times = read_accessor(js, binary, sampler["input"])
        values = read_accessor(js, binary, sampler["output"])
        rows.append({
            "node": node,
            "path": path,
            "interpolation": sampler.get("interpolation", "LINEAR"),
            "times": times,
            "values": values,
        })
    return rows


def pack_floats(values):
    flat = [component for value in values for component in value]
    return struct.pack("<" + "f" * len(flat), *flat)


def digest_rows(rows):
    payload = []
    for row in sorted(rows, key=lambda item: (item["node"], item["path"])):
        payload.append({
            "node": row["node"],
            "path": row["path"],
            "interpolation": row["interpolation"],
            "count": len(row["times"]),
            "input": hashlib.sha256(pack_floats(row["times"])).hexdigest(),
            "output": hashlib.sha256(pack_floats(row["values"])).hexdigest(),
        })
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def structure_digest(js):
    payload = {key: js[key] for key in STRUCT_KEYS if key in js}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def close(a, b, tolerance=1e-6):
    return abs(a - b) <= tolerance


def tuples_close(a, b, tolerance=1e-6):
    return len(a) == len(b) and all(close(x, y, tolerance) for x, y in zip(a, b))


def expected_times(duration):
    frames = round(duration * FPS)
    return [i * duration / frames for i in range(frames + 1)], frames


def check_legacy(js, binary, errors):
    animations = js.get("animations", [])
    names = [animation.get("name") for animation in animations]
    for name, duration in LEGACY.items():
        if name not in names:
            errors.append(f"missing legacy clip {name!r}")
            continue
        animation = animations[names.index(name)]
        if len(animation["channels"]) != 26:
            errors.append(f"{name}: {len(animation['channels'])} channels, expected 26")
        rows = channel_rows(js, binary, animation)
        if not rows:
            errors.append(f"{name}: no channels")
            continue
        times = rows[0]["times"]
        if not times:
            errors.append(f"{name}: empty time accessor")
            continue
        if not close(times[-1][0], duration, 1e-4):
            errors.append(f"{name}: duration {times[-1][0]:.4f}s, expected {duration}s")


def check_life(js, binary, name, duration, errors):
    animations = js.get("animations", [])
    names = [animation.get("name") for animation in animations]
    if name not in names:
        errors.append(f"missing new clip {name!r}")
        return
    animation = animations[names.index(name)]
    rows = channel_rows(js, binary, animation)
    if len(animation["channels"]) != 26 or len(rows) != 26:
        errors.append(f"{name}: {len(rows)} channels, expected 26")
    targets = [(row["node"], row["path"]) for row in rows]
    if len(set(targets)) != len(targets):
        errors.append(f"{name}: duplicate channel targets")
    missing = EXPECTED_TARGETS - set(targets)
    extra = set(targets) - EXPECTED_TARGETS
    if missing:
        errors.append(f"{name}: missing channels {sorted(missing)}")
    if extra:
        errors.append(f"{name}: unexpected channels {sorted(extra)}")

    wanted, frames = expected_times(duration)
    by_target = {(row["node"], row["path"]): row for row in rows}
    for target, row in by_target.items():
        if row["interpolation"] != "LINEAR":
            errors.append(f"{name}.{target[0]}.{target[1]}: interpolation "
                          f"{row['interpolation']!r}, expected LINEAR")
        if len(row["times"]) != frames + 1:
            errors.append(f"{name}.{target[0]}.{target[1]}: {len(row['times'])} keys, "
                          f"expected {frames + 1}")
            continue
        for index, (actual, wanted_time) in enumerate(zip(row["times"], wanted)):
            if not close(actual[0], wanted_time, 1e-5):
                errors.append(f"{name}.{target[0]}.{target[1]}: time[{index}] "
                              f"{actual[0]:.6f}, expected {wanted_time:.6f}")
                break
        if target[1] == "weights" and len(row["values"]) != len(row["times"]):
            errors.append(f"{name}.{target[0]}.weights: value count "
                          f"{len(row['values'])} != key count {len(row['times'])}")
        if target[1] != "weights" and len(row["values"]) != len(row["times"]):
            errors.append(f"{name}.{target[0]}.{target[1]}: value count "
                          f"{len(row['values'])} != key count {len(row['times'])}")
        if name != "walk" and target[1] != "weights":
            if not tuples_close(row["values"][0], row["values"][-1], 1e-6):
                errors.append(f"{name}.{target[0]}.{target[1]}: does not return to "
                              f"its first pose")
    if "walk" in LIFE and name == "walk":
        for target, row in by_target.items():
            if not row["values"]:
                continue
            if not tuples_close(row["values"][0], row["values"][-1], 1e-6):
                errors.append(f"walk.{target[0]}.{target[1]}: first and last "
                              f"keyframes differ, loop is not seamless")

    if ("Hips", "translation") not in by_target:
        errors.append("walk: missing Hips.translation")
    else:
        rest = None
        for node in js["nodes"]:
            if node.get("name") == "Hips":
                rest = tuple(node.get("translation", (0.0, 0.0, 0.0)))
                break
        values = by_target[("Hips", "translation")]["values"]
        if rest is None:
            errors.append("Hips node missing")
        else:
            for index, value in enumerate(values):
                if not tuples_close(value, rest, 1e-6):
                    errors.append(f"{name}.Hips.translation[{index}] {value} != "
                                  f"rest {rest}")
                    break
            if values and any(component != values[0][0] for component in
                              (value[0] for value in values)):
                errors.append(f"{name}.Hips.translation: X is not constant")
            if values and any(component != values[0][1] for component in
                              (value[1] for value in values)):
                errors.append(f"{name}.Hips.translation: Y is not constant")
            if values and any(component != values[0][2] for component in
                              (value[2] for value in values)):
                errors.append(f"{name}.Hips.translation: Z is not constant")

    if ("Chest", "scale") not in by_target:
        errors.append(f"{name}: missing Chest.scale")
    else:
        for index, value in enumerate(by_target[("Chest", "scale")]["values"]):
            if not tuples_close(value, (1.0, 1.0, 1.0), 1e-6):
                errors.append(f"{name}.Chest.scale[{index}] {value} != (1, 1, 1)")
                break

    if ("Root", "rotation") not in by_target:
        errors.append(f"{name}: missing Root.rotation")
    else:
        for index, value in enumerate(by_target[("Root", "rotation")]["values"]):
            if not (close(value[0], 0.0) and close(value[1], 0.0)
                    and close(value[2], 0.0) and close(abs(value[3]), 1.0)):
                errors.append(f"{name}.Root.rotation[{index}] {value} is not identity")
                break

    for blink in ("Blink_L", "Blink_R"):
        target = (blink, "weights")
        if target not in by_target:
            errors.append(f"{name}: missing {blink} weights channel")
            continue
        values = [value[0] for value in by_target[target]["values"]]
        if not values:
            continue
        if not close(values[0], 0.0, 1e-6) or not close(values[-1], 0.0, 1e-6):
            errors.append(f"{name}.{blink}.weights: base weight not 0 "
                          f"(first {values[0]:.3f}, last {values[-1]:.3f})")
        if min(values) < -1e-6 or max(values) > 1.0 + 1e-6:
            errors.append(f"{name}.{blink}.weights: values outside [0, 1]")
        if name in ("greet", "look_around") and max(values) < 0.85:
            errors.append(f"{name}.{blink}.weights: blink peak {max(values):.3f} < 0.85")
        if name in ("groom", "petting") and max(values) < 0.75:
            errors.append(f"{name}.{blink}.weights: expression peak "
                          f"{max(values):.3f} < 0.75")


def check_finite(js, binary, errors):
    seen = set()
    for animation in js.get("animations", []):
        for sampler in animation["samplers"]:
            for index in (sampler["input"], sampler["output"]):
                if index in seen:
                    continue
                seen.add(index)
                for value in read_accessor(js, binary, index):
                    if not all(math.isfinite(component) for component in value):
                        errors.append(f"animation accessor {index} contains "
                                      f"NaN/Inf: {value}")
                        break
                if errors and errors[-1].startswith(f"animation accessor {index}"):
                    break


def check_snapshot(snapshot_path: Path, js, binary, legacy_digests, errors):
    if not snapshot_path.exists():
        errors.append(f"snapshot {snapshot_path} does not exist")
        return False
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if snapshot.get("version") != 1:
        errors.append(f"snapshot {snapshot_path}: unsupported version")
        return False
    expected_legacy = snapshot.get("legacy", {})
    for name in LEGACY:
        want = expected_legacy.get(name)
        got = legacy_digests.get(name)
        if not want:
            errors.append(f"snapshot is missing legacy clip {name!r}")
        elif want != got:
            errors.append(f"legacy clip {name!r} changed: snapshot "
                          f"{want[:12]} != current {got[:12]}")
    if snapshot.get("structure_sha256") != structure_digest(js):
        errors.append("scene structure (nodes/meshes/skins/materials/textures) changed")
    original_length = snapshot.get("bin_length")
    if not isinstance(original_length, int) or original_length > len(binary):
        errors.append("BIN chunk is shorter than the original snapshot")
    else:
        digest = hashlib.sha256(binary[:original_length]).hexdigest()
        if digest != snapshot.get("bin_sha256"):
            errors.append("original BIN bytes changed (mesh/texture/morph data)")
    return True


def validate_file(path: Path, snapshot_dir: Path | None):
    errors = []
    try:
        js, binary = load_glb(path)
    except (OSError, ValueError, struct.error) as exc:
        return [f"cannot load {path.name}: {exc}"], {}

    animations = js.get("animations", [])
    names = [animation.get("name") for animation in animations]
    if len(animations) != 12:
        errors.append(f"expected 12 animations, found {len(animations)}")
    if names[:len(LEGACY)] != list(LEGACY):
        errors.append(f"legacy clips are not first in order: {names[:6]}")
    if names[len(LEGACY):] != list(LIFE):
        errors.append(f"new clips are not appended in order: {names[6:]}")
    for name in LIFE:
        if names.count(name) > 1:
            errors.append(f"duplicate animation name {name!r}")
    for name in LEGACY:
        if names.count(name) > 1:
            errors.append(f"duplicate animation name {name!r}")

    check_finite(js, binary, errors)
    check_legacy(js, binary, errors)
    for name, duration in LIFE.items():
        check_life(js, binary, name, duration, errors)

    legacy_digests = {}
    try:
        for animation in animations:
            if animation.get("name") in LEGACY:
                rows = channel_rows(js, binary, animation)
                legacy_digests[animation["name"]] = digest_rows(rows)
    except (ValueError, struct.error, IndexError) as exc:
        errors.append(f"cannot hash legacy clips: {exc}")

    if snapshot_dir is not None:
        check_snapshot(snapshot_dir / f"{path.name}.json", js, binary,
                       legacy_digests, errors)

    summary = {
        "animations": len(animations),
        "names": names,
        "binary": len(binary),
        "legacy_digests": legacy_digests,
        "structure": structure_digest(js),
        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "file_size": path.stat().st_size,
    }
    return errors, summary


def write_snapshot(assets: Path, out_dir: Path, overwrite: bool):
    out_dir.mkdir(parents=True, exist_ok=True)
    failed = False
    for filename in FILES:
        path = assets / filename
        destination = out_dir / f"{filename}.json"
        if destination.exists() and not overwrite:
            print(f"REFUSING {destination}: snapshot already exists "
                  f"(use --overwrite-snapshot to replace)")
            failed = True
            continue
        try:
            js, binary = load_glb(path)
            legacy = {}
            for animation in js.get("animations", []):
                name = animation.get("name")
                if name in LEGACY:
                    legacy[name] = digest_rows(channel_rows(js, binary, animation))
            missing = [name for name in LEGACY if name not in legacy]
            if missing:
                print(f"{filename}: missing legacy clips {missing}, not snapshotting")
                failed = True
                continue
            payload = {
                "version": 1,
                "file": filename,
                "file_size": path.stat().st_size,
                "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bin_length": len(binary),
                "bin_sha256": hashlib.sha256(binary).hexdigest(),
                "structure_sha256": structure_digest(js),
                "legacy": legacy,
            }
            destination.write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            print(f"{filename}: snapshot of {len(legacy)} legacy clips -> {destination}")
        except (OSError, ValueError, struct.error) as exc:
            print(f"{filename}: cannot snapshot: {exc}")
            failed = True
    return 1 if failed else 0


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets", type=Path, default=ASSETS,
                        help="directory containing the three stage GLBs")
    parser.add_argument("--snapshot", type=Path,
                        help="directory with pre-generation snapshots")
    parser.add_argument("--write-snapshot", type=Path,
                        help="write original-content snapshots and exit")
    parser.add_argument("--overwrite-snapshot", action="store_true",
                        help="allow replacing an existing snapshot")
    args = parser.parse_args(argv)

    if args.snapshot and args.write_snapshot:
        parser.error("--snapshot and --write-snapshot are mutually exclusive")
    if args.write_snapshot:
        return write_snapshot(args.assets, args.write_snapshot,
                              args.overwrite_snapshot)

    total_errors = 0
    print(f"assets: {args.assets}")
    for filename in FILES:
        path = args.assets / filename
        errors, summary = validate_file(path, args.snapshot)
        print(f"\n== {filename}")
        if summary:
            print(f"  animations={summary['animations']} "
                  f"size={summary['file_size']} B bin={summary['binary']} B")
            life_counts = []
            for name, duration in LIFE.items():
                if name in summary["names"]:
                    life_counts.append(f"{name} {duration:g}s")
                else:
                    life_counts.append(f"{name} MISSING")
            print(f"  life: {', '.join(life_counts)}")
            if args.snapshot:
                count = len(summary["legacy_digests"])
                print(f"  legacy snapshot: {count}/{len(LEGACY)} clips hashed")
        if errors:
            total_errors += len(errors)
            for error in errors:
                print(f"  FAIL {error}")
        else:
            print("  PASS all life-clip invariants")
    print()
    if total_errors:
        print(f"FAILED: {total_errors} problem(s)")
        return 1
    print("PASS: 3 files, 12 animations each, six life clips match the contract")
    if args.snapshot:
        print("PASS: legacy clip hashes, scene structure and BIN prefix match "
              "the original snapshot")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
