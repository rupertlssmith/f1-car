#!/usr/bin/env python3
"""Setup sheet for the redbull mod, computed offline from its jbeam.

    python3 tools/rb14/setup_report.py [--config baseline] [--json out.json]

BeamNG can't run here, so this reads the vehicle the way the game would
(default slot tree + a configuration's parts and variables) and estimates
what matters for handling:

  mass       total, per axle (weight distribution), CoG height; node weights,
             the nodes pressureWheels generate, fuel
  suspension a linear spring-network solve: every beam is a spring of its
             beamSpring, every torsionbar an angular spring; chassis nodes
             held, loads applied at the wheel axle nodes -> wheel rate,
             heave rate and roll rate per axle, ride frequencies
  aero       flat-plate estimate over the aero triangles: downforce and drag
             by axle at given speeds. BeamNG's exact aero model is not public,
             so these are estimates; drag is calibrated (see AERO_K)
  powertrain torque/power curve, gearing, speed per gear, and a straight-line
             launch simulation (traction-limited) for 0-100 / 0-200 / top
  grip       BeamNG's tyre load sensitivity (noLoadCoef/fullLoadCoef/slope)
             -> lateral g with aero at speed, braking g

Everything here is an estimate to steer tuning toward the targets in
plans/rb14-model-swap.md; the in-game tests are the ground truth.
"""
import argparse
import glob
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import jbeam  # noqa: E402

G = 9.81
RHO = 1.225
DEFAULT_NODE_WEIGHT = 25.0      # BeamNG's default when a part sets none
GASOLINE_KG_PER_L = 0.74
# Flat-plate aero: F = 0.5 rho v^2 A * coef/100 * shape(alpha). AERO_K scales
# drag so the original F4's baseline setup reproduces its in-game top speed
# (63.8 m/s, from its info file); lift uses the same model unscaled.
AERO_K = 1.4


# ------------------------------------------------------------ loading

def evaluate(v, variables):
    if isinstance(v, bool):
        return float(v)
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and v.startswith("$="):
        expr = re.sub(r"\$[A-Za-z_][A-Za-z0-9_]*", lambda m: repr(float(variables.get(m.group(), 0))), v[2:])
        expr = expr.replace("case(", "_case(")
        return float(eval(expr, {"__builtins__": {}, "_case": lambda *a: a[1] if a[0] else a[-1]}))
    if isinstance(v, str) and v.startswith("$"):
        return float(variables.get(v, 0))
    if isinstance(v, str) and v.upper() == "FLT_MAX":
        return 1e30
    if v in ("", None):
        return None
    return float(v)


class Vehicle:
    def __init__(self, mod="redbull", config=None):
        d = f"vehicles/{mod}"
        dirs = [d] + sorted(x for x in glob.glob(f"vehicles/common/{mod}_*") if os.path.isdir(x))
        self.parts = {}
        for dd in dirs:
            for f in sorted(glob.glob(f"{dd}/*.jbeam")):
                for k, v in jbeam.load(f).items():
                    self.parts[k] = v
        self.variables = {}
        for p in self.parts.values():
            for r in jbeam.table_rows(p.get("variables", [])):
                self.variables[r["name"]] = r.get("default", 0)
        overrides = {}
        if config:
            cfg = jbeam.load(f"{d}/{config}.pc")
            overrides = {k: v for k, v in (cfg.get("parts") or {}).items() if v}
            for k, v in (cfg.get("vars") or {}).items():
                self.variables[k] = v
        main = next(n for n, p in self.parts.items() if p.get("slotType") == "main")
        self.tree = []
        self._walk(main, (0.0, 0.0, 0.0), overrides)
        self._nodes()

    def _walk(self, name, off, overrides):
        self.tree.append((name, off))
        part = self.parts[name]
        rows = jbeam.table_rows(part.get("slots", [])) + [
            {**r, "type": r.get("name")} for r in jbeam.table_rows(part.get("slots2", []))]
        for r in rows:
            choice = overrides.get(r.get("type"), r.get("default"))
            if not choice or choice not in self.parts:
                continue
            no = r.get("nodeOffset")
            child = tuple(float(no.get(k, 0)) for k in "xyz") if isinstance(no, dict) else off
            self._walk(choice, child, overrides)

    def section(self, name):
        """Rows of one section over the whole vehicle, the way BeamNG merges
        them: tables concatenated in slot-tree order, option rows ({...})
        carrying on into the next part's rows."""
        opts, header = {}, None
        for pname, _ in self.tree:
            table = self.parts[pname].get(name)
            if not isinstance(table, list) or not table:
                continue
            if isinstance(table[0], list):
                header = table[0]
                body = table[1:]
            else:
                body = table
            for row in body:
                if isinstance(row, dict):
                    opts = {**opts, **row}
                    continue
                if not isinstance(row, list) or header is None:
                    continue
                r = dict(opts)
                r.update(zip(header, row))
                if len(row) > len(header) and isinstance(row[-1], dict):
                    r.update(row[-1])
                yield pname, r

    def _nodes(self):
        self.pos, self.mass, self.group = {}, {}, {}
        offsets = dict(self.tree)
        for pname, r in self.section("nodes"):
            off = offsets[pname]
            if True:
                x, y, z = (evaluate(r[k], self.variables) for k in ("posX", "posY", "posZ"))
                sx = 1.0 if x >= 0 else -1.0
                self.pos[r["id"]] = np.array([x + sx * off[0], y + off[1], z + off[2]])
                w = r.get("nodeWeight")
                self.mass[r["id"]] = evaluate(w, self.variables) if w not in (None, "") else DEFAULT_NODE_WEIGHT
                g = r.get("group") or []
                self.group[r["id"]] = [g] if isinstance(g, str) else list(g)

    def wheels(self):
        """[(name, node1, node2, radius, width, tyre_node_w, hub_node_w, rays, part)]"""
        out = []
        # pressureWheels options merge down the tree; collect per wheel row
        for pname, r in self.section("pressureWheels"):
            if not isinstance(r.get("name"), str) or r.get("node1:") is None:
                continue
            out.append(r)
        return out

    def val(self, v, default=0.0):
        e = evaluate(v, self.variables) if v is not None else None
        return default if e is None else e


