"""Body panels for the RB14 mesh: exact cuts along panel lines, and lips.

The RB14 model's bodywork is one continuous skin (split by material, not by
component). build_model.py used to give each whole triangle to a part by its
centroid, so every panel edge was a ragged staircase of triangles. Here the
skin is sliced exactly along smooth cut surfaces (CUTS: planes and curves
placed on the RB14's own panel lines where the model has them -- the nose
joint at y = -1.65, the airbox panel behind the cockpit, the seam behind the
airbox at y = 0.62, the floor junction), triangles straddling a cut are split
with interpolated normals and UVs, and every piece is then assigned by
region() using the same cuts, so each panel edge lies exactly on a cut.

lips() then gives every cut edge a thin inward lip (LIP_DEPTH), on both
panels that meet there, so a removed panel shows a panel edge rather than a
zero-thickness hole.

Coordinates: BeamNG axes, x left (+), y rearward (+), z up; ax = |x|.
"""
import numpy as np

LIP_DEPTH = 0.007            # m, inward depth of the lip on cut edges
LIP_MATS = ("redbull_paint", "redbull_carbon1", "generics")   # decal overlays get none


def _interp(pts, y):
    a = np.asarray(pts, float)
    return np.interp(y, a[:, 0], a[:, 1])


# floor top (just above the floor plate and the diffuser roof), by y
FLOOR_TOP = [(-1.20, 0.145), (-0.45, 0.145), (-0.30, 0.176), (0.0, 0.172), (1.60, 0.210), (2.00, 0.245),
             (2.20, 0.345), (2.45, 0.415)]
# sidepod / engine cover seam height, and the sidepod's inner edge, by y
SIDEPOD_TOP = [(-0.05, 0.70), (0.30, 0.70), (0.45, 0.66), (0.80, 0.57), (1.10, 0.46), (1.40, 0.36), (1.60, 0.30)]
SIDEPOD_IN = [(-0.05, 0.30), (0.40, 0.30), (1.00, 0.24), (1.30, 0.18), (1.60, 0.12)]

# floor edge by the rear tyres: its fences and slots stand above the floor top
Y_FLOOR_EDGE, AX_FLOOR_EDGE, Z_FLOOR_EDGE = 1.20, 0.45, 0.30
# bargeboards (floor): outside the tub, ahead of the sidepods, below this
BARGEBOARD_IN = [(-1.15, 0.25), (-0.60, 0.27), (-0.30, 0.37), (-0.03, 0.37)]
Z_BARGEBOARD = 0.56

Y_NOSE = -1.645              # nose / chassis joint (the RB14's own seam)
Y_FLOOR_FRONT = -1.12        # front of the floor
Y_SIDEPOD = -0.03            # front of the sidepods (inlet lip)
Y_COCKPIT = 0.10             # cockpit rear: halo feet (y <= 0.06) stay on the chassis
Y_SIDEPOD_SPLIT = 0.20       # front (inlet mouth) / rear sidepod panels (where the F4's nodes split them)
Y_AIRBOX = 0.628             # seam behind the airbox (the RB14's own)
AX_AIRBOX = 0.31             # half-width of the airbox panel (the RB14's own)
Z_AIRBOX = 0.50              # airbox panel: above this
Y_SIDEPOD_END = 1.60         # sidepods end at the coke bottle
AX_ENDPLATE_F = 0.83         # front wing / endplate joint

# Halo mounts (round 19 c): the body skin rises into a plinth under the halo's
# centre pillar and into a nozzle around each rear leg (with an open socket
# for it). They go with the halo part; without the halo, halo_cover()
# makes the flush covers that replace them.
HALO_FRONT = dict(ax=0.03, y=(-0.80, -0.53))                  # plinth: above the chassis deck
DECK_Z = lambda P: 0.6889 + 0.341 * P[..., 0] ** 2             # chassis deck there (fit, rms 1.6 mm)
HALO_FRONT_Z = 0.003                                            # above the deck's own +-1.6 mm
HALO_REAR = dict(ax=(0.262, 0.335), y=(0.0, 0.30))               # nozzles: above the shoulder deck
# the shoulder deck beside the cockpit (top of the cockpit-side box, which
# the halo's leg fairing rises out of), by y
SHOULDER_DECK = [(0.00, 0.758), (0.02, 0.771), (0.04, 0.780), (0.06, 0.785), (0.10, 0.787), (0.14, 0.790),
                 (0.20, 0.792), (0.30, 0.794)]
HALO_REAR_Z = 0.002

