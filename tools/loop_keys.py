"""Keep a baked Drako clip's frame count and its loop seam intact across a round trip.

What the measurements showed
----------------------------
`tools/qa_pet/drako_dewasa_lids.glb` holds the adult `sleep` clip as 127 keys per
channel, the last at 4.2000 s (= frame 126) with the same pose as frame 0, so the
loop has no seam.  Importing that file into Blender and exporting it again - with
nothing edited - writes 126 keys ending at 4.1667 s.  Doing it once more gives 125
keys at 4.1333 s, which is what shipped.  The clip loses exactly one frame per
round trip, in every channel at once, so it is not an animation decision: it is
the storage.

The chain is:

* glTF stores sampler times as **float32 seconds**.  4.2 s is not representable,
  so the file holds 4.1999998092 s.
* Blender's importer turns that into a keyframe at `t * fps` = **125.99999428**
  frames, just below the integer the author meant.
* The exporter's armature channels for these baked clips come out of the sampled
  path, whose range is `int(action.frame_range[1])`
  (`io_scene_gltf2/blender/exp/animation/action.py`, feeding
  `export_settings['ranges']`) = **125**.  A sample grid of 0..125 cannot emit a
  key at 125.99999, so the loop-closing key is gone, and the new last key is
  125/30 - again not float32-exact - which starts the next round of the same thing.

Every clip whose authored length is exact in float32 (2.0, 1.6, 1.0, 0.8 s) is
untouched, which is why only the adult's `sleep` - the one clip authored at 4.2 s
- shrank, and why the symptom looked like a single flaky clip.

A second, much larger version of the same bug is a *wrong* frame rate rather than a
rounding error.  The exporter quantises sampled armature keys onto
`scene.render.fps`, and a Blender session started with `--factory-startup` is at 24
fps, not the 30 fps every Drako clip is authored on.  `tools/drako_lid_sync.py` was
the one builder that never set it; run on the shipped baby rig it rewrote the same
keys at k/24, so `celebrate` went from 1.8000 s to 2.2500 s and `sleep` from 4.3333 s
to 5.4167 s - the loops stayed self-consistent, so a seam check passes and the pet
just plays 25 % slower in the app.  `tools/glb_export.py` now owns the frame rate for
the whole pipeline; this module only measures the damage.

Two operations, both safe to re-run
----------------------------------
`snap_to_grid` puts every keyframe back on the integer frame it was authored on.
The keys are on-grid by construction (they come from a 30 fps bake), so anything
within `tol` frames of an integer is the float32 error, and writing the integer
back makes `frame_range[1]` exact, so the exporter's own `int()` is a no-op.

`close_loops` restores what earlier round trips already ate: for a clip the author
ended on its opening pose, it inserts that pose on the authored end frame.  The
baseline (frames + whether the clip loops at all) comes from the untouched asset,
dumped by `tools/lid_sync_verify.py --durations-json`, because a clip the author
deliberately left open - a one-shot - must not be forced shut.  Measured that way,
with the quaternion-aware seam below, all 25 clips of all three Drako stages are
authored as closed loops; the flag exists so a future one-shot is respected instead
of assumed.

Nothing here imports bpy, so the caller passes live Blender data.
"""

import math

from lid_curves import channelbags

SEAM_TOL = 1e-4          # pose difference (Blender units) that still counts as closed
QUATERNION_PATH = "rotation_quaternion"
# A frame time this close to an integer is that integer wearing float32 error.
# 1e-3 of a frame is 0.033 ms at 30 fps, four orders of magnitude above the storage
# noise (a 4.3 s time carries ~5e-6 frames of it) and two below the authored fractions
# the 25 fps clips really do have (0.2, 0.4, 0.6 of a frame), so it separates the two
# cases instead of guessing.
GRID_EPS = 1e-3


def pair_seam(v0, v1, rotation=False):
    """How far two endpoint samples of one channel are from each other.

    A quaternion has to be compared as a rotation, not as four numbers: `q` and
    `-q` are the same orientation, and the two ends of a perfectly closed loop
    routinely land on opposite signs because that is what the exporter happens to
    write.  Measured on the three authored Drako assets, the worst seam in the whole
    library is exactly 2.0 on `Root.rotation_quaternion` - the identity rotation
    written once as (1,0,0,0) and once as (-1,0,0,0).  Comparing the components
    directly called that an open loop and mislabelled `celebrate` a one-shot in all
    three stages; matching `q` against `-q` as well makes it 0, like every other
    clip.  So a rotation channel is closed if either sign agrees.
    """
    d = max((abs(a - b) for a, b in zip(v0, v1)), default=0.0)
    if rotation and len(v0) == 4:
        d = min(d, max(abs(a + b) for a, b in zip(v0, v1)))
    return float(d)


