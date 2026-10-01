#!/usr/bin/env python3
"""Test-car variants around one issue (round 12: front-wheel judder,
Front Fix N; round 13: steering centring, Steering Fix N -- see variants()).

    python3 tools/rb14/variants.py            (after f1_setup.py)

Writes vehicles/redbull/<PREFIX>_<n>.pc with info_<PREFIX>_<n>.json (the
name shown in the game's vehicle selector) and a labelled thumbnail, plus
the test sheet (SHEET). Each changes a few tuning variables from Baseline. They are ordered safest first: every car is run through the
same checks as the main configs, and the ones that go over a limit say so
in their description (they may break at spawn -- that's the point of
trying several). build_mod.py --no-variants leaves them out.
"""
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import setup_report as sr  # noqa: E402
import f1_setup as fs  # noqa: E402

V = "vehicles/redbull"


PREFIX, LABEL, SHEET = "drift", "Drift Fix", "plans/drift-fixes.md"
GBX = {"redbull_wheeldata_R": "redbull_wheeldata_R_gbx"}
FIXES = [   # (short name, suspect + what it changes, sensors that show it, {vars}, {parts})
    ("Stiff rear hubs", "the hub shifting on its upright: rear hub toe torsion bar 5x (the most the gates allow)",
     "sn_R?_hub_* (axle node to upright distances), sn_R?_toe", {"$rear_toe_stiff": 5}, {}),
    ("Stiffer rear links", "the six upright-to-gearbox links stretching: 1.2x stiffer (1.5x goes over the "
     "solver limits)", "sn_R?_link_*", {"$rear_link_stiff": 1.2}, {}),
    ("Driveshaft play", "the driveshaft end stops pushing the inner axle node: 3x the plunge before the stops "
     "(+-15 % of its length)", "sn_R?_shaft (base stops at +-33 mm)", {"$halfshaft_play": 3}, {}),
    ("Rear droop room", "the unloaded inner wheel reaching its droop stop: 2x the droop travel",
     "sn_R?_spring, sn_R?_in_z / out_z", {"$rear_droop": 2}, {}),
    ("Gearbox torque reaction", "the drive-torque reaction pushing the axle: reaction on the wheel's own side "
     "of the gearbox (Rear Fix 3's part)", "sn_R?_in_y / out_y (fore-aft), sn_R?_toe", {}, GBX),
    ("Rear toe reset", "the 3-4 deg rear toe-in itself: toe / camber links reset for ~0.3 deg per side",
     "sn_R?_toe at rest and on the straights", {"$toe_R": 1.0329, "$camber_R": 0.991}, {}),
]


def variants(b):
    """(title, what it tries, {vars}, {slot: part}). Round 17: one car per
    suspect for the post-corner drift (the inner rear wheel losing ~3 deg of
    toe-in and holding it ~2 s), each measurable with the redbullSensors
    values in a replay; then all of them (hub torsion 4x there: 5x with the
    rest goes over the stiffness target)."""
    out = [(name, tries + "; check: " + sens, over, parts) for name, tries, sens, over, parts in FIXES]
    allv, allp = {}, {}
    for _, _, _, o, p in FIXES:
        allv.update(o)
        allp.update(p)
    allv["$rear_toe_stiff"] = 4
    out.append(("All drift fixes", "1-6 together (hub torsion 4x)", allv, allp))
    return out


def gates(v):
    st = sr.stability_report(v, top=400)
    corner = max((float(m.split(":")[0]) for m in st["damped_modes"]
                  if any(k in m.split(":")[1].split(",")[0] for k in fs.CORNER_NODES)), default=0.0)
    ref = {r["name"][0]: r for r in sr.Vehicle("fr04", None).wheels()}
    tyre = 0.0
    for r in v.wheels():
        f4 = ref[r["name"][0]]
        for key in fs.TYRE_SPRINGS:
            tyre = max(tyre, (v.val(r.get(key)) / v.val(r.get("nodeWeight"))) /
                       (v.val(f4.get(key)) / v.val(f4.get("nodeWeight"))))
    mr = sr.mass_report(v)
    v._yf, v._yr = mr["yf"], mr["yr"]
    aero, _ = sr.aero_report(v)
    strength = sr.strength_report(v, mr, aero)[0][0]
    hits = sr.wheel_clearance(v, fs.WHEEL_CLEARANCE)
    over = []
    if st["max"] > fs.MAX_OMEGA_DT:
        over.append("stiffness %.2f > %.2f" % (st["max"], fs.MAX_OMEGA_DT))
    if st["damped"] > fs.MAX_DAMPED:
        over.append("damping %.2f > %.2f" % (st["damped"], fs.MAX_DAMPED))
    if corner > fs.MAX_DAMPED_CORNER + 1e-9:
        over.append("wheel-corner damping %.2f > %.2f" % (corner, fs.MAX_DAMPED_CORNER))
    if tyre > fs.TYRE_MAX_K_PER_KG + 1e-6:
        over.append("tyres %.2f x the F4's per kg" % tyre)
    if strength > fs.STRENGTH_MAX_RATIO:
        over.append("strength %.2f" % strength)
    if hits:
        over.append("wheel clearance")
    if st["max"] >= 2 or st["damped"] >= 2:
        raise SystemExit("variant over the hard solver limit (2): would certainly break")
    return dict(stiff=st["max"], damped=st["damped"], corner=corner, tyre=tyre, strength=strength, over=over)