# ------------------------------------------------------------- mass

def mass_report(v):
    total = sum(v.mass.values())
    # wheels: merge options from all pressureWheels sections that mention the wheel
    wheel_rows = {}
    for pname, r in v.section("pressureWheels"):
        nm = r.get("name")
        if isinstance(nm, str) and r.get("node1:"):
            wheel_rows[nm] = {k: x for k, x in r.items() if x not in ("",)}
    wheel_mass = {}
    for nm, r in wheel_rows.items():
        rays = v.val(r.get("numRays"), 16)
        tyre = v.val(r.get("nodeWeight"), 0) * rays * 2 if r.get("hasTire", True) else 0
        hub = v.val(r.get("hubNodeWeight"), 0) * rays * 2
        wheel_mass[nm] = (tyre, hub, r)
    fuel = 0.0
    for pname, p in v.tree:
        es = v.parts[pname]
        for key, blk in es.items():
            if isinstance(blk, dict) and "startingFuelCapacity" in blk:
                fuel += v.val(blk["startingFuelCapacity"]) * GASOLINE_KG_PER_L
    # positions: generated wheel nodes sit at the wheel centre
    pts = [(v.mass[n], v.pos[n]) for n in v.mass]
    for nm, (tyre, hub, r) in wheel_mass.items():
        c = (v.pos[r["node1:"]] + v.pos[r["node2:"]]) / 2
        pts.append((tyre + hub, c))
    fuel_node = next((n for n in v.pos if n.startswith("ft")), None)
    if fuel and fuel_node:
        pts.append((fuel, v.pos[fuel_node]))
    m = sum(w for w, _ in pts)
    cog = sum(w * p for w, p in pts) / m
    yf = np.mean([(v.pos[r["node1:"]][1] + v.pos[r["node2:"]][1]) / 2 for nm, (_, _, r) in wheel_mass.items() if nm.startswith("F")])
    yr = np.mean([(v.pos[r["node1:"]][1] + v.pos[r["node2:"]][1]) / 2 for nm, (_, _, r) in wheel_mass.items() if nm.startswith("R")])
    front = (yr - cog[1]) / (yr - yf)
    return dict(total=m, nodes=total, wheels={k: t + h for k, (t, h, _) in wheel_mass.items()}, fuel=fuel,
                cog=cog, front=front, yf=yf, yr=yr, wheelbase=yr - yf, wheel_rows=wheel_rows)


# ------------------------------------------------------- suspension FEM

def torsion_angle(p1, p2, p3, p4):
    b1, b2, b3 = p2 - p1, p3 - p2, p4 - p3
    n1, n2 = np.cross(b1, b2), np.cross(b2, b3)
    m1 = np.cross(n1, b2 / np.linalg.norm(b2))
    return math.atan2(np.dot(m1, n2), np.dot(n1, n2))


