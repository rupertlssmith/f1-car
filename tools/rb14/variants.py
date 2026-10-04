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


PREFIX, LABEL, SHEET = "wob", "Wobble Fix", "plans/wobble-fixes.md"
BRACE = {"$front_toe_brace": 1}                        # 201 -> 373 Nm/deg front toe stiffness
DAMPER = {"$front_toe_damp": 150}
RODS = {"$tierod_stiff": 1.5, "$tierod_damp": 10}
BALANCE = {"$wing_angle_F": 0, "$wing_angle_R": 6}     # aero 41 -> 46 % front (weight 46 %)
ARB = {"$arb_spring_F": 150000, "$arb_spring_R": 200000}
FIXES = [   # (short name, what it changes, {vars}, {slot: part})
    ("Front toe brace", "torsion bar holding each front axle against toe about its upright's steering axis "
     "(100 kNm/rad): front toe stiffness 201 -> 373 Nm/deg", BRACE, {}),
    ("Toe brace strong", "toe brace 150 kNm/rad (395 Nm/deg; just over the stiffness target)",
     {"$front_toe_brace": 1.5}, {}),
    ("Shimmy damper", "damping of each front axle's toe about its upright, 150 Nms/rad (about half critical)",
     DAMPER, {}),
    ("Shimmy damper strong", "shimmy damper 200 Nms/rad, uprights +2 kg (from the rims) to carry it; "
     "just over the stiffness target", {"$front_toe_damp": 200, "$upright_mass_F": 4}, {}),
    ("Stiffer track rods", "front track rods 1.5x stiffer", {"$tierod_stiff": 1.5}, {}),
    ("Damped track rods", "front track rods 10x damping (1500 Ns/m)", {"$tierod_damp": 10}, {}),
    ("Front wing +3 deg", "front wing 0 deg (was -3): aero balance 41 -> 45 % front, +5 % downforce",
     {"$wing_angle_F": 0}, {}),
    ("Aero balance to weight", "front wing 0 deg, rear wing 6 deg (was 8): aero balance 46 % front like the "
     "weight, drag -5 %", BALANCE, {}),
    ("Roll balance rearward", "front anti-roll bar 150 kN/m (was 260), rear 200 kN/m (was 110)", ARB, {}),
    ("Front grip +6 %", "front dry tyres 6 % more grip", {"$tyre_grip_F": 1.06}, {}),
    ("Brace + track rods", "1 + track rods 1.5x stiffer, 10x damping (418 Nm/deg)", {**BRACE, **RODS}, {}),
    ("Damper + track rods", "3 + track rods 1.5x stiffer, 10x damping", {**DAMPER, **RODS}, {}),
    ("Brace + balance", "1 + aero balance to weight + roll balance rearward", {**BRACE, **BALANCE, **ARB}, {}),
    ("Damper + balance", "3 + aero balance to weight + roll balance rearward", {**DAMPER, **BALANCE, **ARB}, {}),
    ("All: brace", "brace + track rods + aero balance + roll balance + front grip +6 %",
     {**BRACE, **RODS, **BALANCE, **ARB, "$tyre_grip_F": 1.06}, {}),
    ("All: damper", "shimmy damper + track rods + aero balance + roll balance + front grip +6 %",
     {**DAMPER, **RODS, **BALANCE, **ARB, "$tyre_grip_F": 1.06}, {}),
]


def variants(b):
    """(title, what it tries, {vars}, {slot: part}). Round 20: front-wheel
    shimmy (~7 Hz, 2-4 deg in fast corners) and the understeer behind it."""
    return [(name, tries, over, parts) for name, tries, over, parts in FIXES]


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
                    "-annotate", "+0+24", " %s " % label.replace("%", "%%"), "-quality", "85", path], check=True)


def main():
    os.chdir(REPO)
    for pre in ("fix", "steer", "rear", "drift", "hub", "wob"):  # earlier rounds' test cars (test_01, no halo, stays)
        for f in glob.glob(f"{V}/{pre}_*") + glob.glob(f"{V}/info_{pre}_*"):
            os.remove(f)
    base = json.load(open(f"{V}/baseline.pc"))
    base_info = json.load(open(f"{V}/info_baseline.json"))
    bv = {k: float(x) for k, x in base["vars"].items()}
    sheet = ["# Wobble-fix test cars (round 20)", "",
             "Silverstone replay (tools/rb14/handling_analysis.py): each front wheel shimmies at ~7 Hz on its",
             "own track rod and hub, 2-4 deg RMS in fast corners (it grows with lateral g), not from the",
             "driver, the rack or the bounce (5 Hz). Behind it: heavy understeer -- front tyres at 8-12 deg of",
             "slip against 2.5-3.6 at the rear, yaw at 24-46 % of geometric, aero balance 41 % front against",
             "46 % weight -- and a soft front corner: ~200 Nm/deg toe stiffness (FEM, chassis and rack held),",
             "most of it the hub turning on its upright. Baseline is unchanged (Hub Fix 15, with halo).",
             "Every car now records sn_FL_wobble / sn_FR_wobble (deg RMS above ~3 Hz, at frame rate).",
             "In the game: *Wobble Fix N · ...*.", "",
             "Test drive per car: a few fast corners (Silverstone's Copse / Maggotts / Stowe are ideal), then",
             "`python3 tools/rb14/handling_analysis.py <replay>`: shimmy RMS by lateral g, yaw / geometric,",
             "front / rear slip angles.", "",
             "| # | Car | Change |", "|---|---|---|"] + [
             "| %d | %s | %s |" % (i + 1, n, w) for i, (n, w, _, _) in enumerate(FIXES)] + ["",
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
        changed = ", ".join([f"{k.lstrip('$')} {x:g}" for k, x in over.items()] + [f"part {p}" if p else f"no {slot}" for slot, p in parts.items()])
        desc = f"{LABEL} car {n}: {tries}. Everything else is Baseline ({changed}). {risk}"
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