def _curve_groups(action):
    """[(is_rotation, [fcurve per component])] - one glTF channel at a time.

    Component curves are grouped by data path because a quaternion's sign only
    means anything across all four of them.
    """
    groups = {}
    for cb in channelbags(action):
        for fc in cb.fcurves:
            if not fc.keyframe_points:
                continue
            groups.setdefault(fc.data_path, {})[int(getattr(fc, "array_index", 0) or 0)] = fc
    out = []
    for path, by_index in groups.items():
        curves = [by_index[i] for i in sorted(by_index)]
        out.append((path.endswith(QUATERNION_PATH) and len(curves) == 4, curves))
    return out


def last_frame(action):
    """Highest keyframe time across every fcurve of an action, in frames."""
    hi = None
    for cb in channelbags(action):
        for fc in cb.fcurves:
            if not fc.keyframe_points:
                continue
            f = fc.keyframe_points[-1].co[0]
            hi = f if hi is None or f > hi else hi
    return hi


def authored_target(entry, fps):
    """The frame the closing key has to sit on, or None if the entry has no end.

    The authored end is a time in seconds.  A clip whose seconds value is an integer
    number of frames (`sleep` at 4.2 s = 126) has to end on exactly that frame, and
    one that is not - the baby rig was authored at 25 fps, so `head_look` at 1.92 s
    is 57.6 frames at 30 - has to end on the frame *after* it, because that is the
    first frame the loop can close on without deleting the motion in front of it.
    Flooring is what the retime did, and it is why ten of the baby's 25 clips ship
    with an open seam today (measured 0.00097 to 0.01061 on Head, Tail, Wing and
    Chest rotations): the clip restarts on a pose it never reaches.

    Ceil needs a real tolerance, not an epsilon of nothing.  glTF times are float32,
    so `1.43333328 * 30` comes back as 43.0000019 - already the authored frame - and
    a bare `ceil` pushed 15 of the baby's clips one whole frame past their own
    runtime duration, which the audit then read as the repair being needed.  Anything
    within `GRID_EPS` frames of an integer *is* that integer; only a genuine fraction
    rounds up.
    """
    if entry.get("duration") is not None:
        x = float(entry["duration"]) * float(fps)
        near = math.floor(x + 0.5)
        if abs(x - near) <= GRID_EPS:
            return int(near)
        return int(math.ceil(x - GRID_EPS))
    if entry.get("frames") is not None:
        return int(entry["frames"])
    return None


def seam_delta(action):
    """How far the clip's last sample sits from its first, across every channel."""
    worst = 0.0
    for is_rot, curves in _curve_groups(action):
        end = curves[0].keyframe_points[-1].co[0]
        v0 = [fc.evaluate(0.0) for fc in curves]
        v1 = [fc.evaluate(end) for fc in curves]
        worst = max(worst, pair_seam(v0, v1, is_rot))
    return worst


def snap_to_grid(actions, tol=0.02):
    """Write every near-integer keyframe time back as the integer it meant to be.

    Handles travel by the same delta so a BEZIER curve keeps its tangent; the
    exported clips are LINEAR, so this only matters if a future clip is authored
    with bezier handles.
    """
    report = []
    for act in actions:
        moved, worst = 0, 0.0
        for cb in channelbags(act):
            for fc in cb.fcurves:
                touched = False
                for kp in fc.keyframe_points:
                    f = kp.co[0]
                    n = round(f)
                    d = n - f
                    if abs(d) <= tol and d != 0.0:
                        kp.co[0] = float(n)
                        kp.handle_left[0] += d
                        kp.handle_right[0] += d
                        moved += 1
                        worst = max(worst, abs(d))
                        touched = True
                if touched:
                    fc.update()
        report.append({"clip": act.name, "keys_snapped": moved,
                       "worst_delta_frames": round(worst, 9), "last": last_frame(act)})
    return report


