"""The one place Drako's blink curves are read and written.

`tools/drako_eyelids.py` authors the lid keys when the cards are first built and
`tools/drako_lid_sync.py` repairs clips that were authored before it.  Both must
agree on the channel path, on how a Blender 4.4+ action reaches its fcurves
(slots and layered action strips instead of `action.fcurves`), and on what
"the same blink on both eyes" means, so the rules live here once.

Why the two eyes have to share keys exactly: the blink curve scales the lid bone
over three frames (1.8 to close, 1.0 held, 4.0 to open), and `tools/drako_eyelids.py`
used to write the right lid 0.7 frames later than the left.  At the frame the app
samples, the left card was at scale 30 - fully shut - while the right was still
at 26.3, so one eye visibly blinked later than the other in every clip.

The shortened `sleep` clip is a separate bug and must not be attributed to this
offset: `tools/lid_sync_verify.py` shows the lost loop-closing key across all 78
channels of that clip, lids included, on assets that were already in sync.  It is
the float32 frame-grid ratchet - see `tools/loop_keys.py`.

Nothing in here touches bpy, so `tools/lid_curve_probe.py` can reuse it.
"""

LID_PATH = 'pose.bones["Lid_%s"].scale'
LID_SIDES = ("L", "R")
CURVE_GROUP = "Eyelids"
SCALE_COMPONENTS = (0, 1, 2)


def lid_path(side):
    return LID_PATH % side


def channelbags(action):
    """Every fcurve bag an action owns, however many slots or strips it uses.

    Blender 4.4 moved fcurves out of `Action` and into layered action strips
    bound to ID slots; a glTF clip imported as its own action has exactly one of
    each, but nothing here assumes that.
    """
    for lane in getattr(action, "layers", ()) or ():
        for strip in getattr(lane, "strips", ()) or ():
            for slot in getattr(action, "slots", ()) or ():
                cb = strip.channelbag(slot)
                if cb is not None:
                    yield cb


def scale_curves(cb, side):
    """{component: fcurve} for one lid bone's scale, or {} when it has none."""
    path = lid_path(side)
    got = {}
    for fc in cb.fcurves:
        if getattr(fc, "data_path", None) != path:
            continue
        idx = getattr(fc, "array_index", None)
        if idx is None:
            raise SystemExit(
                "LID_SCALE_IS_ONE_VECTOR_CURVE for %s - the copy below needs the "
                "three component curves that glTF export and authoring produce, and "
                "guessing a vector curve's data layout would corrupt the blink" % path)
        got[int(idx)] = fc
    return got


def curve_keys(fcurves):
    """[[frame, value], ...] of one component fcurve, in frame order."""
    return [[round(float(kp.co[0]), 5), round(float(kp.co[1]), 6)]
            for kp in sorted(fcurves.keyframe_points, key=lambda k: k.co[0])]


def lid_state(action, sides=LID_SIDES):
    """Every lid scale key this action carries, per side and component.

    A bag that has the bone on one axis only reports the components it has, so a
    missing channel shows up as an empty dict instead of silently as "in sync".
    """
    state = {side: {} for side in sides}
    for cb in channelbags(action):
        for side in sides:
            for idx, fc in sorted(scale_curves(cb, side).items()):
                state[side].setdefault(idx, []).extend(curve_keys(fc))
    for side in sides:
        for idx in state[side]:
            state[side][idx] = sorted(state[side][idx])
    return state


def _copy_component(cb, src, idx, dst_path):
    for fc in [f for f in list(cb.fcurves)
               if getattr(f, "data_path", None) == dst_path
               and getattr(f, "array_index", None) == idx]:
        cb.fcurves.remove(fc)
    fc = cb.fcurves.new(dst_path, index=idx, group_name=CURVE_GROUP)
    try:
        fc.extrapolation = src.extrapolation
    except (AttributeError, TypeError):
        pass
    for skp in sorted(src.keyframe_points, key=lambda k: k.co[0]):
        kp = fc.keyframe_points.insert(skp.co[0], skp.co[1], options={"FAST"})
        kp.interpolation = skp.interpolation
        if skp.interpolation not in ("LINEAR", "CONSTANT"):
            # Only the easing curves use handles; on a linear blink key they are
            # dead weight, and writing them back would let Blender recompute the
            # automatic ones and move a key that has to stay put.
            kp.handle_left_type = skp.handle_left_type
            kp.handle_right_type = skp.handle_right_type
            kp.handle_left = skp.handle_left
            kp.handle_right = skp.handle_right
    return fc


