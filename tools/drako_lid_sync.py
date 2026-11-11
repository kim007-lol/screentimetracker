"""Put both Drako eyelids back on the same blink timing, without touching geometry.

Why this exists
---------------
`tools/drako_eyelids.py` used to author the right lid's non-rest keys 0.7 frames
after the left one:

    for side, delay in (("L", 0.0), ("R", 0.7)):

Two consequences, both visible in the app:

* the blink curve closes a lid in 1.8 frames, so at the frame the app samples the
  left card is at scale 30 (shut) while the right is still at 26.3 - one eye
  halfway closed, every blink, in all 25 clips of all three stages;
* in the `sleep` clip every key *is* a non-rest key, so the right lid's keys land
  at start+0.7 and end+0.7, past the clip's own last frame.

The second of those was long blamed for the `sleep` clip arriving from Blender one
frame short.  That is wrong, and `tools/lid_sync_verify.py` proves it: the missing
key is uniform across all 78 channels of the clip, lid and non-lid alike, and it
reproduces on assets whose two eyes were already in sync.  The real cause is the
float32 frame-grid ratchet - the closing key sits at 125.99999428 frames and the
exporter samples `int(frame_range[1])` = 125 - and it is documented in
`tools/loop_keys.py`, repaired by `tools/drako_loop_restore.py`, and prevented on
every export by `tools/glb_export.py`.  This tool only fixes the eyes.

This tool takes the shipped curves as they are, copies the left lid's scale keys
onto the right lid in every clip, and re-exports.  It is the repair for assets
that were authored before the generator itself stopped adding the delay; new
assets never need it.

Nothing else is edited: the mesh, materials, textures, bones and every other
channel are only imported and written back out.  It prints the key inventory
before and after so the change is auditable, and it fails rather than exporting
if any clip ends up with the two eyes disagreeing.

Run:
  blender -b --factory-startup --python-exit-code 1 --python \
      tools/drako_lid_sync.py -- <in.glb> <out.glb> [--report sync.json] [--no-export]
"""
import argparse
import json
import os
import sys

import bpy


def _tools_dir():
    """This file's own directory, however Blender was pointed at it."""
    for cand in (os.environ.get("QA_TOOLS_DIR"),
                 os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else None,
                 os.path.abspath("tools")):
        if cand and os.path.isfile(os.path.join(cand, "lid_curves.py")):
            return os.path.abspath(cand)
    raise SystemExit("CANNOT_FIND lid_curves.py - run this script from the project root")


sys.path.insert(0, _tools_dir())
import glb_export                                              # noqa: E402
import lid_curves                                              # noqa: E402

argv = sys.argv
tail = argv[argv.index("--") + 1:] if "--" in argv else []
if tail and tail[0] == "--":
    tail = tail[1:]
ap = argparse.ArgumentParser(prog="drako_lid_sync")
ap.add_argument("src")
ap.add_argument("out")
ap.add_argument("--report", default=None)
ap.add_argument("--no-export", dest="no_export", action="store_true",
                help="inventory and sync in memory only - a look at what would change")
a = ap.parse_args(tail)

src, out = os.path.abspath(a.src), os.path.abspath(a.out)
if not os.path.exists(src):
    raise SystemExit("NO_SUCH_FILE " + src)

bpy.ops.wm.read_factory_settings(use_empty=True)
# Through glb_export so the import lands on the 30 fps grid the clips are authored
# on.  Setting the rate after this point is too late: the importer has already put
# every keyframe second on the scene's frame number, and re-exporting then stretches
# the whole asset (measured on the shipped baby rig: celebrate 1.8 s -> 2.25 s).
glb_export.import_glb(src)
arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
if len(arms) != 1:
    raise SystemExit("EXPECTED_ONE_ARMATURE, found %d - this tool assumes the single "
                     "Drako rig" % len(arms))
arm = arms[0]
for side in lid_curves.LID_SIDES:
    if "Lid_" + side not in arm.data.bones:
        raise SystemExit("NO_BONE Lid_%s in %s - nothing to sync" % (side, src))

