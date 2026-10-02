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


PREFIX, LABEL, SHEET = "test", "Test", "plans/round19-tests.md"
FIXES = [   # (short name, what it changes, {vars}, {slot: part})
    ("No halo", "Baseline (round 18's Hub Fix 15) without the halo: its part (mesh, mounts, logo, 6 kg of nodes, "
     "beams and collision triangles) replaced by flush covers over the mounts", {}, {"redbull_halo": "redbull_halo_cover"}),
]


def variants(b):
    """(title, what it tries, {vars}, {slot: part}). Round 19: one car."""
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
                    "-annotate", "+0+24", f" {label} ", "-quality", "85", path], check=True)


def main():
    os.chdir(REPO)
    for pre in ("fix", "steer", "rear", "test", "drift", "hub"):  # earlier rounds' test cars too
        for f in glob.glob(f"{V}/{pre}_*") + glob.glob(f"{V}/info_{pre}_*"):
            os.remove(f)
    base = json.load(open(f"{V}/baseline.pc"))
    base_info = json.load(open(f"{V}/info_baseline.json"))
    bv = {k: float(x) for k, x in base["vars"].items()}
    sheet = ["# Round 19 test cars", "",
             "Baseline is round 18's Hub Fix 15 (Combined max). This round re-cut the body panels",
             "along the RB14's real panel lines (with lips on every cut edge), made the DRS flap a",
             "hinged part of its own, and moved the halo into its own part. In the game: *Test N · ...*.", "",
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