def sync_action(action, order=LID_SIDES):
    """Copy the first side's lid scale keys onto the rest, component for component.

    Every axis goes, not just the one the blink animates: leaving a stale X or Z
    channel behind would let the rebuilt right lid sit on different frames than
    the left, which is the bug this repairs.  Returns a report dict, or None when
    the action has no lid channels at all.
    """
    src_side = order[0]
    bags = list(channelbags(action))
    srcs = [scale_curves(cb, src_side) for cb in bags]
    if not any(srcs):
        return None
    report = {"clip": action.name, "source": lid_path(src_side), "bags": 0,
              "changed": [], "skipped": [], "missing_source": []}
    for cb, src in zip(bags, srcs):
        if not src:
            report["missing_source"].append(sorted(scale_curves(cb, src_side)))
            continue
        report["bags"] += 1
        for side in order[1:]:
            dst_path = lid_path(side)
            dst = scale_curves(cb, side)
            if sorted(dst) != sorted(src):
                # Rebuild whatever channels do not match instead of editing keys
                # in place: a component present on one side only cannot be
                # reconciled key by key, and the values must be identical.
                for idx in sorted(src):
                    _copy_component(cb, src[idx], idx, dst_path)
                report["changed"].append(
                    "%s[%s] rebuilt" % (side, ",".join(str(i) for i in sorted(src))))
                continue
            changed = []
            for idx in sorted(src):
                if curve_keys(src[idx]) != curve_keys(dst[idx]):
                    changed.append(idx)
                    _copy_component(cb, src[idx], idx, dst_path)
            if changed:
                report["changed"].append("%s%s" % (side, ",".join(str(i) for i in changed)))
    for cb in bags:
        for side in order[1:]:
            for idx, fc in sorted(scale_curves(cb, side).items()):
                fc.update()
    state = lid_state(action, order)
    ref = state.get(order[0], {})
    report["identical"] = all(state.get(s, {}) == ref for s in order[1:])
    report["keys"] = {s: {i: len(v) for i, v in sorted(state.get(s, {}).items())}
                      for s in order}
    return report


def uniform_scale(action, sides=LID_SIDES):
    """Copy each lid's local-Y scale keys onto its X and Z channels.

    The bind is the authored card compressed 1/REST_DIV on all three bone axes,
    because compressing the sweep alone left a full-width ribbon on the brow where
    the head had fallen away - the 40 mm blade.  A uniform bind only expands back
    into the card if the blink scales uniformly too, and every shipped clip animates
    local Y alone.  This writes the missing two components from the one that
    exists, so the peak the coverage was measured at is the peak the clip reaches.

    Returns a report dict; `written` empty means every clip was already uniform.
    """
    report = {"clip": action.name, "bags": 0, "written": [], "missing_y": []}
    for cb in channelbags(action):
        for side in sides:
            cur = scale_curves(cb, side)
            if 1 not in cur:
                report["missing_y"].append(side)
                continue
            report["bags"] += 1
            src = cur[1]
            for idx in (0, 2):
                if idx in cur and curve_keys(cur[idx]) == curve_keys(src):
                    continue
                _copy_component(cb, src, idx, lid_path(side))
                report["written"].append("%s[%d]" % (side, idx))
    return report


def uniform_state(action, sides=LID_SIDES):
    """Whether every lid scale curve in `action` carries one identical profile."""
    state = lid_state(action, sides)
    return {side: sorted(state[side]) == [0, 1, 2]
            and state[side][0] == state[side][1] == state[side][2]
            for side in sides}


def sync_lids(actions, order=LID_SIDES):
    """Sync every action that carries lid channels; returns one report per clip."""
    out = []
    for action in actions:
        rep = sync_action(action, order)
        if rep is not None:
            out.append(rep)
    return out