# name -> f(P) for P (..., 3); a cut is the surface f = 0
CUTS = {
    "nose": lambda P: P[..., 1] - Y_NOSE,
    "floor_front": lambda P: P[..., 1] - Y_FLOOR_FRONT,
    "floor": lambda P: P[..., 2] - _interp(FLOOR_TOP, P[..., 1]),
    "sidepod_front": lambda P: P[..., 1] - Y_SIDEPOD,
    "cockpit": lambda P: P[..., 1] - Y_COCKPIT,
    "sidepod_top": lambda P: P[..., 2] - _interp(SIDEPOD_TOP, P[..., 1]),
    "sidepod_in": lambda P: np.abs(P[..., 0]) - _interp(SIDEPOD_IN, P[..., 1]),
    "sidepod_split": lambda P: P[..., 1] - Y_SIDEPOD_SPLIT,
    "airbox_rear": lambda P: P[..., 1] - Y_AIRBOX,
    "airbox_side": lambda P: np.abs(P[..., 0]) - AX_AIRBOX,
    "airbox_low": lambda P: P[..., 2] - Z_AIRBOX,
    "sidepod_end": lambda P: P[..., 1] - Y_SIDEPOD_END,
    "halo_f_x": lambda P: np.abs(P[..., 0]) - HALO_FRONT["ax"],
    "halo_f_y0": lambda P: P[..., 1] - HALO_FRONT["y"][0],
    "halo_f_y1": lambda P: P[..., 1] - HALO_FRONT["y"][1],
    "halo_f_z": lambda P: P[..., 2] - DECK_Z(P) - HALO_FRONT_Z,
    "halo_r_ax0": lambda P: np.abs(P[..., 0]) - HALO_REAR["ax"][0],
    "halo_r_ax1": lambda P: np.abs(P[..., 0]) - HALO_REAR["ax"][1],
    "halo_r_y0": lambda P: P[..., 1] - HALO_REAR["y"][0],
    "halo_r_y1": lambda P: P[..., 1] - HALO_REAR["y"][1],
    "halo_r_z": lambda P: P[..., 2] - _interp(SHOULDER_DECK, P[..., 1]) - HALO_REAR_Z,
    "floor_edge_y": lambda P: P[..., 1] - Y_FLOOR_EDGE,
    "floor_edge_ax": lambda P: np.abs(P[..., 0]) - AX_FLOOR_EDGE,
    "floor_edge_z": lambda P: P[..., 2] - Z_FLOOR_EDGE,
    "bargeboard_in": lambda P: np.abs(P[..., 0]) - _interp(BARGEBOARD_IN, P[..., 1]),
    "bargeboard_top": lambda P: P[..., 2] - Z_BARGEBOARD,
}
WING_F_CUTS = {"endplate_F": lambda P: np.abs(P[..., 0]) - AX_ENDPLATE_F}


def side(x):
    return "L" if x >= 0 else "R"


def region(c):
    """Body panel for a (sliced) skin triangle with centroid c."""
    x, y, z = c
    ax = abs(x)
    if halo_mount(c):
        return "redbull_halo"
    if y < Y_NOSE:
        return "redbull_nose"
    if y > Y_FLOOR_FRONT and z < _interp(FLOOR_TOP, y):
        return "redbull_floor"
    if y > Y_FLOOR_EDGE and ax > AX_FLOOR_EDGE and z < Z_FLOOR_EDGE:
        return "redbull_floor"
    if Y_FLOOR_FRONT < y < Y_SIDEPOD and ax > _interp(BARGEBOARD_IN, y) and z < Z_BARGEBOARD:
        return "redbull_floor"
    sidepod = (Y_SIDEPOD < y < Y_SIDEPOD_END and ax > _interp(SIDEPOD_IN, y)
               and z < _interp(SIDEPOD_TOP, y))
    if sidepod:
        return ("redbull_sidepod_F" if y < Y_SIDEPOD_SPLIT else "redbull_sidepod_R") + side(x)
    if y < Y_COCKPIT:
        return "redbull_monocoque"
    if y < Y_AIRBOX and ax < AX_AIRBOX and z > Z_AIRBOX:
        return "redbull_rollhoop"
    return "redbull_enginecover"


def halo_mount(c):
    x, y, z = c
    ax = abs(x)
    if ax < HALO_FRONT["ax"] and HALO_FRONT["y"][0] < y < HALO_FRONT["y"][1] and z > DECK_Z(np.asarray(c)) + HALO_FRONT_Z:
        return "front"
    if (HALO_REAR["ax"][0] < ax < HALO_REAR["ax"][1] and HALO_REAR["y"][0] < y < HALO_REAR["y"][1]
            and z > _interp(SHOULDER_DECK, y) + HALO_REAR_Z):
        return "rear"
    return None