def off_grid(actions, limit=0.0):
    """The worst distance any keyframe time sits from an integer frame, per clip.

    On a correctly imported asset this is float32 noise: measured across all 25 baby
    clips after `snap_to_grid`, 7.6e-06 of a frame.  It is how a tool can tell that
    the keys are *not* on the grid it is about to export against, which is the
    signature of reading the file at the wrong frame rate - a 30 fps clip imported in
    a 24 fps scene lands on 43.2, two tenths of a frame off, and no amount of
    closing-key repair makes the motion right again (the endpoints still line up with
    the authored length, which is exactly why the length checks alone pass it).
    `at` names the channel so the message is traceable.
    """
    out = []
    for act in actions:
        worst, where = 0.0, None
        for cb in channelbags(act):
            for fc in cb.fcurves:
                for kp in fc.keyframe_points:
                    f = float(kp.co[0])
                    d = abs(f - round(f))
                    if d > worst and d > limit:
                        worst, where = d, (fc.data_path, round(f, 6))
        out.append({"clip": act.name, "worst_off_grid": round(worst, 9), "at": where})
    return out


def close_loops(actions, baseline, fps=30.0, only_missing=True):
    """Append the opening pose on the authored end frame, for looping clips only.

    `baseline` maps clip name -> {"duration" or "frames", "loop": bool} as dumped
    from the untouched asset.  A clip already at its target is left alone; one a
    round trip shortened gets its closing key back, which restores the seam and,
    when the authored length fits the frame grid, the duration too.  `gap_frames`
    in the report is how many frames were missing.  A clip the author left open
    (loop=False) is never touched.
    """
    report = []
    for act in actions:
        b = baseline.get(act.name)
        if b is None:
            report.append({"clip": act.name, "action": "no-baseline", "skipped": True})
            continue
        target = authored_target(b, fps)
        if not b.get("loop", True):
            report.append({"clip": act.name, "action": "one-shot", "skipped": True})
            continue
        last = last_frame(act)
        if last is None:
            report.append({"clip": act.name, "action": "no-keys", "skipped": True})
            continue
        have = int(round(last))
        if have > target:
            # Longer than the author wrote.  Appending would make it worse and
            # trimming would delete motion, so this is left for `verify` to fail on
            # and the caller to explain - it is the signature of an export that ran
            # at the wrong frame rate, not of a clip that needs a closing key.
            report.append({"clip": act.name, "action": "LONGER-THAN-AUTHORED",
                           "frames": have, "authored": target, "skipped": True})
            continue
        if have == target and only_missing:
            # Already as long as the author wrote, so there is nothing to append.  A
            # clip at the right length whose last key is not its first would need a
            # key *moved*, and silently editing authored pose values is not this
            # function's job - `verify` fails that clip instead of guessing.
            seam = seam_delta(act)
            report.append({"clip": act.name, "action": "already-closed", "frames": have,
                           "seam": round(seam, 8), "seam_open": seam > SEAM_TOL})
            continue
        inserted = 0
        seam_before = seam_delta(act)
        for cb in channelbags(act):
            for fc in cb.fcurves:
                if not fc.keyframe_points:
                    continue
                prev = fc.keyframe_points[-1]
                kp = fc.keyframe_points.insert(float(target), fc.evaluate(0.0),
                                               options={"FAST"})
                kp.interpolation = prev.interpolation
                inserted += 1
        for cb in channelbags(act):
            for fc in cb.fcurves:
                fc.update()
        report.append({"clip": act.name, "action": "closed", "keys_inserted": inserted,
                       "frames_before": have, "frames_after": target,
                       "gap_frames": target - have,
                       "seam_before": round(seam_before, 8),
                       "seam_after": round(seam_delta(act), 8)})
    return report


def verify(actions, baseline, fps=30.0):
    """Every looping clip must reach its authored end frame on a closed seam.

    Returns [{clip, why}] - empty means the asset can be exported.  This is the
    gate the builders run before writing, because the damage this module repairs
    is invisible in a viewport still playing the shortened clip.
    """
    bad = []
    for act in actions:
        b = baseline.get(act.name)
        if b is None or not b.get("loop", True):
            continue
        last = last_frame(act)
        if last is None:
            continue
        have, target = int(round(last)), authored_target(b, fps)
        if have < target:
            bad.append({"clip": act.name, "why": "SHORT %d/%d frames" % (have, target)})
            continue
        if have > target:
            # The signature of an export that quantised the clip onto the wrong frame
            # grid.  Measured for real: a builder that left Blender at its factory
            # 24 fps wrote the baby's `celebrate` as 2.25 s instead of 1.8 s - the same
            # keys, 25 % slower, and the loop still "closed", so a seam-only check
            # waved it through.  Length is part of the animation, so it is gated here
            # too rather than left to be noticed in the app.
            bad.append({"clip": act.name, "why": "LONG %d/%d frames" % (have, target)})
            continue
        seam = seam_delta(act)
        if have == target and seam > SEAM_TOL:
            bad.append({"clip": act.name, "why": "SEAM-OPEN %.6f" % seam})
    return bad
