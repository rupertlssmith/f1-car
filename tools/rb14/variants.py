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


PREFIX, LABEL, SHEET = "test", "Test", "plans/round16-tests.md"
FIXES = [   # (short name, what it changes, {vars}) -- worst issue first
    ("Stiff rear hubs", "rear hub toe stiffness 4x (the torsion bar holding each rear axle line to its upright): "
     "less rear toe-in under drive torque and load (replays: 2.6-5 deg per side, rising with throttle)",
     {"$rear_toe_stiff": 4}),
    ("Rear toe reset", "rear toe / camber links reset for ~0.3 deg toe-in per side, camber kept at -1.8 deg "
     "(Rear Fix 1's setting)", {"$toe_R": 1.0329, "$camber_R": 0.991}),
    ("DRS flap fix", "the wing stays put; DRS acts as forces on the gearbox (-1.3 kN drag, -3.1 kN downforce "
     "at 300 km/h) instead of tilting the whole wing and lifting the pillar off", {"$drs_model": 1}),
    ("Traction", "torque map allows 18 % rear slip (12 %): less throttle trimming below 160 km/h",
     {"$tc_slip": 0.18}),
    ("Power to spec", "combustion engine +12 %: ~650 kW at the wheels (590), toward a 2018 power unit",
     {"$pu_power": 1.12}),
    ("Brakes to spec", "brake force 1.3x: ~5 g from 300 km/h (3.9 g, brake-torque limited)",
     {"$brakestrength": 1.3}),
    ("Brake modulation", "brakes eased at low speed like a driver bleeding the pedal (50 % at a standstill, "
     "full from 250 km/h): no lock-ups below 150 km/h", {"$brake_map": 1}),
]


def variants(b):
    """(title, what it tries, {vars}, {slot: part}). Round 16, from replays
    A / B / C with Rear Fix 4 (now Baseline): one car per fix, then the
    fixes combined worst-first up to all of them, plus the performance
    changes alone."""
    out = [(name, tries, over, {}) for name, tries, over in FIXES]
    for n in range(2, len(FIXES) + 1):
        over = {}
        for _, _, o in FIXES[:n]:
            over.update(o)
        title = "All fixes" if n == len(FIXES) else "Fixes 1-%d" % n
        out.append((title, " + ".join(f[0] for f in FIXES[:n]), over, {}))
    perf = {}
    for _, _, o in FIXES[3:]:
        perf.update(o)
    out.append(("Performance only", " + ".join(f[0] for f in FIXES[3:]), perf, {}))
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
    for pre in ("fix", "steer", "rear", "test"):  # earlier rounds' test cars too
        for f in glob.glob(f"{V}/{pre}_*") + glob.glob(f"{V}/info_{pre}_*"):
            os.remove(f)
    base = json.load(open(f"{V}/baseline.pc"))
    base_info = json.load(open(f"{V}/info_baseline.json"))
    bv = {k: float(x) for k, x in base["vars"].items()}
    sheet = ["# Round 16 test cars", "",
             "Test cars generated by `tools/rb14/variants.py` (round 16) from replays A / B / C",
             "with Rear Fix 4, which is now **Baseline** (freer diff). One car per fix -- worst",
             "issue first -- then the fixes combined in that order up to all of them, and the",
             "performance changes alone. In the game: *Test NN · ...*. Record the replay",
             "sequence (docs/replay-test-guide.pdf) with the promising ones; note for each:",
             "spawns cleanly? drives straight / re-centres? wobble? speed, braking.", "",
             "| # | Fix | What it changes |", "|---|---|---|"] + [
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
