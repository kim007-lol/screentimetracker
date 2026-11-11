#!/usr/bin/env python3
"""Turn Drako's teen head back to facing forward, in the bind pose.

Why this exists.  The shipped teen reads as a lopsided dog face: one eye sits
frontal and huge, the other is wrapped around the silhouette, and the muzzle
with its nostrils points to the viewer's right.  That is not the eyelid cards
and not the repaint.  In bind pose - pose zeroed, armature modifier ignored, so
this is the raw mesh - the head's sagittal plane is fitted at +17.5 deg while
its own torso is at -8.1 deg.  The adult and the baby both fit at 0.0 deg with
millimetre residuals and their front renders are symmetric, so the fit is not
the artifact: the teen skull really is modelled turned, inherited from
`docs/docs-assets-chr/paket-drako-3d-final/drako_remaja.glb`, whose head is
turned the *other* way (centre offset -0.097 m, mirror median 74 mm).  The
reference art in that same folder shows the teen facing straight ahead with two
equal eyes, so the turn is a defect against the brief, not a style.

What it does.  One rigid rotation of the head assembly about the vertical axis,
ramped to zero across the neck by the same skin-weight field the rig already
uses to animate the head, so:

  * every vertex with >= 0.5 total Head/Horn/Lid weight turns by the full angle
    as one piece - skull, horns, brow, muzzle, and both blink cards;
  * vertices below that turn by smoothstep(w) of the angle, which is the same
    blend the clips already apply when Head rotates, so the neck bends the way
    it bends during head_look instead of tearing;
  * vertex normals turn with their vertex, because the exporter writes the
    stored custom normals and a stale 17 deg normal would re-light the face;
  * every bone from `Head` down gets the same rigid motion on its rest matrix,
    and no animation curve is touched.  Parent and child rests both become
    R*M, so their relative rest offset is unchanged and the posed world
    transform of the head family becomes R*(what it was): the clips now turn a
    straight head from straight instead of swinging a turned one.

The angle is measured in-run, never hardcoded, and the deformed mesh is read
back and refitted to prove the turn collapsed.  `RIGID_GUARD` and
`SYMMETRY_GUARD` fail the run if the skull bent or the turn survived.

Run:
  blender -b --python tools/drako_head_yaw.py -- src.glb out.glb \
      [--target world|body] [--angle <deg>] [--pivot auto|head] [--force]

`--target world` (default) faces the head at the app camera, which is what the
reference art shows.  `--target body` aligns the head plane with the fitted
torso plane instead, i.e. 25.6 deg here, and shears the neck much harder for an
8 deg gain on a torso whose own fit residual is 56 mm - that residual is why
world is the default.
"""
import bpy
import sys
import os
import math
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_export                                              # noqa: E402

argv = sys.argv
args = argv[argv.index("--") + 1:] if "--" in argv else []
BOOL = ("force",)
flags, positional = {}, []
i = 0
while i < len(args):
    a = args[i]
    if a.startswith("--"):
        key = a[2:]
        if key in BOOL or i + 1 >= len(args) or args[i + 1].startswith("--"):
            flags[key] = True
            i += 1
        else:
            flags[key] = args[i + 1]
            i += 2
    else:
        positional.append(a)
        i += 1
if len(positional) < 2:
    raise SystemExit("usage: drako_head_yaw.py -- src.glb out.glb [options]")
src, out = os.path.abspath(positional[0]), os.path.abspath(positional[1])
TARGET = str(flags.get("target", "world"))
FORCE = bool(flags.get("force", False))
PIVOT_MODE = str(flags.get("pivot", "auto"))
if TARGET not in ("world", "body"):
    raise SystemExit("BAD_TARGET " + TARGET)

HEAD_FAMILY = ("Head", "Horn_L", "Horn_R", "Lid_L", "Lid_R")
HARD = 0.5          # at or above this head-family weight a vertex is skull
SOFT = 0.02         # at or below this it is body and must not move at all
SUB = 1600          # cloud size for the symmetric-chamfer fit
CHUNK = 200

