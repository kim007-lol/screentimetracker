#!/usr/bin/env python3
"""GLB-level proof of lid symmetry and clip loop integrity.

Two questions this answers with the bytes the runtime actually loads, without a
Blender round-trip:

1. Lid sync - does `Lid_R` carry exactly the same blink curve as `Lid_L`?  The
   builder used to hand-write the right lid 0.7 frames behind the left, which
   made one eye half-shut at every blink.  Comparing the two samplers elementwise
   (times AND all three scale components) is the only check that catches a
   re-sync that "looks close".

2. Loop closure - every source clip is authored as N+1 keys where the last key
   repeats frame 0 so the loop has no seam.  The adult `sleep` clip ships 126
   keys spanning 4.1667 s and came back from a rebuild with 125 spanning 4.1333 s:
   the closing key was dropped, so the loop snaps.  This walks every channel of
   every clip and reports the frame count, span, and whether the value at the
   last key equals the value at the first key.

Read-only: parses the GLB header + JSON + BIN chunks with struct/numpy.

  python lid_sync_verify.py <glb> [--fps=30] [--show-diff=clip[,clip]]
"""
import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lid_curve_probe import read_glb, accessor  # noqa: E402
import loop_keys                               # noqa: E402  (pose comparison rules)

# Largest L/R scale disagreement that is still "the same curve".  The blink curve
# runs 1.0 -> 30.0, and the bug this gate exists to catch (the right lid authored
# 0.7 frames behind the left) shows up as a 7.5 disagreement at the blink peak.
# float32 storage of a curve copied in doubles moves values by ~1e-6 at 30.0, so
# 1e-4 separates "the exporter rounded it" from "the animator desynced it" by three
# orders of magnitude on either side.
LID_ATOL = 1e-4


def channels_of(js, binv, anim):
    """[(node_name, path, times, values)] for every sampler channel of one clip."""
    nodes = js["nodes"]
    out = []
    for ch in anim["channels"]:
        tgt = ch["target"]
        name = nodes[tgt["node"]].get("name", "node%d" % tgt["node"])
        sm = anim["samplers"][ch["sampler"]]
        t = accessor(js, binv, sm["input"]).ravel()
        v = accessor(js, binv, sm["output"])
        out.append((name, tgt["path"], t, v, sm.get("interpolation", "LINEAR")))
    return out


