#!/usr/bin/env python3
"""Consistency checks for a BeamNG vehicle mod in this repo.

    python3 tools/check_mod.py [--mod redbull] [--fit]

Loads the mod's jbeam, meshes (.dae), materials and configurations (.pc) and
reports what the game would otherwise only show as console errors or a
broken car:

  - jbeam files that do not parse
  - slot defaults / configuration parts that do not exist
  - every reference between pieces, checked in the default car, in every
    configuration (.pc) and with every optional part fitted in turn:
      nodes (every "...:" column or option: beams, torsion bars, wheels'
      torque arms, rails, gearbox / oil-pan nodes...), node groups
      ("[...]:"), $variables, named beams (breakTriggerBeam), deform groups,
      powertrain inputs, wheels, energy storages, rails (slidenodes),
      triggers and their actions, and the electrics that hydros, thrusters
      and props read (from the game or the mod's Lua)
  - the mod's Lua controllers run (luajit, stubbed game) on each car's real
    nodes and parameters: missing nodes, errors, disabled controllers
  - configurations without their info_*.json / thumbnail
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
        for pat, why in ACCEPTED:
            if re.search(pat, msg):
                self.notes.append(f"accepted: {msg} -- {why}")
                return
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

    check_references(parts, main_part, variables, args.mod, dirs, actions, rep)

    if args.fit:
        fit_report(tree, parts, nodes, groups, meshes, variables, rep)
    return finish(rep, len(tree), len(nodes), len(meshes))


# ------------------------------------------------------------ references
# BeamNG convention: a column or option whose name ends in ":" holds node
# ids ("id1:", "torqueArm:", "links:"...), and "[...]:" holds node groups.
SKIP_SECTIONS = {"information", "slots", "slots2", "variables", "nodes", "flexbodies"}
# electrics the game itself provides (inputs, drivetrain, lights...)
BASE_ELECTRICS = {
    "throttle", "throttle_input", "brake", "brake_input", "clutch", "clutch_input", "steering", "steering_input",
    "parkingbrake", "parkingbrake_input", "rpm", "rpmspin", "rpmTacho", "wheelspeed", "airspeed", "gear", "gear_A",
    "gear_M", "gearIndex", "ignition", "ignitionLevel", "running", "engineRunning", "fuel", "oiltemp", "watertemp",
    "lowfuel", "lights", "lowbeam", "highbeam", "signal_L", "signal_R", "hazard", "reverse", "horn", "brakelights",
    "abs", "esc", "tcs", "checkengine", "odometer", "trip", "turboBoost", "avgWheelAV", "clutchRatio", "virtualAirspeed",
    "engineLoad", "isShifting", "throttleOverride", "brakelight_signal_L", "brakelight_signal_R",
}
# Known leftovers from the F4, checked and accepted: (regex on the message,
# why). Printed as notes, so anything new still shows up as a warning.
ACCEPTED = [
    (r"unknown node 'nc7'", "F4 front wing: node nc7 commented out in the F4 itself; its beams are dead"),
    (r"unknown node 'fw2[rl]'", "F4 front hub: fw2 nodes never existed in the F4; dead beams (removing them would "
                                "shift f1_setup's row-by-row F4 calibration)"),
    (r"unknown node 'rh5[rl]'", "F4 rear hub: rh5 nodes commented out in the F4 (round 18's brace nodes are rh6 / rh7)"),
    (r"slot redbull_flywheel .* unknown part", "F4 flywheel slot: the F4 never had the part; engine inertia is "
                                               "set in mainEngine"),
    (r"deform group 'mainEngine_piping'", "F4 engine: no piping beams; that damage type just never happens"),
]
LUA_ELECTRIC = re.compile(r"electrics\.values\.([A-Za-z_]\w*)\s*=(?!=)|electrics\.values\[\"([A-Za-z_]\w*)\"\]\s*=(?!=)")
VAR_TOKEN = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")


def tree_info(tree, parts, variables, rep=None):
    """What the parts of one car define: nodes (positions), groups, beam
    names, deform groups, wheels, powertrain devices, storages, rails,
    triggers, variables."""
    info = {k: {} for k in ("nodes", "groups")}
    info["containers"] = []
    info.update({k: set() for k in ("beams", "deform", "wheels", "devices", "storages", "rails", "triggers", "vars")})
    for name, off in tree:
        part = parts[name][1]
        for r in jbeam.table_rows(part.get("variables", [])):
            info["vars"].add(r.get("name"))
        for r in jbeam.table_rows(part.get("nodes", [])):
            try:
                x, y, z = (evaluate(r[k], variables) for k in ("posX", "posY", "posZ"))
            except (ValueError, KeyError, SyntaxError, TypeError) as e:
                if rep:
                    rep.error(f"{name}: node {r.get('id')} has a bad coordinate ({e})")
                continue
            sx = 1.0 if x >= 0 else -1.0
            info["nodes"][r["id"]] = ((x + sx * off[0], y + off[1], z + off[2]), name)
            # "[attr]:" references select nodes by any list / name property
            # ("[group]:", "[engineGroup]:"...): index them all
            for attr, g in r.items():
                if attr in ("id", "posX", "posY", "posZ") or not isinstance(g, (str, list)):
                    continue
                for gg in ([g] if isinstance(g, str) else g):
                    if isinstance(gg, str) and gg:
                        info["groups"].setdefault((attr, gg), []).append(r["id"])
            if r.get("containerBeam"):
                info["containers"].append((name, r["id"], r["containerBeam"]))
        for sec in ("beams", "triangles", "hydros", "torsionbars"):
            for r in jbeam.table_rows(part.get(sec, [])):
                if sec == "beams" and r.get("name"):
                    info["beams"].add(r["name"])
                if r.get("deformGroup"):
                    info["deform"].add(r["deformGroup"])
        for r in jbeam.table_rows(part.get("pressureWheels", [])) + jbeam.table_rows(part.get("hubWheels", [])):
            info["wheels"].add(r.get("name"))
            for col in ("hubGroup", "group"):
                if isinstance(r.get(col), str) and r[col]:
                    info["groups"].setdefault(("group", r[col]), []).append(None)
        for r in jbeam.table_rows(part.get("powertrain", [])):
            info["devices"].add(r.get("name"))
        for r in jbeam.table_rows(part.get("energyStorage", [])):
            info["storages"].add(r.get("name"))
        if isinstance(part.get("rails"), dict):
            info["rails"].update(part["rails"])
        for r in jbeam.table_rows(part.get("triggers2", [])) + jbeam.table_rows(part.get("triggers", [])):
            info["triggers"].add(r.get("id"))
    return info


def _walk(v, path, fn):
    """Call fn(key, value, path) for every dict key below v."""
    if isinstance(v, dict):
        for k, x in v.items():
            fn(k, x, path)
            _walk(x, path, fn)
    elif isinstance(v, list):
        for x in v:
            _walk(x, path, fn)


def tree_refs(tree, parts, info, actions, electrics):
    """[(level, message)] for every reference the car can't resolve."""
    out = []
    nodes, groups = info["nodes"], info["groups"]

    def names(v):
        return [v] if isinstance(v, str) else [x for x in v if isinstance(x, str)] if isinstance(v, list) else []

    for name, _ in tree:
        part = parts[name][1]
        for sec, val in part.items():
            if sec in SKIP_SECTIONS:
                continue
            where = f"{name}.{sec}"

            def ref(k, v, _p=None, where=where):
                if not (isinstance(k, str) and k.endswith(":")):
                    return
                for n in names(v):
                    if not n or n == "9999":
                        continue
                    if k.startswith("["):
                        if (k[1:k.index("]")], n) not in groups:
                            out.append(("error", f"{where}: no node has {k[1:k.index(']')]} {n!r} ({k})"))
                    elif ":" in k[:-1]:
                        continue                # "triggerId:triggers2" style: checked below
                    elif n not in nodes:
                        out.append(("warn", f"{where}: unknown node {n!r} ({k}) (ignored by the game)"))
            rows = jbeam.table_rows(val)
            if rows:
                for r in rows:
                    for k, v in r.items():
                        ref(k, v)
                    for k, v in r.items():
                        _walk(v, where, lambda kk, vv, _p, where=where: ref(kk, vv))
            else:
                _walk({sec: val}, where, lambda kk, vv, _p, where=where: ref(kk, vv))

            # named things
            def named(k, v, _p, where=where):
                if k == "breakTriggerBeam" and isinstance(v, str) and v and v not in info["beams"]:
                    out.append(("warn", f"{where}: breakTriggerBeam {v!r} is no beam's name (never breaks)"))
                if isinstance(k, str) and (k == "deformGroups" or k.startswith("deformGroups_")):
                    for g in names(v):
                        if g not in info["deform"]:
                            out.append(("warn", f"{where}: deform group {g!r} is on no beam (damage never triggers)"))
                if k == "connectedWheel" and isinstance(v, str) and v not in info["wheels"]:
                    out.append(("error", f"{where}: connectedWheel {v!r} is not a wheel"))
                if k == "energyStorage" and isinstance(v, str) and v not in info["storages"]:
                    out.append(("error", f"{where}: energyStorage {v!r} not defined"))
            _walk({sec: val}, where, named)
            for r in rows:
                _walk(r, where, named)

        lost = {}
        for owner, node, beam in info["containers"]:
            if owner == name and beam not in info["beams"]:
                lost.setdefault(beam, []).append(node)
        for beam, ns in lost.items():
            out.append(("warn", f"{name}.nodes: containerBeam {beam!r} (on {', '.join(ns)}) is no beam's name"))
        for r in jbeam.table_rows(part.get("powertrain", [])):
            src = r.get("inputName")
            if src and src != "dummy" and src not in info["devices"]:
                out.append(("error", f"{name}.powertrain: {r.get('name')} input {src!r} is no powertrain device"))
        for r in jbeam.table_rows(part.get("slidenodes", [])):
            if r.get("railName") and r["railName"] not in info["rails"]:
                out.append(("error", f"{name}.slidenodes: rail {r['railName']!r} not defined"))
        for r in jbeam.table_rows(part.get("triggerEventLinks2", [])):
            t, a = r.get("triggerId:triggers2"), r.get("inputAction")
            if t and t not in info["triggers"]:
                out.append(("error", f"{name}.triggerEventLinks2: trigger {t!r} not defined"))
            if a and ":" not in a and a not in actions:
                out.append(("error", f"{name}.triggerEventLinks2: action {a!r} not in the interaction file"))
        for sec, col in (("hydros", "inputSource"), ("thrusters", "control"), ("props", "func")):
            for r in jbeam.table_rows(part.get(sec, [])):
                e = r.get(col)
                if isinstance(e, str) and e and e not in electrics:
                    out.append(("warn", f"{name}.{sec}: electrics value {e!r} is set by neither the game nor the mod's Lua"))

        # $variables used but not defined anywhere in this car
        def var(k, v, _p, name=name):
            if isinstance(v, str) and v.startswith("$"):
                for t in VAR_TOKEN.findall(v):
                    if t not in info["vars"]:
                        out.append(("error", f"{name}: variable {t} used but not defined in this car (reads as 0)"))
        _walk({k: x for k, x in part.items() if k not in ("variables", "information")}, name, var)
        for k, x in part.items():
            if isinstance(x, list):
                for row in x:
                    if isinstance(row, list):
                        for c in row:
                            var(None, c, None)
    return out


