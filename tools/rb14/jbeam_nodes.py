"""Collect node positions and beams from a vehicle's jbeam files.

Resolves what a plain parse leaves open: coordinates written as expressions
("$=($wing_angle_F*0.003)+0.14") are evaluated with the variables' default
values, and parts mounted in a slot with a nodeOffset (the wheels) get the
offset applied, mirrored in x like BeamNG does.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import jbeam  # noqa: E402

_VAR = re.compile(r"\$[A-Za-z_][A-Za-z0-9_]*")


def load_parts(dirs):
    """{part_name: (file, part_dict)} for every .jbeam under dirs."""
    parts = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.jbeam"))):
            for name, part in jbeam.load(f).items():
                parts[name] = (f, part)
    return parts


def variable_defaults(parts):
    out = {}
    for _, part in parts.values():
        for r in jbeam.table_rows(part.get("variables", [])):
            out[r["name"]] = r.get("default", 0)
    return out


def evaluate(v, variables):
    """Evaluate a jbeam value: numbers pass through, "$=expr" is computed."""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str) and v.startswith("$="):
        expr = _VAR.sub(lambda m: repr(float(variables.get(m.group(), 0))), v[2:])
        if not re.fullmatch(r"[0-9eE+\-*/(). ]+", expr):
            raise ValueError(f"unsupported expression {v!r}")
        return float(eval(expr, {"__builtins__": {}}))  # arithmetic only
    if isinstance(v, str) and v.startswith("$"):
        return float(variables[v])
    raise ValueError(f"not a coordinate: {v!r}")


def slot_offsets(parts):
    """{slot type: nodeOffset dict} from every part's slots table."""
    out = {}
    for _, part in parts.values():
        for r in jbeam.table_rows(part.get("slots", [])):
            if isinstance(r.get("nodeOffset"), dict):
                out[r["type"]] = r["nodeOffset"]
    return out


def collect(dirs):
    """(nodes, beams): nodes = {id: dict(pos=(x,y,z), part=..., file=...,
    group=[...], raw=(x,y,z) as written, offset=(ox,oy,oz))}; beams = [(a, b)]."""
    parts = load_parts(dirs)
    variables = variable_defaults(parts)
    offsets = slot_offsets(parts)
    nodes = {}
    beams = []
    for name, (f, part) in parts.items():
        off = offsets.get(part.get("slotType"), {})
        ox, oy, oz = (float(off.get(k, 0.0)) for k in ("x", "y", "z"))
        for r in jbeam.table_rows(part.get("nodes", [])):
            raw = (r["posX"], r["posY"], r["posZ"])
            x, y, z = (evaluate(v, variables) for v in raw)
            sx = 1.0 if x >= 0 else -1.0
            g = r.get("group", [])
            g = [g] if isinstance(g, str) else list(g or [])
            nodes.setdefault(r["id"], dict(pos=(x + sx * ox, y + oy, z + oz), part=name,
                                           file=f, group=[x for x in g if x], raw=raw,
                                           offset=(sx * ox, oy, oz)))
        for r in jbeam.table_rows(part.get("beams", [])):
            a, b = r.get("id1:"), r.get("id2:")
            if isinstance(a, str) and isinstance(b, str):
                beams.append((a, b))
    return nodes, beams
