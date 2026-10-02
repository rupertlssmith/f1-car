#!/usr/bin/env python3
"""Build the redbull mod's meshes from the RB14 model.

    python3 tools/rb14/build_model.py [--preview DIR]

Reads   redbull/source/rb14.glb              the RB14 (visible car)
        vehicles/fr04/F4.dae                 the original F4 (hidden internals)
Writes  vehicles/redbull/redbull.dae         body, aero, suspension, cockpit
        vehicles/redbull/rb14.materials.json + rb14_*.png   its materials
        vehicles/common/redbull_wheels/redbull_wheels.dae   rims and tyres
        vehicles/common/redbull_wheels/rb14_wheels.materials.json + textures

The RB14 comes as one mesh split by material, not by component. Loose pieces
that are one component (suspension members, uprights, wing elements, the
DRS flap, the exhaust...) go to their part whole (classify_piece); the
continuous body skin is sliced exactly along the panel lines and given a
lip on every cut edge (panels.py). Part names are the F4's flexbody/prop
names, so the existing jbeam picks them up unchanged: nose and wings still
break off, sidepods and engine cover are separate panels, and so on.

The F4's internals that the RB14 model does not have (engine, gearbox,
radiators, springs, anti-roll bars, pedals, steering rack...) are kept, moved
through the same F4->RB14 map as the jbeam (fitmap.py), so they sit on their
re-fitted nodes inside the RB14 body.

--preview DIR also writes DIR/parts.glb (each part a flat colour) and
DIR/car.glb (textured, wheels in place) for tools/rb14/render.py.
"""
import argparse
import colorsys
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import dae  # noqa: E402
import fitmap  # noqa: E402
import glb  # noqa: E402
import materials  # noqa: E402
import panels  # noqa: E402

SRC_GLB = "redbull/source/rb14.glb"
SRC_F4 = "vehicles/fr04/F4.dae"
OUT_CAR = "vehicles/redbull/redbull.dae"
OUT_WHEELS = "vehicles/common/redbull_wheels/redbull_wheels.dae"

# The model is 6.6 mm off-centre in x (wheel centres at +0.786/-0.799).
X_SHIFT = 0.0066
WHEEL_CENTRE = {"F": np.array([0.7925, -1.5247, 0.3377]), "R": np.array([0.789, 2.03, 0.3347])}

# Wing pivots: the jbeam places these three flexbodies with "pos" (their
# pivot, so the wing-angle setting can rotate them); the mesh is written
# relative to the pivot. Values are the F4 pivots moved through fitmap.
WING_PIVOT_F4 = {"redbull_wing_F": (0.0, -1.9694, 0.1382),
                 "redbull_wing_R": (0.0, 2.1941, 0.8839),
                 "redbull_wing_B": (0.0, 1.9247, 0.4955),
                 "redbull_wing_R_flap": (0.0, 2.1941, 0.8839)}
# Steering wheel prop: rotates about its node origin.
STEER_ORIGIN = np.array([0.0, -0.366, 0.585])

STEER_MATS = {"toro_rosso_steeringwheel", "sw_decals", "toro_rosso_steeringwheel_detail",
              "toro_rosso_carbon4", "toro_rosso_carbon4.001", "DRS", "driver_number", "LCD",
              "CLEARLED", "CLEARLED_PRE", "kers_brown", "kers_green", "BLACK"}
FIXED_MATS = {"glass.001": "redbull_windshield", "redbull_mirror_left": "redbull_mirror_L",
              "redbull_mirror_right": "redbull_mirror_R", "halo": "redbull_halo",
              "rear_light": "redbull_rainlight", "generics_cockpit": "redbull_seat",
              "redbull_carbon3": "redbull_headrest"}

# F4 meshes kept as internals: parts the RB14 model lacks that sit fully
# inside its bodywork (checked with envelope.py), plus the driveshafts,
# which are exposed on the real car too. They show when panels come off.
# Everything else of the F4 is replaced by the RB14 or dropped - notably the
# inboard front suspension, radiators and exhaust, which would poke through
# the RB14's narrower nose and sidepods.
F4_KEEP = {"redbull_engine", "redbull_intake", "redbull_transaxle", "redbull_fueltank",
           "redbull_rocker_RL", "redbull_rocker_RR", "redbull_spring_RL", "redbull_spring_RR",
           "redbull_shockbottom_RL", "redbull_shockbottom_RR", "redbull_shocktop_RL", "redbull_shocktop_RR",
           "redbull_rollbar_R", "redbull_rollbar_R_links", "redbull_rollbar_R_mounts",
           "redbull_steeringrack", "redbull_steeringshaft_a", "redbull_steeringshaft_b", "redbull_brakecyls",
           "redbull_pedal_gas", "redbull_pedal_brake", "redbull_pedal_clutch", "redbull_pedallink_brake",
           "redbull_pedallink_clutch", "redbull_halfshafts", "redbull_pulley1", "redbull_pulley2",
           "redbull_pulley3", "redbull_pulley4"}


