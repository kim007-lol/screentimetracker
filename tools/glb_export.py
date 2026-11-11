"""The one way a Drako pipeline tool writes a GLB, so a round trip cannot eat a key.

Why this exists
---------------
Every builder used to call `bpy.ops.export_scene.gltf` itself with the same long
flag list.  That is two problems, not one of style.

* The flags drift.  Eleven of them decide whether animations come out per-action,
  unoptimized, in +Y up, with skins and morphs; `drako_texture_reapply.py` already
  carries an extra `export_image_format`.  A tool that forgets one ships an asset
  the runtime reads differently, and the difference shows up as "the pet lost its
  blink", not as an error.
* The frame-grid ratchet (`tools/loop_keys.py`).  glTF stores sampler times as
  float32 seconds, so a clip ending at frame 126 comes back from Blender as
  125.99999428; the exporter's sampled-armature range is `int(frame_range[1])`, so
  it writes 0..125 and the loop-closing key is gone.  Every naive re-export costs
  one more frame.  Measured on the adult `sleep` clip: 127 keys -> 126 -> 125,
  which is what shipped.
* The scene frame rate.  The exporter samples at `scene.render.fps` and a factory
  Blender session is at 24, while every Drako clip is on a 30 grid - so an import
  reads seconds onto the wrong grid and the export writes them back at the wrong
  spacing.  `ASSET_FPS`, `set_frame_rate` and `import_glb` are the fix; `export_glb`
  always writes at the asset rate and says so when it had to change the scene.

So the export goes through here: snap every key back onto the integer frame it was
authored on, restore any closing key the input still had, verify against the
input's own frame counts, and only then write.  Verification is a gate, not a log -
a builder refuses to export rather than ship a clip shorter than the file it was
given, or longer.

The baseline is the tool's own input file, read structurally (no Blender, no
mutation), because "do not make this clip shorter than the file you imported" is the
rule that holds for every asset.  Repairing damage an earlier round trip already did
is a different job - that needs what the author wrote, not what the last export left
behind, and `tools/drako_loop_restore.py` does it with an authored baseline.

Run from a Blender script, e.g.

    sys.path.insert(0, tools_dir)
    import glb_export
    glb_export.export_glb(out, src=src, tag="LID_SYNC")
"""
import json
import os
import sys

import bpy


def _tools_dir():
    """This file's own directory, however Blender was pointed at it."""
    for cand in (os.environ.get("QA_TOOLS_DIR"),
                 os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else None,
                 os.path.abspath("tools")):
        if cand and os.path.isfile(os.path.join(cand, "loop_keys.py")):
            return os.path.abspath(cand)
    raise SystemExit("CANNOT_FIND loop_keys.py - run this script from the project root")


sys.path.insert(0, _tools_dir())
import loop_keys                                             # noqa: E402
from lid_curve_probe import read_glb, accessor               # noqa: E402

# The settings every Drako export has agreed on: one animation per action, no key
# reduction, +Y up, skins and morph targets kept, custom properties kept.
GLTF_EXPORT_FLAGS = {
    "export_format": "GLB",
    "use_selection": False,
    "export_animations": True,
    "export_animation_mode": "ACTIONS",
    "export_nla_strips": False,
    "export_anim_slide_to_zero": True,
    "export_optimize_animation_size": False,
    "export_morph": True,
    "export_skins": True,
    "export_yup": True,
    "export_extras": True,
}


# Every Drako clip is authored, baked and shipped on a 30 fps grid.  Measured, not
# assumed: `tools/qa_rig/tmp_grid_probe.py` multiplies all sampler times of the three
# shipped assets by candidate rates and only 30 (and its multiples) comes back clean
# to 7e-6 of a frame.  This matters because the glTF exporter quantises sampled
# armature keys onto `scene.render.fps`, and a `--factory-startup` Blender session is
# at 24.  One builder forgot to set it and silently rewrote the baby rig at k/24:
# `celebrate` 1.8000 s -> 2.2500 s, `sleep` 4.3333 s -> 5.4167 s, 44 keys -> 35.  The
# loops stayed closed, so only a length check catches it - which is why the rate is
# owned here instead of repeated in eight scripts.
ASSET_FPS = 30.0


def _named_actions():
    return sorted((a for a in bpy.data.actions if a.name), key=lambda a: a.name)