bpy.ops.wm.read_factory_settings(use_empty=True)
glb_export.import_glb(src)          # 30 fps grid before any key time is read

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
if arm.animation_data:
    for t in arm.animation_data.nla_tracks:
        t.mute = True
    arm.animation_data.action = None
for pb in arm.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
amw = arm.matrix_world.copy()

# ------------------------------------------------------------------ read bind
# ob.data.vertices is the bind table, so the rest pose is read without touching
# a single modifier, and the weight sum comes from each vertex's own group
# elements because Blender 5.2 leaves Mesh.skin_vertices empty on import.
records = []
for ob in bpy.data.objects:
    if ob.type != "MESH" or ob.parent != arm:
        continue
    gw = {vg.index for vg in ob.vertex_groups if vg.name in HEAD_FAMILY}
    n = len(ob.data.vertices)
    co = np.empty((n, 3))
    ob.data.vertices.foreach_get("co", co.reshape(-1))
    mw = np.asarray(ob.matrix_world, dtype=np.float64)
    world = co @ mw[:3, :3].T + mw[:3, 3]
    w = np.zeros(n)
    for idx, v in enumerate(ob.data.vertices):
        s = 0.0
        for g in v.groups:
            if g.group in gw:
                s += g.weight
        w[idx] = s
    records.append((ob, world, w))
    print("BIND %-14s n=%6d  head>=%.2f: %6d  blend: %5d  body: %6d" %
          (ob.name, n, HARD, int((w >= HARD).sum()),
           int(((w > SOFT) & (w < HARD)).sum()), int((w <= SOFT).sum())))
if not records:
    raise SystemExit("NO_SKINNED_MESH")


# ------------------------------------------------------------------- the fit
def _nn(X, Y):
    out = np.empty(len(X))
    for i in range(0, len(X), CHUNK):
        blk = X[i:i + CHUNK]
        out[i:i + CHUNK] = np.sqrt(((blk[:, None, :] -
                                     Y[None, :, :]) ** 2).sum(-1)).min(1)
    return out


def sym_cost(P, theta, pivot):
    """Mean two-way nearest distance between P turned by theta and its mirror."""
    c, s = math.cos(theta), math.sin(theta)
    R = np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])
    A = (P - pivot) @ R.T + pivot
    M = A.copy()
    M[:, 0] = 2.0 * pivot[0] - M[:, 0]
    return 0.5 * (_nn(A, M).mean() + _nn(M, A).mean())


def fit_yaw(P, name):
    """Sagittal plane of a cloud, as the angle its forward axis leans to +X.

    The fit rotates the cloud by theta and scores it against its own x-mirror;
    the minimum sits at theta = -alpha, so the plane angle is the negation of
    the best theta and the correction to apply is the best theta itself.  PCA is
    not used: the torso's longest XY axis is the wingspan.  The same fit gives a
    sharp minimum at 0.0 deg on the adult and baby heads, whose front renders
    are symmetric, so a plane angle away from zero is a real turn.
    """
    rng = np.random.default_rng(11)
    A = P[rng.permutation(len(P))[:SUB]]
    pivot_c = A.mean(0)
    base = sym_cost(A, 0.0, pivot_c)
    coarse = [math.radians(t) for t in range(-30, 35, 5)]
    costs = [sym_cost(A, t, pivot_c) for t in coarse]
    k = int(np.argmin(costs))
    lo, hi = coarse[max(k - 1, 0)], coarse[min(k + 1, len(coarse) - 1)]
    fine = [lo + (hi - lo) * j / 4.0 for j in range(5)]
    fc = [sym_cost(A, t, pivot_c) for t in fine]
    j = int(np.argmin(fc))
    print("FIT %-6s n=%6d  plane=%+.2f deg  chamfer@0=%.4f m  apply=%+.2f deg "
          "-> %.4f m (%.0f%%)" %
          (name, len(P), -math.degrees(fine[j]), base, math.degrees(fine[j]),
           fc[j], 100.0 * (1.0 - fc[j] / base)))
    print("     sweep:", " ".join("%+d:%.4f" % (round(math.degrees(t)), c)
                                  for t, c in zip(coarse, costs)))
    return math.degrees(fine[j]), base, fc[j]