# ------------------------------------------------------------------ rules

def side(x):
    return "L" if x >= 0 else "R"


def classify_piece(mat, lo, hi, pc):
    """Part for a whole loose piece, or None to fall through to per-face
    rules. lo/hi/pc: piece bounds and centroid (x already centred)."""
    alo, ahi = min(abs(lo[0]), abs(hi[0])) if lo[0] * hi[0] > 0 else 0.0, max(abs(lo[0]), abs(hi[0]))
    span = hi - lo
    # rear wing (round 19): the DRS flap, the main plane and its centre pod,
    # and the endplates' lower strakes are separate pieces in the RB14
    if lo[1] >= 2.39 and lo[2] >= 0.84 and hi[2] <= 0.99 and ahi <= 0.47:
        return "redbull_wing_R_flap"
    if lo[1] >= 2.14 and lo[2] >= 0.76 and hi[1] <= 2.46 and hi[2] <= 0.90:
        return "redbull_wing_R"
    if lo[1] >= 2.14 and lo[2] >= 0.76 and ahi <= 0.02:
        return "redbull_wing_R"                     # DRS actuator pod
    if alo >= 0.38 and ahi <= 0.44 and lo[1] >= 2.30 and hi[2] < 0.60:
        return "redbull_endplate_R" + side(pc[0])
    # exhaust tailpipe and wastegate pipes
    if mat == "redbull_detail" and ahi <= 0.11 and lo[1] >= 1.2 and hi[1] <= 2.3 and lo[2] >= 0.5 and hi[2] <= 0.68:
        return "redbull_exhaust"
    # front wing pylons belong to the nose
    if ahi <= 0.08 and hi[1] <= -1.70 and lo[2] >= 0.15 and hi[2] <= 0.42 and lo[1] >= -2.6 and span[1] > 0.3:
        return "redbull_nose"
    # bargeboards and the vanes above them (floor)
    if -1.15 <= lo[1] and hi[1] <= -0.30 and alo >= 0.20 and mat == "redbull_carbon1" and hi[2] <= 0.56:
        return "redbull_floor"
    for axle, cy in (("F", -1.5247), ("R", 2.03)):
        # uprights, brake ducts: inside the wheel
        if alo > 0.40 and abs(lo[1] - cy) < 0.36 and abs(hi[1] - cy) < 0.36 and hi[2] < 0.58:
            return f"redbull_hubs_{axle}"
    # front suspension members reach from the chassis out to the upright
    if -1.85 < lo[1] and hi[1] < -1.05 and ahi > 0.45 and span[0] > 0.2 and hi[2] < 0.65 and alo > 0.04:
        if span[1] < 0.14 and pc[1] < -1.53 and pc[2] < 0.40:
            return "redbull_tierod_" + side(pc[0])
        if span[2] > 0.18:
            return "redbull_pushrod_F"
        return "redbull_arm_upper_F" if pc[2] > 0.44 else "redbull_arm_lower_F"
    # rear wing endplates
    if alo > 0.33 and ahi < 0.50 and lo[1] > 2.0 and hi[2] > 0.70:
        return "redbull_endplate_R" + side(pc[0])
    # rear suspension members
    if 1.55 < lo[1] and hi[1] < 2.45 and ahi > 0.40 and span[0] > 0.2 and hi[2] < 0.60:
        if pc[2] > 0.45:
            return "redbull_arm_upper_R"
        if span[2] > 0.15:
            return "redbull_pushrod_R"
        return "redbull_arm_lower_R"
    # rear crash structure
    if ahi < 0.10 and lo[1] > 1.9 and hi[2] < 0.70:
        return "redbull_crashbox"
    # nose tip ("thumb"), above the front wing
    if ahi < 0.20 and lo[1] > -2.60 and hi[1] < -1.9 and lo[2] > 0.09:
        return "redbull_nose"
    # mirror housings
    if alo > 0.26 and ahi < 0.57 and lo[1] > -0.38 and hi[1] < -0.23 and lo[2] > 0.60:
        return "redbull_mirror_" + side(pc[0])
    return None