def set_frame_rate(fps=ASSET_FPS):
    """Put the scene on the grid the exported keys will be sampled at.

    Returns what the rate was before, so a caller can tell whether it was already
    right.  Blender 5.x stores this as an integer `render.fps` divided by a float
    `render.fps_base`, and assigning a float to it raises
    `RenderSettings.fps expected an int type, not float` - so the whole part goes in
    `fps` and any remainder is carried by `fps_base` (the effective rate is
    `fps / fps_base`, which has to say 30 or the exporter writes k/25).
    """
    scene = bpy.context.scene
    was = float(scene.render.fps) / float(scene.render.fps_base)
    want = float(fps)
    if abs(was - want) <= 1e-6:
        return was
    whole = int(round(want)) or 1
    scene.render.fps = whole
    scene.render.fps_base = whole / want if abs(whole - want) > 1e-9 else 1.0
    return was


def import_glb(path, fps=ASSET_FPS):
    """Read a GLB the way every Drako tool means to: on the asset's own frame grid.

    The importer converts seconds to frames with the *current* scene rate, so setting
    the rate after the import is too late - by then the keys already live on the wrong
    grid and re-exporting just rescales the damage.  Any tool that imports a Drako
    asset and writes it back should import through here.
    """
    was = set_frame_rate(fps)
    bpy.ops.import_scene.gltf(filepath=os.path.abspath(path))
    return was


def baseline_from_glb(path, fps=30.0):
    """{clip: {frames, loop, duration, seam, channels}} straight out of a GLB file.

    `loop` is the author's own ending: the last sample of every channel repeats the
    first, judged as a pose (see `loop_keys.pair_seam` - a quaternion written with
    the opposite sign is the same rotation, not an open loop).  A one-shot ends
    somewhere else and must not be closed, which is why this is read from the file
    rather than assumed.
    """
    js, binv = read_glb(path)
    out = {}
    for an in js.get("animations", []):
        name = an.get("name", "?")
        spans = []
        for ch in an["channels"]:
            sm = an["samplers"][ch["sampler"]]
            t = accessor(js, binv, sm["input"]).ravel()
            v = accessor(js, binv, sm["output"])
            if t.size:
                spans.append((ch["target"]["path"], t, v))
        if not spans:
            continue
        hi = max(float(t[-1]) for _p, t, _v in spans)
        seam = max((loop_keys.pair_seam(list(v[0]), list(v[-1]), p == "rotation")
                    for p, t, v in spans), default=0.0)
        out[name] = {"frames": int(round(hi * fps)), "duration": round(hi, 6),
                     "loop": seam < loop_keys.SEAM_TOL, "seam": round(seam, 8),
                     "channels": len(spans)}
    return out


def skinned_mesh_nodes(js):
    """{node name: joints?} for every node the file binds to a skin.

    `joints` is whether any primitive of that mesh carries JOINTS_0, which is the
    half of the binding the exporter actually writes: a node can keep its `skin`
    and still lose the weights, or lose the armature modifier in Blender and be
    written as a rigid mesh with no `skin` at all.
    """
    out = {}
    for n in js.get("nodes", []):
        if "skin" not in n or "mesh" not in n:
            continue
        mesh = js["meshes"][n["mesh"]]
        has = any("JOINTS_0" in p.get("attributes", {}) for p in mesh.get("primitives", []))
        out[n.get("name") or "mesh:%s" % mesh.get("name", "?")] = has
    return out


def check_skin(src, out):
    """Return the meshes a round trip unskinned, comparing two GLB files.

    Empty list means the output binds every mesh the input bound, with weights.
    This is the guard against a builder that removes an armature modifier for
    bind-space maths and forgets to put it back: the exporter then writes that
    mesh as a rigid object, so the body stops following the bones while every
    clip still looks intact in a key-level audit.  Measured on the adult:
    `drako_eyelids_fix.py` did exactly that and `DrakoMesh` came out with
    neither `skin` nor `JOINTS_0` - only a render showed it, because the mesh
    simply vanished from a viewer that culls unskinned objects.
    """
    if not (src and os.path.exists(src) and os.path.exists(out)):
        return []
    before = skinned_mesh_nodes(read_glb(src)[0])
    after = skinned_mesh_nodes(read_glb(out)[0])
    lost = [n for n in before if n not in after]
    unweighted = [n for n in before if n in after and before[n] and not after[n]]
    return [{"node": n, "why": "skin binding gone"} for n in lost] + \
           [{"node": n, "why": "JOINTS_0 missing"} for n in unweighted]


