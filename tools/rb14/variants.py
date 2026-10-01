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


PREFIX, LABEL, SHEET = "hub", "Hub Fix", "plans/hub-fixes.md"
CHECK = "sn_R?_hub_* (axle node to upright, mm) and the toe vs in_z slope in the SENSORS section"
M = "$rear_corner_mass"
FIXES = [   # (short name, what it changes, {vars}); graded, safest first per fix
    ("Axle beams 1.25x", "the 8 axle-node-to-upright beams 1.25x stiffer", {"$rear_hub_beam": 1.25}),
    ("Axle beams 1.5x", "axle beams 1.5x (+4 kg per rear corner, from the engine ballast, to stay stable)",
     {"$rear_hub_beam": 1.5, M: 4}),
    ("Axle beams 2x", "axle beams 2x (+8 kg per rear corner)", {"$rear_hub_beam": 2, M: 8}),
    ("Axle beams 2.5x", "axle beams 2.5x (+12 kg per rear corner; just over the stiffness target)",
     {"$rear_hub_beam": 2.5, M: 12}),
    ("Hub bracing 0.5", "brace beams from new nodes ahead of / behind the axle on the upright to both axle "
     "nodes, at 0.5x the upright-link stiffness", {"$rear_brace": 0.5}),
    ("Hub bracing 1", "bracing at 1x (+6 kg per rear corner)", {"$rear_brace": 1, M: 6}),
    ("Hub bracing 1.5", "bracing at 1.5x (+10 kg per rear corner)", {"$rear_brace": 1.5, M: 10}),
    ("Hub bracing 2", "bracing at 2x (+12 kg per rear corner; just over the stiffness target)",
     {"$rear_brace": 2, M: 12}),
    ("Toe brace 200k", "torsion bar holding the outer axle node against toe about the upright, 200 kNm/rad",
     {"$rear_toe_brace": 2}),
    ("Toe brace 400k", "toe brace 400 kNm/rad", {"$rear_toe_brace": 4}),
    ("Toe brace 600k", "toe brace 600 kNm/rad (+8 kg per rear corner; just over the stiffness target)",
     {"$rear_toe_brace": 6, M: 8}),
    ("Corner mass only", "control: +12 kg per rear corner and nothing else (to tell the mass from the fixes)",
     {M: 12}),
    ("Combined medium", "axle beams 1.5x + bracing 1 + toe brace 400k (+8 kg per corner)",
     {"$rear_hub_beam": 1.5, "$rear_brace": 1, "$rear_toe_brace": 4, M: 8}),
    ("Combined strong", "axle beams 2x + bracing 1 + toe brace 400k (+12 kg per corner)",
     {"$rear_hub_beam": 2, "$rear_brace": 1, "$rear_toe_brace": 4, M: 12}),
    ("Combined max", "axle beams 2x + bracing 1.5 + toe brace 600k (+12 kg per corner; over the stiffness target)",
     {"$rear_hub_beam": 2, "$rear_brace": 1.5, "$rear_toe_brace": 6, M: 12}),
    ("Strong + more toe-in", "Combined strong with ~0.6 deg more static rear toe-in (offline model), in case the "
     "stiffer hub takes away the toe-in the soft hub gave at rest", {"$rear_hub_beam": 2, "$rear_brace": 1,
                                                                    "$rear_toe_brace": 4, M: 12, "$toe_R": 0.9855}),
    ("More rear toe-in", "static rear toe-in only: ~0.6 deg more per side (offline model)", {"$toe_R": 0.9855}),
    ("Less rear toe-in", "static rear toe-in only: ~0.6 deg less per side (offline model)", {"$toe_R": 1.0}),
]


def variants(b):
    """(title, what it tries, {vars}, {slot: part}). Round 18: the rear axle
    nodes shift 2-4 mm on the upright as the wheel compresses and the toe
    follows (replayTurns); graded stiffer axle beams, new bracing, a toe
    brace, combinations, and two static-toe cars."""
    return [(name, tries + "; check: " + CHECK, over, {}) for name, tries, over in FIXES]


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
    for pre in ("fix", "steer", "rear", "test", "drift", "hub"):  # earlier rounds' test cars too
        for f in glob.glob(f"{V}/{pre}_*") + glob.glob(f"{V}/info_{pre}_*"):
            os.remove(f)
    base = json.load(open(f"{V}/baseline.pc"))
    base_info = json.load(open(f"{V}/info_baseline.json"))
    bv = {k: float(x) for k, x in base["vars"].items()}
    sheet = ["# Hub-fix test cars (round 18)", "",
             "The problem: after a hard turn, with the steering centred, the car keeps turning",
             "the other way for ~2.5-5 s. The round-17 sensors (replayTurns, Baseline) show why:",
             "the rear toe follows the rear axle height at ~0.17 deg per mm (the offline model:",
             "0.007), because the axle nodes shift 2-4 mm on the upright as the wheel compresses;",
             "after a turn the inner wheel's toe lags its height ~1-1.5 s, 0.6-0.8 deg of net rear",
             "steer. These cars stiffen the hub on the upright three ways, each in graded steps:",
             "the axle beams themselves, new bracing (two nodes on each upright, ahead of and",
             "behind the axle, braced to both axle nodes) and a toe brace (torsion bar). The",
             "stiffer steps need more mass at the rear corner to stay under the 2 kHz solver",
             "limit; it comes out of the engine ballast (same total weight), and car 12 has the",
             "mass alone as a control. Baseline is unchanged except for the brace nodes (+3 kg per",
             "rear corner, unbraced, taken from the ballast). In the game: *Hub Fix N · ...*.", "",
             "Test drive per car (one short replay): three hard left turns at speed, each followed",
             "by straightening up and holding the wheel centred 5-6 s; then three hard right turns.",
             "Then `python3 tools/rb14/replay_analysis.py <replay>`: the SENSORS section gives the",
             "hub_* movement and the toe vs in_z slope (Baseline ~0.17 deg/mm); a fix that works",
             "brings both down and the post-turn yaw with them.", "",
             "| # | Fix | Change |", "|---|---|---|"] + [
             "| %d | %s | %s |" % (i + 1, n, w) for i, (n, w, _) in enumerate(FIXES)] + ["",
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
