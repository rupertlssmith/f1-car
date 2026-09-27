#!/usr/bin/env python3
"""Assemble the built mod's meshes into a textured .glb for preview renders.

    python3 tools/rb14/preview.py OUT.glb [--nodes OUT_NODES.json]

Reads what the game will read - vehicles/redbull/*.dae, the wheels .dae,
*.materials.json and the texture files they name - and places the wheels
and the pivoted wings where the jbeam puts them, so a render of the result
shows the car as built (not as the source model). Materials whose textures
are not PNG files in the mod (base-game or DDS-only) render flat grey.

--nodes also writes the jbeam's node positions and beams (default config) as
JSON for render.py --nodes.
"""
import argparse
import glob
import json
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import dae  # noqa: E402
import jbeam  # noqa: E402
import jbeam_nodes  # noqa: E402

MOD = "vehicles/redbull"
WHEELS = "vehicles/common/redbull_wheels"


def load_materials():
    mats = {}
    for f in glob.glob(f"{MOD}/*.materials.json") + glob.glob(f"{WHEELS}/*.materials.json"):
        for k, v in jbeam.load(f).items():
            if isinstance(v, dict):
                mats[v.get("mapTo", k)] = v
    return mats


def part_offsets(parts):
    """{part: nodeOffset dict}: a slot's nodeOffset applies to the part in
    it and everything below it in the slot tree (the tyres sit in a slot of
    the wheel part, which sits in the offset wheel slot)."""
    out = {}

    def visit(name, off):
        out[name] = off
        for r in jbeam.table_rows(parts[name][1].get("slots", [])):
            child = r.get("default")
            if child and child in parts:
                visit(child, r["nodeOffset"] if isinstance(r.get("nodeOffset"), dict) else off)
        # alternatives that are not defaults inherit through their slot type
        return out

    main = next(n for n, (_, p) in parts.items() if p.get("slotType") == "main")
    visit(main, {})
    # non-default parts: same offset as the default part of their slot type
    by_type = {parts[n][1].get("slotType"): o for n, o in out.items()}
    for n, (_, p) in parts.items():
        out.setdefault(n, by_type.get(p.get("slotType"), {}))
    return out


def flexbody_placements(parts, variables, offsets):
    """{mesh: [(pos, rot_z_180)]} for flexbodies with an explicit pos."""
    out = {}
    for pname, (f, part) in parts.items():
        off = offsets.get(pname, {})
        for r in jbeam.table_rows(part.get("flexbodies", [])):
            pos = r.get("pos")
            if not isinstance(pos, dict):
                continue
            p = np.array([jbeam_nodes.evaluate(pos.get(k, 0), variables) for k in "xyz"])
            sx = 1.0 if p[0] >= 0 else -1.0
            p = p + np.array([sx * float(off.get("x", 0)), float(off.get("y", 0)), float(off.get("z", 0))])
            rz = jbeam_nodes.evaluate((r.get("rot") or {}).get("z", 0), variables)
            out.setdefault(r["mesh"], []).append((p, abs(abs(rz) - 180) < 1e-6))
    return out