def config_trees(parts, main_part, mod):
    """(label, tree, variables, missing slots) for the default car, every
    configuration, and every optional part fitted to the default car."""
    defaults = {}
    for _, p in parts.values():
        for r in jbeam.table_rows(p.get("variables", [])):
            defaults[r["name"]] = r.get("default", 0)
    out = []
    tree, missing = default_tree(parts, main_part)
    out.append(("default", tree, dict(defaults), missing, {}))
    used = {n for n, _ in tree}
    for pc in sorted(glob.glob(f"vehicles/{mod}/*.pc")):
        try:
            cfg = jbeam.load(pc)
        except jbeam.JbeamError:
            continue
        over = {k: v for k, v in (cfg.get("parts") or {}).items() if v}
        t, m = default_tree(parts, main_part, over)
        out.append((os.path.basename(pc)[:-3], t, {**defaults, **(cfg.get("vars") or {})}, m, over))
        used |= {n for n, _ in t}
    slot_types = set()
    for _, p in parts.values():
        for r in jbeam.table_rows(p.get("slots", [])):
            slot_types.add(r.get("type"))
        for r in jbeam.table_rows(p.get("slots2", [])):
            slot_types.add(r.get("name"))
    for name, (f, p) in sorted(parts.items()):
        st = p.get("slotType")
        if name in used or st == "main":
            continue
        if st not in slot_types:
            out.append((f"part {name}", None, None, None, {"_unused": st}))
            continue
        t, m = default_tree(parts, main_part, {st: name})
        if name in {n for n, _ in t}:
            out.append((f"with {name}", t, dict(defaults), m, {st: name}))
        else:
            out.append((f"part {name}", None, None, None, {"_unreached": st}))
    return out


