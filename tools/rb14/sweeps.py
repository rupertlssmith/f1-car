#!/usr/bin/env python3
"""Setup sweeps: test cars that each change one thing from the baseline.

    python3 tools/rb14/sweeps.py            (after f1_setup.py)

Writes, for every sweep level, vehicles/redbull/sweep_<key>_<n>.pc with its
info_sweep_<key>_<n>.json (the name shown in the game's vehicle selector,
e.g. "Sweep 01 · Front Wing -5° (1/5)", and a description of what it tunes)
and a thumbnail stamped with the same label; plus plans/sweeps.md, the test
sheet. Every car is checked like the main configs (solver stability, beam
strength, wheel clearance). Old sweep files are removed first, so editing
build_sweeps() and re-running keeps the set exact; steps are relative to Baseline.

Each sweep has 5 steps with the baseline value in the middle (3/5): if the
best-feeling car is 1/5 or 5/5, widen that sweep past it and re-run.
build_mod.py --no-sweeps leaves them out of a release build.
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

# Every sweep is relative to Baseline (read from baseline.pc), so the steps
# follow when the baseline changes. Step 3/5 is always the baseline value.
ROLL = [(+80000, -40000), (+40000, -20000), (0, 0), (-40000, +20000), (-80000, +40000)]   # front, rear ARB offsets
ROLL_LABELS = ("more front", "front+", "baseline", "rear+", "more rear")
HEAVE = [0.0, 0.5, 1.0, 1.5, 2.0]


def build_sweeps(b):
    """(key, title, tuning-menu place, [(label, {vars})]) from the baseline vars b."""
    clip = lambda x: max(0.0, round(x, 3))
    wf, af, ar = b["$wing_angle_F"], b["$arb_spring_F"], b["$arb_spring_R"]
    return [
        ("wingF", "Front Wing", "Aerodynamics > Front Wing Angle",
         [("%+d°" % (wf + d), {"$wing_angle_F": wf + d}) for d in (-2, -1, 0, 1, 2)]),
        ("roll", "Roll Balance", "Suspension > Anti-Roll Bar (front and rear)",
         [(lab, {"$arb_spring_F": af + df, "$arb_spring_R": ar + dr}) for lab, (df, dr) in zip(ROLL_LABELS, ROLL)]),
        ("diffpower", "Diff Power Lock", "Differentials > Power Lock Rate",
         [("%.2f" % clip(b["$lsdlockcoef_R"] + d), {"$lsdlockcoef_R": clip(b["$lsdlockcoef_R"] + d)}) for d in (-0.2, -0.1, 0, 0.1, 0.2)]),
        ("diffcoast", "Diff Coast Lock", "Differentials > Coast Lock Rate",
         [("%.2f" % clip(b["$lsdlockcoefrev_R"] + d), {"$lsdlockcoefrev_R": clip(b["$lsdlockcoefrev_R"] + d)}) for d in (-0.12, -0.06, 0, 0.06, 0.12)]),
        ("heave", "Heave Springs", "Suspension > Heave Spring (front and rear)",
         [("x%.1f" % k, {"$heave_spring_F": round(b["$heave_spring_F"] * k), "$heave_spring_R": round(b["$heave_spring_R"] * k)}) for k in HEAVE]),
        ("height", "Ride Height", "Suspension > Spring Height (front and rear)",
         [("%+d mm" % d, {"$springheight_F": round(b["$springheight_F"] + d / 1000, 4), "$springheight_R": round(b["$springheight_R"] + d / 1000, 4)})
          for d in (-6, -3, 0, 3, 6)]),
        ("rake", "Rake", "Suspension > Spring Height (rear only)",
         [("rear %+d mm" % d, {"$springheight_R": round(b["$springheight_R"] + d / 1000, 4)}) for d in (-8, -4, 0, 4, 8)]),
        ("tyres", "Tyre Pressures", "Wheels > Tire Pressure (front and rear)",
         [("%g/%g psi" % (b["$tirepressure_F"] + d, b["$tirepressure_R"] + d),
           {"$tirepressure_F": b["$tirepressure_F"] + d, "$tirepressure_R": b["$tirepressure_R"] + d}) for d in (-4, -2, 0, 2, 4)]),
        ("bias", "Brake Bias", "Brakes > Brake Bias",
         [("%d%% front" % round((b["$brakebias"] + d) * 100), {"$brakebias": round(b["$brakebias"] + d, 3)}) for d in (-0.04, -0.02, 0, 0.02, 0.04)]),
    ]


def build_grid(b):
    """The two balance levers that interact most, as a 3 x 3 grid."""
    wf, af, ar = b["$wing_angle_F"], b["$arb_spring_F"], b["$arb_spring_R"]
    return ("wingxroll", "Wing x Roll", "Front Wing Angle and Anti-Roll Bars",
            [("wing %+d° / roll %s" % (wf + dw, rl), {"$wing_angle_F": wf + dw, "$arb_spring_F": af + ROLL[ri][0], "$arb_spring_R": ar + ROLL[ri][1]})
             for dw in (-2, 0, 2) for rl, ri in (("front", 1), ("base", 2), ("rear", 3))])


def summary(v):
    """A few offline numbers that tell the levels of a sweep apart."""
    mr = sr.mass_report(v)
    v._yf, v._yr = mr["yf"], mr["yr"]
    aero, _ = sr.aero_report(v)
    sus = sr.suspension_report(v, mr)
    q = 0.5 * sr.RHO * (300 / 3.6) ** 2
    rollF = sus["F"]["roll"] / (sus["F"]["roll"] + sus["R"]["roll"])
    return dict(cla=aero[300]["down"] / q, cda=aero[300]["drag"] / q, front=aero[300]["front"], roll_front=rollF,
                heaveF=sus["F"]["heave"] / 1000, heaveR=sus["R"]["heave"] / 1000,
                sagF=sus["F"]["sag"] * 1000, sagR=sus["R"]["sag"] * 1000)


def check(v, name):
    st = sr.stability_report(v)
    if st["max"] > fs.MAX_OMEGA_DT:
        raise SystemExit(f"{name}: highest mode omega*dt {st['max']:.2f} > {fs.MAX_OMEGA_DT}")
    if st["damped"] > fs.MAX_DAMPED:
        raise SystemExit(f"{name}: highest damped mode {st['damped']:.2f} > {fs.MAX_DAMPED}")
    hits = sr.wheel_clearance(v, fs.WHEEL_CLEARANCE)
    if hits:
        raise SystemExit(f"{name}: nodes near a spinning wheel: {hits[:3]}")
    mr = sr.mass_report(v)
    v._yf, v._yr = mr["yf"], mr["yr"]
    aero, _ = sr.aero_report(v)
    worst = sr.strength_report(v, mr, aero)[0]
    if worst[0] > fs.STRENGTH_MAX_RATIO:
        raise SystemExit(f"{name}: beam {worst[3]}-{worst[4]} at {worst[0]:.2f} of its deform limit ({worst[1]})")
    return max(st["max"], 0), worst[0]


def thumbnail(label, path):
    subprocess.run(["convert", f"{V}/baseline.jpg", "-gravity", "South", "-fill", "white",
                    "-undercolor", "#000000B0", "-font", "DejaVu-Sans-Bold", "-pointsize", "40",
                    "-annotate", "+0+24", f" {label} ", "-quality", "85", path], check=True)


def main():
    os.chdir(REPO)
    for f in glob.glob(f"{V}/sweep_*") + glob.glob(f"{V}/info_sweep_*"):
        os.remove(f)
    base = json.load(open(f"{V}/baseline.pc"))
    base_info = json.load(open(f"{V}/info_baseline.json"))
    sheet = ["# Setup sweeps", "",
             "Test cars generated by `tools/rb14/sweeps.py`: each changes one thing from",
             "**Baseline** (everything else identical). In the game they are in the RB14's",
             "configuration list as *Sweep NN · ...*. Drive each sweep's cars back to back",
             "on one track and note which step feels best; if that is 1/5 or 5/5, the",
             "sweet spot may lie beyond it -- ask for that sweep to be widened.",
             "",
             "Offline estimates (setup_report): ClA / front = downforce coefficient and",
             "aero balance at 300 km/h, roll F = front share of roll stiffness, sag =",
             "static ride-height change (+ = lower). The aero numbers use the modelled",
             "ride height, so sweeps 06-07 only show their height change offline.", ""]
    bv = {k: float(x) for k, x in base["vars"].items()}
    sweeps = build_sweeps(bv)
    all_sweeps = [(i + 1, sw) for i, sw in enumerate(sweeps)] + [(len(sweeps) + 1, build_grid(bv))]
    count = 0
    for num, (key, title, where, levels) in all_sweeps:
        sheet += [f"## Sweep {num:02d} · {title}", "", f"Tuning menu: {where}.", "",
                  "| Car | Setting | ClA / front | roll F | sag F / R | best? | notes |",
                  "|---|---|---|---|---|---|---|"]
        for n, (label, over) in enumerate(levels, 1):
            name = f"sweep_{key}_{n}"
            vars_ = dict(base["vars"])
            vars_.update(over)
            is_base = all(abs(float(base["vars"][k]) - float(x)) < 1e-6 for k, x in over.items())
            ui = f"Sweep {num:02d} · {title} {label} ({n}/{len(levels)}{', baseline' if is_base else ''})"
            pc = {**base, "vars": {k: vars_[k] for k in sorted(vars_)}}
            with open(f"{V}/{name}.pc", "w", newline="\n") as fh:
                json.dump(pc, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            v = sr.Vehicle("redbull", name)
            stab, strength = check(v, name)
            s = summary(sr.Vehicle("redbull", name))
            changed = ", ".join(f"{k.lstrip('$')} {x:g}" for k, x in over.items())
            if key in ("height", "rake"):
                # the offline aero model uses the modelled node positions, so
                # it can't see ride height; give the height change instead
                hF, hR = (round(-s[k]) or 0 for k in ("sagF", "sagR"))
                est = (f"Static ride height {hF:+d} mm front / {hR:+d} mm rear vs Baseline "
                       f"(the aero change from ride height and rake only shows in the game).")
            else:
                est = (f"Offline estimate: ClA {s['cla']:.2f} m², {s['front'] * 100:.0f}% front at 300 km/h, "
                       f"front roll stiffness {s['roll_front'] * 100:.0f}%.")
            desc = (f"Setup sweep {num:02d}, step {n} of {len(levels)}: {title.lower()} {label}"
                    f"{' (the baseline value)' if is_base else ''}. Everything else is Baseline. "
                    f"Tuning menu: {where} ({changed}). {est}")
            info = {**base_info, "Config Type": "Custom", "Configuration": ui, "Description": desc}
            with open(f"{V}/info_{name}.json", "w", newline="\n") as fh:
                json.dump(info, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            thumbnail(f"Sweep {num:02d} · {title} {label} ({n}/{len(levels)})", f"{V}/{name}.jpg")
            sheet.append(f"| `{name}` {n}/{len(levels)}{' (baseline)' if is_base else ''} | {label} | "
                         f"{s['cla']:.2f} / {s['front'] * 100:.0f}% | {s['roll_front'] * 100:.0f}% | "
                         f"{s['sagF']:+.1f} / {s['sagR']:+.1f} mm | | |")
            print(f"{ui:60s} ω·dt {stab:.2f}  strength {strength:.2f}  ClA {s['cla']:.2f} front {s['front'] * 100:.0f}% "
                  f"rollF {s['roll_front'] * 100:.0f}%")
            count += 1
        sheet.append("")
    with open("plans/sweeps.md", "w") as fh:
        fh.write("\n".join(sheet))
    print(f"{count} sweep cars written; test sheet plans/sweeps.md")


if __name__ == "__main__":
    main()
