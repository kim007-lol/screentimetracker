"""Stop the frame-grid ratchet and give a shortened clip back its loop-closing key.

Two defects, one tool.  See `tools/loop_keys.py` for the measurement behind them.

* The ratchet: a clip whose authored length is not exact in float32 (the adult
  `sleep` at 4.2000 s) arrives in Blender with its last key at 125.99999428 frames,
  and the glTF exporter's sampled armature channels run over `int(frame_range[1])`
  = 125 frames - so the closing key is silently dropped, one frame per round trip.
  127 keys became 126, then 125, which is what shipped: the sleep loop ends two
  frames early and on a pose that is not its opening pose, so every loop snaps.
* The already-lost keys: snapping alone cannot bring back what an earlier round
  trip ate, so the clip is also extended back to the authored end frame with the
  opening pose written there - the convention every clip in the asset follows,
  measured against the untouched file (`tools/qa_rig/dragon_look/authored_*.json`
  records 25 of 25 clips in each stage ending on their frame-0 pose; a clip an
  author left open would be skipped instead).

This tool changes nothing else: the mesh, textures, bones and the values of
existing keys are imported and written back as they were.  It prints the per-clip
before/after, refuses to export a clip that is still short or still open, and
dumps a report so the change is auditable.

Run:
  blender -b --factory-startup --python-exit-code 1 --python \
      tools/drako_loop_restore.py -- <in.glb> <authored.json> <out.glb> \
      [--report restore.json] [--no-export] [--tol-frames=0.02]
"""
import argparse
import json
import os
import sys

import bpy

argv = sys.argv
tail = argv[argv.index("--") + 1:] if "--" in argv else []
if tail and tail[0] == "--":
    tail = tail[1:]
ap = argparse.ArgumentParser(prog="drako_loop_restore")
ap.add_argument("src")
ap.add_argument("authored", help="clip baseline from lid_sync_verify --durations-json")
ap.add_argument("out")
ap.add_argument("--report", default=None)
ap.add_argument("--fps", type=float, default=30.0)
ap.add_argument("--tol-frames", dest="tol_frames", type=float, default=0.02)
ap.add_argument("--snap-only", dest="snap_only", action="store_true",
                help="only put keys back on the grid; do not append closing keys")
ap.add_argument("--no-export", dest="no_export", action="store_true")
a = ap.parse_args(tail)

src = os.path.abspath(a.src)
out = os.path.abspath(a.out)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_export   # noqa: E402
import loop_keys    # noqa: E402
if not os.path.exists(src):
    raise SystemExit("NO_SUCH_FILE " + src)
baseline_blob = json.load(open(os.path.abspath(a.authored), encoding="utf-8"))
raw = baseline_blob["clips"] if "clips" in baseline_blob else baseline_blob["durations"]
# A bare {clip: seconds} baseline is accepted too; "loop" is then assumed, which is
# what every Drako clip except the one-shots is.
baseline = {k: (v if isinstance(v, dict) else
                {"frames": int(round(float(v) * a.fps)), "loop": True})
            for k, v in raw.items()}
if baseline_blob.get("fps") and float(baseline_blob["fps"]) != a.fps:
    raise SystemExit("BASELINE_FPS %s != --fps %s; the frame counts would be wrong"
                     % (baseline_blob["fps"], a.fps))

bpy.ops.wm.read_factory_settings(use_empty=True)
glb_export.import_glb(src, fps=a.fps)

arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
if len(arms) != 1:
    raise SystemExit("EXPECTED_ONE_ARMATURE, found %d" % len(arms))
arm = arms[0]
actions = sorted((x for x in bpy.data.actions if x.name), key=lambda x: x.name)
print("IMPORT %s actions=%d bones=%d fps=%g"
      % (os.path.basename(src), len(actions), len(arm.data.bones), a.fps))

before = {x.name: {"last": loop_keys.last_frame(x), "seam": loop_keys.seam_delta(x)}
          for x in actions}
for name in sorted(before):
    b = baseline.get(name)
    if not b:
        continue
    print("BEFORE %-16s last=%-13.6f authored=%-4d seam=%.6f"
          % (name, before[name]["last"], loop_keys.authored_target(b, a.fps),
             before[name]["seam"]))

snapped = loop_keys.snap_to_grid(actions, tol=a.tol_frames)
n_snapped = sum(r["keys_snapped"] for r in snapped)
worst = max((r["worst_delta_frames"] for r in snapped), default=0.0)
print("SNAP %d keyframe times onto the frame grid (worst shift %.9f frames) over %d clips"
      % (n_snapped, worst, len(snapped)))

closed = [] if a.snap_only else loop_keys.close_loops(actions, baseline, fps=a.fps)
for r in closed:
    print("LOOP %-16s %s%s" % (r["clip"], r["action"],
          "" if r.get("skipped") else
          " keys=%d %s" % (r.get("keys_inserted", 0),
                           ("frames %s->%s seam %.6f->%.6f"
                            % (r["frames_before"], r["frames_after"],
                               r["seam_before"], r["seam_after"]))
                           if r["action"] == "closed"
                           else ("seam %.6f" % r["seam"]) if "seam" in r else "")))

bad = loop_keys.verify(actions, baseline, fps=a.fps)
after = {x.name: {"last": loop_keys.last_frame(x), "seam": loop_keys.seam_delta(x)}
         for x in actions}
for name in sorted(after):
    b = baseline.get(name)
    if not b:
        continue
    print("AFTER  %-16s last=%-13.6f authored=%-4d seam=%.6f"
          % (name, after[name]["last"], loop_keys.authored_target(b, a.fps),
             after[name]["seam"]))

rep = {"src": os.path.basename(src), "out": os.path.basename(out),
       "authored": os.path.basename(os.path.abspath(a.authored)), "fps": a.fps,
       "snap": {"keys_snapped": n_snapped, "worst_delta_frames": worst,
                "tol_frames": a.tol_frames, "per_clip": snapped},
       "close": closed,
       "before": {k: {"last": round(v["last"], 6), "seam": round(v["seam"], 8)}
                  for k, v in before.items()},
       "after": {k: {"last": round(v["last"], 6), "seam": round(v["seam"], 8)}
                 for k, v in after.items()},
       "failures": bad}
if bad:
    print("LOOP_RESTORE FAILED %s - nothing was exported"
          % ", ".join("%s:%s" % (f["clip"], f["why"]) for f in bad))
    if a.report:
        json.dump(rep, open(os.path.abspath(a.report), "w"), indent=2)
    raise SystemExit("LOOP_NOT_RESTORED")
n_closed = sum(1 for r in closed if r["action"] == "closed")
print("LOOP_RESTORE PASS - %d clips at their authored length on a closed seam, "
      "%d repaired, 0 short or open" % (len(actions), n_closed))
if a.report:
    with open(os.path.abspath(a.report), "w") as f:
        json.dump(rep, f, indent=2)
    print("WROTE " + os.path.abspath(a.report))
if a.no_export:
    print("LOOP_RESTORE_NO_EXPORT")
    raise SystemExit(0)

# The exporter reads the pose it finds for the node transforms, so leave the bind
# state exactly as it arrived; the flags and the frame-grid guard come from
# `tools/glb_export.py` so no builder can ship an asset off the agreed settings.
glb_export.export_glb(out, baseline=baseline, src=src, fps=a.fps, actions=actions,
                      reset_pose=True, arm=arm, tag="LOOP_RESTORE",
                      tol_frames=a.tol_frames)
