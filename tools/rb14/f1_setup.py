#!/usr/bin/env python3
"""Milestone 4: turn the re-fitted F4 physics into a 2018 F1 car.

    python3 tools/rb14/f1_setup.py

Sets absolute values (never increments), so it is safe to re-run, e.g. after
fit_jbeam.py. Each block below states the real-world target it implements;
tools/rb14/setup_report.py checks the result against plans/rb14-model-swap.md.
Coordinates are left to fit_jbeam.py; this only touches physics parameters.
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
import jbeam_edit as je  # noqa: E402

V = "vehicles/redbull"
W = "vehicles/common/redbull_wheels"


def weights(path, table):
    for node, w in table.items():
        je.set_node_option(path, node, "nodeWeight", w)


# ---------------------------------------------------------------- mass
# 2018 F1: 733 kg minimum including the driver (fuel on top). Power unit
# >= 145 kg; ~80 kg driver sitting low; light unsprung corners; ballast in
# the plank to reach the minimum and set ~45.5 % front. The F4 carried its
# driver as 5 kg nodes from floor to roll hoop; move that mass down.
def mass():
    # tub + driver (~150 kg): heavy low nodes (seat, floor of the tub), light
    # high ones (cockpit rim, halo, hoop)
    weights(f"{V}/redbull_body.jbeam", {
        "rt1r": 12, "rt1l": 12, "rt3r": 12, "rt3l": 12,        # tub floor, rear
        "mt1r": 8, "mt1l": 8, "mt1": 10,                        # tub floor, front
        "rt2r": 3, "rt2l": 3, "rt4r": 3, "rt4l": 3,             # cockpit rim / hoop base
        "mt2r": 5, "mt2l": 5, "mt3": 8, "fs1": 6,
        "fx1r": 5.5, "fx1l": 5.5, "fx2r": 5.5, "fx2l": 5.5,     # front bulkhead, low
        "fx3r": 5, "fx3l": 5, "fx4r": 5, "fx4l": 5})
    # power unit 145 kg (ICE, turbo, MGU-K/H), CoG ~0.3 m
    weights(f"{V}/redbull_engine.jbeam", {
        "e1r": 25, "e1l": 25, "e2r": 25, "e2l": 25, "e3r": 11.25, "e3l": 11.25, "e4r": 11.25, "e4l": 11.25})
    # gearbox + casing ~40 kg
    weights(f"{V}/redbull_transaxle.jbeam", {
        "rx1r": 5, "rx1l": 5, "rx2r": 5, "rx2l": 5, "rx3r": 5, "rx3l": 5, "rx4r": 5, "rx4l": 5})
    weights(f"{V}/redbull_differential_R.jbeam", {"rdiff": DIFF_NODE_WEIGHT})
    # rear crash structure: the F4's 1 kg nodes sit right at the stability limit
    weights(f"{V}/redbull_crashbox.jbeam", {n: 1.15 for n in ("cb1r", "cb1l")})
    weights(f"{V}/redbull_crashbox.jbeam", {n: 1.15 for n in ("cb3r", "cb3l")})
    weights(f"{V}/redbull_crashbox.jbeam", {n: 1.0 for n in ("cb4r", "cb4l")})
    # uprights, brakes, wishbone ends: roughly half the F4's corner mass
    weights(f"{V}/redbull_suspension_F.jbeam", {
        "fh1r": 5, "fh1l": 5, "fh2r": 1, "fh2l": 1, "fh3r": 4, "fh3l": 4, "fh4r": 4, "fh4l": 4, "fh5r": 4, "fh5l": 4})
    weights(f"{V}/redbull_suspension_R.jbeam", {
        "rh1r": 5, "rh1l": 5, "rh3r": 4, "rh3l": 4, "rh4r": 4, "rh4l": 4})
    weights(f"{V}/redbull_suspension_F.jbeam", {"fh6r": 6.5, "fh6l": 6.5})  # steering rack ends (stiff rack: see stiffness())
    # chassis nodes that carry very stiff beams keep enough mass for the
    # 2 kHz solver (see stiffness() below)
    weights(f"{V}/redbull_body.jbeam", CHASSIS_MIN_MASS)
    ballast()


# Plank ballast + ES (battery, ~25 kg) along the centre of the floor. Solved
# (setup_report) so the car makes 733 kg with the driver and no fuel and
# 45.5 % front whatever the other node weights are: a front group and a rear
# group of floor nodes are scaled from these shapes.
BALLAST_F = {"fl1r": 9, "fl1l": 9, "fl2": 14, "fl2r": 6, "fl2l": 6}
BALLAST_R = {"fl3": 25, "fl3r": 15, "fl3l": 15, "fl4": 20, "fl4r": 7, "fl4l": 7}
DRY_MASS, FRONT = 733.0, 0.465   # 46.5 % front (round 8: heavier wheel carriers; also calms the rear)


def ballast():
    import numpy as np
    import setup_report as sr
    f = f"{V}/redbull_floor.jbeam"
    weights(f, {**BALLAST_F, **BALLAST_R})

    def state():
        v = sr.Vehicle("redbull", None)
        v.variables["$fuel"] = 0
        v._nodes()
        mr = sr.mass_report(v)
        return mr["total"], mr["front"] * mr["total"]

    m0, f0 = state()
    sF, sR = sum(BALLAST_F.values()), sum(BALLAST_R.values())
    # front-axle share of each group (lever rule on the node positions)
    v = sr.Vehicle("redbull", None)
    mr = sr.mass_report(v)
    share = lambda g: sum(w * (mr["yr"] - v.pos[n][1]) / (mr["yr"] - mr["yf"]) for n, w in g.items()) / sum(g.values())
    aF, aR = share(BALLAST_F), share(BALLAST_R)
    # solve for new group totals xF, xR
    A = np.array([[1, 1], [aF, aR]])
    b = np.array([DRY_MASS - (m0 - sF - sR), FRONT * DRY_MASS - (f0 - aF * sF - aR * sR)])
    xF, xR = np.linalg.solve(A, b)
    if xF < 0 or xR < 0:
        raise ValueError(f"ballast would be negative (front {xF:.1f}, rear {xR:.1f} kg): car too heavy")
    if min(xF / sF, xR / sR) * min(min(BALLAST_F.values()), min(BALLAST_R.values())) < 1.0:
        raise ValueError(f"ballast too small (front {xF:.1f}, rear {xR:.1f} kg): floor nodes would drop under 1 kg")
    new = {n: round(w * xF / sF, 2) for n, w in BALLAST_F.items()}
    new.update({n: round(w * xR / sR, 2) for n, w in BALLAST_R.items()})
    weights(f, new)
    print("ballast: front %.1f kg, rear %.1f kg" % (xF, xR))


# ------------------------------------------------------------ stability
# BeamNG integrates at 2 kHz; every vibration mode of the node/beam network
# must stay below omega * dt = 2 or the solver pumps energy into it (the car
# shakes, beams break, wheels come off). setup_report.stability_report()
# computes the modes, including an approximation of the wheels the game
# generates. Calibration from game tests: the F4 (fine) peaks at 1.84 with
# the wheels / 1.69 without; our 1.77 chassis mode visibly shook and 1.96 at
# the wheel axles lost the wheels. Target: <= 1.65 everywhere.
# Lightening the uprights and wheel carriers for F1 unsprung mass put them
# over the limit on the F4's very stiff wishbone / hub beams (8-14 MN/m,
# 40-80x the wheel rate); those are capped instead of adding the mass back
# (the arms stay ~30x stiffer than the suspension, so handling barely
# changes). Chassis and gearbox nodes get mass instead, paid for by the
# plank ballast (solved in ballast()).
MAX_OMEGA_DT = float(os.environ.get("RB14_MAX_OMEGA_DT", 1.65))
HUB_SPRING_SCALE = 0.65                      # hub beams vs the F4's (hub nodes 0.35 vs 0.55 kg)
HUB_NODE_WEIGHT = 0.45                       # kg x 32 per rim (was 0.35; F4 0.55)
CARRIER_DAMP = 600                           # beamDamp floor on the capped wheel-carrier beams
WHEEL_AXLE_WEIGHT = 4.5                      # kg, wheel axle nodes (F4: 5)
CHASSIS_MIN_MASS = {"rt4r": 4.5, "rt4l": 4.5}
HUB_TORSION_F = 80000                        # was 200000 (F4)
SPRING_CAP = {                               # part -> highest beamSpring (N/m)
    "redbull_suspension_F": 6.0e6,
    "redbull_steering": 10.0e6,          # steering hydros at the F4's 10 MN/m (tie rods 14 -> 10): a softer rack let
                                          # the front wheels sit off-centre after a turn
    "redbull_suspension_R": 6.0e6,
}
SPRING_CAP_FILES = {"redbull_suspension_F": "suspension_F", "redbull_steering": "suspension_F",
                    "redbull_suspension_R": "suspension_R"}


def stiffness():
    import re
    for part, cap in SPRING_CAP.items():
        name = SPRING_CAP_FILES[part]
        f = f"{V}/redbull_{name}.jbeam"
        orig = open(f"vehicles/fr04/fr04_{name}.jbeam", encoding="utf-8", newline="").read()
        a0, b0 = _part_block(orig, part.replace("redbull", "fr04"))
        text = je._read(f)
        a, b = _part_block(text, part)
        pat = re.compile(r'("beamSpring"\s*:\s*)(\d+(?:\.\d+)?)(\s*,\s*"beamDamp"\s*:\s*\d+(?:\.\d+)?)?')
        src = [(float(m.group(2)), m.group(3)) for m in pat.finditer(orig[a0:b0])]
        block = text[a:b]
        if len(pat.findall(block)) != len(src):
            raise ValueError(f"{part}: beamSpring count differs from the F4")
        it = iter(src)

        def cap_row(m):
            k, damp = next(it)
            out = m.group(1) + "%d" % min(k, cap)
            if damp:
                d = float(re.search(r'([\d.]+)$', damp).group(1))
                if k > cap and part != "redbull_steering":
                    d = max(d, CARRIER_DAMP)      # capped carrier beams: damp the wheel judder
                out += re.sub(r'[\d.]+$', "%d" % d, damp)
            return out
        block = pat.sub(cap_row, block)
        je._write(f, text[:a] + block + text[b:])
    # the front steering-arm rigidifier torsionbar has ~0.13 m arms, so its
    # 200 kNm/rad acts like a ~10 MN/m spring on the light upright nodes
    je.set_in_part(f"{V}/redbull_suspension_F.jbeam", "redbull_suspension_F",
                   r'\{"spring":\d+, "damp":0, "deform":\d+, "strength":\d+\}',
                   '{"spring":%d, "damp":0, "deform":%d, "strength":%d}' % (HUB_TORSION_F, 25000 * 4, 100000 * 4))
    je.set_in_part(f"{V}/redbull_suspension_R.jbeam", "redbull_suspension_R",
                   r'\{"spring":50000, "damp":0, "deform":\d+, "strength":\d+\}',
                   '{"spring":50000, "damp":0, "deform":%d, "strength":%d}' % (35000 * 4, 100000 * 4))
    # generated wheel hubs: lighter hub nodes than the F4 (0.35 vs 0.55 kg),
    # so the hub beams scale with them to keep the F4's (stable) frequencies
    k = HUB_SPRING_SCALE
    for f in (f"{W}/redbull_wheels_F_13.jbeam", f"{W}/redbull_wheels_R_13.jbeam"):
        je.set_all(f, r'\{"hubTreadBeamSpring":\d+,', '{"hubTreadBeamSpring":%d,' % (990900 * k))
        je.set_all(f, r'\{"hubPeripheryBeamSpring":\d+,', '{"hubPeripheryBeamSpring":%d,' % (990900 * k))
        je.set_all(f, r'\{"hubSideBeamSpring":\d+,', '{"hubSideBeamSpring":%d,' % (1601000 * k))
        je.set_all(f, r'\{"hubBeamDeform":\d+, "hubBeamStrength":\d+\}',
                   '{"hubBeamDeform":%d, "hubBeamStrength":%d}' % (43600 * RIM_STRENGTH_SCALE, 78000 * RIM_STRENGTH_SCALE))
    for axle, tread in (("F", (13000, 17000, 55000, 55000)), ("R", (12000, 16000, 50000, 50000))):
        f = f"{W}/redbull_tires_{axle}_13.jbeam"
        k = TYRE_STRENGTH_SCALE
        je.set_all(f, r'\{"wheelSideBeamDeform":\d+,"wheelSideBeamStrength":\d+\}',
                   '{"wheelSideBeamDeform":%d,"wheelSideBeamStrength":%d}' % (17000 * k, 22000 * k))
        je.set_all(f, r'\{"wheelTreadBeamDeform":\d+,"wheelTreadBeamStrength":\d+\}',
                   '{"wheelTreadBeamDeform":%d,"wheelTreadBeamStrength":%d}' % (tread[0] * k, tread[1] * k))
        je.set_all(f, r'\{"wheelPeripheryBeamDeform":\d+,"wheelPeripheryBeamStrength":\d+\}',
                   '{"wheelPeripheryBeamDeform":%d,"wheelPeripheryBeamStrength":%d}' % (tread[2] * k, tread[3] * k))


# --------------------------------------------------------- torque paths
# Drive and brake torque reach the chassis through the nodes each pressure
# wheel names; the force is torque / lever, so short levers make huge forces.
# The F4 named a drive torqueCoupling ("tra1") that doesn't exist, a
# torqueArm 2 cm from the axle line and an engine node as torqueArm2; its
# rear brake arm was the lower upright node (7 cm lever on the RB14). Fine
# for the F4's ~2 kNm of drive torque, not for ~9.7 kNm in first gear and
# 2-3 kNm of brake torque per wheel. Per BeamNG's docs: coupling at the
# differential, arms on the same rigid structure (the gearbox), not in line.
# And the beams on those load paths are made ~3x stronger than the F4's
# (loads are 3.4-4.7x higher; the longer levers take the rest).
# Coupling at the differential; arms on the engine block (bolted rigidly to
# the gearbox): the lower engine node (25 kg, 0.77 m away) and the opposite
# upper one (11 kg, 0.78 m, out of line). BeamNG: "nodes that are heavier and
# further apart allow more torque before running into stability issues" --
# 5 kg gearbox nodes 0.4-0.5 m away made the rear wheels shake and break
# under first-gear torque (4.8 kNm per wheel).
# Round 8: the car pulled to one side pulling away. Both wheels now use the
# same, left-right symmetric set (the two lower engine nodes); before, each
# wheel had its own diagonal pair.
DRIVE_REACTION = {"R": ("rdiff", "e2r", "e2l"), "L": ("rdiff", "e2l", "e2r")}
DIFF_NODE_WEIGHT = 10.0         # kg, differential + final drive (was 5)
BRAKE_ARM_R = {"R": "rh3r", "L": "rh3l"}      # upper upright node, 13 cm lever
# part -> (file, deform/strength multiple of the F4's). setup_report's
# strength_report() load cases (aero at 300 km/h, 5 g braking, 4.7 g
# cornering, traction, each with a 1.5x bump factor) must stay under half
# of every corner beam's beamDeform (STRENGTH_MAX_RATIO).
STRENGTH_PARTS = {"redbull_suspension_F": ("suspension_F", 5.0), "redbull_suspension_R": ("suspension_R", 6.0),
                  "redbull_coilover_F": ("suspension_F", 4.0), "redbull_coilover_R": ("suspension_R", 4.0),
                  "redbull_swaybar_F": ("suspension_F", 4.0), "redbull_swaybar_R": ("suspension_R", 4.0),
                  "redbull_steering": ("suspension_F", 3.0),
                  "redbull_differential_R": ("differential_R", 3.0), "redbull_halfshafts_R": ("differential_R", 3.0)}
STRENGTH_MAX_RATIO = 0.5
TORSION_DEFORM = 40000          # Nm, ARB and heave torsionbars (F4 ARB: 10000)
# the F4's tyres and rims carried ~1.5 g on a 650 kg car; F1 loads are 3-4x
TYRE_STRENGTH_SCALE = 4.0
RIM_STRENGTH_SCALE = 4.0


def torque_paths():
    import re
    f = f"{V}/redbull_suspension_R.jbeam"
    for side in ("R", "L"):
        c, a1, a2 = DRIVE_REACTION[side]
        text = je._read(f)
        pat = re.compile(r'(\["R%s", "wheel_R%s", "tire_R%s", "rw1%s", "rw1%s", 9999, )"[^"]+"(, -?1, \{)"torqueCoupling:":"[^"]*", "torqueArm:":"[^"]*",\s*"torqueArm2:":"[^"]*"'
                         % (side, side, side, side.lower() * 2, side.lower()))
        text, n = pat.subn(lambda m: m.group(1) + '"%s"' % BRAKE_ARM_R[side] + m.group(2)
                           + '"torqueCoupling:":"%s", "torqueArm:":"%s", "torqueArm2:":"%s"' % (c, a1, a2), text)
        if n != 1:
            raise ValueError(f"rear wheel {side}: pressureWheels row not found")
        je._write(f, text)
    # beam strengths on the load paths, from the F4 originals
    for part, (name, scale) in STRENGTH_PARTS.items():
        f = f"{V}/redbull_{name}.jbeam"
        orig = open(f"vehicles/fr04/fr04_{name}.jbeam", encoding="utf-8", newline="").read()
        a0, b0 = _part_block(orig, part.replace("redbull", "fr04"))
        text = je._read(f)
        a, b = _part_block(text, part)
        block = text[a:b]
        for key in ("beamDeform", "beamStrength"):
            pat = re.compile(r'("%s"\s*:\s*)(\d+(?:\.\d+)?)' % key)
            src = [float(m.group(2)) for m in pat.finditer(orig[a0:b0])]
            if len(pat.findall(block)) != len(src):
                raise ValueError(f"{part}: {key} count differs from the F4")
            it = iter(src)
            block = pat.sub(lambda m: m.group(1) + "%d" % (next(it) * scale), block)
        je._write(f, text[:a] + block + text[b:])


# ------------------------------------------------------------- steering
# The F4's steering actuators (hydros) move at inRate/outRate 1.25 -- slower
# than BeamNG's default 2 -- so the rack lagged the input by up to ~0.8 s
# lock to centre: vague, and off-centre for a moment after a sharp turn
# (round 7). F1 steering is direct: faster actuators, more road-wheel angle
# per input (factor), fewer steering-wheel degrees to full lock.
STEER_RATE = 4.0
STEER_FACTOR = 0.095            # hydro length change at full input (F4 0.072)
STEER_WHEEL_LOCK = 180          # steering-wheel degrees at full lock (F4 230)


def steering():
    f = f"{V}/redbull_suspension_F.jbeam"
    for side, sign in (("r", ""), ("l", "-")):
        je.set_all(f, r'\["fh6%s","fx3[rl]", \{"factor":\s*-?[\d.]+,"steeringWheelLock":\d+, "inRate":[\d.]+,"outRate":[\d.]+\}\]' % side,
                   '["fh6%s","fx3%s", {"factor":%s%s,"steeringWheelLock":%d, "inRate":%s,"outRate":%s}]'
                   % (side, "l" if side == "r" else "r", sign, STEER_FACTOR, STEER_WHEEL_LOCK, STEER_RATE, STEER_RATE))


# ------------------------------------------------------------ rear wing
# Round 7: the rear wing flexed back and forth at speed. It hung only from
# its endplates and beam wing (F4 stiffness, sized for a fraction of the
# RB14's ~6 kN of rear-wing downforce) on 0.25-0.4 kg nodes. Now: a central
# pylon (the RB14's swan neck) from the wing's trailing edge -- which DRS
# doesn't move -- to the crash structure, the wing's own beams 3x stiffer
# and better damped, a stiffer DRS actuator, and ~10 kg of wing assembly.
WING_R_STIFF = 3.0
WING_R_DAMP = 150
WING_R_WEIGHTS = {"wing": 0.6, "beamwing": 0.8, "beamwing_mid": 0.9, "endplate": 0.6}
PYLON = dict(spring=1201000, damp=200, deform=60000, strength=150000)
# The pylon lands on the gearbox, the same rigid structure the beam wing
# and endplates hang from. (Round 8: mounted on the crumple-zone crash box
# it moved differently from the endplates on the spawn jolt and snapped
# the F4-strength endplate-to-wing beams -- the wing top broke off.)
PYLON_BASE = ("rx4r", "rx4l", "rx3r", "rx3l")   # gearbox top, rear and front: braced fore-aft
WING_R_STRENGTH = 4.0           # deform / break forces of the wing's beams vs the F4's


def rear_wing():
    import re
    f = f"{V}/redbull_wing_R.jbeam"
    text = je._read(f)
    for group, key in (("redbull_wing_R", "wing"), ("redbull_wing_B", "beamwing"), ("redbull_endplate_RR", "endplate")):
        text, n = re.subn(r'(\{"nodeWeight":)[\d.]+(\},\r\n         \{"group":"%s"\})' % group,
                          lambda m: m.group(1) + str(WING_R_WEIGHTS[key]) + m.group(2), text)
        if n != 1:
            raise ValueError(f"rear wing: node weight row for {group} not found")
    text = re.sub(r'(\["bwg1",\s*0\.0, [\d.]+, [\d.]+,\{"nodeWeight":)[\d.]+', lambda m: m.group(1) + str(WING_R_WEIGHTS["beamwing_mid"]), text)
    # wing beams from the F4 originals (the "{spring, damp}" option rows)
    orig = open("vehicles/fr04/fr04_wing_R.jbeam", encoding="utf-8", newline="").read()
    pat = re.compile(r'\{"beamSpring":(\d+),"beamDamp":(\d+)\}')
    src = [(int(a), int(b)) for a, b in pat.findall(orig)]
    if len(pat.findall(text)) != len(src):
        raise ValueError("rear wing: option rows differ from the F4")
    it = iter(src)

    def row(m):
        k, d = next(it)
        if k >= 50000:                       # structure, not the weak helper links
            k, d = int(k * WING_R_STIFF), max(d, WING_R_DAMP)
        return '{"beamSpring":%d,"beamDamp":%d}' % (k, d)
    text = pat.sub(row, text)
    # deform / break forces with the stiffness (from the F4 originals)
    pat = re.compile(r'\{"beamDeform":("FLT_MAX"|\d+),"beamStrength":("FLT_MAX"|\d+)\}')
    src = pat.findall(orig)
    if len(pat.findall(text)) != len(src):
        raise ValueError("rear wing: deform/strength rows differ from the F4")
    it = iter(src)
    scale = lambda x: x if x.startswith('"') else "%d" % (int(x) * WING_R_STRENGTH)
    text = pat.sub(lambda m: (lambda d, st: '{"beamDeform":%s,"beamStrength":%s}' % (scale(d), scale(st)))(*next(it)), text)
    # pylon, inline options so nothing carries on into later parts
    text = re.sub(r'          //pylon \(f1_setup\.py\).*?\r\n(          \["rwg2","(?:cb|rx)[1-4][rl]", \{[^}]*\}\],\r\n)+', "", text, flags=re.S)
    opts = ('{"beamSpring":%d, "beamDamp":%d, "beamDeform":%d, "beamStrength":%d, "breakGroup":"wing_R_pylon"}'
            % (PYLON["spring"], PYLON["damp"], PYLON["deform"], PYLON["strength"]))
    block = "          //pylon (f1_setup.py): swan neck from the trailing edge to the gearbox\r\n" + "".join(
        '          ["rwg2","%s", %s],\r\n' % (n, opts) for n in PYLON_BASE)
    at = text.index('    ],\r\n    "hydros": [')
    text = text[:at] + block + text[at:]
    je._write(f, text)


def check_stability():
    import setup_report as sr
    worst = 0.0
    for cfg in CONFIGS:
        st = sr.stability_report(sr.Vehicle("redbull", cfg))
        worst = max(worst, st["max"])
        if st["max"] > MAX_OMEGA_DT:
            raise SystemExit(f"{cfg}: highest mode omega*dt {st['max']:.2f} > {MAX_OMEGA_DT}: {st['modes'][0]}")
    print("stability: highest mode omega*dt %.2f (limit 2, target <= %.2f)" % (worst, MAX_OMEGA_DT))
    for cfg in CONFIGS:
        hits = sr.wheel_clearance(sr.Vehicle("redbull", cfg), WHEEL_CLEARANCE)
        if hits:
            raise SystemExit("%s: nodes inside / within %d mm of a spinning wheel: %s" % (
                cfg, WHEEL_CLEARANCE * 1000, ", ".join("%s %s %+.0f mm" % (w, n, g * 1000) for g, w, n in hits[:6])))
    print("wheel clearance: nothing within %d mm of a spinning wheel" % (WHEEL_CLEARANCE * 1000))
    worst = None
    for cfg in CONFIGS:
        v = sr.Vehicle("redbull", cfg)
        mr = sr.mass_report(v)
        v._yf, v._yr = mr["yf"], mr["yr"]
        aero, _ = sr.aero_report(v)
        top = sr.strength_report(v, mr, aero)[0]
        if worst is None or top[0] > worst[0]:
            worst = top + (cfg,)
    ratio, case, part, a, b, force, dfm, cfg = worst
    msg = "strength: worst corner beam at %.2f of its deform limit (%s, %s %s-%s, %.1f kN / %.1f kN, %s)" % (
        ratio, case, part, a, b, abs(force) / 1000, dfm / 1000, cfg)
    if ratio > STRENGTH_MAX_RATIO:
        raise SystemExit(msg + " > %.2f" % STRENGTH_MAX_RATIO)
    print(msg)


# Rim ring width. The pressure wheel's rim ring spins with the wheel; the
# RB14's real rim widths (0.30 / 0.35 m) put the rear ring's inner edge
# 175 mm inboard of the wheel centre, exactly on the rear upright's top
# node (rh4, 172 mm from the axle): the wheel caught on it every
# revolution. Keep the rings between the axle nodes (0.27 m apart), as the
# F4 did; the tyres keep their 305 / 405 mm width.
HUB_WIDTH = {"F": 0.26, "R": 0.26}
WHEEL_CLEARANCE = 0.025         # m, nothing within this of a spinning wheel


def wheels():
    for a in ("F", "R"):
        je.set_all(f"{W}/redbull_wheels_{a}_13.jbeam", r'\{"hubWidth":[\d.]+\}', '{"hubWidth":%s}' % HUB_WIDTH[a])
    # axle nodes of the wheel parts: 3 kg each (were 5)
    for f in (f"{W}/redbull_wheels_F_13.jbeam", f"{W}/redbull_wheels_R_13.jbeam"):
        je.set_all(f, r'\{"nodeWeight":[\d.]+\}', '{"nodeWeight":%s}' % WHEEL_AXLE_WEIGHT)
        # rims + hubs + discs: 32 hub nodes x 0.35 kg = 11 kg per wheel (were 0.55)
        je.set_all(f, r'\{"hubNodeWeight":[\d.]+\}', '{"hubNodeWeight":%s}' % HUB_NODE_WEIGHT)


# --------------------------------------------------------------- tyres
# 2018 Pirelli P Zero 13in: front 305/670 (~9.6 kg), rear 405/670 (~10.9 kg);
# 21 / 19.5 psi (near Pirelli's 2018 minimums). Grip with strong load
# sensitivity, BeamNG's mu = full + (noLoad - full) * exp(-slope * load):
# ~1.9 at 2 kN (slow corners, ~2 g) falling to ~1.26 at 7 kN (fast corners
# with 3x-weight downforce, ~4.5 g).
# The 405 mm rears get ~5 % more grip than the 305 mm fronts (round 7: the
# rear let go too easily; wider tyres, same load sensitivity).
TYRE_GRIP = {"F": (2.65, 1.07), "R": (2.78, 1.12)}      # noLoadCoef, fullLoadCoef (round 8: +6.5 % all round)


def tyres():
    for axle, node_w in (("F", 0.30), ("R", 0.34)):
        f = f"{W}/redbull_tires_{axle}_13.jbeam"
        dry, wet = f"tire_{axle}_redbull", f"tire_{axle}_redbull_wet"
        for part in (dry, wet):
            je.set_in_part(f, part, r'\{"nodeWeight":[\d.]+\}', '{"nodeWeight":%s}' % node_w)
        je.set_in_part(f, dry, r'\{"noLoadCoef":[\d.]+\}', '{"noLoadCoef":%s}' % TYRE_GRIP[axle][0])
        je.set_in_part(f, dry, r'\{"fullLoadCoef":[\d.]+\}', '{"fullLoadCoef":%s}' % TYRE_GRIP[axle][1])
        je.set_in_part(f, dry, r'\{"loadSensitivitySlope":[\d.]+\}', '{"loadSensitivitySlope":0.00025}')
        # wets: less grip than slicks on a dry track, tread for standing water
        je.set_in_part(f, wet, r'\{"noLoadCoef":[\d.]+\}', '{"noLoadCoef":2.10}')
        je.set_in_part(f, wet, r'\{"fullLoadCoef":[\d.]+\}', '{"fullLoadCoef":0.85}')
        je.set_in_part(f, wet, r'\{"loadSensitivitySlope":[\d.]+\}', '{"loadSensitivitySlope":0.00025}')
        psi = 21 if axle == "F" else 19.5
        je.set_all(f, r'\["\$tirepressure_%s", "range", "psi", "Wheels", [\d.]+, 0, 50,' % axle,
                   '["$tirepressure_%s", "range", "psi", "Wheels", %s, 0, 50,' % (axle, psi))


# ---------------------------------------------------------------- fuel
# ~110 kg max race fuel (2018: 105 kg limit) -> 140 L tank; configs set the load
def fuel():
    f = f"{V}/redbull_fueltank.jbeam"
    je.set_all(f, r'"fuelCapacity": [\d.]+', '"fuelCapacity": 140')
    je.set_all(f, r'\["\$fuel", "range", "L", "Chassis", [\d.]+, 0, [\d.]+,', '["$fuel", "range", "L", "Chassis", 60, 0, 140,')


# ----------------------------------------------------------- suspension
# 2018 F1: tiny travel, stiff platform. Targets per wheel (setup_report):
#   heave  F ~170 / R ~175 N/mm  -> ~5.5 / ~5 Hz ride on 134 / 170 kg corners
#   roll   F ~320 / R ~240 N/mm  -> ~57 % front roll stiffness (stable, mild
#          understeer; configs trade it)
# The corner springs (hub -> central chassis node, as in the F4) carry
# the static load and give the base rate in both modes. On top of them:
#   - an anti-roll bar per axle (torsionbar across the car, roll only),
#   - a heave spring per axle: a torsionbar about a lengthwise axis on the
#     car's centreline with the two hubs as its arms. Both wheels rising
#     twist it; one up / one down only turns it, so it adds heave rate
#     without roll rate -- the F1 third spring.
# Variables for ARB and heave springs are in N/m of added wheel rate; the
# torsionbar factors (arm length^2 / 2 for heave) were fitted with the
# setup_report FEM. Ride height: spring preload is set so the car sits at its
# modelled height with a 60 L fuel load (static sag ~0), and the spring
# height slider moves the car by that many metres.
SUSP = {
    # axle: spring, heave, arb, bump, rebound, packer gap (m wheel travel)
    "F": dict(spring=355000, heave=70000, arb=260000, bump=14000, rebound=24000, packer=0.025),
    "R": dict(spring=495000, heave=65000, arb=110000, bump=19000, rebound=30000, packer=0.032),
}
# Starting values only: _calibrate() replaces them with values solved on the
# setup_report FEM (spring preload for zero static sag, spring-beam motion
# ratio, torsionbar factors so the variables read as wheel rate).
PRELOAD = {"F": 2650.0, "R": 3700.0}    # static spring-beam force (N)
# Baseline sits this much above the modelled (RB14 model) ride height: the
# plank and front wing endplates scraped at speed at the modelled height
# (round 7). Spring Height 0 = this raised baseline.
RIDE_RAISE = {"F": 0.010, "R": 0.010}
MOTION = {"F": 0.55, "R": 0.50}         # spring-beam travel / wheel travel
HEAVE_ARM2 = {"F": 0.40, "R": 0.40}     # heave torsionbar: k_t = rate * HEAVE_ARM2
ARB_ARM2 = {"F": 0.1225, "R": 0.1225}   # ARB torsionbar:   k_t = rate * ARB_ARM2
HEAVE_AXIS = {"F": ("fs1", "mt3"), "R": ("rs1", "fl7")}


def suspension():
    _write_suspension()
    _alignment()
    _calibrate()
    _write_suspension()


# ------------------------------------------------------------ alignment
# Static alignment at the modelled ride height (2018 F1 ballpark): front
# camber ~-3.2 deg, rear ~-1.8 deg; front toe slightly out, rear toe in.
# The F4 set toe through fixed tie-rod precompression, which on the RB14
# geometry gives ~1.3 deg front toe-in; toe gets its own variables here and
# the defaults are solved on the setup_report FEM.
ALIGN = {"camber_F": -3.2, "camber_R": -1.8, "toe_F": -0.10, "toe_R": 0.40}   # rear toe-in 0.25 -> 0.40 (round 7: rear too loose)


def _alignment():
    fF, fR = f"{V}/redbull_suspension_F.jbeam", f"{V}/redbull_suspension_R.jbeam"
    # toe variables next to camber/caster, and the links they act on
    for f, a, anchor in ((fF, "F", '["$caster_F", "range"'), (fR, "R", '["$camber_R", "range"')):
        text = je._read(f)
        if '["$toe_%s"' % a not in text:
            i = text.index(anchor)
            j = text.index("\r\n", i) + 2
            lo, hi = (0.995, 1.005) if a == "F" else (0.98, 1.02)     # about +-1.7 deg either way
            text = text[:j] + ('        ["$toe_%s", "range", "", "Wheel Alignment", 1.0, %s, %s, "Toe Adjust", '
                               '"Adjusts the toe angle (lower: more toe-in)", {"subCategory":"%s"}],\r\n'
                               % (a, lo, hi, "Front" if a == "F" else "Rear")) + text[j:]
            je._write(f, text)
    je.set_all(fF, r'"beamPrecompression":"\$=\$camber_F\*(?:0\.995|\$toe_F)"', '"beamPrecompression":"$=$camber_F*$toe_F"')
    text = je._read(fR)
    import re
    text = re.sub(r'(\["rx3([rl])","rh4\2", \{"breakGroup":"upperarm_R[RL]","beamPrecompression":)"\$(?:camber_R|=\$camber_R\*\$toe_R)"',
                  lambda m: m.group(1) + '"$=$camber_R*$toe_R"', text)
    je._write(fR, text)

    import numpy as np
    import setup_report as sr

    def static(**kw):
        v = sr.Vehicle("redbull", None)
        v.variables.update({"$" + k: val for k, val in kw.items()})
        mr = sr.mass_report(v)
        sus = sr.suspension_report(v, mr)
        out = {}
        for a in ("F", "R"):
            K, idx, wl, pre, e = sr.axle_system(v, a)
            load = pre.copy()
            for n in wl:
                load[3 * idx[n] + 2] += sus[a]["sprung_corner"] * sr.G / 2
            w = np.zeros(len(K))
            for n in wl:
                w[3 * idx[n] + 2] = 1 / len(wl)
            F0 = -(w @ np.linalg.solve(K, load)) / (w @ np.linalg.solve(K, e))
            u = np.linalg.solve(K, load + F0 * e)
            n1, n2 = a.lower() + "w1r", a.lower() + "w1rr"          # right wheel axle, inner -> outer
            d = (v.pos[n2] + u[3 * idx[n2]:3 * idx[n2] + 3]) - (v.pos[n1] + u[3 * idx[n1]:3 * idx[n1] + 3])
            out["camber_" + a] = -math.degrees(math.atan2(d[2], abs(d[0])))
            out["toe_" + a] = -math.degrees(math.atan2(d[1], abs(d[0])))     # + = toe-in
        return out

    cur = {k: None for k in ALIGN}
    v0 = sr.Vehicle("redbull", None).variables
    vals = {k: float(v0["$" + k]) for k in ("camber_R", "toe_F", "toe_R")}
    for _ in range(3):              # nearly linear: a few secant steps
        base = static(**vals)
        for k in vals:
            h = 0.001
            d = (static(**{**vals, k: vals[k] + h})[k] - base[k]) / h
            vals[k] += (ALIGN[k] - base[k]) / d
        vals = {k: round(x, 4) for k, x in vals.items()}
    res = static(**vals)
    je.set_all(fR, r'\["\$camber_R", "range", "", "Wheel Alignment", [\d.]+,',
               '["$camber_R", "range", "", "Wheel Alignment", %s,' % vals["camber_R"])
    for a in ("F", "R"):
        je.set_all(fF if a == "F" else fR, r'\["\$toe_%s", "range", "", "Wheel Alignment", [\d.]+,' % a,
                   '["$toe_%s", "range", "", "Wheel Alignment", %s,' % (a, vals["toe_" + a]))
    print("alignment:", vals, {k: round(x, 2) for k, x in res.items()})


def _calibrate():
    import numpy as np
    import setup_report as sr

    def vehicle(**kw):
        v = sr.Vehicle("redbull", None)
        v.variables.update({"$" + k: val for k, val in kw.items()})
        return v

    def rates(v):
        return sr.suspension_report(v, sr.mass_report(v))

    off = dict(arb_spring_F=0, arb_spring_R=0, heave_spring_F=0, heave_spring_R=0)
    base = rates(vehicle(**off))
    arb = rates(vehicle(**{**off, "arb_spring_F": 100000, "arb_spring_R": 100000}))
    heave = rates(vehicle(**{**off, "heave_spring_F": 100000, "heave_spring_R": 100000}))
    for a in ("F", "R"):
        ARB_ARM2[a] = float("%.4g" % (ARB_ARM2[a] * 100000 / (arb[a]["roll"] - base[a]["roll"])))
        HEAVE_ARM2[a] = float("%.4g" % (HEAVE_ARM2[a] * 100000 / (heave[a]["heave"] - base[a]["heave"])))
    _write_suspension()
    # ride height: spring preload F0 that puts the wheels at their modelled
    # position (zero sag) under the sprung weight; slope H (N of preload per
    # m of height) at the default rates, split as MR*spring + heave/MR so the
    # spring height slider stays in metres when the rates change
    v = vehicle()
    mr = sr.mass_report(v)
    sus = sr.suspension_report(v, mr)
    for a in ("F", "R"):
        K, idx, wl, pre, e = sr.axle_system(v, a)
        load = pre.copy()
        for n in wl:
            load[3 * idx[n] + 2] += sus[a]["sprung_corner"] * sr.G / 2
        w = np.zeros(len(K))
        for n in wl:
            w[3 * idx[n] + 2] = 1 / len(wl)
        s_load = w @ np.linalg.solve(K, load)
        s_unit = w @ np.linalg.solve(K, e)          # sag per N of spring preload (< 0)
        PRELOAD[a] = round(-s_load / s_unit, 0)
        H = -1 / s_unit
        ks, kh = v.variables["$spring_" + a], v.variables["$heave_spring_" + a]
        MOTION[a] = round((H + math.sqrt(max(H * H - 4 * ks * kh, 0))) / (2 * ks), 4)   # spring-dominated root
    print("calibrated: preload", PRELOAD, "motion", MOTION, "arb", ARB_ARM2, "heave", HEAVE_ARM2)


def _write_suspension():
    for a in ("F", "R"):
        f = f"{V}/redbull_suspension_{a}.jbeam"
        c = SUSP[a]
        sub = "Front" if a == "F" else "Rear"
        hub = "fh1" if a == "F" else "rh1"
        # variables (defaults and ranges)
        je.set_all(f, r'\["\$springheight_%s", "range", "\+m", "Suspension", [^\]]*\]' % a,
                   '["$springheight_%s", "range", "+m", "Suspension", 0, -0.03, 0.03, "Spring Height", '
                   '"Raises or lowers this end of the car (static ride height)", {"stepDis":0.001, "subCategory":"%s"}]' % (a, sub))
        je.set_all(f, r'\["\$spring_%s", "range", "N/m", "Suspension", [^\]]*\]' % a,
                   '["$spring_%s", "range", "N/m", "Suspension", %d, 150000, 900000, "Spring Rate", '
                   '"Corner spring stiffness (heave and roll)", {"stepDis":5000, "subCategory":"%s"}]' % (a, c["spring"], sub))
        je.set_all(f, r'\["\$damp_bump_%s", "range", "N/m/s", "Suspension", [^\]]*\]' % a,
                   '["$damp_bump_%s", "range", "N/m/s", "Suspension", %d, 2000, 40000, "Bump Damping", '
                   '"Damper rate in compression", {"stepDis":500, "subCategory":"%s"}]' % (a, c["bump"], sub))
        je.set_all(f, r'\["\$damp_rebound_%s", "range", "N/m/s", "Suspension", [^\]]*\]' % a,
                   '["$damp_rebound_%s", "range", "N/m/s", "Suspension", %d, 2000, 60000, "Rebound Damping", '
                   '"Damper rate in extension", {"stepDis":500, "subCategory":"%s"}],\r\n'
                   '        ["$heave_spring_%s", "range", "N/m", "Suspension", %d, 0, 300000, "Heave Spring", '
                   '"Third spring: extra wheel rate when both wheels rise together (aero load), none in roll", {"stepDis":5000, "subCategory":"%s"}],\r\n'
                   '        ["$packer_%s", "range", "m", "Suspension", %s, 0.010, 0.050, "Packer Gap", '
                   '"Wheel travel in bump before the packers (progressive bump stops) engage", {"stepDis":0.001, "subCategory":"%s"}]'
                   % (a, c["rebound"], sub, a, c["heave"], sub, a, c["packer"], sub))
        # the added rows above are re-matched by set_all on re-runs: drop duplicates
        _dedupe_rows(f, (f"$heave_spring_{a}", f"$packer_{a}"))
        # spring preload: static load at the modelled height, plus spring height
        je.set_all(f, r'"precompressionRange":"\$=[^"]*"',
                   '"precompressionRange":"$=(($springheight_%s + %s)*(%s*$spring_%s + $heave_spring_%s/%s) + %s)/$spring_%s"'
                   % (a, RIDE_RAISE[a], MOTION[a], a, a, MOTION[a], PRELOAD[a], a))
        # pushrods/pullrods only drive the rockers: no preload of their own
        je.set_all(f, r'"breakGroupType":1,"beamPrecompression":(?:"\$=\(\$springheight_%s \+ 1\.0\d\)"|1\.0)' % a,
                   '"breakGroupType":1,"beamPrecompression":1.0')
        # packers: the coilover's progressive bump stop, gap in wheel travel
        _set_packers(f, a, hub)
        # ARB on its own variable (the F4's rear bar used the front one)
        je.set_in_part(f, f"redbull_swaybar_{a}", r'\{"spring":"\$=\$arb_spring_[FR]\*[^"]*", "damp":10, "deform":\d+,',
                       '{"spring":"$=$arb_spring_%s*%s", "damp":10, "deform":%d,' % (a, ARB_ARM2[a], TORSION_DEFORM))
        je.set_all(f, r'\["\$arb_spring_%s", "range", "N/m", "Suspension", [^\]]*\]' % a,
                   '["$arb_spring_%s", "range", "N/m", "Suspension", %d, 0, 400000, "Anti-Roll Bar", '
                   '"Extra wheel rate in roll from the anti-roll bar", {"stepDis":5000, "subCategory":"%s"}]' % (a, c["arb"], sub))
        _heave_spring(f, a, hub)


def _dedupe_rows(path, names):
    text = je._read(path)
    lines = text.split("\r\n")
    seen, out = set(), []
    for ln in lines:
        key = next((n for n in names if ln.strip().startswith('["%s"' % n)), None)
        if key:
            if key in seen:
                continue
            seen.add(key)
        out.append(ln)
    je._write(path, "\r\n".join(out))


def _set_packers(path, a, hub):
    """The coilover part's bump stop becomes the packer: engages after
    $packer_X of wheel travel (converted to spring-beam travel)."""
    text = je._read(path)
    import re
    pat = re.compile(r'(\["%s[rl]","%ss1", \{"breakGroup":[^{}]*?"longBoundRange":0\.04,"shortBoundRange":)([^,]+)(,"boundZone":)([^,]+)(,)'
                     % (hub, a.lower()))
    new, n = pat.subn(lambda m: m.group(1) + '"$=$packer_%s*%s"' % (a, MOTION[a]) + m.group(3) + "0.012" + m.group(5), text)
    if n != 2:
        raise ValueError(f"{path}: expected 2 packer rows, found {n}")
    je._write(path, new)


def _heave_spring(path, a, hub):
    """Heave torsionbar in the coilover part (see the block comment above)."""
    part = f"redbull_coilover_{a}"
    text = je._read(path)
    axis = HEAVE_AXIS[a]
    row = ('    "torsionbars": [\r\n'
           '        ["id1:", "id2:", "id3:", "id4:"],\r\n'
           '        //heave (third) spring: lengthwise axis on the centreline, hubs as arms\r\n'
           '        {"spring":"$=$heave_spring_%s*%s", "damp":"$=$heave_spring_%s*%s*0.03", "deform":%d, "strength":9999999},\r\n'
           '        ["%sr", "%s", "%s", "%sl"],\r\n'
           '    ],\r\n') % (a, HEAVE_ARM2[a], a, HEAVE_ARM2[a], TORSION_DEFORM, hub, axis[0], axis[1], hub)
    import re
    # (re-runs) drop the block wherever it is, then insert it before the
    # coilover part's "beams" section
    text = re.sub(r'    "torsionbars": \[\r\n        \["id1:", "id2:", "id3:", "id4:"\],\r\n        //heave \(third\) spring.*?    \],\r\n',
                  "", text, flags=re.S)
    start = re.search(r'"%s"\s*:\s*\{' % part, text).start()
    at = text.index('    "beams": [', start)
    text = text[:at] + row + text[at:]
    je._write(path, text)


# ---------------------------------------------------------- power unit
# 2018 PU: 1.6 L V6 turbo, 15,000 rpm limit but fuel flow (100 kg/h above
# 10,500 rpm) caps power, so torque is flat to ~10,500 then falls: ~560 kW
# (750 hp) from the ICE. MGU-K adds up to 120 kW (161 hp). The jbeam curve is
# ICE + MGU-K; lua/controller/redbullERS.lua caps the throttle to the ICE
# share whenever the energy store isn't deploying, so the car has ~750 hp
# with ERS off and ~910 hp while it deploys.
ICE_CURVE = [(0, 0), (1000, 150), (2000, 230), (3000, 300), (4000, 360), (5000, 410), (6000, 450),
             (7000, 480), (8000, 500), (9000, 505), (10000, 505), (10500, 505), (11000, 485),
             (11500, 462), (12000, 440), (12500, 405), (13000, 360), (13500, 300), (14000, 240)]
ERS_KW, ERS_MAX_TQ = 120.0, 180.0


def ers_torque(rpm):
    if rpm <= 0:
        return 0.0
    return min(ERS_MAX_TQ, ERS_KW * 1000 / (rpm * math.pi / 30))


def _set_torque_table(path, rows):
    import re
    text = je._read(path)
    body = "".join("            [%d, %d],\r\n" % (r, t) for r, t in rows)
    new, n = re.subn(r'("torque":\[\r\n            \["rpm", "torque"\],\r\n)(?:            \[[^\]]*\],\r\n)+',
                     lambda m: m.group(1) + body, text, count=1)
    if n != 1:
        raise ValueError(f"{path}: torque table not found")
    je._write(path, new)


def power_unit():
    f = f"{V}/redbull_engine.jbeam"
    # No engine-block torque reaction: in a longitudinal engine + transaxle the
    # crank's roll reaction is cancelled by the gearbox and final drive; BeamNG
    # applied the full 644 Nm as chassis roll, loading one rear tyre more than
    # the other -- the car pulled to one side pulling away (round 8).
    import re
    text = je._read(f)
    text = re.sub(r'        "torqueReactionNodes:":\["e1l","e2l","e4r"\],\r\n', '        //"torqueReactionNodes:":["e1l","e2l","e4r"], (off, see tools/rb14/f1_setup.py)\r\n', text)
    je._write(f, text)
    total = [(r, round(t + ers_torque(r) * (1 if r >= 1000 else 0))) for r, t in ICE_CURVE]
    _set_torque_table(f, total)
    je.set_in_part(f, "redbull_engine_i4", r'"name":"[^"]*"', '"name":"1.6L V6 Turbo Hybrid Power Unit"')
    for key, val in (("idleRPM", 4000), ("idleRPMRoughness", 150), ("maxRPM", 13000), ("revLimiterCutTime", 0.02),
                     ("inertia", 0.03), ("friction", 15), ("dynamicFriction", 0.02), ("engineBrakeTorque", 50),
                     ("maxTorqueRating", 800), ("maxOverTorqueDamage", 1200), ("engineBlockAirCoolingEfficiency", 40),
                     ("oilVolume", 6)):
        je.set_in_part(f, "redbull_engine_i4", r'"%s":\s*[\d.]+' % key, '"%s":%s' % (key, val))
    # thermal efficiency ~47 % at full load (2018 PUs were near 50 %)
    je.set_in_part(f, "redbull_engine_i4", r'"burnEfficiency":\[[^\]]*?(?:\[[^\]]*\],?\s*)+\]',
                   '"burnEfficiency":[\r\n            [0, 0.15],\r\n            [0.05, 0.35],\r\n            [0.4, 0.46],\r\n'
                   '            [0.7, 0.49],\r\n            [1, 0.47],\r\n        ]')
    # dry sump: oil pickup safe to ~6.5 g (the F4's 2.5 g would starve it in fast corners)
    je.set_in_part(f, "redbull_oilpan", r'"oilpanMaximumSafeG":\s*[\d.]+', '"oilpanMaximumSafeG": 6.5')
    je.set_in_part(f, "redbull_engine_ecu", r'"revLimiterRPM":\s*[\d.]+', '"revLimiterRPM":12500')
    je.set_in_part(f, "redbull_engine_ecu", r'"revLimiterCutTime":\s*[\d.]+', '"revLimiterCutTime":0.02')
    je.set_in_part(f, "redbull_engine_ecu", r'"name":"[^"]*"', '"name":"RB14 Power Unit ECU"')


# ------------------------------------------------------ gearbox and diff
# 8-speed seamless sequential. Overall ratios for ~105 km/h in 1st and
# ~345 km/h in 8th at 12,500 rpm on the 0.335 m rears, final drive 4.0.
GEARS = {
    "standard": [3.76, 2.90, 2.375, 2.00, 1.725, 1.50, 1.30, 1.14],
    "short": [4.10, 3.16, 2.59, 2.18, 1.88, 1.635, 1.417, 1.245],    # ~9 % shorter: tight tracks
}


def gearbox():
    f = f"{V}/redbull_transaxle.jbeam"
    ratios = lambda g: "[-3.2, 0, " + ", ".join("%g" % x for x in g) + "]"
    je.set_in_part(f, "redbull_transaxle", r'"gearRatios":\[[^\]]*\]', '"gearRatios":' + ratios(GEARS["standard"]))
    je.set_in_part(f, "redbull_gearset_standard", r'"gearRatios":\[[^\]]*\]', '"gearRatios":' + ratios(GEARS["standard"]))
    je.set_in_part(f, "redbull_gearset_short", r'"gearRatios":\[[^\]]*\]', '"gearRatios":' + ratios(GEARS["short"]))
    je.set_in_part(f, "redbull_transaxle", r'"name":"[^"]*"', '"name":"8-Speed Seamless Sequential Transaxle"')
    # shift logic: arrays are [R, N, 1..8]
    je.set_in_part(f, "redbull_transaxle", r'"lowShiftDownRPM":\[[^\]]*\]', '"lowShiftDownRPM":[0,0,0,6000,6500,6500,6500,6500,6500,6500]')
    je.set_in_part(f, "redbull_transaxle", r'"lowShiftUpRPM":\[[^\]]*\]', '"lowShiftUpRPM":[0,0,9500,9500,9500,9500,9500,9500,9500]')
    je.set_in_part(f, "redbull_transaxle", r'"clutchLaunchStartRPM":\s*[\d.]+', '"clutchLaunchStartRPM":7000')
    je.set_in_part(f, "redbull_transaxle", r'"clutchLaunchTargetRPM":\s*[\d.]+', '"clutchLaunchTargetRPM":7500')
    je.set_in_part(f, "redbull_transaxle", r'"ignitionCutTime":\s*[\d.]+', '"ignitionCutTime": 0.03')
    je.set_in_part(f, "redbull_transaxle", r'"additionalEngineInertia":\s*[\d.]+', '"additionalEngineInertia":0.02')
    je.set_in_part(f, "redbull_transaxle", r'"clutchMass":\s*[\d.]+', '"clutchMass":1.5')
    # limited-slip diff with adjustable preload / power and coast locking
    d = f"{V}/redbull_differential_R.jbeam"
    je.set_all(d, r'\{"diffType":"(?:open|lsd)"[^}]*\}',
               '{"diffType":"lsd", "lsdPreload":"$lsdpreload_R", "lsdLockCoef":"$lsdlockcoef_R", "lsdRevLockCoef":"$lsdlockcoefrev_R", '
               '"uiName":"Rear Differential","defaultVirtualInertia":0.25}')
    je.set_all(d, r'"gearRatio":\s*(?:[\d.]+|"\$finaldrive_R")\s*,', '"gearRatio":"$finaldrive_R",')
    je.set_in_part(d, "redbull_differential_R", r'"name":"[^"]*"', '"name":"Limited Slip Rear Differential"')
    je.set_all(d, r'\["\$lsdlockcoef_R", "range", "", "Differentials", [\d.]+,', '["$lsdlockcoef_R", "range", "", "Differentials", 0.20,')
    text = je._read(d)
    if '"$finaldrive_R"' not in text.split('"variables"')[-1] or '"variables"' not in text:
        i = text.index('    "differential_R": {')
        text = text[:i] + (
            '    "variables": [\r\n'
            '        ["name", "type", "unit", "category", "default", "min", "max", "title", "description"],\r\n'
            '        ["$finaldrive_R", "range", ":1", "Differentials", 4.0, 3.2, 4.8, "Final Drive Gear Ratio", "Ratio of the rear differential; higher is shorter gearing", {"stepDis":0.01, "subCategory":"Rear"}],\r\n'
            '        ["$lsdpreload_R", "range", "N/m", "Differentials", 60, 0, 400, "Pre-load Torque", "Locking torque between the rear wheels at all times", {"stepDis":5, "subCategory":"Rear"}],\r\n'
            '        ["$lsdlockcoef_R", "range", "", "Differentials", 0.25, 0, 0.6, "Power Lock Rate", "Extra locking on throttle, as a share of drive torque (traction, exit understeer)", {"stepDis":0.01, "subCategory":"Rear"}],\r\n'
            '        ["$lsdlockcoefrev_R", "range", "", "Differentials", 0.12, 0, 0.6, "Coast Lock Rate", "Extra locking off throttle (entry stability)", {"stepDis":0.01, "subCategory":"Rear"}],\r\n'
            '    ],\r\n') + text[i:]
        je._write(d, text)


# --------------------------------------------------------------- brakes
# Carbon-carbon, 278 / 266 mm discs. ~5 g from 300 km/h needs ~10 kNm at the
# wheels in total; 5000 Nm per wheel before the bias split puts ~2.85 kNm on
# each front and ~2.15 kNm on each rear at the default 57 % front. The bias
# controller (lua/controller/flyBrakeBias.lua) now takes these torques from
# the jbeam instead of its own hard-coded F4 values.
BRAKE_TQ = 5000


def brakes():
    f = f"{V}/redbull_brakes.jbeam"
    je.set_in_part(f, "redbull_brake_F", r'\{"brakeTorque":"[^"]*"\}', '{"brakeTorque":"$=$brakestrength*%d*$brakebias"}' % BRAKE_TQ)
    je.set_in_part(f, "redbull_brake_R", r'\{"brakeTorque":"[^"]*"\}', '{"brakeTorque":"$=$brakestrength*%d*(1-$brakebias)"}' % BRAKE_TQ)
    for part, dia, mass, vent in (("redbull_brake_F", 0.278, 5.0, 0.8), ("redbull_brake_R", 0.266, 4.0, 0.7)):
        je.set_in_part(f, part, r'\{"brakeDiameter":[\d.]+\}', '{"brakeDiameter":%s}' % dia)
        je.set_in_part(f, part, r'\{"brakeMass":[\d.]+\}', '{"brakeMass":%s}' % mass)
        je.set_in_part(f, part, r'\{"rotorMaterial":"[^"]*"\}', '{"rotorMaterial":"carbon-ceramic"}')
        je.set_in_part(f, part, r'\{"brakeVentingCoef":[\d.]+\}', '{"brakeVentingCoef":%s}' % vent)
    je.set_in_part(f, "redbull_brake_F", r'"name":"[^"]*"', '"name":"Front Carbon Brakes"')
    je.set_in_part(f, "redbull_brake_R", r'"name":"[^"]*"', '"name":"Rear Carbon Brakes"')
    m = f"{V}/redbull.jbeam"
    je.set_all(m, r'\["\$brakebias", "range", "", "Brakes", [^\]]*\]',
               '["$brakebias", "range", "", "Brakes", 0.58, 0.50, 0.64, "Brake Bias", "Share of brake torque on the front wheels", {"minDis":50, "maxDis":64}]')
    je.set_all(m, r'\["flyBrakeBias", \{[^}]*\}\]',
               '["flyBrakeBias", {"startBias":"$brakebias", "torqueFront":"$=$brakestrength*%d", "torqueRear":"$=$brakestrength*%d", '
               '"minBias":0.50, "maxBias":0.64}]' % (BRAKE_TQ, BRAKE_TQ))


# ----------------------------------------------------------------- aero
# 2018 F1 (setup_report's flat-plate estimate at the baseline wing angles):
# ClA ~5.0 m^2 (downforce ~2.8x weight at 300 km/h), CdA ~1.3 m^2
# (L/D ~3.8), 43 % front. Split roughly as the real cars: floor and diffuser
# ~40 %, rear wing ~35 %, front wing ~25 %. Coefficients are set as the F4's
# original values (vehicles/fr04) times these factors; wing drag grows with
# its downforce, and the body picks up the drag of the exposed 13" wheels
# and the cooling the F4 doesn't model.
AERO = {
    # factors solved with setup_report for ClA 5.0, 41 % front (round 7: 43 % let the rear go too easily), floor 40 %
    "redbull_wing_F": dict(lift=1.195, drag=1.195),   # L/D ~7 (in ground effect)
    "redbull_wing_R": dict(lift=1.069, drag=4.53),       # L/D ~3.5, like a real high-AoA rear wing
    "redbull_floor": dict(lift=3.97, drag=1.0),
    "redbull_body": dict(lift=1.0, drag=2.0),         # + exposed wheels, cooling
}
AERO_FILES = {"redbull_wing_F": "wing_F", "redbull_wing_R": "wing_R", "redbull_floor": "floor", "redbull_body": "body"}


def _part_block(text, part):
    import re
    m = re.search(r'"%s"\s*:\s*\{' % re.escape(part), text)
    nxt = re.compile(r'\r?\n"[A-Za-z0-9_]+"\s*:\s*\{').search(text, m.end())
    return m.start(), (nxt.start() if nxt else len(text))


def aero():
    import re
    for part, fac in AERO.items():
        f = f"{V}/redbull_{AERO_FILES[part]}.jbeam"
        orig = open(f"vehicles/fr04/fr04_{AERO_FILES[part]}.jbeam", encoding="utf-8", newline="").read()
        a0, b0 = _part_block(orig, part.replace("redbull", "fr04"))
        text = je._read(f)
        a, b = _part_block(text, part)
        block = text[a:b]
        for key, k in (("liftCoef", fac["lift"]), ("dragCoef", fac["drag"])):
            pat = re.compile(r'("%s"\s*:\s*)(\d+(?:\.\d+)?)' % key)
            src = [float(m.group(2)) for m in pat.finditer(orig[a0:b0])]
            it = iter(src)
            n = len(pat.findall(block))
            if n != len(src):
                raise ValueError(f"{part}: {n} {key} values, F4 has {len(src)}")
            block = pat.sub(lambda m: m.group(1) + ("%g" % round(next(it) * k, 1)), block)
        text = text[:a] + block + text[b:]
        je._write(f, text)


# ----------------------------------------------------------- ERS / DRS
# Controllers in lua/controller/ (see their headers); keys in
# inputmaps/keyboard.json, actions in redbull.interaction.json.
def hybrid():
    m = f"{V}/redbull.jbeam"
    ice = "[" + ", ".join("[%d, %d]" % rt for rt in ICE_CURVE) + "]"
    ers = ('["redbullERS", {"order":1000, "deployKW":%g, "maxTorque":%g, "storeMJ":4.0, "mguhKW":40, "harvestKW":120, '
           '"iceTorque":%s}]' % (ERS_KW, ERS_MAX_TQ, ice))
    drs = '["redbullDRS", {"minSpeed":20}]'
    tc = '["redbullTraction", {"order":1100, "targetSlip":0.12, "minSlipSpeed":2.5, "gain":4.0, "release":3.0}]'
    text = je._read(m)
    import re
    for c in ("redbullERS", "redbullDRS", "redbullTraction"):
        text = re.sub(r',\r\n        \["%s", \{.*?\}\]' % c, "", text)
    i = text.index('        ["flyBrakeBias"')
    j = text.index("\r\n", i)
    text = text[:j] + ",\r\n        " + ers + ",\r\n        " + drs + ",\r\n        " + tc + text[j:]
    for action in ("ersMode", "drsToggle", "tcMode"):
        if '["%s"]' % action not in text:
            k = text.index('        ["biasMinus"],')
            k = text.index("\r\n", k) + 2
            text = text[:k] + '        ["%s"],\r\n' % action + text[k:]
    je._write(m, text)
    drs_hydros()


# DRS: the rear wing's leading-edge nodes hang from the endplates by stiff
# beams; the two near-vertical ones per side (rep2/rep3 -> rwg1) are dropped
# and the rep1 -> rwg1 beam becomes a hydro that lengthens with
# electrics.values.drs, lifting the leading edge until the upper wing is
# about flat (rotating about its trailing edge, which stays fixed).
DRS_LIFT = 0.060        # m the leading edge rises when open


def drs_hydros():
    import re
    import numpy as np
    import setup_report as sr
    f = f"{V}/redbull_wing_R.jbeam"
    text = je._read(f)
    for side in "rl":
        # remove the vertical attachments of the leading edge (idempotent)
        for anchor in ("rep1", "rep2", "rep3"):
            text = re.sub(r'          \["%s%s","rwg1%s"\],\r\n' % (anchor, side, side), "", text)
    v = sr.Vehicle("redbull", None)
    rows = []
    for side in "rl":
        a, b = v.pos["rep1" + side], v.pos["rwg1" + side]
        L0 = np.linalg.norm(b - a)
        L1 = np.linalg.norm(b + np.array([0, 0, DRS_LIFT]) - a)
        rows.append('        ["rep1%s","rwg1%s", {"factor":%.4f, "inputSource":"drs", "inputFactor":1, "inRate":4, "outRate":4, '
                    '"beamSpring":2001000, "beamDamp":200, "beamDeform":"FLT_MAX", "beamStrength":20000, "breakGroup":"endplates_R%s"}],\r\n'
                    % (side, side, (L1 - L0) / L0, side.upper()))
    # every setting inline: option rows would carry on into the steering
    # hydro of a later part
    block = ('    "hydros": [\r\n'
             '        ["id1:", "id2:"],\r\n'
             '        //DRS: lifts the leading edge (see tools/rb14/f1_setup.py)\r\n' + "".join(rows) +
             '    ],\r\n')
    text = re.sub(r'    "hydros": \[\r\n        \["id1:", "id2:"\],\r\n        //DRS.*?    \],\r\n', "", text, flags=re.S)
    k = text.index('    "triangles": [')
    text = text[:k] + block + text[k:]
    je._write(f, text)


# --------------------------------------------- ride-height floor (optional)
# Part redbull_floor_groundeffect (slot in the floor, empty by default):
# lua/controller/redbullGroundEffect.lua reads the floor's ride height and
# drives thrusters that add (or take away) the ground-effect difference to
# the static floor. Thrusters push down on fl6 (front of the floor's upper
# frame) and rs1 (gearbox, rear) -- split 36/64 like the floor's centre of
# pressure -- and pull up on fl2 / rdiff.
def ground_effect():
    import re
    import setup_report as sr
    v = sr.Vehicle("redbull", None)
    mr = sr.mass_report(v)
    v._yf, v._yr = mr["yf"], mr["yr"]
    _, per = sr.aero_report(v)
    q300 = 0.5 * sr.RHO * (300 / 3.6) ** 2
    cla = -per["redbull_floor"][0] / q300
    radius = 0.335
    h0F = (v.pos["fl1l"][2] + v.pos["fl1r"][2]) / 2 - (v.pos["fw1l"][2] + v.pos["fw1r"][2]) / 2 + radius + RIDE_RAISE["F"]
    h0R = v.pos["fl4"][2] - (v.pos["rw1l"][2] + v.pos["rw1r"][2]) / 2 + radius + RIDE_RAISE["R"]
    fmax, rear = 8000, 0.64
    part = ('"redbull_floor_groundeffect": {\r\n'
            '    "information":{\r\n'
            '        "authors":"redbull mod (RB14 conversion)",\r\n'
            '        "name":"Ride-Height Sensitive Floor (experimental)",\r\n'
            '        "value":5000,\r\n'
            '    },\r\n'
            '    "slotType" : "redbull_floor_groundeffect",\r\n'
            '    "controller": [\r\n'
            '        ["fileName"],\r\n'
            '        ["redbullGroundEffect", {"floorClA":%.3f, "gain":12, "stallHeight":0.018, "stallLoss":0.8, '
            '"maxForce":%d, "radius":%.3f, "h0F":%.4f, "h0R":%.4f}],\r\n'
            '    ],\r\n'
            '    "thrusters": [\r\n'
            '        ["id1:", "id2:", "factor", "thrustLimit", "control"],\r\n'
            '        //more downforce: push down on the car (force on id2, towards id1)\r\n'
            '        ["fl2", "fl6", %d, %d, "floorGEDown"],\r\n'
            '        ["rdiff", "rs1", %d, %d, "floorGEDown"],\r\n'
            '        //less downforce (too high, or stalled): pull up\r\n'
            '        ["fl6", "fl2", %d, %d, "floorGEUp"],\r\n'
            '        ["rs1", "rdiff", %d, %d, "floorGEUp"],\r\n'
            '    ],\r\n'
            '},\r\n') % (cla, fmax, radius, h0F, h0R,
                          fmax * (1 - rear), fmax * (1 - rear), fmax * rear, fmax * rear,
                          fmax * (1 - rear), fmax * (1 - rear), fmax * rear, fmax * rear)
    f = f"{V}/redbull_floor.jbeam"
    text = je._read(f)
    text = re.sub(r'"redbull_floor_groundeffect": \{.*?\r\n\},\r\n', "", text, flags=re.S)
    if '"slots"' not in text[:text.index('"flexbodies"')]:
        i = text.index('    "flexbodies": [')
        text = text[:i] + ('    "slots": [\r\n'
                           '        ["type", "default", "description"],\r\n'
                           '        ["redbull_floor_groundeffect", "", "Floor Aerodynamics"],\r\n'
                           '    ],\r\n') + text[i:]
    j = text.index("{") + 1
    j = text.index("\n", j) + 1
    text = text[:j] + part + text[j:]
    je._write(f, text)
    print("ground effect: floor ClA %.2f, h0 front %.3f rear %.3f" % (cla, h0F, h0R))


# -------------------------------------------------------------- configs
# The four setups (plans/rb14-model-swap.md, Milestone 3/4). Every tuning
# variable is written out (the jbeam default unless overridden) so the
# configs show a complete setup sheet in the tuning menu. Wing angles come
# from the setup_report aero map (ClA / CdA / front at 300 km/h).
TUNING = ["$fuel", "$tirepressure_F", "$tirepressure_R",
          "$wing_angle_F", "$wing_angle_R", "$wing_angle_B",
          "$spring_F", "$spring_R", "$heave_spring_F", "$heave_spring_R", "$arb_spring_F", "$arb_spring_R",
          "$damp_bump_F", "$damp_rebound_F", "$damp_bump_R", "$damp_rebound_R",
          "$packer_F", "$packer_R", "$springheight_F", "$springheight_R",
          "$camber_F", "$caster_F", "$toe_F", "$camber_R", "$toe_R",
          "$brakebias", "$brakestrength",
          "$finaldrive_R", "$lsdpreload_R", "$lsdlockcoef_R", "$lsdlockcoefrev_R", "$ffbstrength"]
CONFIGS = {
    # ClA 4.6 / CdA 1.12 / 43 %: long straights; longer final drive, a touch lower
    "lowdf": dict(parts={}, vars={"$wing_angle_F": -5, "$wing_angle_R": 4, "$wing_angle_B": 3,
                                  "$finaldrive_R": 3.85, "$springheight_F": -0.003, "$springheight_R": -0.003,
                                  "$tirepressure_F": 22, "$tirepressure_R": 20.5}),
    # ClA 5.0 / CdA 1.30 / 43 %: the jbeam defaults
    "baseline": dict(parts={}, vars={}),
    # ClA 5.7 / CdA 1.75 / 43 %: tight tracks; softer, higher, short gears, more front brake
    "highdf": dict(parts={"redbull_gearset": "redbull_gearset_short"},
                   vars={"$wing_angle_F": 0, "$wing_angle_R": 15, "$wing_angle_B": 3,
                         "$spring_F": 300000, "$spring_R": 430000, "$arb_spring_F": 180000, "$arb_spring_R": 110000,
                         "$springheight_F": 0.004, "$springheight_R": 0.004, "$brakebias": 0.58,
                         "$tirepressure_F": 20, "$tirepressure_R": 19, "$lsdlockcoef_R": 0.30}),
    # qualifying trim: 10 L of fuel, ClA 5.5 / 44 % front, softer front and
    # stiffer rear roll for rotation, less coast locking for turn-in
    "aggressive": dict(parts={}, vars={"$fuel": 10, "$wing_angle_F": 0, "$wing_angle_R": 12, "$wing_angle_B": 3,
                                       "$arb_spring_F": 170000, "$arb_spring_R": 170000,
                                       "$springheight_F": -0.003, "$brakebias": 0.56,
                                       "$lsdlockcoefrev_R": 0.06, "$lsdpreload_R": 40}),
}


def configs():
    import json
    import setup_report as sr
    defaults = sr.Vehicle("redbull", None).variables
    for name, c in CONFIGS.items():
        missing = [k for k in TUNING if k not in defaults]
        if missing:
            raise KeyError(f"variables not defined in the jbeam: {missing}")
        vs = {k: defaults[k] for k in TUNING}
        vs.update(c["vars"])
        vs = {k: (round(float(x), 6) if not float(x).is_integer() else int(x)) for k, x in sorted(vs.items())}
        pc = {"format": 2, "mainPartName": "redbull", "model": "redbull", "parts": c["parts"], "vars": vs}
        with open(f"{V}/{name}.pc", "w", newline="\n") as fh:
            json.dump(pc, fh, indent=2)
            fh.write("\n")


if __name__ == "__main__":
    os.chdir(REPO)
    stiffness()
    torque_paths()
    wheels()
    tyres()
    fuel()
    mass()
    suspension()
    power_unit()
    gearbox()
    brakes()
    steering()
    rear_wing()
    aero()
    hybrid()
    ground_effect()
    configs()
    check_stability()
    print("applied: mass, wheels, tyres, fuel, suspension, power unit, gearbox, brakes, ERS/DRS")
