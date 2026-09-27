"""RB14 materials: source material -> BeamNG material name, and the BeamNG
material definitions plus their textures.

Textures are written as PNG with BeamNG's naming convention
(<name>_b.color.png for sRGB colour, _n.normal.png for normal maps); the game
cooks them into DDS on first load, the same way it handles the .png paths the
F4's materials referenced.
"""
import json
import os

# source (glTF) material -> BeamNG material. "mirror" and "@screen" are
# special: mirror glass uses the game's reflective mirror material, and the
# steering wheel LCD shows the dashboard HTML display.
NAMES = {
    "redbull_carbon1": "rb14_carbon", "redbull_paint": "rb14_paint", "redbull_detail": "rb14_detail",
    "generics": "rb14_mechanical", "generics_cockpit": "rb14_cockpit", "redbull_carbon3": "rb14_headrest",
    "halo": "rb14_halo", "glass.001": "rb14_screen", "rear_light": "rb14_rearlight", "decals": "rb14_decals",
    "redbull_number_1.002": "rb14_numbers", "redbull_mirror_left": "mirror", "redbull_mirror_right": "mirror",
    "toro_rosso_steeringwheel": "rb14_sw_body", "sw_decals": "rb14_sw_decals",
    "toro_rosso_steeringwheel_detail": "rb14_sw_detail", "toro_rosso_carbon4": "rb14_sw_carbon",
    "toro_rosso_carbon4.001": "rb14_sw_column", "DRS": "rb14_sw_detail", "driver_number": "rb14_sw_carbon",
    "LCD": "redbull_screen", "CLEARLED": "rb14_sw_leds", "CLEARLED_PRE": "rb14_sw_leds",
    "kers_brown": "rb14_sw_kers", "kers_green": "rb14_sw_kers", "BLACK": "rb14_sw_black",
    "Tyre_thread": "rb14_tyre", "tyre_side": "rb14_tyre", "redbull_wheel_hub": "rb14_rim",
}

# BeamNG material -> (texture image, options). Image names are the glTF's
# embedded images.
BODY = {
    "rb14_carbon": dict(color="ext_carbon_fiber_d", normal="EXT_carbon_fiber_NM", rough=0.35, aniso=True),
    "rb14_paint": dict(color="redbull_main_paint_d", rough=0.55),        # the 2018 livery is matte
    "rb14_halo": dict(color="redbull_main_paint_d", rough=0.55),
    "rb14_detail": dict(color="redbull_detail_d", rough=0.6),
    "rb14_mechanical": dict(color="generic_main_d", rough=0.55, metal=0.3),
    "rb14_cockpit": dict(color="generic_cockpit_d", rough=0.7),
    "rb14_headrest": dict(color="cf_pattern_3_d", rough=0.8),
    "rb14_decals": dict(color="redbull_main_decal_da", rough=0.5, alpha="test"),
    "rb14_numbers": dict(color="redbull_driver_33", rough=0.5, alpha="test"),
    "rb14_screen": dict(color="glass_da", rough=0.05, alpha="blend"),
    "rb14_rearlight": dict(color="rear_light_a", rough=0.3),
    "rb14_rearlight_on": dict(color="rear_light_a", rough=0.3, emissive=[1.0, 0.1, 0.05], emissive_strength=6),
    "rb14_sw_body": dict(color="toro_rosso_steering_wheel_d", rough=0.6),
    "rb14_sw_decals": dict(color="redbull_steering_wheel_decal", rough=0.5, alpha="test"),
    "rb14_sw_detail": dict(color="drs", rough=0.5),
    "rb14_sw_carbon": dict(color="int_carbon_fiber", normal="int_carbon_fiber_nm", rough=0.4),
    "rb14_sw_column": dict(color="ext_carbon_fiber", rough=0.4),
    "rb14_sw_leds": dict(color="clearled", rough=0.2),
    "rb14_sw_kers": dict(color="color_green", rough=0.3),
    "rb14_sw_black": dict(color="AC_black", rough=0.9),
}
WHEELS = {
    # the rims' colour atlas is pale; the RB14 ran dark rims
    "rb14_rim": dict(color="redbull_wheel_d", rough=0.45, metal=0.6, factor=[0.32, 0.32, 0.34, 1]),
    "rb14_rim_alt": dict(color="redbull_wheel_d", rough=0.5, metal=0.4, factor=[0.12, 0.12, 0.13, 1]),
    "rb14_tyre": dict(color="Tyre", normal="Tyre_NM", rough=0.8),
    "rb14_tyre_alt": dict(color="Tyre", normal="Tyre_NM", rough=0.7, factor=[0.85, 0.9, 1.0, 1]),
}


def tex_file(image, kind):
    return f"rb14_{image.lower()}_{'n.normal' if kind == 'normal' else 'b.color'}.png"


def definition(name, opts, tex_dir):
    stage = {"baseColorMap": f"/{tex_dir}/{tex_file(opts['color'], 'color')}",
             "roughnessFactor": opts.get("rough", 0.5),
             "metallicFactor": opts.get("metal", 0.0)}
    if "factor" in opts:
        stage["baseColorFactor"] = opts["factor"]
    if "normal" in opts:
        stage["normalMap"] = f"/{tex_dir}/{tex_file(opts['normal'], 'normal')}"
    if opts.get("aniso"):
        stage["useAnisotropic"] = True
    if "emissive" in opts:
        stage["emissiveFactor"] = opts["emissive"]
        stage["emissiveMap"] = stage["baseColorMap"]
        stage["glow"] = True
    m = {"name": name, "mapTo": name, "class": "Material", "version": 1.5,
         "Stages": [stage, {}, {}, {}], "doubleSided": True, "dynamicCubemap": True,
         "materialTag0": "beamng", "materialTag1": "vehicle"}
    if opts.get("alpha") == "test":
        m["alphaTest"] = True
        m["alphaRef"] = 100
    elif opts.get("alpha") == "blend":
        stage["opacityFactor"] = 1.0
        m["translucent"] = True
        m["translucentBlendOp"] = "PreMulAlpha"
        m["castShadows"] = False
    return m


def write(images, vehicle_dir, wheels_dir):
    """Write both materials files and every texture they reference."""
    for defs, d, fname in ((BODY, vehicle_dir, "rb14.materials.json"),
                           (WHEELS, wheels_dir, "rb14_wheels.materials.json")):
        out = {}
        for name, opts in defs.items():
            out[name] = definition(name, opts, d)
            for kind in ("color", "normal"):
                img = opts.get(kind)
                if img:
                    with open(os.path.join(d, tex_file(img, kind)), "wb") as fh:
                        fh.write(images[img])
        with open(os.path.join(d, fname), "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2)
            fh.write("\n")