# ------------------------------------------------------------ RB14 split

def pieces_of(pos, tri):
    """Connected-component label per triangle, joining vertices that share a
    position (the model splits vertices at UV seams)."""
    _, inv = np.unique(np.round(pos, 5), axis=0, return_inverse=True)
    inv = inv.ravel()
    f = inv[tri]
    parent = np.arange(inv.max() + 1)

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root

    for a, b, c in f:
        ra, rb, rc = find(a), find(b), find(c)
        if rb != ra:
            parent[rb] = ra
        if rc != ra and rc != rb:
            parent[rc] = ra
    roots = np.array([find(a) for a in range(len(parent))])
    return roots[f[:, 0]]


def is_front_wing(lo, hi):
    """Loose pieces of the front wing assembly (elements and endplates)."""
    alo = min(abs(lo[0]), abs(hi[0])) if lo[0] * hi[0] > 0 else 0.0
    ahi = max(abs(lo[0]), abs(hi[0]))
    return hi[1] <= -1.90 and hi[2] <= 0.34 and (ahi >= 0.30 or alo >= 0.30)


def split_rb14(prims):
    """{part: {material: (pos, nrm, uv) corner arrays}} for the RB14.

    Loose pieces that are one component go to their part whole
    (classify_piece). The rest -- the continuous body skin and the front
    wing assembly -- is sliced exactly along the panel cuts (panels.py) and
    assigned by region, and every cut edge gets a lip."""
    soups = {}

    def add(part, mat, P, N, U):
        soups.setdefault(part, {}).setdefault(mat, []).append((P, N, U))

    for p in prims:
        mat = p["material"]
        pos = p["pos"] + np.array([X_SHIFT, 0, 0])
        tri = p["tri"]
        uv_all = p["uv"].copy()
        uv_all[:, 1] = 1.0 - uv_all[:, 1]                # glTF -> Collada v
        P, N, U = pos[tri], p["nrm"][tri], uv_all[tri]
        cent = P.mean(axis=1)
        if mat in ("discs",):
            continue                                    # base-game brake meshes instead
        if mat in ("Tyre_thread", "tyre_side", "redbull_wheel_hub"):
            kind = "rim" if mat == "redbull_wheel_hub" else "tyre"
            parts = np.array([f"{kind}_{'F' if c[1] < 0.25 else 'R'}" if c[0] > 0 else "" for c in cent])
            for part in set(parts) - {""}:
                sel = parts == part
                add(part, mat, P[sel], N[sel], U[sel])
            continue
        if mat in STEER_MATS:
            add("redbull_steer", mat, P, N, U)
            continue
        if mat in FIXED_MATS:
            add(FIXED_MATS[mat], mat, P, N, U)
            continue
        labels = pieces_of(pos, tri)
        skin, wing = [], []
        for lab in np.unique(labels):
            sel = labels == lab
            pts = P[sel].reshape(-1, 3)
            lo, hi = pts.min(0), pts.max(0)
            part = classify_piece(mat, lo, hi, pts.mean(0))
            if part:
                add(part, mat, P[sel], N[sel], U[sel])
            elif is_front_wing(lo, hi):
                wing.append(sel)
            else:
                skin.append(sel)
        for sels, cuts, region in ((skin, panels.CUTS, panels.region), (wing, panels.WING_F_CUTS, panels.region_wing_F)):
            if not sels:
                continue
            sel = np.any(sels, axis=0)
            sp, sn, su = panels.slice_all(P[sel], N[sel], U[sel], cuts, region)
            parts = np.array([region(c) for c in sp.mean(axis=1)], dtype=object)
            for part in set(parts):
                s2 = parts == part
                add(part, mat, sp[s2], sn[s2], su[s2])
    soups = {part: {m: tuple(np.concatenate(a) for a in zip(*chunks)) for m, chunks in mats.items()}
             for part, mats in soups.items()}
    body = {part: mats for part, mats in soups.items() if not part.startswith(("rim_", "tyre_"))}
    for part, mats in panels.lips(body).items():
        for m, (P, N, U) in mats.items():
            if m in soups[part]:
                soups[part][m] = tuple(np.concatenate([a, b]) for a, b in zip(soups[part][m], (P, N, U)))
            else:
                soups[part][m] = (P, N, U)
    # corner arrays -> flat per-corner arrays
    return {part: {m: (P.reshape(-1, 3), N.reshape(-1, 3), U.reshape(-1, 2)) for m, (P, N, U) in mats.items()}
            for part, mats in soups.items()}