print("== BIND-POSE SAGITTAL FIT (0 deg == facing glTF +Z)")
HEAD_P = np.vstack([c[w >= HARD] for _, c, w in records])
BODY_P = np.vstack([c[w <= SOFT] for _, c, w in records])
BLEND_P = np.vstack([c[(w > SOFT) & (w < HARD)] for _, c, w in records])
th_head, h0, h1 = fit_yaw(HEAD_P, "HEAD")
th_body, b0, b1 = fit_yaw(BODY_P, "BODY")
phi = th_head if TARGET == "world" else th_head - th_body
if "angle" in flags:
    phi = float(flags["angle"])
    print("ANGLE_OVERRIDE -> %+.3f deg" % phi)
print("== HEAD_CORRECTION %+0.2f deg   BODY_CORRECTION %+0.2f deg   TARGET=%s"
      % (th_head, th_body, TARGET))
print("== APPLY %+.3f deg about the vertical axis" % phi)
if abs(phi) < 2.0 and not FORCE:
    raise SystemExit("ALREADY_STRAIGHT %+.3f deg - nothing to do (use --force)"
                     % phi)
if abs(phi) > 40.0 and not FORCE:
    raise SystemExit("ANGLE_IMPLAUSIBLE %+.3f deg - refusing to bend the neck "
                     "that far without --force" % phi)

# ---------------------------------------------------------------- the pivot
head_joint = np.asarray(amw @ arm.data.bones["Head"].head_local,
                        dtype=np.float64)
pivot = (BLEND_P.mean(0)[:2].tolist() + [0.0]) if (PIVOT_MODE == "auto" and
                                                   len(BLEND_P) > 200) else \
    [head_joint[0], head_joint[1], 0.0]
print("PIVOT mode=%s (%+.4f, %+.4f)  head_joint (%+.4f, %+.4f, %+.4f)  "
      "blend band n=%d" % (PIVOT_MODE, pivot[0], pivot[1], head_joint[0],
                           head_joint[1], head_joint[2], len(BLEND_P)))


def turn(P, angles):
    """Rotate world points by `angles` (scalar or per-point) about the pivot Z."""
    a = np.asarray(angles, dtype=np.float64)
    if a.ndim == 0:
        a = np.full(len(P), float(a))
    ca, sa = np.cos(a), np.sin(a)
    dx = P[:, 0] - pivot[0]
    dy = P[:, 1] - pivot[1]
    return np.column_stack([pivot[0] + dx * ca - dy * sa,
                            pivot[1] + dx * sa + dy * ca, P[:, 2]])


