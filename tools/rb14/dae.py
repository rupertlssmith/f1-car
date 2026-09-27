"""Minimal Collada (.dae) reader/writer for BeamNG vehicle meshes.

BeamNG loads vehicle meshes from Collada and finds each flexbody/prop by the
scene node's name; materials are resolved by the Collada material *name*
against the vehicle's *.materials.json. That is all this module models:

    Mesh(name, matrix, prims)
      name    scene node name (what jbeam flexbodies/props refer to)
      matrix  4x4 node transform (numpy), identity for most flexbodies;
              props rotate around their node origin, so theirs matters
      prims   list of Prim(material, attrs) triangle batches, where attrs
              maps (semantic, set) -> float array of shape (n_corners, k),
              e.g. ("POSITION", 0) -> (n, 3), ("TEXCOORD", 0) -> (n, 2).
              Corners come in triples: one triangle per 3 rows.

The writer emits the same layout Blender's Collada exporter produces (Z-up,
metres, one geometry per node, <triangles> per material), which is the
layout the original F4 mesh used and BeamNG is known to load.
"""
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

import numpy as np

NS = "http://www.collada.org/2005/11/COLLADASchema"
_Q = "{%s}" % NS


@dataclass
class Prim:
    material: str
    attrs: dict = field(default_factory=dict)

    @property
    def ntris(self):
        return len(self.attrs[("POSITION", 0)]) // 3


@dataclass
class Mesh:
    name: str
    matrix: np.ndarray
    prims: list

    def world_positions(self):
        """All corner positions with the node matrix applied, (n, 3)."""
        pts = [p.attrs[("POSITION", 0)] for p in self.prims]
        if not pts:
            return np.zeros((0, 3))
        p = np.concatenate(pts)
        return p @ self.matrix[:3, :3].T + self.matrix[:3, 3]


# ----------------------------------------------------------------- reading

def _floats(el):
    return np.array(el.text.split(), dtype=np.float64) if el is not None and el.text else np.zeros(0)


def _ints(el):
    return np.array(el.text.split(), dtype=np.int64) if el is not None and el.text else np.zeros(0, np.int64)