def main():
    path = sys.argv[1]
    fps = float(next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--fps=")), 30))
    js, binv = read_glb(path)
    anims = js.get("animations", [])
    print("# %s  animations=%d" % (os.path.basename(path), len(anims)))

    desynced, loop_bad, no_lid = [], [], []
    short_clips, long_clips = [], []
    clips, longest = {}, 0.0
    # --show-diff=clip[,clip] prints the per-sample L/R values for the named clips,
    # so a "v=False" verdict can be read as an actual curve instead of a boolean.
    show_diff = set(next((a.split("=", 1)[1] for a in sys.argv
                          if a.startswith("--show-diff=")), "").split(",")) - {""}
    # --authored=glb_or_json is the frame-count baseline: the file (or dumped JSON)
    # that still holds the clips as they were authored, before any rebuild of this
    # asset went through the Blender round trip.  A clip one frame shorter than that
    # baseline lost its loop-closing key, which is invisible in the viewport and a
    # hard snap on every loop.
    authored_path = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--authored=")), None)
    authored = {}
    authored_loop = {}
    if authored_path:
        p = os.path.abspath(authored_path)
        if p.endswith(".json"):
            blob = json.load(open(p, encoding="utf-8"))
            if "clips" in blob:
                authored = {k: v["duration"] for k, v in blob["clips"].items()}
                authored_loop = {k: bool(v.get("loop", True)) for k, v in blob["clips"].items()}
            else:
                authored = blob.get("durations", blob)
        else:
            ajs, abinv = read_glb(p)
            for an in ajs.get("animations", []):
                authored[an.get("name", "?")] = round(max(
                    float(accessor(ajs, abinv, an["samplers"][ch["sampler"]]["input"]).max())
                    for ch in an["channels"]), 4)
        print("AUTHORED_BASELINE %s (%d clips, %d authored as a closed loop)"
              % (os.path.basename(p), len(authored),
                 sum(1 for v in authored_loop.values() if v)))
    dump = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--durations-json=")), None)
    durations = {}
    print("%-16s %6s %8s %9s %-34s %-22s %s"
          % ("clip", "chan", "keys", "dur(s)", "lid L vs R", "loop (last key ~ frame0)", "verdict"))
    for an in anims:
        name = an.get("name", "?")
        chs = channels_of(js, binv, an)
        lids = {n: (t, v) for n, p, t, v, _i in chs
                if p == "scale" and re.match(r"^(Bone_\d+:)?Lid_[LR]$", n)}
        # GLB node names carry the armature prefix on some exports; key on the
        # trailing side letter so both spellings land in one bucket.
        by_side = {}
        for k, (t, v) in lids.items():
            by_side.setdefault(k[-1], (t, v))

        if len(by_side) == 2:
            (tl, vl), (tr, vr) = by_side["L"], by_side["R"]
            same_t = tl.shape == tr.shape and np.array_equal(tl, tr)
            # The curve is authored in doubles and stored in float32, and a blink that
            # opens 30x shut has a peak value of 30.0 - a 1e-6 disagreement is the
            # storage, not the animation.  Anything a renderer can show (a visible
            # frame of lag, a lid stuck half open) is orders of magnitude larger, so
            # the gate is LID_ATOL absolute and the byte-exact case keeps its label.
            dmax = float(np.abs(vl - vr).max()) if vl.shape == vr.shape else float("inf")
            same_v = vl.shape == vr.shape and np.allclose(vl, vr, rtol=0, atol=LID_ATOL)
            exact = vl.shape == vr.shape and np.array_equal(vl, vr)
            tag = "byte-exact" if exact else "d=%.1e" % dmax
            lid_desc = ("in sync %s (%d keys)" % (tag, len(tl)) if (same_t and same_v) else
                        "DESYNC t=%s v=%s d=%.4f n=%d/%d" % (same_t, same_v, dmax, len(tl), len(tr)))
            if not (same_t and same_v):
                desynced.append(name)
            if name in show_diff and vl.shape == vr.shape:
                d = np.abs(vl - vr).max(axis=1)
                idx = np.flatnonzero(d > 0)
                print("      LID_DIFF %s: %d/%d samples differ, max %.3e at f%s"
                      % (name, idx.size, len(tl), d.max(),
                         round(tl[d.argmax()] * fps)) if idx.size
                      else "      LID_DIFF %s: every sample byte-identical" % name)
                for i in idx[:14]:
                    print("        f%-5d t=%-7.4f  L=(%.8f %.8f %.8f) R=(%.8f %.8f %.8f)"
                          % (round(tl[i] * fps), tl[i], *vl[i], *vr[i]))
        else:
            lid_desc = "no lid scale channel"
            no_lid.append(name)

        # Loop: the clip's end pose must equal its start pose, per channel.  Judge
        # every channel, including one that stops early - its last sample is what
        # the renderer holds for the rest of the clip, so it is part of the end pose.
        # A rotation is compared as a rotation: q and -q are the same orientation,
        # which is why `celebrate` used to read as an open loop on all three stages.
        spans = [(n, p, t, v) for n, p, t, v, _i in chs]
        durs = [t[-1] for _n, _p, t, _v in spans if t.size]
        max_t = max(durs) if durs else 0.0
        longest = max(longest, max_t)
        early = [n for n, _p, t, _v in spans if t.size and t[-1] < max_t - 1e-4]
        seam = []
        for n, p, t, v in spans:
            if t.size < 2:
                continue
            seam.append((loop_keys.pair_seam(list(v[0]), list(v[-1]), p == "rotation"),
                         "%s %s" % (n, p)))
        worst, worst_chan = max(seam) if seam else (float("nan"), "")
        closed = bool(seam) and worst < loop_keys.SEAM_TOL
        one_shot = bool(authored) and name in authored and not authored_loop.get(name, True)
        state = "closed" if closed else ("one-shot" if one_shot else "SEAM-OPEN")
        if state == "SEAM-OPEN":
            loop_bad.append(name)
        keys = sum(t.size for _n, _p, t, _v in spans)
        frames = int(round(max_t * fps))
        clips[name] = {"duration": round(float(max_t), 6), "frames": frames,
                       "seam": round(float(worst), 8) if seam else None,
                       "loop": bool(closed)}
        short = ""
        if authored and name in authored and authored_loop.get(name, True):
            # The frame the closing key belongs on: the authored time, or the next
            # grid frame after it when the author worked in fractions of a frame
            # (see loop_keys.authored_target).  The label says which way the clip is
            # wrong, because the two directions have different causes.
            af = loop_keys.authored_target({"duration": authored[name]}, fps)
            x = float(authored[name]) * fps
            exact = abs(x - round(x)) <= loop_keys.GRID_EPS
            if af > frames:
                short = " %s %d/%d frames" % ("SHORT" if exact else "FLOOR", frames, af)
                short_clips.append(name)
            elif frames > af:
                # Longer than the author wrote, and always by a rate ratio rather than
                # a rounding error.  This is what an export at the wrong scene frame
                # rate does: at Blender's factory 24 fps the baby's `celebrate` went
                # 1.8000 s -> 2.2500 s with its keys intact and its seam still closed,
                # so a seam-only audit waves it through and the app plays the pet 25%
                # slow.  Length is part of the animation, so it fails the run.
                short = " LONG %d/%d frames" % (frames, af)
                long_clips.append(name)
        print("%-16s %6d %8d %9.4f %-34s %-22s %s%s"
              % (name, len(chs), keys, max_t, lid_desc,
                 ("seam d=%.5f" % worst) if seam else "single-sample",
                 state if name not in desynced else state + " LID-DESYNC", short))
        if state == "SEAM-OPEN":
            print("      SEAM_DRIVEN_BY %s" % worst_chan)
        if early:
            print("      EARLY-END channels (%d, stop before t=%.4f): %s"
                  % (len(early), max_t, ", ".join(sorted(set(early))[:6])))

    if no_lid and len(no_lid) == len(anims):
        print("\nLID_SYNC N/A - this asset has no Lid_L/Lid_R scale channel at all "
              "(pre-eyelid build); nothing to compare")
    else:
        print("\nLID_SYNC %s - %d/%d clips drive Lid_L and Lid_R with the same curve "
              "(agree within %.0e on every sample)"
              % ("PASS" if not desynced else "FAIL",
                 len(anims) - len(desynced) - len(no_lid), len(anims), LID_ATOL))
    if desynced:
        print("  DESYNCED:", ", ".join(desynced))
    if no_lid:
        print("  NO_LID_CHANNEL:", ", ".join(no_lid))
    # The seam verdict only means something against the authored baseline: a clip
    # whose author left the last frame off has an open seam by design and is not a
    # defect, while a rebuilt clip that lost a key is a snap on every loop.
    print("LOOP_SEAM %d/%d clips end on their opening pose (longest span %.4f s)"
          % (len(anims) - len(loop_bad), len(anims), longest))
    if authored:
        off = sorted(short_clips) + sorted(long_clips)
        print("LOOP_FRAMES %s - %d/%d clips end on the authored closing frame%s"
              % ("PASS" if not off else "FAIL",
                 len(authored) - len(off), len(authored),
                 "" if not off else ": " + ", ".join(off)))
        if long_clips:
            print("  LOOP_STRETCHED %s - a clip longer than the author wrote is an "
                  "export at the wrong frame rate, not an animation edit"
                  % ", ".join(sorted(long_clips)))
    if dump:
        with open(dump, "w", encoding="utf-8") as fh:
            json.dump({"source": os.path.basename(path), "fps": fps,
                       "note": "clip baseline for tools/drako_loop_restore.py: frames = "
                               "the frame the last key sits on, loop = the author ended "
                               "the clip on its opening pose",
                       "clips": clips}, fh, indent=1, sort_keys=True)
        print("DURATIONS_WROTE %s (%d clips, %d authored as a closed loop)"
              % (dump, len(clips), sum(1 for v in clips.values() if v["loop"])))
    return 1 if (desynced or short_clips) else 0


if __name__ == "__main__":
    sys.exit(main())
