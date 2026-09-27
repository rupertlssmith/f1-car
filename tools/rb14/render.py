"""Render preview images of a vehicle model with Blender (headless, Cycles CPU).

    blender -b --factory-startup --python tools/rb14/render.py -- \
        --model model.glb [--model other.glb] --out plans/previews/name \
        [--nodes nodes.json] [--views side,top,front,rear,three_quarter] \
        [--size 1400x800] [--samples 24] [--xray]

--model   glTF files to load (BeamNG axes: Z up, nose towards -Y).
--nodes   JSON {"nodes": [[x, y, z], ...], "beams": [[i, j], ...]} drawn as
          small spheres (and thin lines) over the model, to check that the
          jbeam lines up with the mesh.
--xray    make the model semi-transparent so nodes inside it show.
Writes <out>_<view>.png per view.
"""
import argparse
import json
import math
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument("--model", action="append", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--nodes")
ap.add_argument("--views", default="side,top,front,rear,three_quarter")
ap.add_argument("--size", default="1400x800")
ap.add_argument("--samples", type=int, default=24)
ap.add_argument("--xray", action="store_true")
ap.add_argument("--camera", help="extra 'close' view: camera position x,y,z (BeamNG axes)")
ap.add_argument("--target", help="point the 'close' view looks at, x,y,z")
ap.add_argument("--vertex-colors", action="store_true", help="shade meshes by their colour attribute")
args = ap.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
for path in args.model:
    bpy.ops.import_scene.gltf(filepath=path)
meshes = [o for o in scene.objects if o.type == "MESH"]

if args.vertex_colors:
    vc = bpy.data.materials.new("vertex_colour")
    vc.use_nodes = True
    nt = vc.node_tree
    attr = nt.nodes.new("ShaderNodeVertexColor")
    nt.links.new(attr.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.6
    for o in meshes:
        if o.data.color_attributes:
            attr.layer_name = o.data.color_attributes[0].name
            o.data.materials.clear()
            o.data.materials.append(vc)

if args.xray:
    for m in bpy.data.materials:
        if not m.use_nodes:
            continue
        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs["Alpha"].default_value = 0.18
            for l in list(bsdf.inputs["Alpha"].links):
                m.node_tree.links.remove(l)
        m.blend_method = "BLEND"

if args.nodes:
    data = json.load(open(args.nodes))
    mat = bpy.data.materials.new("node_mat")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (1.0, 0.05, 0.6, 1)
    b.inputs["Emission Color"].default_value = (1.0, 0.05, 0.6, 1)
    b.inputs["Emission Strength"].default_value = 2.0
    bmat = bpy.data.materials.new("beam_mat")
    bmat.use_nodes = True
    bb = bmat.node_tree.nodes["Principled BSDF"]
    bb.inputs["Base Color"].default_value = (0.0, 0.9, 1.0, 1)
    bb.inputs["Emission Color"].default_value = (0.0, 0.9, 1.0, 1)
    bb.inputs["Emission Strength"].default_value = 1.0
    # one mesh of instanced spheres keeps this fast for a few hundred nodes
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, segments=10, ring_count=6)
    proto = bpy.context.object
    proto.data.materials.append(mat)
    for p in data.get("nodes", []):
        o = proto.copy()
        o.location = p
        scene.collection.objects.link(o)
    bpy.data.objects.remove(proto)
    pts = data.get("nodes", [])
    if data.get("beams"):
        cu = bpy.data.curves.new("beams", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = 0.0035
        for i, j in data["beams"]:
            if i == j:
                continue
            sp = cu.splines.new("POLY")
            sp.points.add(1)
            sp.points[0].co = (*pts[i], 1.0)
            sp.points[1].co = (*pts[j], 1.0)
        ob = bpy.data.objects.new("beams", cu)
        scene.collection.objects.link(ob)
        cu.materials.append(bmat)

# bounds of the model
lo = Vector((1e9, 1e9, 1e9))
hi = Vector((-1e9, -1e9, -1e9))
for o in meshes:
    for c in o.bound_box:
        w = o.matrix_world @ Vector(c)
        lo = Vector(map(min, lo, w))
        hi = Vector(map(max, hi, w))
center = (lo + hi) / 2
size = hi - lo

scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = False
w, h = (int(v) for v in args.size.split("x"))
scene.render.resolution_x, scene.render.resolution_y = w, h
scene.render.film_transparent = False
world = bpy.data.worlds.new("w")
scene.world = world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.82, 0.84, 0.88, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0

sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
sun.data.energy = 3.0
sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(30))
scene.collection.objects.link(sun)

cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
scene.collection.objects.link(cam)
scene.camera = cam
cam.data.type = "ORTHO"

VIEWS = {
    # name: (direction from centre to camera, ortho?)
    "side": (Vector((1, 0, 0)), True),
    "top": (Vector((0, 0, 1)), True),
    "front": (Vector((0, -1, 0)), True),
    "rear": (Vector((0, 1, 0)), True),
    "three_quarter": (Vector((1.0, -1.3, 0.8)).normalized(), False),
}
aspect = w / h
views = args.views.split(",") + (["close"] if args.camera else [])
for name in views:
    if name == "close":
        cam.data.type = "PERSP"
        cam.data.lens = 35
        cam.location = Vector([float(v) for v in args.camera.split(",")])
        tgt = Vector([float(v) for v in args.target.split(",")])
        cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{args.out}_{name}.png"
        bpy.ops.render.render(write_still=True)
        continue
    d, ortho = VIEWS[name]
    cam.data.type = "ORTHO" if ortho else "PERSP"
    if ortho:
        # fit the model's extent perpendicular to the view direction
        if name == "side":
            span_w, span_h = size.y, size.z
        elif name == "top":
            span_w, span_h = size.y, size.x
        else:
            span_w, span_h = size.x, size.z
        cam.data.ortho_scale = max(span_w, span_h * aspect) * 1.08
        cam.location = center + d * 10
    else:
        cam.data.lens = 50
        cam.location = center + d * (max(size) * 1.9)
    # explicit camera orientations: nose (-Y) on the left in side/top views
    fixed = {"side": (90, 0, 90), "top": (0, 0, 90), "front": (90, 0, 0), "rear": (90, 0, 180)}
    if name in fixed:
        cam.rotation_euler = tuple(math.radians(a) for a in fixed[name])
    else:
        cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = f"{args.out}_{name}.png"
    bpy.ops.render.render(write_still=True)
    print("RENDERED", scene.render.filepath)