actions = sorted((x for x in bpy.data.actions if x.name), key=lambda x: x.name)
print("IMPORT %s actions=%d bones=%d" % (os.path.basename(src), len(actions),
                                         len(arm.data.bones)))

before = {x.name: lid_curves.lid_state(x) for x in actions}
n_clips = sum(1 for v in before.values() if any(v[s] for s in lid_curves.LID_SIDES))
if not n_clips:
    raise SystemExit("NO_LID_CURVES in %s - this asset has no blink keys to sync" % src)
for name, st in sorted(before.items()):
    if not any(st[s] for s in lid_curves.LID_SIDES):
        continue
    line = "BEFORE %s" % name
    for side in lid_curves.LID_SIDES:
        for idx in sorted(st[side]):
            fr = [k[0] for k in st[side][idx]]
            line += " | %s[%d] n=%d %s..%s" % (side, idx, len(fr),
                                               min(fr) if fr else "-", max(fr) if fr else "-")
    print(line)

reports = lid_curves.sync_lids(actions)
after = {x.name: lid_curves.lid_state(x) for x in actions}

changed = [r for r in reports if r["changed"]]
desynced = [r["clip"] for r in reports if not r["identical"]]
for r in reports:
    print("SYNC %s bags=%d changed=%s identical=%s keys=%s%s"
          % (r["clip"], r["bags"], ",".join(r["changed"]) or "none", r["identical"],
             r["keys"],
             "  MISSING_LEFT_LID_CHANNEL" if r["missing_source"] else ""))
for name, st in sorted(after.items()):
    if not any(st[s] for s in lid_curves.LID_SIDES):
        continue
    fr = [k[0] for s in lid_curves.LID_SIDES for k in st[s].get(1, [])]
    print("AFTER  %s | both lids y-keys=%d frames %s..%s"
          % (name, len(fr) // 2, min(fr) if fr else "-", max(fr) if fr else "-"))

rep = {"src": os.path.basename(src), "out": os.path.basename(out),
       "clips_with_lid_curves": n_clips, "clips_changed": len(changed),
       "clips_desynced": desynced, "reports": reports,
       "frames": {}, "bounds": {}}
for name, st in sorted(after.items()):
    if not any(st[s] for s in lid_curves.LID_SIDES):
        continue
    act = next(x for x in actions if x.name == name)
    lo, hi = (float(v) for v in act.frame_range)
    ys = st["L"].get(1, [])
    rep["frames"][name] = {"keys_per_lid": len(ys), "frames": [k[0] for k in ys],
                           "values": [k[1] for k in ys]}
    rep["bounds"][name] = [round(lo, 4), round(hi, 4)]
    outside = [k[0] for k in ys if k[0] < lo - 1e-4 or k[0] > hi + 1e-4]
    if outside:
        rep["bounds"].setdefault("_outside", []).append("%s %s" % (name, outside))
        print("KEYS_OUTSIDE_CLIP_RANGE %s at %s - the exporter will drop them"
              % (name, outside))
if desynced:
    print("LID_SYNC FAILED %s - not exporting" % desynced)
    raise SystemExit("LID_CURVES_STILL_DESYNCED " + " ".join(desynced))
print("LID_SYNC %d/%d clips already matched, %d repaired, 0 desynced"
      % (n_clips - len(changed), n_clips, len(changed)))
if a.report:
    with open(os.path.abspath(a.report), "w") as f:
        json.dump(rep, f, indent=2)
    print("WROTE " + os.path.abspath(a.report))
if a.no_export:
    print("LID_SYNC_NO_EXPORT")
    raise SystemExit(0)

# The bind state has to leave the file exactly as it arrived: the exporter reads
# the pose it finds for the node transforms, so drop any posing import did.  The
# flags and the frame-grid guard come from `tools/glb_export.py`, where the input
# file itself is the baseline - this tool must not shorten a clip either.
glb_export.export_glb(out, src=src, actions=actions,
                      reset_pose=True, arm=arm, tag="LID_SYNC")