def stiffness(v, free, fixed_extra=()):
    """Assemble the linear stiffness matrix over the free nodes."""
    idx = {n: i for i, n in enumerate(free)}
    K = np.zeros((3 * len(free), 3 * len(free)))

    def add(nodes, vec, k):
        # K += k * g g^T for a scalar measure with gradient g over nodes
        for a, ga in zip(nodes, vec):
            if a not in idx:
                continue
            for b, gb in zip(nodes, vec):
                if b not in idx:
                    continue
                ia, ib = 3 * idx[a], 3 * idx[b]
                K[ia:ia + 3, ib:ib + 3] += k * np.outer(ga, gb)

    for pname, r in v.section("beams"):
        a, b = r.get("id1:"), r.get("id2:")
        if a not in v.pos or b not in v.pos or (a not in idx and b not in idx):
            continue
        btype = str(r.get("beamType", "|NORMAL"))
        if "SUPPORT" in btype:
            continue            # only pushes back when compressed past its length
        k = v.val(r.get("beamSpring"), 0)
        if "BOUNDED" in btype and k == 0:
            continue            # pure limiters/dampers
        if r.get("optional") and False:
            pass
        d = v.pos[b] - v.pos[a]
        L = np.linalg.norm(d)
        if L < 1e-9:
            continue
        u = d / L
        add([a, b], [-u, u], k)
    for pname, r in v.section("torsionbars"):
        ns = [r.get(f"id{i}:") for i in range(1, 5)]
        if any(n not in v.pos for n in ns) or not any(n in idx for n in ns):
            continue
        k = v.val(r.get("spring"), 0)
        P = [v.pos[n] for n in ns]
        th0 = torsion_angle(*P)
        grads = []
        h = 1e-6
        for i in range(4):
            gi = np.zeros(3)
            for c in range(3):
                Q = [p.copy() for p in P]
                Q[i][c] += h
                t1 = torsion_angle(*Q)
                Q[i][c] -= 2 * h
                t2 = torsion_angle(*Q)
                d = (t1 - t2 + math.pi) % (2 * math.pi) - math.pi   # flat bars sit at +-180 deg
                gi[c] = d / (2 * h)
            grads.append(gi)
        add(ns, grads, k)
    return K, idx


def axle_system(v, axle):
    """Linear model of one axle with the chassis held: (K, idx, wheel axle
    nodes, preload force vector, unit force vector of the two corner springs
    pushing their ends apart, sprung corner weight in N)."""
    free = corner_nodes(v, axle)
    K, idx = stiffness(v, free)
    K += np.eye(len(K)) * 1e-3
    wl = {"F": ("fw1l", "fw1ll", "fw1r", "fw1rr"), "R": ("rw1l", "rw1ll", "rw1r", "rw1rr")}[axle]
    pre_all = preload_forces(v, free, idx)
    pre_spring = preload_forces(v, free, idx, only=lambda r: str(r.get("name", "")).startswith("spring_"))
    e = np.zeros(3 * len(free))
    for pname, r in v.section("beams"):
        if not str(r.get("name", "")).startswith("spring_" + axle):
            continue
        a, b = r["id1:"], r["id2:"]
        d = v.pos[b] - v.pos[a]
        u = d / np.linalg.norm(d)
        for n, sgn in ((a, -1), (b, 1)):
            if n in idx:
                e[3 * idx[n]:3 * idx[n] + 3] += sgn * u
    return K, idx, wl, pre_all - pre_spring, e


def preload_forces(v, free, idx, only=None):
    """Forces the precompressed beams put on the free nodes at the modelled
    position (beamPrecompression ratio, or precompressionRange in metres,
    which takes precedence); positive precompression pushes the ends apart."""
    f = np.zeros(3 * len(free))
    for pname, r in v.section("beams"):
        a, b = r.get("id1:"), r.get("id2:")
        if a not in v.pos or b not in v.pos or (a not in idx and b not in idx):
            continue
        if only is not None and not only(r):
            continue
        btype = str(r.get("beamType", "|NORMAL"))
        k = v.val(r.get("beamSpring"), 0)
        if "SUPPORT" in btype or k == 0:
            continue
        d = v.pos[b] - v.pos[a]
        L = np.linalg.norm(d)
        u = d / L
        rng = r.get("precompressionRange")
        if rng not in (None, ""):
            dl = v.val(rng, 0)
        else:
            dl = (v.val(r.get("beamPrecompression"), 1.0) - 1.0) * L
        if dl == 0:
            continue
        for n, sgn in ((a, -1), (b, 1)):
            if n in idx:
                f[3 * idx[n]:3 * idx[n] + 3] += sgn * k * dl * u
    return f


