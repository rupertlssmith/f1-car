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


PREFIX, LABEL, SHEET = "shim", "Shimmy Fix", "plans/shimmy-fixes.md"
# FEM, front-left corner, rack free (Baseline: 0.107 deg toe-out per kN of
# cornering force, 0.239 per kN rearward, toe stiffness 320 Nm/deg)
WISHBONE = {"$wishbone_stiff_F": 2, "$balljoint_mass_F": 2}       # 0.037 / 0.202 deg per kN, 387 Nm/deg
ARM = {"$steer_arm_F": 20}                                           # 0.115 / 0.158, 454 Nm/deg; lock -18 %
BOUNCE = {"$arb_damp_F": 8000, "$packer_F": 0.035}
BALANCE = {"$wing_angle_F": 0, "$wing_angle_R": 6}                  # aero 41 -> 46 % front (weight 46 %)
ARB = {"$arb_spring_F": 150000, "$arb_spring_R": 200000}
FIXES = [   # (short name, what it changes, {vars}, {slot: part})
    ("Stiffer wishbones", "front wishbone legs 2x stiffer, 2 kg per corner from the rim to the upper ball "
     "joint to carry it: toe-out per kN of cornering force 0.107 -> 0.037 deg", WISHBONE, {}),
    ("Longer steering arm", "track rods' outer ends 20 mm forward (arm 78 -> 96 mm): toe stiffness 320 -> 454 "
     "Nm/deg, toe-out per kN rearward 0.24 -> 0.16 deg; ~18 % less steering lock, slower steering", ARM, {}),
    ("Front roll damper", "damping on the front anti-roll bar, 8000 Ns/m at the wheels in roll (the 7-8 Hz "
     "corner bounce)", {"$arb_damp_F": 8000}, {}),
    ("Later front packers", "front packers engage after 35 mm of wheel travel (was 25)", {"$packer_F": 0.035}, {}),
    ("Aero balance to weight", "front wing 0 deg, rear wing 6 deg (was -3 / 8): aero balance 46 % front like "
     "the weight, drag -5 %", BALANCE, {}),
    ("Roll balance rearward", "front anti-roll bar 150 kN/m (was 260), rear 200 kN/m (was 110)", ARB, {}),
    ("Wishbones + arm", "1 + 2: 0.055 deg per kN cornering, 0.136 per kN rearward, 540 Nm/deg",
     {**WISHBONE, **ARM}, {}),
    ("Wishbones 2.5x + arm", "wishbones 2.5x + 2: 0.043 / 0.131 deg per kN, 561 Nm/deg",
     {**WISHBONE, **ARM, "$wishbone_stiff_F": 2.5}, {}),
    ("Wishbones 3x + arm", "wishbones 3x, 2.5 kg to the ball joints + 2: 0.035 / 0.128 deg per kN, 576 Nm/deg; "
     "just over the damping target", {**WISHBONE, **ARM, "$wishbone_stiff_F": 3, "$balljoint_mass_F": 2.5}, {}),
    ("Roll damper + packers", "3 + 4 (the corner bounce)", BOUNCE, {}),
    ("Wishbones + arm + bounce", "7 + roll damper + later packers", {**WISHBONE, **ARM, **BOUNCE}, {}),
    ("Wishbones + arm + balance", "7 + aero balance to weight + roll balance rearward",
     {**WISHBONE, **ARM, **BALANCE, **ARB}, {}),
    ("All", "wishbones 2.5x + arm + roll damper + later packers + aero balance + roll balance",
     {**WISHBONE, **ARM, **BOUNCE, **BALANCE, **ARB, "$wishbone_stiff_F": 2.5}, {}),
]


def variants(b):
    """(title, what it tries, {vars}, {slot: part}). Round 21: front-wheel
    shimmy -- compliance steer through the wishbones, driven by the 7-8 Hz
    tyre-load bounce in hard corners (Baseline = round 20's Wobble Fix 2)."""
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
    for pre in ("fix", "steer", "rear", "drift", "hub", "wob", "shim"):  # earlier rounds' test cars (test_01, no halo, stays)
        for f in glob.glob(f"{V}/{pre}_*") + glob.glob(f"{V}/info_{pre}_*"):
            os.remove(f)
    base = json.load(open(f"{V}/baseline.pc"))
    base_info = json.load(open(f"{V}/info_baseline.json"))
    bv = {k: float(x) for k, x in base["vars"].items()}
    sheet = ["# Shimmy-fix test cars (round 21)", "",
             "Baseline is round 20's Wobble Fix 2 (front toe brace 1.5). Its Silverstone lap still shimmies",
             "(~8 Hz, 2 deg RMS above 3.5 g). Replay + FEM: each front tyre's load bounces at 7-8 Hz in hard",
             "corners (rear too, but the rear toe stays put); cornering force bends the front wishbone legs,",
             "the upright moves back and the track rod turns it toe-out -- 0.107 deg per kN of cornering",
             "force, 0.239 per kN rearward (FEM) and ~4x that in the game near the corner's resonance. Every",
             "wheel steers away from the corner as its load rises, inner and outer alike. A stiffer track rod",
             "does not help (its stretch is ~1/4 of the toe motion; rigid makes the toe-out per kN worse).",
             "In the game: *Shimmy Fix N · ...*.", "",
             "Test drive per car: a few fast corners (Silverstone's Copse / Maggotts / Stowe are ideal), then",
             "`python3 tools/rb14/handling_analysis.py <replay>`: shimmy RMS by lateral g, yaw / geometric,",
             "front / rear slip angles. Cars 2, 7-9 and 11-13 steer slower (longer steering arm).", "",
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