def _source_array(src):
    arr = _floats(src.find(_Q + "float_array"))
    acc = src.find(f"{_Q}technique_common/{_Q}accessor")
    stride = int(acc.get("stride", "1"))
    count = int(acc.get("count", str(len(arr) // stride)))
    return arr[:count * stride].reshape(count, stride)


def _read_geometry(geom, materials):
    mesh = geom.find(_Q + "mesh")
    sources = {s.get("id"): _source_array(s) for s in mesh.findall(_Q + "source")}
    vert_inputs = {}
    for v in mesh.findall(_Q + "vertices"):
        vert_inputs[v.get("id")] = [(i.get("semantic"), i.get("source")[1:])
                                    for i in v.findall(_Q + "input")]
    prims = []
    for tag in ("triangles", "polylist", "polygons"):
        for pl in mesh.findall(_Q + tag):
            inputs = pl.findall(_Q + "input")
            stride = max(int(i.get("offset", "0")) for i in inputs) + 1
            if tag == "polygons":
                idx = np.concatenate([_ints(p) for p in pl.findall(_Q + "p")])
                vcount = np.array([len(_ints(p)) // stride for p in pl.findall(_Q + "p")])
            else:
                idx = _ints(pl.find(_Q + "p"))
                vcount = (_ints(pl.find(_Q + "vcount")) if tag == "polylist"
                          else np.full(len(idx) // stride // 3, 3))
            idx = idx.reshape(-1, stride)
            # fan-triangulate polygons into corner indices
            corners = []
            start = 0
            for n in vcount:
                for k in range(1, n - 1):
                    corners += [start, start + k, start + k + 1]
                start += n
            corners = np.array(corners, dtype=np.int64)
            attrs = {}
            for i in inputs:
                sem = i.get("semantic")
                off = int(i.get("offset", "0"))
                sset = int(i.get("set", "0"))
                src = i.get("source")[1:]
                rows = idx[corners, off]
                if sem == "VERTEX":
                    for vsem, vsrc in vert_inputs[src]:
                        attrs[(vsem, 0)] = sources[vsrc][rows]
                else:
                    attrs[(sem, sset)] = sources[src][rows]
            symbol = pl.get("material")
            prims.append(Prim(materials.get(symbol, symbol), attrs))
    return prims


def read(path):
    """Read a .dae into a list of Mesh (only nodes with geometry)."""
    root = ET.parse(path).getroot()
    mat_names = {m.get("id"): m.get("name") or m.get("id")
                 for m in root.iter(_Q + "material")}
    geoms = {g.get("id"): g for g in root.iter(_Q + "geometry")}
    out = []

    def walk(node, parent):
        m = np.eye(4)
        mt = node.find(_Q + "matrix")
        if mt is not None:
            m = _floats(mt).reshape(4, 4)
        for tr in node.findall(_Q + "translate"):
            t = np.eye(4)
            t[:3, 3] = _floats(tr)
            m = m @ t
        world = parent @ m
        for ig in node.findall(_Q + "instance_geometry"):
            symbols = {}
            for im in ig.iter(_Q + "instance_material"):
                symbols[im.get("symbol")] = mat_names.get(im.get("target")[1:], im.get("target")[1:])
            prims = _read_geometry(geoms[ig.get("url")[1:]], symbols)
            out.append(Mesh(node.get("name") or node.get("id"), world, prims))
        for child in node.findall(_Q + "node"):
            walk(child, world)

    for vs in root.iter(_Q + "visual_scene"):
        for node in vs.findall(_Q + "node"):
            walk(node, np.eye(4))
    return out


# ----------------------------------------------------------------- writing

def _fmt(a):
    return " ".join(f"{x:.6g}" for x in np.asarray(a).ravel())


def _xml_id(s):
    return "".join(c if c.isalnum() or c in "_-." else "_" for c in s)


def write(path, meshes, author="f1-car tools/rb14"):
    """Write meshes to a Blender-style Collada 1.4.1 file."""
    materials = sorted({p.material for m in meshes for p in m.prims})
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           f'<COLLADA xmlns="{NS}" version="1.4.1">',
           "  <asset>",
           f"    <contributor><author>{author}</author><authoring_tool>{author}</authoring_tool></contributor>",
           "    <created>2000-01-01T00:00:00</created><modified>2000-01-01T00:00:00</modified>",
           '    <unit name="meter" meter="1"/>',
           "    <up_axis>Z_UP</up_axis>",
           "  </asset>",
           "  <library_effects>"]
    for mat in materials:
        mid = _xml_id(mat)
        out.append(f'    <effect id="{mid}-effect"><profile_COMMON><technique sid="common"><lambert>'
                   '<diffuse><color sid="diffuse">0.8 0.8 0.8 1</color></diffuse>'
                   "</lambert></technique></profile_COMMON></effect>")
    out.append("  </library_effects>")
    out.append("  <library_materials>")
    for mat in materials:
        mid = _xml_id(mat)
        out.append(f'    <material id="{mid}-material" name="{mat}"><instance_effect url="#{mid}-effect"/></material>')
    out.append("  </library_materials>")
    out.append("  <library_geometries>")
    for m in meshes:
        gid = _xml_id(m.name) + "-mesh"
        out.append(f'    <geometry id="{gid}" name="{m.name}"><mesh>')
        # one set of sources per attribute, concatenated over prims
        keys = []
        for p in m.prims:
            for k in p.attrs:
                if k not in keys:
                    keys.append(k)
        keys.sort(key=lambda k: (["POSITION", "NORMAL", "TEXCOORD", "COLOR"].index(k[0])
                                 if k[0] in ("POSITION", "NORMAL", "TEXCOORD", "COLOR") else 9, k[1]))
        ranges = []
        for k in keys:
            arrs = []
            for p in m.prims:
                a = p.attrs.get(k)
                if a is None:   # pad missing attributes so offsets line up
                    width = next(q.attrs[k].shape[1] for q in m.prims if k in q.attrs)
                    a = np.zeros((len(p.attrs[("POSITION", 0)]), width))
                arrs.append(a)
            data = np.concatenate(arrs)
            sid = f"{gid}-{k[0].lower()}{k[1]}"
            width = data.shape[1]
            params = {3: "XYZ", 2: "ST", 4: "RGBA"}.get(width, "XYZW"[:width])
            if k[0] == "COLOR" and width == 3:
                params = "RGB"
            out.append(f'      <source id="{sid}"><float_array id="{sid}-array" count="{data.size}">{_fmt(data)}</float_array>'
                       f'<technique_common><accessor source="#{sid}-array" count="{len(data)}" stride="{width}">'
                       + "".join(f'<param name="{c}" type="float"/>' for c in params) +
                       "</accessor></technique_common></source>")
            ranges.append((k, sid))
        out.append(f'      <vertices id="{gid}-vertices"><input semantic="POSITION" source="#{gid}-position0"/></vertices>')
        start = 0
        for p in m.prims:
            n = len(p.attrs[("POSITION", 0)])
            ins = []
            for off, (k, sid) in enumerate(ranges):
                if k == ("POSITION", 0):
                    ins.append(f'<input semantic="VERTEX" source="#{gid}-vertices" offset="{off}"/>')
                else:
                    setattr_ = f' set="{k[1]}"' if k[0] in ("TEXCOORD", "COLOR") else ""
                    ins.append(f'<input semantic="{k[0]}" source="#{sid}" offset="{off}"{setattr_}/>')
            idx = np.repeat(np.arange(start, start + n)[:, None], len(ranges), axis=1)
            out.append(f'      <triangles material="{_xml_id(p.material)}-material" count="{n // 3}">'
                       + "".join(ins) + f"<p>{' '.join(map(str, idx.ravel()))}</p></triangles>")
            start += n
        out.append("    </mesh></geometry>")
    out.append("  </library_geometries>")
    out.append('  <library_visual_scenes><visual_scene id="Scene" name="Scene">')
    for m in meshes:
        gid = _xml_id(m.name) + "-mesh"
        binds = "".join(
            f'<instance_material symbol="{_xml_id(mat)}-material" target="#{_xml_id(mat)}-material">'
            '<bind_vertex_input semantic="UV1" input_semantic="TEXCOORD" input_set="0"/></instance_material>'
            for mat in sorted({p.material for p in m.prims}))
        out.append(f'    <node id="{_xml_id(m.name)}" name="{m.name}" type="NODE">'
                   f'<matrix sid="transform">{_fmt(m.matrix)}</matrix>'
                   f'<instance_geometry url="#{gid}" name="{m.name}"><bind_material><technique_common>{binds}'
                   "</technique_common></bind_material></instance_geometry></node>")
    out.append('  </visual_scene></library_visual_scenes>')
    out.append('  <scene><instance_visual_scene url="#Scene"/></scene>')
    out.append("</COLLADA>")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
