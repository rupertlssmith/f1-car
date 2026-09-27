#!/usr/bin/env python3
"""Re-fit the redbull jbeam onto the RB14 body.

Rewrites, in place, every coordinate in vehicles/redbull/*.jbeam that comes
from the Carbonworks F4: node positions, the wheel slots' nodeOffset, the
absolute flexbody positions (brakes, wing pivots), the wheel/tyre mesh
offsets and the internal cameras. New values are always computed from the
untouched originals in vehicles/fr04 (matched by node id / mesh name), so
running this again gives the same result - it never compounds.

Coordinates written as expressions ("$=($wing_angle_F*0.003)+0.14") stay
expressions, rescaled by the map's local slope so their tuning variable
keeps working.

Anything not present in the F4 (parts added later for the RB14) is left
alone.

    python3 tools/rb14/fit_jbeam.py [--check]   # --check: report, don't write
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import fitmap  # noqa: E402
import jbeam  # noqa: E402
import jbeam_nodes  # noqa: E402

SRC_DIRS = ["vehicles/fr04", "vehicles/common/fr04_wheels"]
DST_DIRS = ["vehicles/redbull", "vehicles/common/redbull_wheels"]

# RB14 wheel centres (measured from rb14.glb): |x|, y, z
WHEEL_CENTRE = {"F": (0.7925, -1.5247, 0.3377), "R": (0.789, 2.03, 0.3347)}
# Cameras placed from the RB14 itself rather than mapped from the F4: the
# driver's eye sits under the halo, just ahead of the headrest.
CAMERA_OVERRIDE = {"dash": (0.0, -0.08, 0.80)}
# Nodes placed by hand instead of by the map. The F4's front wing endplates
# run back beside its narrow front tyres; mapped, their rear nodes end up
# 15 cm behind the RB14 endplate (y -1.963) and inside the 305 mm tyres'
# steering sweep, so the tyres hit invisible endplate collision triangles
# and bend the wing. Put them on the RB14 endplate's rear edge.
NODE_OVERRIDE = {
    "fep2r": (-0.862, -1.975, 0.100), "fep4r": (-0.862, -1.975, 0.290),
    "fep2l": (0.862, -1.975, 0.100), "fep4l": (0.862, -1.975, 0.290),
    # rear floor / diffuser edges: mapped, they sit 20-50 mm inside the 405 mm
    # rear tyres' inner face; ~10 cm clearance leaves room for tyre bulge and
    # suspension compliance
    "fl4r": (-0.520, 1.378, 0.164), "fl4l": (0.520, 1.378, 0.164),
    "fl5r": (-0.460, 2.045, 0.201), "fl5l": (0.460, 2.045, 0.201),
}
# Mirror view origins: offsets (vehicle axes) from the mirror's reference
# node to the centre of the RB14 mirror glass.
MIRROR_OFFSET = {"redbull_mirror_R": (-0.14, 0.06, 0.571), "redbull_mirror_L": (0.138, 0.06, 0.571)}
MIRROR_ROW = re.compile(r'(\[\s*"(redbull_mirror_[LR])"[^\n]*?"refBaseTranslation"\s*:\s*\{\s*"x"\s*:\s*)(-?[\d.]+)(\s*,\s*"y"\s*:\s*)(-?[\d.]+)(\s*,\s*"z"\s*:\s*)(-?[\d.]+)')

# Wheel parts put their axle nodes at |x| 0.33 and 0.60 (mid 0.465) relative
# to the slot's nodeOffset; the wheel/tyre meshes are centred on the tyre.
AXLE_MID = 0.465

NUM = r"-?(?:\d+\.?\d*|\.\d+)"
VAL = rf'(?:{NUM}|"\$=[^"]*")'
NODE_ROW = re.compile(rf'(\[\s*"([A-Za-z0-9_.\-]+)"\s*,\s*)({VAL})(\s*,\s*)({VAL})(\s*,\s*)({VAL})')
NODE_OFFSET = re.compile(r'("nodeOffset"\s*:\s*\{\s*"x"\s*:\s*)(' + NUM + r')(\s*,\s*"y"\s*:\s*)(' + NUM +
                         r')(\s*,\s*"z"\s*:\s*)(' + NUM + r')')
FLEX_POS = re.compile(r'(\[\s*"([A-Za-z0-9_.\-]+)"\s*,\s*(\[[^\]]*\])[^\n]*?"pos"\s*:\s*\{\s*"x"\s*:\s*)(' + NUM +
                      r')(\s*,\s*"y"\s*:\s*)(' + NUM + r')(\s*,\s*"z"\s*:\s*)(' + NUM + r')')


def fmt(v):
    s = f"{v:.4f}".rstrip("0")
    return s + "0" if s.endswith(".") else s


def mapped_value(raw, axis, p_orig, p_new, variables):
    """New text for one coordinate. raw is the F4's value as written."""
    if isinstance(raw, str) and raw.startswith("$="):
        v0 = jbeam_nodes.evaluate(raw, variables)
        a = fitmap.local_slope(axis, p_orig)
        b = p_new[axis] - a * v0
        return f'"$=({raw[2:]})*{fmt(a)}+{fmt(b)}"'
    return fmt(p_new[axis])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report changes only")
    args = ap.parse_args()
    os.chdir(REPO)

    src_nodes, _ = jbeam_nodes.collect(SRC_DIRS)
    src_parts = jbeam_nodes.load_parts(SRC_DIRS)
    variables = jbeam_nodes.variable_defaults(src_parts)
    offsets = jbeam_nodes.slot_offsets(src_parts)
    offset_slots = set(offsets)

    # absolute flexbody positions in the F4, keyed by (mesh, side, groups):
    # front and rear brakes share mesh names and differ only by group
    def flex_key(groups):
        if isinstance(groups, str):
            groups = re.findall(r'"([^"]*)"', groups)
        return tuple(g.replace("fr04", "redbull") for g in groups)

    flex_pos = {}
    for pname, (f, part) in src_parts.items():
        if part.get("slotType") in offset_slots:
            continue   # wheel/tyre meshes are positioned relative; see below
        for r in jbeam.table_rows(part.get("flexbodies", [])):
            pos = r.get("pos")
            if isinstance(pos, dict):
                p = tuple(jbeam_nodes.evaluate(pos[k], variables) for k in "xyz")
                flex_pos[(r["mesh"].replace("fr04", "redbull"), p[0] >= 0, flex_key(r.get("[group]:") or []))] = p

    cameras = {}
    for _, (f, part) in src_parts.items():
        for r in jbeam.table_rows(part.get("camerasInternal", [])):
            cameras[r["type"]] = (r["x"], r["y"], r["z"])

    changed = 0
    seen = set()
    for d in DST_DIRS:
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".jbeam"):
                continue
            path = os.path.join(d, fn)
            text = open(path, encoding="utf-8", newline="").read()   # keep CRLF
            new = text
            wheel_file = "wheels" in fn or "tires" in fn

            def node_sub(m):
                nid = m.group(2)
                if nid in cameras and not wheel_file:
                    p = tuple(float(v) for v in cameras[nid])
                    q = CAMERA_OVERRIDE.get(nid) or fitmap.map_point(p)
                    return f"{m.group(1)}{fmt(q[0])}{m.group(4)}{fmt(q[1])}{m.group(6)}{fmt(q[2])}"
                n = src_nodes.get(nid)
                if n is None or wheel_file or any(abs(c) > 0 for c in n["offset"]):
                    return m.group(0)
                p = n["pos"]
                if nid in NODE_OVERRIDE:
                    q = NODE_OVERRIDE[nid]
                    return f"{m.group(1)}{fmt(q[0])}{m.group(4)}{fmt(q[1])}{m.group(6)}{fmt(q[2])}"
                q = fitmap.map_point(p)
                vals = [mapped_value(n["raw"][i], i, p, q, variables) for i in range(3)]
                return f"{m.group(1)}{vals[0]}{m.group(4)}{vals[1]}{m.group(6)}{vals[2]}"

            new = NODE_ROW.sub(node_sub, new)

            def offset_sub(m):
                # which axle? front offsets have negative y in the F4
                axle = "F" if float(m.group(4)) < 0 else "R"
                cx, cy, cz = WHEEL_CENTRE[axle]
                return (f"{m.group(1)}{fmt(cx - AXLE_MID)}{m.group(3)}{fmt(cy)}{m.group(5)}{fmt(cz)}")

            new = NODE_OFFSET.sub(offset_sub, new)

            def flex_sub(m):
                mesh = m.group(2)
                x_old = float(m.group(4))
                if wheel_file:
                    # wheel and tyre meshes: centred on the tyre, which sits
                    # AXLE_MID outboard of the slot offset
                    x = AXLE_MID if x_old >= 0 else -AXLE_MID
                    return f"{m.group(1)}{fmt(x)}{m.group(5)}0.0{m.group(7)}0.0"
                p = flex_pos.get((mesh, x_old >= 0, flex_key(m.group(3))))
                if p is None:
                    return m.group(0)
                q = fitmap.map_point(p)
                return f"{m.group(1)}{fmt(q[0])}{m.group(5)}{fmt(q[1])}{m.group(7)}{fmt(q[2])}"

            new = FLEX_POS.sub(flex_sub, new)
            new = MIRROR_ROW.sub(lambda m: "".join([m.group(1), fmt(MIRROR_OFFSET[m.group(2)][0]), m.group(4),
                                                    fmt(MIRROR_OFFSET[m.group(2)][1]), m.group(6),
                                                    fmt(MIRROR_OFFSET[m.group(2)][2])]), new)
            if wheel_file:
                # physics wheel centred between the axle nodes, like the mesh
                new = re.sub(r'("wheelOffset"\s*:\s*)' + NUM, r"\g<1>0.0", new)
            for m in NODE_ROW.finditer(new):
                if m.group(2) in src_nodes:
                    seen.add(m.group(2))

            if new != text:
                changed += 1
                print(("would update " if args.check else "updated ") + path)
                if not args.check:
                    with open(path, "w", encoding="utf-8", newline="") as fh:
                        fh.write(new)
    missing = sorted(set(src_nodes) - seen)
    if missing:
        print("WARNING: F4 nodes not found in the redbull jbeam:", " ".join(missing))
    print(f"{changed} file(s) {'need' if args.check else 'got'} changes")


if __name__ == "__main__":
    main()