def thumbnail(label, path):
    subprocess.run(["convert", f"{V}/baseline.jpg", "-gravity", "South", "-fill", "white",
                    "-undercolor", "#000000B0", "-font", "DejaVu-Sans-Bold", "-pointsize", "40",
                    "-annotate", "+0+24", f" {label} ", "-quality", "85", path], check=True)


def main():
    os.chdir(REPO)
    for pre in ("fix", "steer", "rear", "test", "drift"):  # earlier rounds' test cars too
        for f in glob.glob(f"{V}/{pre}_*") + glob.glob(f"{V}/info_{pre}_*"):
            os.remove(f)
    base = json.load(open(f"{V}/baseline.pc"))
    base_info = json.load(open(f"{V}/info_baseline.json"))
    bv = {k: float(x) for k, x in base["vars"].items()}
    sheet = ["# Drift-fix test cars (round 17)", "",
             "The problem: after a hard turn, with the steering centred, the car keeps turning",
             "the other way for ~2.5-4.5 s. In the round-16 replays the inner rear wheel loses",
             "~3 deg of toe-in in the turn and holds it ~1.5-2 s after the steering is centred;",
             "nothing in the offline model explains it. Baseline is round 16's Test 05 (engine",
             "+12 %). Every car now carries virtual sensors (lua/controller/redbullSensors.lua)",
             "recorded in replays; each fix below targets one suspect and names the sensors that",
             "show whether it moved. In the game: *Drift Fix N · ...*.", "",
             "Test drive per car (one short replay, ~1 min, big open area): three hard left turns",
             "at speed, each followed by straightening up and holding the wheel centred 5-6 s;",
             "then three hard right turns the same way. Then `python3 tools/rb14/replay_analysis.py",
             "<replay>` -- its SENSORS section lists, per turn, the inner rear wheel's sensors",
             "that are still off while the car drifts.", "",
             "| # | Fix | Suspect / change | Sensors |", "|---|---|---|---|"] + [
             "| %d | %s | %s | %s |" % (i + 1, n, w, s) for i, (n, w, s, _, _) in enumerate(FIXES)] + [
             "| %d | All drift fixes | 1-6 together (hub torsion 4x) | all |" % (len(FIXES) + 1), "",
             "Offline checks: stiffness = highest omega*dt (target <= %.2f), damped = with"
             % fs.MAX_OMEGA_DT,
             "damping (<= %.2f), corner = wheel-corner modes with damping (<= %.2f; round 10"
             % (fs.MAX_DAMPED, fs.MAX_DAMPED_CORNER),
             "was 1.78 and fine, round 11 1.83 and broke), tyres = stiffness per kg vs the F4's (<= 1).", "",
             "| Car | Tries | stiffness | damped | corner | tyres | spawns? | judder? |",
             "|---|---|---|---|---|---|---|---|"]
    for n, (title, tries, over, parts) in enumerate(variants(bv), 1):
        name = f"{PREFIX}_{n:02d}"
        vars_ = dict(base["vars"])
        vars_.update(over)
        pc = {**base, "parts": {**base.get("parts", {}), **parts}, "vars": {k: vars_[k] for k in sorted(vars_)}}
        with open(f"{V}/{name}.pc", "w", newline="\n") as fh:
            json.dump(pc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        g = gates(sr.Vehicle("redbull", name))
        risk = ("Passes every offline check." if not g["over"] else
                "Over an offline limit (%s): may break at spawn." % "; ".join(g["over"]))
        ui = f"{LABEL} {n:02d} · {title}"
        changed = ", ".join([f"{k.lstrip('$')} {x:g}" for k, x in over.items()] + [f"part {p}" for p in parts.values()])
        desc = f"{LABEL} test car {n}: {tries}. Everything else is Baseline ({changed}). {risk}"
        info = {**base_info, "Config Type": "Custom", "Configuration": ui, "Description": desc}
        with open(f"{V}/info_{name}.json", "w", newline="\n") as fh:
            json.dump(info, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        thumbnail(ui, f"{V}/{name}.jpg")
        sheet.append(f"| `{name}` {title} | {tries} | {g['stiff']:.2f} | {g['damped']:.2f} | {g['corner']:.2f} | "
                     f"{g['tyre']:.2f} | | |")
        print(f"{ui:48s} stiffness {g['stiff']:.2f} damped {g['damped']:.2f} corner {g['corner']:.2f} "
              f"tyres {g['tyre']:.2f} strength {g['strength']:.2f}  {'OK' if not g['over'] else 'OVER: ' + '; '.join(g['over'])}")
    with open(SHEET, "w") as fh:
        fh.write("\n".join(sheet) + "\n")
    print(f"{LABEL} variants written; test sheet {SHEET}")


if __name__ == "__main__":
    main()