def to_mesh(name, mats, origin=np.zeros(3), node_origin=False):
    """Mesh with vertices relative to origin. node_origin=True puts origin in
    the node matrix (props rotate about their node origin); otherwise the
    node is identity and the jbeam's flexbody "pos" places the mesh (wing
    pivots), as in the F4."""
    by_mat = {}
    for mat, (pos, nrm, uv) in mats.items():
        bm = materials.NAMES[mat]
        if bm == "redbull_screen":
            # the LCD's own UVs point at a 16 px black texture; lay a fresh
            # 0..1 map over it so the dashboard HTML display fits the screen
            # (as the driver sees it: car +x is the driver's left)
            x, z = pos[:, 0], pos[:, 2]
            uv = np.c_[(x.max() - x) / np.ptp(x), (z - z.min()) / np.ptp(z)]
        by_mat.setdefault(bm, []).append((pos, nrm, uv))
    prims = []
    for bm, chunks in sorted(by_mat.items()):
        pos, nrm, uv = (np.concatenate(a) for a in zip(*chunks))
        prims.append(dae.Prim(bm, {("POSITION", 0): pos - origin, ("NORMAL", 0): nrm, ("TEXCOORD", 0): uv}))
    m = np.eye(4)
    if node_origin:
        m[:3, 3] = origin
    return dae.Mesh(name, m, prims)


# ------------------------------------------------------- F4 internals

def map_f4_mesh(m):
    """Move one F4 mesh through the F4->RB14 map. Positions are mapped in
    world space; normals follow the local Jacobian (inverse transpose)."""
    origin = m.matrix[:3, 3]
    new_origin = np.array(fitmap.map_point(origin))
    rot = m.matrix[:3, :3]
    prims = []
    for p in m.prims:
        attrs = dict(p.attrs)
        w = p.attrs[("POSITION", 0)] @ rot.T + origin
        wm = fitmap.map_points(w)
        attrs[("POSITION", 0)] = (wm - new_origin) @ np.linalg.inv(rot).T
        if ("NORMAL", 0) in p.attrs:
            n = p.attrs[("NORMAL", 0)] @ rot.T
            h = 1e-3
            jac = np.stack([(fitmap.map_points(w + h * e) - fitmap.map_points(w - h * e)) / (2 * h)
                            for e in np.eye(3)], axis=2)          # (n, 3 out, 3 in)
            nt = np.einsum("nij,nj->ni", np.linalg.inv(jac).transpose(0, 2, 1), n)
            nt /= np.maximum(np.linalg.norm(nt, axis=1, keepdims=True), 1e-12)
            attrs[("NORMAL", 0)] = nt @ np.linalg.inv(rot).T
        prims.append(dae.Prim(p.material.replace("fr04", "redbull"), attrs))
    mat = m.matrix.copy()
    mat[:3, 3] = new_origin
    return dae.Mesh(m.name.replace("fr04", "redbull"), mat, prims)


# ------------------------------------------------------------- preview

