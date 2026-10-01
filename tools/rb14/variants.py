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


PREFIX, LABEL, SHEET = "rear", "Rear Fix", "plans/rear-fixes.md"
FULL_TOE = {"$toe_R": 1.0329, "$camber_R": 0.991}     # ~0.3 deg toe-in per side in game (if the offset holds)
HALF_TOE = {"$toe_R": 1.0151, "$camber_R": 0.9938}    # ~1.8 deg
FREE_DIFF = {"$lsdlockcoef_R": 0.10, "$lsdpreload_R": 20, "$lsdlockcoefrev_R": 0.06}
GBX = {"redbull_wheeldata_R": "redbull_wheeldata_R_gbx"}


def variants(b):
    """(title, what it tries, {vars}, {slot: part}) from the Baseline vars b.
    Round 14, from the round-13 replay (plans/rb14-model-swap.md): the rear
    axle steers the car after hard turns (rear toe 3.7 deg per side at rest,
    up to 5.9 under power, lopsided drive torque), and ~3 kN of extra
    rolling / scrub resistance holds back acceleration and top speed.
    Singles first, then combinations. Front dampers stay at Baseline."""
    return [
        ("Rear toe fixed", "rear toe and camber links set for ~0.3 deg toe-in per side in game (measured "
         "3.7), camber kept at -1.8 deg: less scrub drag, the rear axle no longer fighting itself",
         FULL_TOE, {}),
        ("Rear toe half-fixed", "the same towards ~1.8 deg per side, in case the game-vs-model toe offset "
         "is not constant", HALF_TOE, {}),
        ("Gearbox torque reaction", "the rear wheels' drive torque reacts on gearbox / engine nodes on the "
         "wheel's own side (was the engine node across the car): rear toe should stop changing with throttle",
         {}, GBX),
        ("Freer differential", "power lock 0.10 (0.20), preload 20 Nm (60), coast lock 0.06 (0.12): the rear "
         "drive torque stayed lopsided after corners", FREE_DIFF, {}),
        ("Toe fixed + gearbox reaction", "1 and 3 together", FULL_TOE, GBX),
        ("Toe fixed + freer diff", "1 and 4 together", {**FULL_TOE, **FREE_DIFF}, {}),
        ("Gearbox reaction + freer diff", "3 and 4 together", FREE_DIFF, GBX),
        ("All rear fixes", "1, 3 and 4 together", {**FULL_TOE, **FREE_DIFF}, GBX),
    ]


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
    for pre in ("fix", "steer", "rear"):  # earlier rounds' test cars too
        for f in glob.glob(f"{V}/{pre}_*") + glob.glob(f"{V}/info_{pre}_*"):
            os.remove(f)
    base = json.load(open(f"{V}/baseline.pc"))
    base_info = json.load(open(f"{V}/info_baseline.json"))
    bv = {k: float(x) for k, x in base["vars"].items()}
    sheet = ["# Rear-axle variants", "",
             "Test cars generated by `tools/rb14/variants.py` (round 14): fixes for what the",
             "round-13 replay showed -- the rear axle steering the car after hard turns, too",
             "much rear toe-in, and extra drag holding back acceleration and top speed. Singles",
             "first, then combinations; everything else is **Baseline** (round 12's Front Fix 4,",
             "best in rounds 12-13; round 13's Steering Fix cars all wobbled more). In the game:",
             "*Rear Fix N · ...*. Best tested with the replay sequence (docs/replay-test-guide.pdf),",
             "at least Replay A tests 1-3 and 6 and Replay B tests 7-10; note for each: does it",
             "spawn cleanly, does it drive straight after hard turns, wobble, speed.", "",
             "Offline checks: stiffness = highest omega*dt (target <= %.2f), damped = with"
             % fs.MAX_OMEGA_DT,
             "damping (<= %.2f), corner = wheel-corner modes with damping (<= %.2f; round 10"
             % (fs.MAX_DAMPED, fs.MAX_DAMPED_CORNER),
             "was 1.78 and fine, round 11 1.83 and broke), tyres = stiffness per kg vs the F4's (<= 1).", "",
             "| Car | Tries | stiffness | damped | corner | tyres | spawns? | judder? |",
             "|---|---|---|---|---|---|---|---|"]
    for n, (title, tries, over, parts) in enumerate(variants(bv), 1):
        name = f"{PREFIX}_{n}"
        vars_ = dict(base["vars"])
        vars_.update(over)
        pc = {**base, "parts": {**base.get("parts", {}), **parts}, "vars": {k: vars_[k] for k in sorted(vars_)}}
        with open(f"{V}/{name}.pc", "w", newline="\n") as fh:
            json.dump(pc, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        g = gates(sr.Vehicle("redbull", name))
        risk = ("Passes every offline check." if not g["over"] else
                "Over an offline limit (%s): may break at spawn." % "; ".join(g["over"]))
        ui = f"{LABEL} {n} · {title}"
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