def halo_cover(mounts):
    """The no-halo covers over the halo mounts ({material: (P, N, U)} of the
    mount skin, decals and details left out), as clean painted surfaces:

    front -- a flat patch over the plinth's footprint, level with the deck;
    rear  -- per side the shoulder deck (the cockpit-side box's top)
             carried on flat over the leg fairing's footprint, out to the
             fairing's outer wall, which stays up to deck height.

    UVs come from the nearest mount vertex, so the livery carries on."""
    P = np.concatenate([v[0] for m, v in mounts.items() if m == "redbull_paint"])
    U = np.concatenate([v[2] for m, v in mounts.items() if m == "redbull_paint"])
    Q, UQ = P.reshape(-1, 3), U.reshape(-1, 2)
    tris = []

    def uv_at(p):
        d = (Q[:, 0] - p[0]) ** 2 + (Q[:, 1] - p[1]) ** 2 + 0.25 * (Q[:, 2] - p[2]) ** 2
        return UQ[int(np.argmin(d))]

    def grid(Z, X, Y, flip):
        """triangles of a heightfield grid, facing up"""
        for i in range(Z.shape[0] - 1):
            for j in range(Z.shape[1] - 1):
                a, b = (X[i, j], Y[i, j], Z[i, j]), (X[i + 1, j], Y[i + 1, j], Z[i + 1, j])
                c, d = (X[i + 1, j + 1], Y[i + 1, j + 1], Z[i + 1, j + 1]), (X[i, j + 1], Y[i, j + 1], Z[i, j + 1])
                for t in ((a, b, c), (a, c, d)):
                    t = np.array(t)
                    n = np.cross(t[1] - t[0], t[2] - t[0])
                    if n[2] < 0:
                        t = t[[0, 2, 1]]
                    tris.append(t)

    # front: flat over the plinth footprint
    fy0, fy1 = HALO_FRONT["y"]
    fx = HALO_FRONT["ax"]
    X, Y = np.meshgrid(np.linspace(-fx, fx, 5), np.linspace(fy0, fy1, 14), indexing="ij")
    Z = DECK_Z(np.stack([X, Y, 0 * X], -1)) + HALO_FRONT_Z + 0.0004
    grid(Z, X, Y, False)
    # rear: the shoulder deck carried on flat over each fairing's footprint,
    # from the cockpit side out to the fairing's outer wall (which stays, up
    # to deck height)
    ax0 = HALO_REAR["ax"][0]
    deck = lambda y: _interp(SHOULDER_DECK, y) + HALO_REAR_Z + 0.0004
    for side in (-1, 1):
        q = Q[(np.sign(Q[:, 0]) == side) & (np.abs(Q[:, 0]) > 0.2)]
        if not len(q):
            continue
        # the footprint's outline: where the cut at deck height runs
        cut = q[np.abs(q[:, 2] - (_interp(SHOULDER_DECK, q[:, 1]) + HALO_REAR_Z)) < 3e-4]
        cut = cut[np.abs(cut[:, 0]) > ax0 + 0.01]               # the outer side (not the inner cut)
        if not len(cut):
            continue
        yb = np.linspace(cut[:, 1].min(), cut[:, 1].max(), 40)
        near = [np.abs(cut[np.abs(cut[:, 1] - b) < 0.006, 0]) for b in yb]
        out = np.array([v.max() if len(v) else np.nan for v in near])
        ok = ~np.isnan(out)
        out = np.interp(yb, yb[ok], out[ok])
        out = np.maximum(out + 0.003, ax0 + 0.004)              # a little onto the wall top
        A = np.array([np.linspace(ax0, o, 6) for o in out]).T          # (6, len(yb))
        Y = np.repeat(yb[None], 6, 0)
        grid(deck(Y), side * A, Y, side < 0)
    T = np.array(tris)
    n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    N = np.repeat(n[:, None], 3, 1)
    UV = np.array([[uv_at(p) for p in t] for t in T])
    return {"redbull_paint": (T, N, UV)}


def region_wing_F(c):
    return "redbull_endplate_F" + side(c[0]) if abs(c[0]) > AX_ENDPLATE_F else "redbull_wing_F"


# ------------------------------------------------------------ slicing