def ramp(w):
    """0 at or below SOFT, 1 at or above HARD, smoothstep in between.

    Saturating at HARD is what keeps the skull rigid: every vertex the Head
    family owns turns by exactly the same angle, and only the neck shell that
    is already shared with the body turns by less.
    """
    t = np.clip((w - SOFT) / (HARD - SOFT), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


phi_rad = math.radians(phi)
P4 = Matrix.Translation(Vector(pivot))
R_world = (P4 @ Matrix.Rotation(phi_rad, 4, "Z") @ P4.inverted())
R_arm = amw.inverted() @ R_world @ amw

# ------------------------------------------------------------- deform the mesh
band_shift = []
for ob, world, w in records:
    ang = phi_rad * ramp(w)
    new = turn(world, ang)
    rigid = w >= HARD
    err = 0.0
    if rigid.any():
        err = float(np.abs(new[rigid] - turn(world[rigid], phi_rad)).max())
    blend = (w > SOFT) & (w < HARD)
    if blend.any():
        band_shift.append(np.linalg.norm(new[blend] - world[blend], axis=1))
    mw_inv = np.asarray(ob.matrix_world.inverted(), dtype=np.float64)
    obj = new @ mw_inv[:3, :3].T + mw_inv[:3, 3]
    ob.data.vertices.foreach_set("co", obj.reshape(-1))
    # normals follow their own vertex; the exporter writes the stored custom
    # normals, so leaving them behind would re-light the face by phi degrees
    nrm = []
    for i, v in enumerate(ob.data.vertices):
        a = ang[i]
        ca, sa = math.cos(a), math.sin(a)
        dx = v.normal.x - pivot[0]
        dy = v.normal.y - pivot[1]
        nrm.append(Vector((pivot[0] + dx * ca - dy * sa,
                           pivot[1] + dx * sa + dy * ca, v.normal.z)))
    ob.data.normals_split_custom_set_from_vertices(nrm)
    ob.data.update()
    print("DEFORM %-14s rigid=%6d blend=%6d rigid_err=%.2e m  max_shift=%.4f m" %
          (ob.name, int(rigid.sum()), int(blend.sum()), err,
           float(np.linalg.norm(new - world, axis=1).max())))

if band_shift:
    d = np.concatenate(band_shift)
    print("BLEND_BAND n=%d  shift median=%.4f m  p90=%.4f m  max=%.4f m" %
          (len(d), float(np.median(d)), float(np.percentile(d, 90)),
           float(d.max())))

# --------------------------------------------------------------- deform bones
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones


def under_head(b):
    p = b.parent
    while p is not None:
        if p.name == "Head":
            return True
        p = p.parent
    return False


family = [b.name for b in eb if b.name == "Head" or under_head(b)]
old_m = {b.name: b.matrix.copy() for b in eb}
for name in family:
    b = eb[name]
    if b.use_connect:
        print("UNCONNECT", name)
        b.use_connect = False
    b.matrix = R_arm @ old_m[name]
bpy.ops.object.mode_set(mode="OBJECT")
print("BONES_TURNED", family)

# ------------------------------------------------------------------- guards
worst_t = worst_r = 0.0
for name in family:
    want = R_arm @ old_m[name]
    got = arm.data.bones[name].matrix_local
    worst_t = max(worst_t, (want.translation - got.translation).length)
    worst_r = max(worst_r, abs(math.degrees(
        want.to_quaternion().rotation_difference(got.to_quaternion()).angle)))
rigid_err = 0.0
after_clouds = []
for ob, world, w in records:
    fresh = np.empty((len(ob.data.vertices), 3))
    ob.data.vertices.foreach_get("co", fresh.reshape(-1))
    mw = np.asarray(ob.matrix_world, dtype=np.float64)
    fresh = fresh @ mw[:3, :3].T + mw[:3, 3]
    sel = w >= HARD
    if sel.any():
        rigid_err = max(rigid_err,
                        float(np.abs(fresh[sel] - turn(world[sel],
                                                      phi_rad)).max()))
        after_clouds.append(fresh[sel])
print("RIGID_GUARD skull_max_err=%.2e m  bone_translation_err=%.2e m  "
      "bone_rotation_err=%.4f deg  %s" %
      (rigid_err, worst_t, worst_r,
       "PASS" if rigid_err < 1e-5 and worst_t < 1e-5 and worst_r < 0.01
       else "FAIL"))
if rigid_err >= 1e-5 or worst_t >= 1e-5 or worst_r >= 0.01:
    raise SystemExit("RIGID_GUARD FAIL - the skull bent or a rest is wrong")

th_now, a0, a1 = fit_yaw(np.vstack(after_clouds), "AFTER")
print("SYMMETRY_GUARD head correction %+0.2f -> %+0.2f deg  chamfer %.4f -> "
      "%.4f m  %s" % (th_head, th_now, h0, a0,
                      "PASS" if abs(th_now) < abs(th_head) - 1.0 else "FAIL"))
if abs(th_now) >= abs(th_head) - 1.0:
    raise SystemExit("SYMMETRY_GUARD FAIL - the turn did not collapse")

# --------------------------------------------------------------------- export
if arm.animation_data:
    arm.animation_data.action = None
glb_export.export_glb(out, src=src, arm=arm, tag="HEAD_YAW")
print("HEAD_YAW_WROTE", out, os.path.getsize(out), "bytes  angle=%+.3f deg" % phi)