def generated_wheels(v):
    """Approximate the hub and tyre the game generates for each pressureWheel
    (BeamNG doesn't document the exact layout): two staggered rings of
    numRays hub nodes at hubRadius, +-hubWidth/2 about the wheel centre,
    each tied to both axle nodes (hubSide), across (hubTread) and around
    (hubPeriphery); two rings of tyre nodes at the radius, +-tireWidth/2,
    tied to the hub (wheelSide, stiff value in extension), across
    (wheelTread / wheelTreadReinf) and around (wheelPeriphery / ...Reinf).
    Returns ({node: pos}, {node: mass}, [(a, b, k)])."""
    pos, mass, beams = {}, {}, []
    for r in v.wheels():
        n1, n2 = r.get("node1:"), r.get("node2:")
        if n1 not in v.pos or n2 not in v.pos:
            continue
        a, b = v.pos[n1], v.pos[n2]
        axis = (b - a) / np.linalg.norm(b - a)
        c = (a + b) / 2 + axis * v.val(r.get("wheelOffset"), 0) * v.val(r.get("wheelDir"), 1)
        e1 = np.cross(axis, [0, 0, 1.0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(axis, e1)
        nr = int(v.val(r.get("numRays"), 16))
        val = lambda k, d=0: v.val(r.get(k), d)
        name = r["name"]
        rings = {}
        for kind, rad, width, w in (("hub", val("hubRadius", 0.2), val("hubWidth", 0.2), val("hubNodeWeight", 0.5)),
                                    ("tyre", val("radius", 0.3), val("tireWidth", 0.2), val("nodeWeight", 0.2))):
            for side, sgn in ((0, -1), (1, 1)):
                ids = []
                for i in range(nr):
                    ang = 2 * math.pi * (i + 0.5 * side) / nr
                    nid = f"{name}_{kind}{side}_{i}"
                    pos[nid] = c + axis * sgn * width / 2 + rad * (math.cos(ang) * e1 + math.sin(ang) * e2)
                    mass[nid] = w
                    ids.append(nid)
                rings[(kind, side)] = ids
        wide = max(val("wheelSideBeamSpringExpansion", 0), val("wheelSideBeamSpring", 0))
        for i in range(nr):
            j, k2 = (i + 1) % nr, (i + 2) % nr
            h0, h1, t0, t1 = rings[("hub", 0)], rings[("hub", 1)], rings[("tyre", 0)], rings[("tyre", 1)]
            for hn in (h0[i], h1[i]):
                beams += [(n1, hn, val("hubSideBeamSpring")), (n2, hn, val("hubSideBeamSpring"))]
            beams += [(h0[i], h1[i], val("hubTreadBeamSpring")), (h0[j], h1[i], val("hubTreadBeamSpring")),
                      (h0[i], h0[j], val("hubPeripheryBeamSpring")), (h1[i], h1[j], val("hubPeripheryBeamSpring"))]
            beams += [(h0[i], t0[i], wide), (h1[i], t1[i], wide), (h0[i], t1[i], val("wheelReinfBeamSpring")),
                      (t0[i], t1[i], val("wheelTreadBeamSpring")), (t0[j], t1[i], val("wheelTreadBeamSpring")),
                      (t0[i], t1[j], val("wheelTreadReinfBeamSpring")),
                      (t0[i], t0[j], val("wheelPeripheryBeamSpring")), (t1[i], t1[j], val("wheelPeripheryBeamSpring")),
                      (t0[i], t0[k2], val("wheelPeripheryReinfBeamSpring")), (t1[i], t1[k2], val("wheelPeripheryReinfBeamSpring"))]
    return pos, mass, beams


def stability_report(v, dt=1 / 2000, top=5):
    """BeamNG's explicit 2 kHz integration is stable while every vibration
    mode of the node/beam network has omega * dt < 2 (in practice the F4,
    which is fine in game, peaks at 1.69, and 1.77 visibly shook). Eigenmodes
    of M^-1 K over all nodes: beams, torsionbars and the generated wheels
    (approximated, see generated_wheels)."""
    wpos, wmass, wbeams = generated_wheels(v)
    free = sorted(v.pos) + sorted(wpos)
    K, idx = stiffness(v, free)
    allpos = {**v.pos, **wpos}
    for a, b, k in wbeams:
        d = allpos[b] - allpos[a]
        u = d / np.linalg.norm(d)
        for n1, g1 in ((a, -u), (b, u)):
            for n2, g2 in ((a, -u), (b, u)):
                i, j = 3 * idx[n1], 3 * idx[n2]
                K[i:i + 3, j:j + 3] += k * np.outer(g1, g2)
    masses = {**v.mass, **wmass}
    m = np.repeat([max(masses[n], 1e-6) for n in free], 3)
    Mi = 1 / np.sqrt(m)
    w, V = np.linalg.eigh(K * Mi[:, None] * Mi[None, :])
    wd = np.sqrt(np.clip(w, 0, None)) * dt
    modes = []
    for j in np.argsort(-wd)[:top]:
        vec = V[:, j] ** 2
        nodes = sorted(((vec[3 * i:3 * i + 3].sum(), n) for n, i in idx.items()), reverse=True)[:3]
        modes.append("%.2f: %s" % (wd[j], ", ".join("%s %.2f kg" % (n, masses[n]) for _, n in nodes)))
    return dict(max=float(wd.max()), over=int((wd >= 2).sum()), modes=modes)


def corner_nodes(v, axle):
    """Nodes that move with the wheels (unsprung + linkage) for one axle."""
    pat = {"F": r"^(fh[1-5]|fw\d|fps1|fs2|fs3|rkf|rbf|rbmf)", "R": r"^(rh\d|rw\d|rps1|rs2|rs3|rkr|rbr|rbmr)"}[axle]
    return sorted(n for n in v.pos if re.match(pat, n))


def suspension_report(v, massr):
    out = {}
    for axle in ("F", "R"):
        free = corner_nodes(v, axle)
        K, idx = stiffness(v, free)
        K += np.eye(len(K)) * 1e-3        # pin mechanisms (wheel spin, free rockers)
        wl = {"F": ("fw1l", "fw1ll", "fw1r", "fw1rr"), "R": ("rw1l", "rw1ll", "rw1r", "rw1rr")}[axle]
        def disp(fl, fr):
            f = np.zeros(len(K))
            for n in wl[:2]:
                f[3 * idx[n] + 2] += fl / 2
            for n in wl[2:]:
                f[3 * idx[n] + 2] += fr / 2
            u = np.linalg.solve(K, f)
            zl = np.mean([u[3 * idx[n] + 2] for n in wl[:2]])
            zr = np.mean([u[3 * idx[n] + 2] for n in wl[2:]])
            return zl, zr
        # static sag: sprung corner weight on the wheels plus spring preloads;
        # positive = wheels up into the car (car sits below its modelled height)
        pre = preload_forces(v, free, idx)
        out[axle] = dict(K=K, idx=idx, wl=wl, pre=pre)
        zl, zr = disp(1000.0, 0.0)
        single = 1000.0 / zl
        zl, zr = disp(1000.0, 1000.0)
        heave = 1000.0 / zl                 # per wheel, both loaded
        zl, zr = disp(1000.0, -1000.0)
        roll = 1000.0 / zl                  # per wheel, opposite loads
        out[axle].update(single=single, heave=heave, roll=roll)
    # ride frequency from heave rate and sprung corner mass
    m, front = massr["total"], massr["front"]
    unsprung = {"F": 0.0, "R": 0.0}
    for nm, w in massr["wheels"].items():
        unsprung[nm[0]] += w
    for axle in ("F", "R"):
        nodes = corner_nodes(v, axle)
        unsprung[axle] += sum(v.mass[n] for n in nodes)
    for axle, share in (("F", front), ("R", 1 - front)):
        sprung_corner = (m * share - unsprung[axle]) / 2
        k = out[axle]["heave"]
        out[axle]["sprung_corner"] = sprung_corner
        out[axle]["unsprung_axle"] = unsprung[axle]
        out[axle]["freq"] = math.sqrt(max(k, 1) / max(sprung_corner, 1)) / (2 * math.pi)
        K, idx, wl, pre = (out[axle].pop(x) for x in ("K", "idx", "wl", "pre"))
        f = pre.copy()
        for n in wl:
            f[3 * idx[n] + 2] += sprung_corner * G / 2
        u = np.linalg.solve(K, f)
        out[axle]["sag"] = float(np.mean([u[3 * idx[n] + 2] for n in wl]))
    return out


# ------------------------------------------------------------- aero

def aero_report(v, speeds=(100, 200, 300)):
    # only triangles that set liftCoef make lift (wings, floor); every triangle
    # has drag
    defaults = dict(dragCoef=100.0, liftCoef=0.0, stallAngle=0.58)
    tris = []
    for pname, r in v.section("triangles"):
        ns = [r.get(f"id{i}:") for i in range(1, 4)]
        if any(n not in v.pos for n in ns):
            continue
        dc = v.val(r.get("dragCoef"), defaults["dragCoef"]) if r.get("dragCoef") not in (None, "") else defaults["dragCoef"]
        lc = v.val(r.get("liftCoef"), defaults["liftCoef"]) if r.get("liftCoef") not in (None, "") else defaults["liftCoef"]
        st = v.val(r.get("stallAngle"), defaults["stallAngle"]) if r.get("stallAngle") not in (None, "") else defaults["stallAngle"]
        tris.append((ns, dc, lc, st, pname))
    scale = v.val(v.parts[v.tree[0][0]].get("scaledragCoef", 1.0), 1.0)
    res = {}
    wind = np.array([0.0, 1.0, 0.0])        # air moves front to back
    yf, yr = v._yf, v._yr
    per_part = {}
    for spd in speeds:
        V = spd / 3.6
        q = 0.5 * RHO * V * V
        Fz = Fd = 0.0
        Ff = 0.0
        for ns, dc, lc, st, pname in tris:
            P = [v.pos[n] for n in ns]
            n = np.cross(P[1] - P[0], P[2] - P[0])
            A = np.linalg.norm(n) / 2
            if A < 1e-9:
                continue
            n = n / (2 * A)
            s = np.dot(n, wind)                       # sin(angle of attack)
            alpha = math.asin(max(-1.0, min(1.0, s)))
            # pressure drag of the plate, and lift perpendicular to the wind
            drag = q * A * dc / 100 * AERO_K * scale * s * s
            a = abs(alpha)
            cl = math.sin(2 * a) if a <= st else math.sin(2 * st) * max(0.0, 1 - (a - st) / st)
            # lift acts along the normal's component perpendicular to the wind
            lift_dir = n - s * wind
            ln = np.linalg.norm(lift_dir)
            lz = 0.0
            if ln > 1e-9:
                # plate force points away from its windward face
                lz = (lift_dir[2] / ln) * math.copysign(1, s) * q * A * lc / 100 * math.pi * cl
            Fz += lz
            Fd += drag
            cy = np.mean([p[1] for p in P])
            Ff += lz * (yr - cy) / (yr - yf)
            if spd == speeds[-1]:
                pp = per_part.setdefault(pname, [0.0, 0.0, 0.0])
                pp[0] += lz
                pp[1] += drag
                pp[2] += lz * (yr - cy) / (yr - yf)     # share carried by the front axle
        res[spd] = dict(down=-Fz, drag=Fd, front=(-Ff / -Fz) if Fz else 0.0)
    return res, per_part


# ------------------------------------------------------- powertrain

def ers_params(v):
    for pname, _ in v.tree:
        for r in jbeam.table_rows(v.parts[pname].get("controller") or []):
            if r.get("fileName") == "redbullERS":
                return r
    return None


def powertrain_report(v, massr, aero, grip, ice_only=False):
    eng = {}
    for pname, _ in v.tree:          # parts (engine, ECU, internals) each add keys
        if isinstance(v.parts[pname].get("mainEngine"), dict):
            eng.update(v.parts[pname]["mainEngine"])
    curve = [(float(r[0]), float(r[1])) for r in eng["torque"][1:]]
    ers = ers_params(v)
    if ice_only and ers:
        curve = [(float(r), float(t)) for r, t in ers["iceTorque"]]
    maxrpm = v.val(eng.get("maxRPM"), 7000)
    gearbox = next(v.parts[p]["gearbox"] for p, _ in v.tree if "gearbox" in v.parts[p])
    ratios = [float(x) for x in gearbox["gearRatios"] if float(x) > 0]
    diff = next(v.parts[p][k] for p, _ in v.tree for k in v.parts[p] if k.startswith("differential_") and isinstance(v.parts[p][k], dict))
    final = v.val(diff["gearRatio"])
    for pname, _ in v.tree:          # revLimiterRPM (ECU) caps the usable rpm
        me = v.parts[pname].get("mainEngine")
        if isinstance(me, dict) and me.get("revLimiterRPM"):
            maxrpm = min(maxrpm, v.val(me["revLimiterRPM"]))
    radius = massr["radius_R"]
    rpms = np.linspace(curve[0][0], curve[-1][0], 400)
    tq = np.interp(rpms, [c[0] for c in curve], [c[1] for c in curve])
    kw = tq * rpms * 2 * math.pi / 60 / 1000
    ipk = int(np.argmax(kw))
    per_gear = [maxrpm / (r * final) * 2 * math.pi / 60 * radius * 3.6 for r in ratios]
    # straight-line simulation: best gear, traction limit on the rear axle
    m = massr["total"]
    eff = 0.92
    dt, t, spd = 0.01, 0.0, 0.1
    marks = {}
    top = 0.0
    k_down = aero[200]["down"] / (200 / 3.6) ** 2
    k_drag = aero[200]["drag"] / (200 / 3.6) ** 2
    front_aero = aero[200]["front"]
    while t < 60:
        best = 0.0
        for r in ratios:
            rpm = spd / radius * 60 / (2 * math.pi) * r * final
            if rpm > maxrpm:
                continue
            rpm = max(rpm, curve[1][0])
            T = float(np.interp(rpm, [c[0] for c in curve], [c[1] for c in curve]))
            best = max(best, T * r * final * eff / radius)
        down = k_down * spd * spd
        rear_load = m * G * (1 - massr["front"]) + down * (1 - front_aero)
        traction = grip(rear_load / 2) * rear_load
        fx = min(best, traction) - k_drag * spd * spd - 0.015 * (m * G + down)
        a = fx / m
        if a <= 0.001:
            top = spd
            break
        spd += a * dt
        t += dt
        for mark in (100, 200, 300):
            if mark not in marks and spd * 3.6 >= mark:
                marks[mark] = t
        top = spd
    return dict(peak_kw=kw[ipk], peak_rpm=rpms[ipk], peak_tq=tq.max(), maxrpm=maxrpm, ratios=ratios, final=final,
                per_gear=per_gear, marks=marks, top=top * 3.6)


def tyre_grip(v, rows):
    """mu(load per wheel) from BeamNG's load-sensitivity parameters."""
    r = rows
    nl = v.val(r.get("noLoadCoef"), 2.0)
    fl = v.val(r.get("fullLoadCoef"), 0.6)
    sl = v.val(r.get("loadSensitivitySlope"), 0.0002)
    fc = v.val(r.get("frictionCoef"), 1.0)
    return lambda load: fc * (fl + (nl - fl) * math.exp(-sl * load))


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mod", default="redbull")
    ap.add_argument("--config")
    ap.add_argument("--json")
    args = ap.parse_args()
    os.chdir(REPO)
    v = Vehicle(args.mod, args.config)
    mr = mass_report(v)
    v._yf, v._yr = mr["yf"], mr["yr"]
    rows = {}
    for nm, r in mr["wheel_rows"].items():
        rows[nm] = r
    rF = next(r for n, r in rows.items() if n.startswith("F"))
    rR = next(r for n, r in rows.items() if n.startswith("R"))
    mr["radius_R"] = v.val(rR.get("radius"), 0.3)
    gripF, gripR = tyre_grip(v, rF), tyre_grip(v, rR)
    sus = suspension_report(v, mr)
    aero, per_part = aero_report(v)
    pt = powertrain_report(v, mr, aero, gripR)
    pt_ice = powertrain_report(v, mr, aero, gripR, ice_only=True) if ers_params(v) else None

    print(f"== {args.mod} ({args.config or 'defaults'})")
    st = stability_report(v)
    print(f"stability   highest mode omega*dt {st['max']:.2f} (must stay < 2 at BeamNG's 2 kHz; {st['over']} over)  "
          f"top: {st['modes'][0]}")
    print(f"mass        {mr['total']:.0f} kg (nodes {mr['nodes']:.0f}, wheels {sum(mr['wheels'].values()):.0f}, fuel {mr['fuel']:.0f})"
          f"  front {mr['front'] * 100:.1f}%  CoG z {mr['cog'][2]:.3f} m  wheelbase {mr['wheelbase']:.3f} m")
    for a in ("F", "R"):
        s = sus[a]
        print(f"suspension {a}  wheel rate single {s['single'] / 1000:.0f} / heave {s['heave'] / 1000:.0f} / roll {s['roll'] / 1000:.0f} N/mm"
              f"  sprung corner {s['sprung_corner']:.0f} kg  ride freq {s['freq']:.1f} Hz"
              f"  static sag {s['sag'] * 1000:+.1f} mm")
    for spd, a in aero.items():
        print(f"aero {spd:3d} km/h  downforce {a['down']:7.0f} N ({a['down'] / (mr['total'] * G):.2f} x weight)"
              f"  drag {a['drag']:6.0f} N  L/D {a['down'] / max(a['drag'], 1):.2f}  front {a['front'] * 100:.0f}%")
    q300 = 0.5 * RHO * (300 / 3.6) ** 2
    # DRS: extend the hydros driven by electrics.values.drs and redo the aero
    drs_hydros = [r for _, r in v.section("hydros") if r.get("inputSource") == "drs"]
    if drs_hydros:
        saved = {k: p.copy() for k, p in v.pos.items()}
        moved = {}
        for r in drs_hydros:
            a, b = r["id1:"], r["id2:"]
            new = v.pos[a] + (v.pos[b] - v.pos[a]) * (1 + v.val(r.get("factor"), 0))
            moved[b] = new - v.pos[b]
            v.pos[b] = new
        # the centre node between a moved r/l pair follows them (in game the
        # wing's beams carry it along)
        for n in list(moved):
            c = n[:-1]
            if n.endswith("r") and c + "l" in moved and c in v.pos:
                v.pos[c] = v.pos[c] + (moved[n] + moved[c + "l"]) / 2
        drs, _ = aero_report(v)
        v.pos = saved
        d = drs[300]
        print(f"aero DRS open, 300 km/h: downforce {d['down']:.0f} N ({(d['down'] / aero[300]['down'] - 1) * 100:+.0f}%)"
              f"  drag {d['drag']:.0f} N ({(d['drag'] / aero[300]['drag'] - 1) * 100:+.0f}%)  front {d['front'] * 100:.0f}%")
        pt_drs = powertrain_report(v, mr, {**aero, 200: {**aero[200], "drag": drs[200]["drag"]}}, gripR)
        print(f"top speed with DRS open: {pt_drs['top']:.0f} km/h")
    print(f"aero coefficients  ClA {aero[300]['down'] / q300:.2f} m^2  CdA {aero[300]['drag'] / q300:.2f} m^2")
    print("aero by part at 300 km/h (downforce N / drag N):",
          ", ".join(f"{k}:{-d:.0f}/{dr:.0f}" for k, (d, dr, _) in sorted(per_part.items(), key=lambda kv: kv[1][0])[:4]))
    print(f"engine      peak {pt['peak_kw']:.0f} kW ({pt['peak_kw'] * 1.341:.0f} hp) @ {pt['peak_rpm']:.0f} rpm, {pt['peak_tq']:.0f} Nm, limit {pt['maxrpm']:.0f}")
    print("gears       " + "  ".join(f"{i + 1}:{s:.0f}" for i, s in enumerate(pt["per_gear"])) + f" km/h (final {pt['final']})")
    for label, p in (("launch", pt), ("ICE only", pt_ice)):
        if p is None:
            continue
        if p is pt_ice:
            print(f"ICE only    peak {p['peak_kw']:.0f} kW ({p['peak_kw'] * 1.341:.0f} hp) @ {p['peak_rpm']:.0f} rpm (ERS store empty)")
        print(f"{label:11s} 0-100 {p['marks'].get(100, float('nan')):.2f} s  0-200 {p['marks'].get(200, float('nan')):.2f} s"
              f"  0-300 {p['marks'].get(300, float('nan')):.2f} s  top {p['top']:.0f} km/h")
    wF = mr["total"] * G * mr["front"] / 2
    wR = mr["total"] * G * (1 - mr["front"]) / 2
    for spd in (0, 100, 200, 300):
        a = aero.get(spd, dict(down=0, front=0))
        dF = a["down"] * a["front"] / 2
        dR = a["down"] * (1 - a["front"]) / 2
        lat = 2 * (gripF(wF + dF) * (wF + dF) + gripR(wR + dR) * (wR + dR)) / (mr["total"] * G)
        drag = a.get("drag", 0)
        brk = (lat * mr["total"] * G + drag) / (mr["total"] * G)
        print(f"grip {spd:3d} km/h  lateral {lat:.2f} g  braking {brk:.2f} g"
              f"  (mu front {gripF(wF + dF):.2f} rear {gripR(wR + dR):.2f})")
    if args.json:
        json.dump(dict(mass=mr["total"], front=mr["front"], sus=sus, aero=aero, launch=pt["marks"], top=pt["top"]),
                  open(args.json, "w"), default=float, indent=1)


if __name__ == "__main__":
    main()