def slice_soup(P, N, U, f):
    """Split the triangles of a soup (P, N, U: (m, 3, k) corner arrays) that
    straddle f = 0, so no triangle crosses it. Winding is kept."""
    d = f(P)
    d = np.where(np.abs(d) < 1e-9, 1e-9, d)
    pos = d > 0
    npos = pos.sum(1)
    cross = (npos == 1) | (npos == 2)
    if not cross.any():
        return P, N, U
    keep = ~cross
    outP, outN, outU = [P[keep]], [N[keep]], [U[keep]]
    idx = np.nonzero(cross)[0]
    newP, newN, newU = [], [], []
    for t in idx:
        dd = d[t]
        # rotate corners so that corner 0 is the lone one (other side)
        if npos[t] == 1:
            lone = int(np.nonzero(pos[t])[0][0])
        else:
            lone = int(np.nonzero(~pos[t])[0][0])
        order = [lone, (lone + 1) % 3, (lone + 2) % 3]
        p, n, u, e = P[t][order], N[t][order], U[t][order], dd[order]
        w1 = e[0] / (e[0] - e[1])
        w2 = e[0] / (e[0] - e[2])
        p1, p2 = p[0] + w1 * (p[1] - p[0]), p[0] + w2 * (p[2] - p[0])
        n1, n2 = n[0] + w1 * (n[1] - n[0]), n[0] + w2 * (n[2] - n[0])
        u1, u2 = u[0] + w1 * (u[1] - u[0]), u[0] + w2 * (u[2] - u[0])
        # lone corner's triangle, then the quad on the other side as two
        newP += [[p[0], p1, p2], [p1, p[1], p[2]], [p1, p[2], p2]]
        newN += [[n[0], n1, n2], [n1, n[1], n[2]], [n1, n[2], n2]]
        newU += [[u[0], u1, u2], [u1, u[1], u[2]], [u1, u[2], u2]]
    newN = np.array(newN)
    newN /= np.maximum(np.linalg.norm(newN, axis=2, keepdims=True), 1e-12)
    outP.append(np.array(newP))
    outN.append(newN)
    outU.append(np.array(newU))
    return np.concatenate(outP), np.concatenate(outN), np.concatenate(outU)


def slice_all(P, N, U, cuts, region=None):
    """Slice along every cut; with region, only the triangles a panel
    boundary runs through (corners or centroid in different panels)."""
    if region is not None:
        cent = P.mean(axis=1)
        tag = np.array([[region(c) for c in t] + [region(m)] for t, m in zip(P, cent)], dtype=object)
        edge = (tag != tag[:, :1]).any(axis=1)
        keepP, keepN, keepU = P[~edge], N[~edge], U[~edge]
        P, N, U = slice_all(P[edge], N[edge], U[edge], cuts)
        return np.concatenate([keepP, P]), np.concatenate([keepN, N]), np.concatenate([keepU, U])
    for f in cuts.values():
        P, N, U = slice_soup(P, N, U, f)
    # drop slivers left by cuts through a corner
    a = np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)
    ok = a > 1e-12
    return P[ok], N[ok], U[ok]


# ------------------------------------------------------------ lips

def lips(soups, depth=LIP_DEPTH):
    """soups: {part: {material: (P, N, U)}}. Returns {part: {"redbull_carbon1":
    (P, N, U)}}: for every edge where a triangle of one part meets one of
    another (the cuts), a strip from the edge inward along the surface
    normals, on each of the parts (the carbon material is double-sided)."""
    key = lambda v: tuple(np.round(v, 5))
    edges = {}
    for part, mats in soups.items():
        for mat, (P, N, U) in mats.items():
            if mat not in LIP_MATS:
                continue
            K = np.round(P, 5)
            for t in range(len(P)):
                for a, b in ((0, 1), (1, 2), (2, 0)):
                    ka, kb = tuple(K[t, a]), tuple(K[t, b])
                    edges.setdefault((min(ka, kb), max(ka, kb)), []).append((part, mat, t, a, b))
    out = {}
    for users in edges.values():
        parts = {u[0] for u in users}
        if len(parts) < 2 or "redbull_halo" in parts:
            continue                # halo mounts: covered by the halo or by its no-halo covers
        for part, mat, t, a, b in users:
            P, N, U = soups[part][mat]
            pa, pb = P[t, a], P[t, b]
            qa, qb = pa - depth * N[t, a], pb - depth * N[t, b]
            ua, ub = U[t, a], U[t, b]
            o = out.setdefault(part, ([], [], []))
            for tri, uv in (([pa, pb, qb], [ua, ub, ub]), ([pa, qb, qa], [ua, ub, ua])):
                g = np.cross(tri[1] - tri[0], tri[2] - tri[0])
                gl = np.linalg.norm(g)
                if gl < 1e-12:
                    continue
                g = g / gl
                o[0].append(tri)            # one face: rb14_carbon is double-sided
                o[1].append([g, g, g])
                o[2].append(uv)
    return {p: {"redbull_carbon1": tuple(np.array(a) for a in v)} for p, v in out.items()}