def check_references(parts, main_part, variables, mod, dirs, actions, rep):
    electrics = set(BASE_ELECTRICS)
    for d in dirs:
        for f in glob.glob(os.path.join(d, "lua", "**", "*.lua"), recursive=True):
            for a, b in LUA_ELECTRIC.findall(open(f, encoding="utf-8", errors="replace").read()):
                electrics.add(a or b)
    found = {}                                  # (level, message) -> [cars]
    cars = []
    for label, tree, vars_, missing, over in config_trees(parts, main_part, mod):
        if tree is None:
            why = over.get("_unused") or over.get("_unreached")
            rep.note(f"{label}: slot type {why!r} is offered by no part the car can reach (part never used)")
            continue
        cars.append(label)
        for owner, stype, choice in missing:
            if stype in over:                   # (slot defaults: reported above)
                found.setdefault(("error", f"slot {stype} in {owner} -> unknown part {choice}"), []).append(label)
        info = tree_info(tree, parts, vars_)
        for key in dict.fromkeys(tree_refs(tree, parts, info, actions, electrics)):
            found.setdefault(key, []).append(label)
        # slots a configuration sets that its car doesn't have
        have = set()
        for n, _ in tree:
            have |= {r.get("type") for r in jbeam.table_rows(parts[n][1].get("slots", []))}
            have |= {r.get("name") for r in jbeam.table_rows(parts[n][1].get("slots2", []))}
        for slot in over:
            if slot not in have:
                found.setdefault(("warn", f"configuration sets slot {slot}, which its car does not have"), []).append(label)
        cars_lua = lua_check(label, tree, parts, info, vars_, dirs)
        for key in dict.fromkeys(cars_lua):
            found.setdefault(key, []).append(label)
    print(f"references checked in {len(cars)} cars: the default, {sum(not c.startswith('with ') for c in cars) - 1} "
          f"configurations and {sum(c.startswith('with ') for c in cars)} optional parts fitted in turn")
    for (level, msg), where in found.items():
        tag = "" if len(where) == len(cars) else " [%s]" % ", ".join(where[:6] + (["..."] if len(where) > 6 else []))
        (rep.error if level == "error" else rep.warn if level == "warn" else rep.note)(msg + tag)
    # every configuration needs its info file and thumbnail
    for pc in sorted(glob.glob(f"vehicles/{mod}/*.pc")):
        stem = pc[:-3]
        base = os.path.basename(stem)
        if not os.path.exists(os.path.join(os.path.dirname(pc), f"info_{base}.json")):
            rep.warn(f"{base}.pc has no info_{base}.json (listed without a name / description)")
        if not any(os.path.exists(stem + e) for e in (".jpg", ".png")):
            rep.warn(f"{base}.pc has no thumbnail")


