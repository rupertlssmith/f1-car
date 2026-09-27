#!/usr/bin/env python3
"""Consistency checks for a BeamNG vehicle mod in this repo.

    python3 tools/check_mod.py [--mod redbull] [--fit]

Loads the mod's jbeam, meshes (.dae), materials and configurations (.pc) and
reports what the game would otherwise only show as console errors or a
broken car:

  - jbeam files that do not parse
  - slot defaults / configuration parts that do not exist
  - beams, triangles, props, cameras... referring to nodes that do not exist
  - flexbody/prop meshes missing from every .dae
  - flexbody node groups that no node belongs to
  - materials used by meshes but not defined; textures missing on disk
  - with --fit: how far each flexbody's vertices sit from the nodes of its
    groups (a mesh far from its nodes deforms badly when hit)

Exit status 1 if there are errors. Things the base game provides (common
brake meshes, the "mirror" material...) are listed as notes, not errors.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "rb14"))
import jbeam  # noqa: E402

# Provided by the base game (vehicles/common and core materials)
BASE_MESHES = re.compile(r"^(brake_|brakepad|disc_)")
BASE_MATERIALS = {"mirror", "generic_perf_parts", "invis", "screen_off", "grille_hex"}

NODE_SECTIONS = {
    "beams": ["id1:", "id2:"],
    "triangles": ["id1:", "id2:", "id3:"],
    "torsionbars": ["id1:", "id2:", "id3:", "id4:"],
    "hydros": ["id1:", "id2:"],
    "thrusters": ["id1:", "id2:"],
    "slidenodes": ["id:", "id1:", "id2:"],
    "props": ["idRef:", "idX:", "idY:"],
    "mirrors": ["idRef:", "id1:", "id2:"],
    "triggers2": ["idRef:", "idX:", "idY:"],
    "pressureWheels": ["node1:", "node2:", "nodeArm:"],
    "refNodes": ["ref:", "back:", "left:", "up:", "leftCorner:", "rightCorner:"],
    "camerasInternal": ["id1:", "id2:", "id3:", "id4:", "id5:", "id6:"],
}


class Report:
    def __init__(self):
        self.errors, self.warnings, self.notes = [], [], []

    def error(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warnings.append(msg)

    def note(self, msg):
        self.notes.append(msg)


def mod_dirs(mod):
    dirs = [f"vehicles/{mod}"]
    dirs += sorted(d for d in glob.glob(f"vehicles/common/{mod}_*") if os.path.isdir(d))
    return dirs


def load_jbeam(dirs, rep):
    parts = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.jbeam"))):
            try:
                data = jbeam.load(f)
            except jbeam.JbeamError as e:
                rep.error(f"parse error: {e}")
                continue
            for name, part in data.items():
                if name in parts:
                    rep.error(f"part {name} defined twice ({parts[name][0]} and {f})")
                parts[name] = (f, part)
    return parts


def default_tree(parts, main, overrides=None):
    """Walk the slot tree from the main part: [(part, nodeOffset)] using slot
    defaults (or a configuration's choices in overrides)."""
    overrides = overrides or {}
    out = []

    def visit(name, offset):
        out.append((name, offset))
        part = parts[name][1]
        rows = jbeam.table_rows(part.get("slots", [])) + [
            {**r, "type": r.get("name")} for r in jbeam.table_rows(part.get("slots2", []))]
        for r in rows:
            stype = r.get("type")
            choice = overrides.get(stype, r.get("default"))
            if not choice:
                continue
            if choice not in parts:
                yield_missing.append((name, stype, choice))
                continue
            no = r.get("nodeOffset")
            child_off = offset
            if isinstance(no, dict):
                child_off = tuple(float(no.get(k, 0)) for k in "xyz")
            visit(choice, child_off)

    yield_missing = []
    visit(main, (0.0, 0.0, 0.0))
    return out, yield_missing


def evaluate(v, variables):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and v.startswith("$="):
        expr = re.sub(r"\$[A-Za-z_][A-Za-z0-9_]*", lambda m: repr(float(variables.get(m.group(), 0))), v[2:])
        return float(eval(expr, {"__builtins__": {}}))
    if isinstance(v, str) and v.startswith("$"):
        return float(variables.get(v, 0))
    raise ValueError(v)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mod", default="redbull")
    ap.add_argument("--fit", action="store_true", help="also measure flexbody-to-node fit")
    args = ap.parse_args()
    os.chdir(REPO)
    rep = Report()
    dirs = mod_dirs(args.mod)
    parts = load_jbeam(dirs, rep)
    mains = [n for n, (f, p) in parts.items() if p.get("slotType") == "main"]
    if len(mains) != 1:
        rep.error(f"expected one main part, found {mains}")
        return finish(rep)
    main_part = mains[0]

    variables = {}
    for _, p in parts.values():
        for r in jbeam.table_rows(p.get("variables", [])):
            variables[r["name"]] = r.get("default", 0)

    tree, missing = default_tree(parts, main_part)
    for owner, stype, choice in missing:
        # base-game parts (bulbs, brake pads) are fine; anything else leaves
        # the slot empty in game
        if re.match(r"^(led_|brakepad_|halogen_)", choice):
            rep.note(f"slot {stype} in {owner} uses base-game part {choice}")
        else:
            rep.warn(f"slot {stype} in {owner} defaults to unknown part {choice} (slot stays empty)")

    # nodes and groups in the default configuration
    nodes, groups = {}, {}
    for name, off in tree:
        for r in jbeam.table_rows(parts[name][1].get("nodes", [])):
            try:
                x, y, z = (evaluate(r[k], variables) for k in ("posX", "posY", "posZ"))
            except (ValueError, KeyError, SyntaxError) as e:
                rep.error(f"{name}: node {r.get('id')} has a bad coordinate ({e})")
                continue
            sx = 1.0 if x >= 0 else -1.0
            p = (x + sx * off[0], y + off[1], z + off[2])
            if r["id"] in nodes:
                rep.warn(f"node {r['id']} defined in {nodes[r['id']][1]} and {name}")
            nodes[r["id"]] = (p, name)
            g = r.get("group") or []
            for gg in ([g] if isinstance(g, str) else g):
                if gg:
                    groups.setdefault(gg, []).append(r["id"])

    # pressureWheels generate the wheel/tyre nodes and their groups at load
    for name, _ in tree:
        for r in jbeam.table_rows(parts[name][1].get("pressureWheels", [])):
            for col in ("hubGroup", "group"):
                g = r.get(col)
                if isinstance(g, str) and g:
                    groups.setdefault(g, []).append(None)

    # node references
    for name, _ in tree:
        part = parts[name][1]
        for sec, cols in NODE_SECTIONS.items():
            for r in jbeam.table_rows(part.get(sec, [])):
                for c in cols:
                    v = r.get(c)
                    if isinstance(v, str) and v and v not in nodes and v != "9999":
                        # the game skips these with a console warning
                        rep.warn(f"{name}.{sec}: unknown node {v!r} (ignored by the game)")

    # meshes
    import dae
    meshes = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.dae"))):
            for m in dae.read(f):
                if m.name in meshes:
                    rep.error(f"mesh {m.name} in both {meshes[m.name][0]} and {f}")
                meshes[m.name] = (f, m)
    for name, _ in tree:
        part = parts[name][1]
        for sec in ("flexbodies", "props"):
            for r in jbeam.table_rows(part.get(sec, [])):
                mesh = r.get("mesh")
                if not mesh or mesh == "SPOTLIGHT" or mesh == "POINTLIGHT":
                    continue
                if mesh not in meshes:
                    if BASE_MESHES.match(mesh):
                        rep.note(f"{name}: mesh {mesh} comes from the base game")
                    else:
                        rep.error(f"{name}.{sec}: mesh {mesh} not in any .dae")
                if sec == "flexbodies":
                    gs = r.get("[group]:", []) or []
                    empty = [g for g in gs if g not in groups]
                    if gs and len(empty) == len(gs):
                        rep.error(f"{name}: flexbody {mesh} has no nodes in any of its groups {gs}")
                    elif empty:
                        rep.note(f"{name}: flexbody {mesh} group(s) {empty} have no nodes")

    # materials
    mats = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.materials.json"))):
            try:
                data = jbeam.load(f)
            except jbeam.JbeamError as e:
                rep.error(f"parse error: {e}")
                continue
            for k, v in data.items():
                mats[v.get("mapTo", k) if isinstance(v, dict) else k] = (f, v)
    used = {}
    for f, m in meshes.values():
        for p in m.prims:
            used.setdefault(p.material, f)
    for mat, f in sorted(used.items()):
        if mat not in mats:
            (rep.note if mat in BASE_MATERIALS else rep.error)(f"material {mat} (used in {f}) not defined in the mod")
    for mat, (f, v) in mats.items():
        for stage in v.get("Stages", []) if isinstance(v, dict) else []:
            for k, path in stage.items():
                if k.endswith("Map") and isinstance(path, str) and path:
                    rel = path.lstrip("/")
                    stem = re.sub(r"\.(png|dds|jpg)$", "", rel)
                    if not any(os.path.exists(stem + ext) for ext in (".png", ".dds", ".jpg")):
                        if rel.startswith(f"vehicles/{args.mod}") or rel.startswith("vehicles/common/" + args.mod):
                            rep.error(f"material {mat}: texture {path} missing")
                        else:
                            rep.note(f"material {mat}: texture {path} from outside the mod")
    # glowMap targets
    for name, _ in tree:
        for k, v in (parts[name][1].get("glowMap") or {}).items():
            for m in [k] + [v.get(s) for s in ("off", "on", "on_intense") if isinstance(v, dict) and v.get(s)]:
                if m not in mats and m not in BASE_MATERIALS:
                    rep.error(f"{name}: glowMap material {m} not defined")

    # controllers: a Lua file in the mod, or one the game ships; actions
    # enabled by the vehicle must be defined in its interaction file
    base_controllers = {"vehicleController", "shiftLights", "gauges/genericGauges", "esc", "tractionControl",
                        "twoStepLaunch", "nitrousOxideInjection", "lightbar", "postCrashBrake", "drivingDynamics/CMU"}
    enabled = []
    for name, _ in tree:
        for r in jbeam.table_rows(parts[name][1].get("controller") or []):
            fn = r.get("fileName")
            if not isinstance(fn, str):
                continue
            lua = [os.path.join(d, "lua", "controller", fn + ".lua") for d in dirs]
            if fn not in base_controllers and not any(os.path.exists(x) for x in lua):
                rep.error(f"{name}: controller {fn} has no lua/controller/{fn}.lua and is not a known base-game controller")
        for r in jbeam.table_rows(parts[name][1].get("actionsEnabled") or []):
            enabled.append((name, r.get("id")))
    inter = f"vehicles/{args.mod}/{args.mod}.interaction.json"
    actions = set()
    if os.path.exists(inter):
        try:
            actions = set((json.load(open(inter)).get("actions") or {}).keys())
        except ValueError as e:
            rep.error(f"{inter}: {e}")
    for name, a in enabled:
        if a not in actions:
            rep.error(f"{name}: enabled action {a} not defined in {os.path.basename(inter)}")
    for km in glob.glob(f"vehicles/{args.mod}/inputmaps/*.json"):
        for b in (json.load(open(km)).get("bindings") or []):
            if b.get("action") not in actions:
                rep.error(f"{os.path.basename(km)}: binding {b.get('control')} -> unknown action {b.get('action')}")

    # configurations
    for pc in sorted(glob.glob(f"vehicles/{args.mod}/*.pc")):
        try:
            cfg = jbeam.load(pc)
        except jbeam.JbeamError as e:
            rep.error(f"parse error: {e}")
            continue
        for slot, choice in (cfg.get("parts") or {}).items():
            if choice and choice not in parts:
                rep.error(f"{os.path.basename(pc)}: slot {slot} -> unknown part {choice}")
        for var in (cfg.get("vars") or {}):
            if var not in variables:
                rep.warn(f"{os.path.basename(pc)}: variable {var} not defined by any part")

    if args.fit:
        fit_report(tree, parts, nodes, groups, meshes, variables, rep)
    return finish(rep, len(tree), len(nodes), len(meshes))


def fit_report(tree, parts, nodes, groups, meshes, variables, rep):
    import numpy as np
    rows = []
    for name, off in tree:
        for r in jbeam.table_rows(parts[name][1].get("flexbodies", [])):
            mesh = r.get("mesh")
            if mesh not in meshes:
                continue
            m = meshes[mesh][1]
            P = m.world_positions()
            pos = r.get("pos")
            if isinstance(pos, dict):
                # flexbody placed at pos (+ the slot's nodeOffset), rotated
                # by rot; wheels use z=180 for the right-hand side
                p = np.array([evaluate(pos.get(k, 0), variables) for k in "xyz"])
                sx = 1.0 if p[0] >= 0 else -1.0
                rz = evaluate((r.get("rot") or {}).get("z", 0), variables)
                if abs(abs(rz) - 180) < 1e-6:
                    P = P * np.array([-1, -1, 1])
                P = P + p + np.array([sx * off[0], off[1], off[2]])
            ids = [n for g in (r.get("[group]:") or []) for n in groups.get(g, []) if n]
            if not ids:
                continue
            N = np.array([nodes[i][0] for i in ids])
            step = max(1, len(P) // 4000)
            Q = P[::step]
            d = np.sqrt(((Q[:, None, :] - N[None, :, :]) ** 2).sum(-1)).min(1)
            rows.append((np.percentile(d, 95), d.max(), len(ids), mesh, name))
    rows.sort(reverse=True)
    print("flexbody fit (distance from vertices to nearest node of their groups):")
    print("   p95     max  nodes  mesh (part)")
    for p95, mx, n, mesh, name in rows:
        flag = "  <-- far" if p95 > 0.35 else ""
        print(f"  {p95:5.2f}  {mx:6.2f}  {n:5d}  {mesh} ({name}){flag}")
        if p95 > 0.35:
            rep.warn(f"flexbody {mesh}: 95% of vertices within {p95:.2f} m of its nodes (loose fit)")


def finish(rep, nparts=0, nnodes=0, nmeshes=0):
    for n in rep.notes:
        print("note:", n)
    for w in rep.warnings:
        print("WARNING:", w)
    for e in rep.errors:
        print("ERROR:", e)
    print(f"{nparts} parts in the default configuration, {nnodes} nodes, {nmeshes} meshes: "
          f"{len(rep.errors)} error(s), {len(rep.warnings)} warning(s)")
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main())