def write_glb(path, items, mats):
    """items: [(name, material, pos (n,3) beamng, nrm, uv collada)]"""
    blob = bytearray()
    views, accessors, meshes, nodes, gl_mats, images, textures = [], [], [], [], [], [], []
    mat_index, img_index = {}, {}

    def add_view(data, target=None):
        while len(blob) % 4:
            blob.append(0)
        views.append({"buffer": 0, "byteOffset": len(blob), "byteLength": len(data), **({"target": target} if target else {})})
        blob.extend(data)
        return len(views) - 1

    def add_acc(arr, typ):
        arr = np.ascontiguousarray(arr, dtype=np.float32)
        v = add_view(arr.tobytes(), 34962)
        acc = {"bufferView": v, "componentType": 5126, "count": len(arr), "type": typ}
        if typ == "VEC3":
            acc["min"] = arr.min(0).tolist()
            acc["max"] = arr.max(0).tolist()
        accessors.append(acc)
        return len(accessors) - 1

    def material(name):
        if name in mat_index:
            return mat_index[name]
        m = mats.get(name, {})
        if name == "__highlight__":
            m = {"Stages": [{"baseColorMap": "", "baseColorFactor": [1, 0, 0.8, 1]}]}
        st = (m.get("Stages") or [{}])[0]
        pbr = {"metallicFactor": float(st.get("metallicFactor", 0)), "roughnessFactor": float(st.get("roughnessFactor", 0.6)),
               "baseColorFactor": st.get("baseColorFactor", [1, 1, 1, 1]) if (st.get("baseColorMap") or name == "__highlight__") else [0.55, 0.55, 0.57, 1]}
        tex = (st.get("baseColorMap") or "").lstrip("/")
        if tex and os.path.exists(tex) and tex.endswith(".png"):
            if tex not in img_index:
                images.append({"bufferView": add_view(open(tex, "rb").read()), "mimeType": "image/png"})
                textures.append({"source": len(images) - 1})
                img_index[tex] = len(textures) - 1
            pbr["baseColorTexture"] = {"index": img_index[tex]}
        elif tex:
            pbr["baseColorFactor"] = [0.35, 0.35, 0.37, 1]
        g = {"name": name, "pbrMetallicRoughness": pbr, "doubleSided": True}
        if m.get("alphaTest"):
            g["alphaMode"] = "MASK"
            g["alphaCutoff"] = float(m.get("alphaRef", 127)) / 255
        elif m.get("translucent"):
            g["alphaMode"] = "BLEND"
        gl_mats.append(g)
        mat_index[name] = len(gl_mats) - 1
        return mat_index[name]

    for name, mat, pos, nrm, uv in items:
        # BeamNG (x, y, z) -> glTF (x, z, -y); Collada v -> glTF v
        P = np.c_[pos[:, 0], pos[:, 2], -pos[:, 1]]
        N = np.c_[nrm[:, 0], nrm[:, 2], -nrm[:, 1]]
        T = np.c_[uv[:, 0], 1.0 - uv[:, 1]]
        prim = {"attributes": {"POSITION": add_acc(P, "VEC3"), "NORMAL": add_acc(N, "VEC3"),
                               "TEXCOORD_0": add_acc(T, "VEC2")}, "material": material(mat)}
        meshes.append({"name": name, "primitives": [prim]})
        nodes.append({"name": name, "mesh": len(meshes) - 1})
    gl = {"asset": {"version": "2.0", "generator": "f1-car tools/rb14/preview.py"},
          "scene": 0, "scenes": [{"nodes": list(range(len(nodes)))}], "nodes": nodes, "meshes": meshes,
          "materials": gl_mats, "accessors": accessors, "bufferViews": views,
          "buffers": [{"byteLength": len(blob)}]}
    if images:
        gl["images"] = images
        gl["textures"] = textures
    js = json.dumps(gl).encode()
    js += b" " * (-len(js) % 4)
    blob += b"\0" * (-len(blob) % 4)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(blob)))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        fh.write(struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out")
    ap.add_argument("--nodes")
    ap.add_argument("--highlight", help="comma list of mesh-name prefixes to paint magenta, or 'f4' for the carried-over F4 meshes")
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    nodes_out = os.path.abspath(args.nodes) if args.nodes else None
    os.chdir(REPO)

    parts = jbeam_nodes.load_parts([MOD, WHEELS])
    variables = jbeam_nodes.variable_defaults(parts)
    placements = flexbody_placements(parts, variables, part_offsets(parts))
    mats = load_materials()

    # default-configuration wheel/tyre meshes only
    shown = {"redbull_wheel_01a_13x8", "redbull_wheel_01a_13x10", "redbull_tire_01a_F", "redbull_tire_01a_R"}
    items = []
    for f in sorted(glob.glob(f"{MOD}/*.dae") + glob.glob(f"{WHEELS}/*.dae")):
        for m in dae.read(f):
            wheel = f.startswith(WHEELS)
            if wheel and m.name not in shown:
                continue
            places = placements.get(m.name) if (wheel or m.name.startswith("redbull_wing_")) else None
            for p, mirrored in (places or [(np.zeros(3), False)]):
                for prim in m.prims:
                    P = prim.attrs[("POSITION", 0)] @ m.matrix[:3, :3].T + m.matrix[:3, 3]
                    N = prim.attrs.get(("NORMAL", 0), np.zeros_like(P)) @ m.matrix[:3, :3].T
                    if mirrored:
                        P = P * np.array([-1, -1, 1])
                        N = N * np.array([-1, -1, 1])
                    mat = prim.material
                    if args.highlight and ((args.highlight == "f4" and not mat.startswith("rb14_") and mat not in ("mirror", "redbull_screen"))
                                           or any(m.name.startswith(h) for h in args.highlight.split(",") if h != "f4")):
                        mat = "__highlight__"
                    items.append((m.name, mat, P + p, N,
                                  prim.attrs.get(("TEXCOORD", 0), np.zeros((len(P), 2)))))
    write_glb(out, items, mats)
    print(f"wrote {out}: {len(items)} primitives")

    if nodes_out:
        nodes, beams = jbeam_nodes.collect([MOD, WHEELS])
        ids = sorted(nodes)
        idx = {k: i for i, k in enumerate(ids)}
        json.dump({"nodes": [list(nodes[k]["pos"]) for k in ids],
                   "beams": [[idx[a], idx[b]] for a, b in beams if a in idx and b in idx]}, open(nodes_out, "w"))
        print(f"wrote {nodes_out}: {len(ids)} nodes")


if __name__ == "__main__":
    main()
