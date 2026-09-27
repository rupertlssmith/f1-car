"""Minimal reader for the binary glTF (.glb) the RB14 model ships as.

Returns raw primitive data exactly as stored (no library conventions in
between), converted to BeamNG axes:

    glTF: Y up, model nose towards +Z      BeamNG: Z up, nose towards -Y
    (x, y, z)_beamng = (x, -z, y)_gltf

Texture coordinates stay in glTF convention (origin top-left); Collada uses
bottom-left, so callers flip v when writing .dae.
"""
import json
import struct

import numpy as np

_CTYPE = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16,
          5125: np.uint32, 5126: np.float32}
_NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _to_beamng(v):
    return np.c_[v[:, 0], -v[:, 2], v[:, 1]]


def load(path):
    """Returns (prims, images, materials):
    prims     list of dict(material, pos (n,3), nrm (n,3), uv (n,2), tri (m,3))
    images    {name: png bytes}
    materials [dict(name, textures={slot: image name}, factors={...})]"""
    data = open(path, "rb").read()
    magic, _, _ = struct.unpack("<III", data[:12])
    assert magic == 0x46546C67, "not a glb"
    jlen = struct.unpack("<I", data[12:16])[0]
    gl = json.loads(data[20:20 + jlen])
    off = 20 + jlen
    blen = struct.unpack("<I", data[off:off + 4])[0]
    binc = data[off + 8:off + 8 + blen]

    def accessor(i):
        a = gl["accessors"][i]
        bv = gl["bufferViews"][a["bufferView"]]
        dt = np.dtype(_CTYPE[a["componentType"]])
        n = _NCOMP[a["type"]]
        start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = bv.get("byteStride", 0) or dt.itemsize * n
        raw = np.frombuffer(binc, dtype=np.uint8, count=stride * (a["count"] - 1) + dt.itemsize * n,
                            offset=start)
        out = np.lib.stride_tricks.as_strided(raw, shape=(a["count"], dt.itemsize * n),
                                              strides=(stride, 1)).copy().view(dt)
        return out.reshape(a["count"], n).astype(np.float64 if dt.kind == "f" else np.int64)

    def node_matrix(node):
        if "matrix" in node:
            return np.array(node["matrix"]).reshape(4, 4).T
        m = np.eye(4)
        t = node.get("translation", [0, 0, 0])
        q = node.get("rotation", [0, 0, 0, 1])
        s = node.get("scale", [1, 1, 1])
        x, y, z, w = q
        r = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                      [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                      [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
        m[:3, :3] = r * np.array(s)
        m[:3, 3] = t
        return m

    mats = []
    for m in gl.get("materials", []):
        tex = {}
        pbr = m.get("pbrMetallicRoughness", {})

        def img_of(ref):
            if ref is None:
                return None
            t = gl["textures"][ref["index"]]
            return gl["images"][t["source"]]["name"]

        tex["baseColor"] = img_of(pbr.get("baseColorTexture"))
        tex["metallicRoughness"] = img_of(pbr.get("metallicRoughnessTexture"))
        tex["normal"] = img_of(m.get("normalTexture"))
        spec = m.get("extensions", {}).get("KHR_materials_specular", {})
        tex["specular"] = img_of(spec.get("specularTexture"))
        tex["specularColor"] = img_of(spec.get("specularColorTexture"))
        factors = dict(baseColor=pbr.get("baseColorFactor", [1, 1, 1, 1]),
                       metallic=pbr.get("metallicFactor", 1.0),
                       roughness=pbr.get("roughnessFactor", 1.0),
                       alphaMode=m.get("alphaMode", "OPAQUE"),
                       doubleSided=m.get("doubleSided", False))
        mats.append(dict(name=m["name"], textures={k: v for k, v in tex.items() if v}, factors=factors))

    images = {}
    for im in gl.get("images", []):
        bv = gl["bufferViews"][im["bufferView"]]
        s = bv.get("byteOffset", 0)
        images[im["name"]] = binc[s:s + bv["byteLength"]]

    prims = []

    def walk(ni, parent):
        node = gl["nodes"][ni]
        world = parent @ node_matrix(node)
        if "mesh" in node:
            rot = world[:3, :3]
            nrm_m = np.linalg.inv(rot).T
            for p in gl["meshes"][node["mesh"]]["primitives"]:
                at = p["attributes"]
                pos = accessor(at["POSITION"]) @ rot.T + world[:3, 3]
                nrm = accessor(at["NORMAL"]) @ nrm_m.T if "NORMAL" in at else np.zeros_like(pos)
                nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
                uv = accessor(at["TEXCOORD_0"]) if "TEXCOORD_0" in at else np.zeros((len(pos), 2))
                tri = accessor(p["indices"]).reshape(-1, 3)
                prims.append(dict(material=mats[p["material"]]["name"], pos=_to_beamng(pos),
                                  nrm=_to_beamng(nrm), uv=uv, tri=tri))
        for c in node.get("children", []):
            walk(c, world)

    scene = gl["scenes"][gl.get("scene", 0)]
    for ni in scene["nodes"]:
        walk(ni, np.eye(4))
    return prims, images, mats