# ------------------------------------------------------------ Lua controllers
LUA_RUNNER = os.path.join(HERE, "rb14", "check_controllers.lua")
_lua_missing = []


def _lua(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(float(v))
    if isinstance(v, str):
        return json.dumps(v)
    if isinstance(v, list):
        return "{" + ", ".join(_lua(x) for x in v) + "}"
    if isinstance(v, dict):
        return "{" + ", ".join("[%s] = %s" % (json.dumps(k), _lua(x)) for k, x in v.items()) + "}"
    return "nil"


def _resolve(v, vars_):
    if isinstance(v, str) and v.startswith("$"):
        try:
            return evaluate(v, vars_)
        except (ValueError, SyntaxError, TypeError, NameError):
            return v
    if isinstance(v, list):
        return [_resolve(x, vars_) for x in v]
    if isinstance(v, dict):
        return {k: _resolve(x, vars_) for k, x in v.items()}
    return v


def lua_check(label, tree, parts, info, vars_, dirs):
    """Run the car's own (mod) Lua controllers on its nodes; [(level, msg)]."""
    import shutil
    import subprocess
    import tempfile
    exe = shutil.which("luajit")
    if not exe or not os.path.exists(LUA_RUNNER):
        if not _lua_missing:
            _lua_missing.append(1)
            return [("note", "luajit not found: Lua controllers not run against the cars")]
        return []
    ctrls = []
    for name, _ in tree:
        for r in jbeam.table_rows(parts[name][1].get("controller") or []):
            fn = r.get("fileName")
            files = [os.path.join(d, "lua", "controller", f"{fn}.lua") for d in dirs] if isinstance(fn, str) else []
            path = next((f for f in files if os.path.exists(f)), None)
            if path:
                params = {k: x for k, x in r.items() if k != "fileName"}
                ctrls.append((fn, path, _resolve(params, vars_)))
    if not ctrls:
        return []
    src = ["return {", "nodes = {"]
    for n, (p, _) in info["nodes"].items():
        src.append("  [%s] = {%r, %r, %r}," % (json.dumps(n), *map(float, p)))
    src.append("}, controllers = {")
    for fn, path, params in ctrls:
        src.append("  {name = %s, path = %s, params = %s}," % (json.dumps(fn), json.dumps(path), _lua(params)))
    src.append("}}")
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False) as fh:
        fh.write("\n".join(src))
        car = fh.name
    try:
        res = subprocess.run([exe, LUA_RUNNER, car], capture_output=True, text=True, timeout=60)
    finally:
        os.remove(car)
    out = []
    for line in (res.stdout + res.stderr).splitlines():
        m = re.match(r"^(ERROR|WARN) (.*)$", line)
        if m:
            out.append(("error" if m.group(1) == "ERROR" else "warn", "Lua " + m.group(2)))
    if res.returncode not in (0, 1) and not out:
        out.append(("error", f"Lua controller runner failed: {(res.stderr or res.stdout).strip()[-300:]}"))
    return out


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