def baseline_from_actions(actions, fps=30.0):
    """The same shape, measured on live Blender actions instead of a file.

    Call this right after import, before editing curves, when the source of the
    clip is not a GLB on disk (a freshly generated rig, for example).
    """
    out = {}
    for act in actions:
        last = loop_keys.last_frame(act)
        if last is None:
            continue
        out[act.name] = {"frames": int(round(last)), "duration": round(last / fps, 6),
                         "loop": loop_keys.seam_delta(act) < loop_keys.SEAM_TOL,
                         "seam": round(loop_keys.seam_delta(act), 8)}
    return out


def load_baseline(spec, fps=30.0):
    """Accept a GLB path, a `lid_sync_verify.py --durations-json` dump, a directory,
    or an already-built dict - anything a caller can reasonably have.

    Bare `{clip: seconds}` maps are normalised too, with `loop` assumed true, since
    a caller who only wrote down durations is describing a looping clip.
    """
    file_fps = float(fps)
    path = None
    if not isinstance(spec, dict):
        path = os.path.abspath(str(spec))
        if path.endswith(".json"):
            blob = json.load(open(path, encoding="utf-8"))
            file_fps = float(blob.get("fps", fps))
            spec = blob.get("clips", blob)
        elif os.path.isfile(path):
            return baseline_from_glb(path, file_fps)
        elif os.path.isdir(path):
            out = {}
            for entry in sorted(os.listdir(path)):
                if entry.lower().endswith((".glb", ".gltf")):
                    out.update(baseline_from_glb(os.path.join(path, entry), file_fps))
            return out
        else:
            raise SystemExit("BASELINE_NOT_READABLE %s - not a GLB, JSON or directory" % path)
    out = {}
    for k, v in spec.items():
        if isinstance(v, dict):
            entry = dict(v)
            if "frames" not in entry:
                entry["frames"] = int(round(float(entry["duration"]) * file_fps))
            entry.setdefault("loop", True)
            out[k] = entry
        else:
            out[k] = {"frames": int(round(float(v) * file_fps)), "loop": True}
    return out