def write_preview(path, meshes, colour_by_part, wheel_meshes=()):
    import trimesh
    scene = trimesh.Scene()
    for i, m in enumerate(meshes):
        tris = []
        for p in m.prims:
            w = p.attrs[("POSITION", 0)] @ m.matrix[:3, :3].T + m.matrix[:3, 3]
            tris.append(w)
        if not tris:
            continue
        v = np.concatenate(tris)
        f = np.arange(len(v)).reshape(-1, 3)
        tm = trimesh.Trimesh(v, f, process=False)
        if colour_by_part:
            h = (i * 0.61803) % 1.0
            r, g, b = colorsys.hsv_to_rgb(h, 0.65, 0.95)
            tm.visual.vertex_colors = np.tile([int(r * 255), int(g * 255), int(b * 255), 255], (len(v), 1))
        scene.add_geometry(tm, node_name=m.name)
    for m, offset in wheel_meshes:
        v = np.concatenate([p.attrs[("POSITION", 0)] for p in m.prims]) + offset
        tm = trimesh.Trimesh(v, np.arange(len(v)).reshape(-1, 3), process=False)
        tm.visual.vertex_colors = np.tile([40, 40, 40, 255], (len(v), 1))
        scene.add_geometry(tm, node_name=m.name + str(offset[1]))
    # trimesh writes glTF Y-up; convert back from BeamNG axes
    scene.apply_transform(np.array([[1, 0, 0, 0], [0, 0, 1, 0], [0, -1, 0, 0], [0, 0, 0, 1]], float))
    scene.export(path)


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preview", help="directory for preview .glb files")
    args = ap.parse_args()
    os.chdir(REPO)

    prims, images, _ = glb.load(SRC_GLB)
    parts = split_rb14(prims)

    car = []
    for name, mats in sorted(parts.items()):
        if name.startswith(("rim_", "tyre_")):
            continue
        if name in WING_PIVOT_F4:
            car.append(to_mesh(name, mats, np.array(fitmap.map_point(WING_PIVOT_F4[name]))))
        elif name == "redbull_steer":
            car.append(to_mesh(name, mats, STEER_ORIGIN, node_origin=True))
        else:
            car.append(to_mesh(name, mats))
    rb_names = {m.name for m in car}

    f4 = {m.name.replace("fr04", "redbull"): m for m in dae.read(SRC_F4)}
    for name in sorted(F4_KEEP):
        if name in rb_names:
            continue
        car.append(map_f4_mesh(f4[name]))
    dae.write(OUT_CAR, car)

    # wheels: left-side RB14 rim/tyre per axle, centred on the wheel, named
    # like the F4 meshes the wheel jbeam refers to
    wheels = []
    names = {"rim_F": ["redbull_wheel_01a_13x8", "redbull_wheel_01b_13x8"],
             "rim_R": ["redbull_wheel_01a_13x10", "redbull_wheel_01b_13x10"],
             "tyre_F": ["redbull_tire_01a_F", "redbull_tire_01b_F"],
             "tyre_R": ["redbull_tire_01a_R", "redbull_tire_01b_RL", "redbull_tire_01b_RR"]}
    for part, outs in names.items():
        axle = part[-1]
        centre = WHEEL_CENTRE[axle] + np.array([X_SHIFT * 0, 0, 0])
        for out in outs:
            mats = parts[part]
            prims_ = []
            by_mat = {}
            for mat, chunk in mats.items():
                mname = materials.NAMES[mat] + ("_alt" if "_01b" in out else "")  # black rims / wet tyres
                by_mat.setdefault(mname, []).append(chunk)
            for mname, chunks in sorted(by_mat.items()):
                pos, nrm, uv = (np.concatenate(a) for a in zip(*chunks))
                prims_.append(dae.Prim(mname, {("POSITION", 0): pos - centre, ("NORMAL", 0): nrm,
                                               ("TEXCOORD", 0): uv}))
            wheels.append(dae.Mesh(out, np.eye(4), prims_))
    dae.write(OUT_WHEELS, wheels)
    materials.write(images, os.path.dirname(OUT_CAR), os.path.dirname(OUT_WHEELS))

    ntri = sum(p.ntris for m in car for p in m.prims)
    print(f"wrote {OUT_CAR}: {len(car)} meshes, {ntri} triangles")
    print(f"wrote {OUT_WHEELS}: {len(wheels)} meshes")
    for m in car:
        if m.name in rb_names:
            print(f"  {m.name:28s} {sum(p.ntris for p in m.prims):6d} tris  {sorted(p.material for p in m.prims)}")

    if args.preview:
        os.makedirs(args.preview, exist_ok=True)
        wl = [(w, WHEEL_CENTRE["F" if "13x8" in w.name or w.name.endswith("_F") else "R"] * s)
              for w in wheels if w.name in ("redbull_wheel_01a_13x8", "redbull_wheel_01a_13x10",
                                             "redbull_tire_01a_F", "redbull_tire_01a_R")
              for s in (np.array([1, 1, 1]),)]
        write_preview(os.path.join(args.preview, "parts.glb"), [m for m in car if m.name in rb_names], True, wl)
        write_preview(os.path.join(args.preview, "internals.glb"), [m for m in car if m.name not in rb_names], True)


if __name__ == "__main__":
    main()