def export_glb(filepath, baseline=None, src=None, fps=None, actions=None,
               extra_flags=None, reset_pose=False, unassign_action=False,
               arm=None, tag="EXPORT", enforce=True, tol_frames=0.02,
               check_grid=True, quiet=False):
    """Snap to the authored frame grid, restore loop-closing keys, verify, write.

    `baseline` is what the clips must end up as long as: a dict from
    `baseline_from_actions`, a GLB path, or a durations JSON.  `src` is the
    shorthand for the common case - the file this tool just imported - and is only
    read when no explicit baseline is given.  Pass neither and the clip lengths are
    not checked: the call still snaps the grid (that alone stops the ratchet on an
    intact asset) and prints `LOOP_GUARD no-baseline`, so the gap is auditable.

    `reset_pose`/`unassign_action`/`arm` reproduce what the builders already did by
    hand; they are opt-in so wiring this in never silently changes an asset.  The
    armature object transform is never touched - several tools deliberately keep the
    imported root position.

    `check_grid` is the frame-rate gate described above: no key may sit more than
    `tol_frames` of a frame away from an integer after snapping.  Turn it off only
    when a clip is really authored between frames, and say why at the call site.
    """
    if fps is None:
        fps = float(os.environ.get("QA_FPS", ASSET_FPS))
    fps = float(fps)
    was = set_frame_rate(fps)
    if abs(was - fps) > 1e-6 and not quiet:
        print("FRAME_RATE the scene was %g fps, this export writes %g fps - if the "
              "asset was imported at %g too, import through glb_export.import_glb()"
              % (was, fps, was))
    filepath = os.path.abspath(filepath)
    acts = list(actions) if actions is not None else _named_actions()
    if baseline is None and src is not None:
        baseline = src
    if baseline:
        baseline = load_baseline(baseline, fps)

    snaps = loop_keys.snap_to_grid(acts, tol=tol_frames)
    moved = sum(s["keys_snapped"] for s in snaps)
    grid = loop_keys.off_grid(acts)
    off = [g for g in grid if g["worst_off_grid"] > tol_frames]
    if not quiet:
        print("GRID %d clips, worst key %.2e of a frame off the integer grid after "
              "snapping to %.3f" % (len(acts), max((g["worst_off_grid"] for g in grid),
                                                   default=0.0), tol_frames))
    if off and check_grid and enforce:
        worst = max(g["worst_off_grid"] for g in off)
        why = off[0]
        raise SystemExit(
            "FRAME_RATE_GRID %d/%d clips still sit up to %.4f of a frame off the "
            "integer grid after snapping to %.3f (%s: %s at frame %s). Those keys were "
            "read onto the wrong scene frame rate, and exporting them writes motion "
            "the author never timed - the endpoints alone can look fine, so the "
            "closing-key checks above pass. Import through "
            "glb_export.import_glb(path, fps=<the asset's own rate>) so the importer "
            "and exporter agree; pass check_grid=False only for a clip genuinely "
            "authored between frames."
            % (len(off), len(acts), worst, tol_frames, why["clip"], why["at"][0],
               why["at"][1]))
    closes = []
    if baseline:
        closes = loop_keys.close_loops(acts, baseline, fps=fps)
    repaired = [c for c in closes if c.get("action") == "closed"]
    bad = loop_keys.verify(acts, baseline, fps=fps) if baseline else []
    if not quiet:
        for s in snaps:
            if s["keys_snapped"]:
                print("SNAP %-18s keys=%d worst=%.2e frames last=%s"
                      % (s["clip"], s["keys_snapped"], s["worst_delta_frames"], s["last"]))
        for c in closes:
            if c.get("action") == "closed":
                print("CLOSE %-16s %d->%d frames keys=%d seam %.6f->%.6f"
                      % (c["clip"], c["frames_before"], c["frames_after"],
                         c["keys_inserted"], c["seam_before"], c["seam_after"]))
            elif c.get("action") == "LONGER-THAN-AUTHORED":
                print("CLOSE %-16s LONGER than baseline %d/%d frames - left alone"
                      % (c["clip"], c["frames"], c["authored"]))
        print("LOOP_GUARD %s snapped=%d repaired=%d checked=%d%s"
              % ("PASS" if not bad else "FAIL", moved, len(repaired),
                 len(baseline) if baseline else 0,
                 "" if baseline else " no-baseline"))
        for b in bad:
            print("LOOP_GUARD %-16s %s" % (b["clip"], b["why"]))
    if bad and enforce:
        raise SystemExit("LOOP_REGRESSION %s - refusing to write %s; pass baseline=None "
                         "or enforce=False only if this clip is meant to change"
                         % (" ".join(sorted(b["clip"] for b in bad)), os.path.basename(filepath)))

    if unassign_action:
        targets = [arm] if arm is not None else [o for o in bpy.data.objects if o.type == "ARMATURE"]
        for obj in targets:
            if obj.animation_data:
                obj.animation_data.action = None
    if reset_pose:
        import mathutils
        ident = mathutils.Matrix.Identity(4)
        targets = [arm] if arm is not None else [o for o in bpy.data.objects if o.type == "ARMATURE"]
        for obj in targets:
            for pb in obj.pose.bones:
                pb.matrix_basis = ident.copy()
    bpy.context.view_layer.update()

    flags = dict(GLTF_EXPORT_FLAGS)
    flags.update(extra_flags or {})
    bpy.ops.export_scene.gltf(filepath=filepath, **flags)
    src_path = os.path.abspath(src) if isinstance(src, (str, os.PathLike)) else None
    lost = check_skin(src_path, filepath)
    if lost:
        names = ", ".join("%s (%s)" % (l["node"], l["why"]) for l in lost)
        if os.path.exists(filepath):
            os.remove(filepath)      # a half-built asset is worse than no asset
        raise SystemExit(
            "SKIN_LOST %s - the written file binds fewer meshes than %s: %s. A mesh "
            "that lost its armature modifier or vertex groups exports as a rigid "
            "object: the clips all still pass, but the body stops following the "
            "bones and the viewer shows only what is still skinned. Restore the "
            "modifiers before exporting (tools/drako_eyelids_fix.py drops them for "
            "bind-space measurement and must put them back). The bad file was "
            "deleted." % (os.path.basename(filepath),
                          os.path.basename(src_path) if src_path else "<no src>",
                          names))
    print("%s_WROTE %s (%d bytes)" % (tag, filepath, os.path.getsize(filepath)))
    return {"snapped": moved, "repaired": [c["clip"] for c in repaired],
            "violations": bad, "bytes": os.path.getsize(filepath)}
