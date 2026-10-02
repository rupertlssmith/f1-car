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
# front upright nodes fh3 / fh5 (4 kg each) take $upright_mass_F kg per
# corner from the front rim's 32 hub nodes (wheels()): same corner mass,
# placed where the limiting wheel-corner mode sits (round 12 variants)
UPRIGHT_F = "$=4+$upright_mass_F/2"


def mass():
    # tub + driver (~150 kg): heavy low nodes (seat, floor of the tub), light
    # high ones (cockpit rim, halo, hoop)
    weights(f"{V}/redbull_body.jbeam", {
        "rt1r": 12, "rt1l": 12, "rt3r": 12, "rt3l": 12,        # tub floor, rear
        "mt1r": 8, "mt1l": 8, "mt1": 10,                        # tub floor, front
        "rt2r": 3, "rt2l": 3, "rt4r": 3, "rt4l": 3,             # cockpit rim / hoop base
        "mt2r": 5, "mt2l": 5, "mt3": 8, "fs1": 6,
        "fx1r": 6.0, "fx1l": 6.0, "fx2r": 5.5, "fx2l": 5.5,     # front bulkhead, low
        "fx3r": 5.5, "fx3l": 5.5, "fx4r": 5.5, "fx4l": 5.5})
    # power unit 145 kg (ICE, turbo, MGU-K/H), CoG ~0.3 m
    weights(f"{V}/redbull_engine.jbeam", {      # (e2r/l: + ballast, see ballast())
        "e1r": 25, "e1l": 25, "e3r": 11.25, "e3l": 11.25, "e4r": 11.25, "e4l": 11.25})
    # gearbox + casing ~40 kg
    weights(f"{V}/redbull_transaxle.jbeam", {      # (rx1r/l: + ballast)
        "rx2r": 5, "rx2l": 5, "rx3r": 5, "rx3l": 5, "rx4r": 5, "rx4l": 5})
    weights(f"{V}/redbull_differential_R.jbeam", {"rdiff": DIFF_NODE_WEIGHT})
    # rear crash structure: the F4's 1 kg nodes sit right at the stability limit
    weights(f"{V}/redbull_crashbox.jbeam", {n: 1.4 for n in ("cb1r", "cb1l")})
    weights(f"{V}/redbull_crashbox.jbeam", {n: 1.4 for n in ("cb3r", "cb3l")})
    weights(f"{V}/redbull_crashbox.jbeam", {n: 1.0 for n in ("cb4r", "cb4l")})
    # uprights, brakes, wishbone ends: roughly half the F4's corner mass
    weights(f"{V}/redbull_suspension_F.jbeam", {
        "fh1r": 5, "fh1l": 5, "fh2r": 1, "fh2l": 1, "fh3r": UPRIGHT_F, "fh3l": UPRIGHT_F, "fh4r": 4, "fh4l": 4, "fh5r": UPRIGHT_F, "fh5l": UPRIGHT_F})
    weights(f"{V}/redbull_suspension_R.jbeam", {
        **{n + s: "$=%g+%g*$rear_corner_mass" % (w, REAR_CORNER_SHARE[n]) for n, w in (("rh1", 5), ("rh3", 4), ("rh4", 4)) for s in "rl"}})
    weights(f"{V}/redbull_suspension_F.jbeam", {"fh6r": 6.5, "fh6l": 6.5})  # steering rack ends (stiff rack: see stiffness())
    # chassis nodes that carry very stiff beams keep enough mass for the
    # 2 kHz solver (see stiffness() below)
    weights(f"{V}/redbull_body.jbeam", CHASSIS_MIN_MASS)
    ballast()


# Ballast + ES (battery, ~25 kg), solved (setup_report) so the car makes
# 733 kg with the driver and no fuel and 46.5 % front whatever the other node
# weights are: a front and a rear group of nodes get extra mass in these
# proportions. It sits on the tub's floor nodes (heavy, stiffly braced)
# rather than on the floor, whose beams were never meant to carry it
# (round 9); the floor nodes are back to the F4's weights.
BALLAST_F = {"fx2r": 1, "fx2l": 1, "mt1": 1}                 # front of the tub floor
BALLAST_R = {"e2r": 1, "e2l": 1, "rx1r": 1, "rx1l": 1}       # engine sump and gearbox front
BALLAST_BASE = {"fx2r": ("body", 5.5), "fx2l": ("body", 5.5), "mt1": ("body", 10),
                "e2r": ("engine", 25), "e2l": ("engine", 25), "rx1r": ("transaxle", 5), "rx1l": ("transaxle", 5)}   # node: (file, kg before ballast)
FLOOR_F4 = {"fl1r": 1.8, "fl1l": 1.8, "fl2": 1.8, "fl2r": 1.0, "fl2l": 1.0, "fl3": 1.8, "fl3r": 1.0, "fl3l": 1.0,
            "fl4": 1.8, "fl4r": 1.0, "fl4l": 1.0}
DRY_MASS, FRONT = 733.0, 0.465   # 46.5 % front (round 8: heavier wheel carriers; also calms the rear)


def ballast():
    import numpy as np
    import setup_report as sr
    weights(f"{V}/redbull_floor.jbeam", FLOOR_F4)
    def put(table):
        for n, w in table.items():
            weights(f"{V}/redbull_{BALLAST_BASE[n][0]}.jbeam", {n: w})
    put({n: base for n, (_, base) in BALLAST_BASE.items()})

    v = sr.Vehicle("redbull", None)
    v.variables["$fuel"] = 0
    # solved without the rear-corner mass shift: it comes out of the engine
    # ballast below (same total; round 19's Baseline = Hub Fix 15 as tested)
    v.variables["$rear_corner_mass"] = 0
    v._nodes()
    mr = sr.mass_report(v)
    m0, f0 = mr["total"], mr["front"] * mr["total"]
    # front-axle share of each group (lever rule on the node positions)
    share = lambda g: sum(w * (mr["yr"] - v.pos[n][1]) / (mr["yr"] - mr["yf"]) for n, w in g.items()) / sum(g.values())
    aF, aR = share(BALLAST_F), share(BALLAST_R)
    A = np.array([[1, 1], [aF, aR]])
    b = np.array([DRY_MASS - m0, FRONT * DRY_MASS - f0])
    xF, xR = np.linalg.solve(A, b)
    if xF < 0 or xR < 0:
        raise ValueError(f"ballast would be negative (front {xF:.1f}, rear {xR:.1f} kg): car too heavy")
    sF, sR = sum(BALLAST_F.values()), sum(BALLAST_R.values())
    new = {n: round(BALLAST_BASE[n][1] + w * xF / sF, 2) for n, w in BALLAST_F.items()}
    new.update({n: round(BALLAST_BASE[n][1] + w * xR / sR, 2) for n, w in BALLAST_R.items()})
    put(new)
    # $rear_corner_mass (round 18; default 0): kg per rear wheel moved from the
    # engine-sump ballast to the rear corner (REAR_CORNER_SHARE), so stiffer
    # rear hub beams stay under the solver limit at the same total mass
    put({n: "$=%g-$rear_corner_mass" % new[n] for n in ("e2r", "e2l")})
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
MAX_OMEGA_DT = float(os.environ.get("RB14_MAX_OMEGA_DT", 1.72))   # round 13: Front Fix 4 at 1.67 was the best car in game; round 19: Hub Fix 15 at 1.72 (rear hub) the best, no shake
# With damping (setup_report: sqrt((omega*dt)^2 + 2*gamma), limit 2): the F4
# peaks at 1.97 (crash box); round 9's rear wing at 2.01 shook itself off.
MAX_DAMPED = 1.85
# Wheel-corner modes (axle, upright, hub, tyre nodes) with damping: round 10
# (1.78) was fine, round 11's 1.83 broke the front suspension at spawn,
# round 12's Front Fix 5 at 1.82 spawned fine -> the limit is 1.82.
# Blind spot: Front Fix 3 (front dampers 40 % firmer, 500 Hz-filtered
# beams) blew up at spawn and no version of this model shows it -- keep the
# front dampers at their Baseline values in test cars.
MAX_DAMPED_CORNER = 1.82
CORNER_NODES = ("fw1", "rw1", "fh", "rh", "_hub", "_tyre")
HUB_SPRING_SCALE = 0.65                      # hub beams vs the F4's (hub nodes 0.45 vs 0.55 kg; 0.8 put the wheel axles at 1.73, round 11)
HUB_NODE_WEIGHT = 0.45                       # kg x 32 per rim (was 0.35; F4 0.55)
CARRIER_DAMP = 600                           # beamDamp floor on the capped wheel-carrier beams (round 11's 900 broke the front suspension at spawn)
WHEEL_AXLE_WEIGHT = 4.5                      # kg, wheel axle nodes (F4: 5)
CHASSIS_MIN_MASS = {"rt4r": 6.0, "rt4l": 6.0, "rt2r": 4.5, "rt2l": 4.5}
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
        pat = re.compile(r'("beamSpring"\s*:\s*)(\d+(?:\.\d+)?|"[^"]*")(\s*,\s*"beamDamp"\s*:\s*(?:\d+(?:\.\d+)?|"[^"]*"))?')
        src = [(float(m.group(2)), m.group(3)) for m in pat.finditer(orig[a0:b0])]
        block = text[a:b]
        if len(pat.findall(block)) != len(src):
            raise ValueError(f"{part}: beamSpring count differs from the F4")
        it = iter(src)

        def cap_row(m):
            k, damp = next(it)
            out = m.group(1) + "%d" % min(k, cap)
            if k > cap and part == "redbull_suspension_R":
                # rear upright links x the tuning variable $rear_link_stiff
                # (round 17; default 1)
                out = m.group(1) + '"$=%d*$rear_link_stiff"' % cap
            if damp:
                d = float(re.search(r'([\d.]+)$', damp).group(1))
                if k > cap and part == "redbull_suspension_F" and d <= CARRIER_DAMP:
                    # capped carrier beams: damp the wheel judder (front: tuning
                    # variable $carrier_damp_F, default CARRIER_DAMP)
                    out += re.sub(r'[\d.]+$', '"$=$carrier_damp_F"', damp)
                    return out
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
    # rear hub rigidifier (axle line vs upright: the rear toe) x the tuning
    # variable $rear_toe_stiff (round 16; default 1)
    je.set_in_part(f"{V}/redbull_suspension_R.jbeam", "redbull_suspension_R",
                   r'\{"spring":(?:50000|"\$=50000\*\$rear_toe_stiff"), "damp":0, "deform":\d+, "strength":\d+\}',
                   '{"spring":"$=50000*$rear_toe_stiff", "damp":0, "deform":%d, "strength":%d}' % (35000 * 4, 100000 * 4))
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
        # x the carcass stiffening (tyre_carcass()), so every tyre beam still
        # deforms / breaks at the same stretch as before: stiffer beams with
        # the old limits dented and burst the tyres on spawn (round 9)
        k = TYRE_STRENGTH_SCALE
        ks, kt, kp = (k * TYRE_SPRINGS[x] for x in ("wheelSideBeamSpringExpansion", "wheelTreadBeamSpring", "wheelPeripheryBeamSpring"))
        # front: x $tyre_carcass_F as well, so the limits follow the stiffness
        x = (lambda n: '"$=%d*$tyre_carcass_F"' % n) if axle == "F" else (lambda n: "%d" % n)
        num = r'(?:\d+|"[^"]*")'
        je.set_all(f, r'\{"wheelSideBeamDeform":%s,"wheelSideBeamStrength":%s\}' % (num, num),
                   '{"wheelSideBeamDeform":%s,"wheelSideBeamStrength":%s}' % (x(17000 * ks), x(22000 * ks)))
        je.set_all(f, r'\{"wheelTreadBeamDeform":%s,"wheelTreadBeamStrength":%s\}' % (num, num),
                   '{"wheelTreadBeamDeform":%s,"wheelTreadBeamStrength":%s}' % (x(tread[0] * kt), x(tread[1] * kt)))
        je.set_all(f, r'\{"wheelPeripheryBeamDeform":%s,"wheelPeripheryBeamStrength":%s\}' % (num, num),
                   '{"wheelPeripheryBeamDeform":%s,"wheelPeripheryBeamStrength":%s}' % (x(tread[2] * kp), x(tread[3] * kp)))


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
STEER_FACTOR = 0.090            # hydro length change at full input (F4 0.072)
STEER_WHEEL_LOCK = 170          # steering-wheel degrees at full lock (F4 230)
# Round 10: at 0.095 the rack (slidenodes fh6r/l) travelled 46.2 mm at full
# lock, past the 45.7 mm to the end of its capped rail (fx3r-fx3l), so it
# rode into the rail cap while the hydros kept pushing. 0.090 stays 2 mm
# short of it; the lock drops to match, so the ratio (road-wheel angle per
# steering-wheel degree) is unchanged. steering() checks the clearance.


def steering():
    import re
    # steering-damper beams (upright -> chassis, the F4's): x the tuning
    # variable $steer_damper_F (default 1; round 13 steering variants)
    f = f"{V}/redbull_suspension_F.jbeam"
    text = je._read(f)
    a, b = _part_block(text, "redbull_steering")
    block = text[a:b]
    block, n1 = re.subn(r'\{"beamDamp":(?:25|"\$=25\*\$steer_damper_F")\}', '{"beamDamp":"$=25*$steer_damper_F"}', block)
    block, n2 = re.subn(r'"beamDampFast":(?:500|"\$=500\*\$steer_damper_F")', '"beamDampFast":"$=500*$steer_damper_F"', block)
    if (n1, n2) != (1, 8):
        raise ValueError(f"steering damper rows: {n1}, {n2}")
    je._write(f, text[:a] + block + text[b:])
    import setup_report as sr
    import numpy as np
    v = sr.Vehicle("redbull", None)
    L0 = np.linalg.norm(v.pos["fh6r"] - v.pos["fx3l"])
    room = abs(v.pos["fx3r"][0] - v.pos["fh6r"][0])
    if STEER_FACTOR * L0 > room - 0.001:
        raise ValueError("steering: rack travel %.1f mm reaches the rail end (%.1f mm)" % (STEER_FACTOR * L0 * 1000, room * 1000))
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
WING_R_DAMP = 0                 # F4's damping (round 9: a 150 floor on 0.6 kg nodes shook the wing off)
WING_R_WEIGHTS = {"wing": 0.6, "beamwing": 0.8, "beamwing_mid": 0.9, "endplate": 0.6}
PYLON = dict(spring=1201000, damp=40, deform=60000, strength=150000)
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
        st = sr.stability_report(sr.Vehicle("redbull", cfg), top=400)
        corner = max((float(m.split(":")[0]) for m in st["damped_modes"]
                      if any(k in m.split(":")[1].split(",")[0] for k in CORNER_NODES)), default=0.0)
        if corner > MAX_DAMPED_CORNER + 1e-9:
            raise SystemExit(f"{cfg}: wheel-corner damped mode {corner:.2f} > {MAX_DAMPED_CORNER}")
        worst_c = max(locals().get("worst_c", 0.0), corner)
        worst = max(worst, st["max"])
        if st["max"] > MAX_OMEGA_DT:
            raise SystemExit(f"{cfg}: highest mode omega*dt {st['max']:.2f} > {MAX_OMEGA_DT}: {st['modes'][0]}")
        if st["damped"] > MAX_DAMPED:
            raise SystemExit(f"{cfg}: highest damped mode {st['damped']:.2f} > {MAX_DAMPED}: {st['damped_modes'][:3]}")
        worst_d = max(locals().get("worst_d", 0.0), st["damped"])
    print("stability: highest mode omega*dt %.2f (limit 2, target <= %.2f), with damping %.2f (target <= %.2f), "
          "wheel corners %.2f (target <= %.2f)" % (worst, MAX_OMEGA_DT, worst_d, MAX_DAMPED, worst_c, MAX_DAMPED_CORNER))
    for cfg in CONFIGS:
        hits = sr.wheel_clearance(sr.Vehicle("redbull", cfg), WHEEL_CLEARANCE)
        if hits:
            raise SystemExit("%s: nodes inside / within %d mm of a spinning wheel: %s" % (
                cfg, WHEEL_CLEARANCE * 1000, ", ".join("%s %s %+.0f mm" % (w, n, g * 1000) for g, w, n in hits[:6])))
    print("wheel clearance: nothing within %d mm of a spinning wheel" % (WHEEL_CLEARANCE * 1000))
    check_tyres()
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


def check_tyres():
    """Every generated-tyre spring, per kg of tyre node, at most
    TYRE_MAX_K_PER_KG x the F4's (see tyre_carcass())."""
    import setup_report as sr
    keys = [k.replace("Spring", "") for k in TYRE_SPRINGS] + ["wheelSideBeam"]
    ref = {r["name"][0]: r for r in sr.Vehicle("fr04", None).wheels()}
    worst = (0, "")
    for cfg in CONFIGS:
        v = sr.Vehicle("redbull", cfg)
        for r in v.wheels():
            f4 = ref[r["name"][0]]
            for key in keys:
                sk = key.replace("Expansion", "") + "Spring" + ("Expansion" if "Expansion" in key else "")
                ratio = (v.val(r.get(sk), 0) / v.val(r.get("nodeWeight"), 1)) / max(v.val(f4.get(sk), 0) / v.val(f4.get("nodeWeight"), 1), 1e-9)
                if ratio > worst[0]:
                    worst = (ratio, f"{cfg} {r['name']} {sk}")
    if worst[0] > TYRE_MAX_K_PER_KG + 1e-6:
        raise SystemExit("tyres: %s at %.2f x the F4's stiffness per kg (limit %.2f)" % (worst[1], worst[0], TYRE_MAX_K_PER_KG))
    print("tyres: stiffest spring per kg of tyre node %.2f x the F4's (%s)" % worst)


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
        # (rear: + a share of $rear_corner_mass, from the engine ballast; round 18)
        aw = WHEEL_AXLE_WEIGHT if "_F_" in f else '"$=%s+%g*$rear_corner_mass"' % (WHEEL_AXLE_WEIGHT, REAR_CORNER_SHARE["rw1"])
        je.set_all(f, r'\{"nodeWeight":(?:[\d.]+|"[^"]*")\}', '{"nodeWeight":%s}' % aw)
        # rims + hubs + discs: 32 hub nodes x 0.35 kg = 11 kg per wheel (were 0.55)
        w = '"$=%s-$upright_mass_F/32"' % HUB_NODE_WEIGHT if "_F_" in f else HUB_NODE_WEIGHT
        je.set_all(f, r'\{"hubNodeWeight":(?:[\d.]+|"[^"]*")\}', '{"hubNodeWeight":%s}' % w)


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


# rear toe slider: wide enough for the round-14 in-game correction (the
# replay measured ~3.3 deg more rear toe-in than this model predicts)
REAR_TOE_RANGE = (0.95, 1.06)


def _alignment():
    fF, fR = f"{V}/redbull_suspension_F.jbeam", f"{V}/redbull_suspension_R.jbeam"
    # toe variables next to camber/caster, and the links they act on
    for f, a, anchor in ((fF, "F", '["$caster_F", "range"'), (fR, "R", '["$camber_R", "range"')):
        text = je._read(f)
        if '["$toe_%s"' % a not in text:
            i = text.index(anchor)
            j = text.index("\r\n", i) + 2
            lo, hi = (0.995, 1.005) if a == "F" else REAR_TOE_RANGE
            text = text[:j] + ('        ["$toe_%s", "range", "", "Wheel Alignment", 1.0, %s, %s, "Toe Adjust", '
                               '"Adjusts the toe angle (lower: more toe-in)", {"subCategory":"%s"}],\r\n'
                               % (a, lo, hi, "Front" if a == "F" else "Rear")) + text[j:]
            je._write(f, text)
    import re
    text = je._read(fR)
    text, n = re.subn(r'(\["\$toe_R", "range", "", "Wheel Alignment", [\d.]+, )[\d.]+, [\d.]+,',
                      lambda m: m.group(1) + "%s, %s," % REAR_TOE_RANGE, text)
    if n != 1:
        raise ValueError("rear toe variable not found")
    je._write(fR, text)
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
    body = "".join('            [%d, "$=%d*$pu_power+%d"],\r\n' % (r, ice, ers) for r, ice, ers in rows)
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
    # ICE x the tuning variable $pu_power (round 16, default 1) + MGU-K
    total = [(r, t, round(ers_torque(r) * (1 if r >= 1000 else 0))) for r, t in ICE_CURVE]
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
# Round 10: 1st-4th shorter for punch out of slow corners (1st ~95 km/h,
# 4th ~185 km/h; 8th unchanged), the steps closing up toward the top.
GEARS = {"standard": [4.15, 3.15, 2.54, 2.12, 1.79, 1.535, 1.32, 1.14]}
GEARS["short"] = [round(g * 1.09, 3) for g in GEARS["standard"]]    # ~9 % shorter: tight tracks


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
    # round 16: Rear Fix 4 (freer diff) is Baseline -- the rear drive torque
    # stayed lopsided after corners with 0.20 / 60 Nm / 0.12
    je.set_all(d, r'\["\$lsdlockcoef_R", "range", "", "Differentials", [\d.]+,', '["$lsdlockcoef_R", "range", "", "Differentials", 0.10,')
    je.set_all(d, r'\["\$lsdpreload_R", "range", "N/m", "Differentials", [\d.]+,', '["$lsdpreload_R", "range", "N/m", "Differentials", 20,')
    je.set_all(d, r'\["\$lsdlockcoefrev_R", "range", "", "Differentials", [\d.]+,', '["$lsdlockcoefrev_R", "range", "", "Differentials", 0.06,')
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
    # brake force slider up to 1.5x (round 16: at 1.0 the brakes cap braking
    # at ~3.9 g from 300 km/h; 2018 F1 cars reached 5+ g)
    je.set_all(m, r'\["\$brakestrength", "range", "", "Brakes", 1, 0.6, [\d.]+, ([^\]]*?)\{"minDis":60, "maxDis":\d+\}\]',
               '["$brakestrength", "range", "", "Brakes", 1, 0.6, 1.5, "Brake Force Multiplier", "Scales the overall brake torque for this setup", {"minDis":60, "maxDis":150}]')
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
        if part == "redbull_body":      # the halo's triangles are in the redbull_halo part (halo_part())
            orig = re.sub(r'        //halo\r\n        \{"dragCoef":[\d.]+\},.*?(?=        //hoop)', "", orig, flags=re.S)
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
           '"iceScale":"$pu_power", "iceTorque":%s}]' % (ERS_KW, ERS_MAX_TQ, ice))
    drs = '["redbullDRS", {"minSpeed":20}]'
    tc = '["redbullTraction", {"order":1100, "targetSlip":"$tc_slip", "minSlipSpeed":2.5, "gain":4.0, "release":3.0}]'
    text = je._read(m)
    import re
    sc = ('["redbullSteerCheck", {}],\r\n        ["redbullPerf", {}],\r\n        '
          '["redbullBrakeMap", {"order":1200, "enabled":"$brake_map", "lowFactor":0.5, "fullSpeed":250}],\r\n        '
          '["redbullSensors", {}]')
    for c in ("redbullERS", "redbullDRS", "redbullTraction", "redbullSteerCheck", "redbullPerf", "redbullBrakeMap",
              "redbullSensors"):
        text = re.sub(r',\r\n        \["%s", \{.*?\}\]' % c, "", text)
    i = text.index('        ["flyBrakeBias"')
    j = text.index("\r\n", i)
    text = text[:j] + ",\r\n        " + ers + ",\r\n        " + drs + ",\r\n        " + tc + ",\r\n        " + sc + text[j:]
    for action in ("ersMode", "drsToggle", "tcMode", "steerCheck"):
        if '["%s"]' % action not in text:
            k = text.index('        ["biasMinus"],')
            k = text.index("\r\n", k) + 2
            text = text[:k] + '        ["%s"],\r\n' % action + text[k:]
    je._write(m, text)
    round16_vars()
    drs_flap()


def round16_vars():
    """The round-16/17 tuning variables (main part, next to the brake force
    slider). Run first in main: the suspension calibration already
    evaluates $rear_link_stiff / $rear_droop."""
    import re
    m = f"{V}/redbull.jbeam"
    text = je._read(m)
    text = re.sub(r'        \["\$(?:%s)", "range".*\r\n' % "|".join(v[0].lstrip("$") for v in ROUND16_VARS), "", text)
    k = text.index('        ["$brakestrength", "range"')
    k = text.index("\r\n", k) + 2
    text = text[:k] + "".join('        ["%s", "range", %s],\r\n' % (n, rest) for n, rest in ROUND16_VARS) + text[k:]
    je._write(m, text)


# Round 16 (fixes from replays A / B / C): defaults are Baseline; the
# test cars (tools/rb14/variants.py) set them. Round 17: Test 05 (engine
# power +12 %) is Baseline, so $pu_power defaults to 1.12.
ROUND16_VARS = [
    ("$rear_toe_stiff", '"x", "Suspension", 1, 1, 6, "Rear Hub Toe Stiffness", '
     '"Stiffness of the rear hubs against toe (axle line vs upright), x the base", {"stepDis":0.5, "subCategory":"Rear"}'),
    ("$pu_power", '"x", "Engine", 1.12, 0.8, 1.25, "Engine Power", "Combustion engine torque, x the base (MGU-K unchanged)", {"stepDis":0.01}'),
    ("$brake_map", '"", "Brakes", 0, 0, 1, "Low-Speed Brake Modulation", '
     '"1: eases the brakes at low speed like a driver modulating the pedal (less lock-up)", {"stepDis":1}'),
    ("$tc_slip", '"", "Engine", 0.12, 0.05, 0.3, "Torque Map Slip", '
     '"Rear wheel slip the torque map allows before cutting power", {"stepDis":0.01}'),
    # round 17 (post-corner drift suspects)
    ("$rear_link_stiff", '"x", "Suspension", 1, 0.5, 2, "Rear Link Stiffness", '
     '"Stiffness of the six links from each rear upright to the gearbox, x the base", {"stepDis":0.05, "subCategory":"Rear"}'),
    ("$rear_droop", '"x", "Suspension", 1, 1, 3, "Rear Droop Travel", '
     '"Rear wheel droop before the hard stop, x the base (~50 mm)", {"stepDis":0.1, "subCategory":"Rear"}'),
    ("$halfshaft_play", '"x", "Differentials", 1, 1, 4, "Driveshaft Plunge", '
     '"Rear driveshaft plunge before its end stops, x the base (+-5 % of its length)", {"stepDis":0.5, "subCategory":"Rear"}'),
    # round 18 (the rear hub shifting on its upright: rear_hub_fix()); round 19:
    # Hub Fix 15 ("Combined max") is Baseline
    ("$rear_hub_beam", '"x", "Suspension", 2, 1, 4, "Rear Axle Beams", '
     '"Stiffness of the beams holding the rear axle nodes to the upright, x the base", {"stepDis":0.25, "subCategory":"Rear"}'),
    ("$rear_brace", '"x", "Suspension", 1.5, 0, 2, "Rear Hub Bracing", '
     '"Extra beams from fore / aft brace nodes on the rear upright to the axle, x the upright links", {"stepDis":0.25, "subCategory":"Rear"}'),
    ("$rear_corner_mass", '"kg", "Suspension", 12, 0, 12, "Rear Corner Mass Shift", '
     '"kg per rear wheel moved from the engine ballast to its axle and upright nodes (same total; lets stiffer hub beams stay stable)", {"stepDis":0.5, "subCategory":"Rear"}'),
    ("$rear_toe_brace", '"x", "Suspension", 6, 0, 10, "Rear Toe Brace", '
     '"Torsion bar holding the rear axle line against toe about the upright, x 100 kNm/rad", {"stepDis":0.5, "subCategory":"Rear"}'),
]


# DRS (round 19): the RB14's DRS flap is its own mesh (build_model.py,
# redbull_wing_R_flap) on its own nodes (FLAP_NODES: leading edge drf1,
# trailing edge drf2; right / centre / left). The trailing edge is the
# hinge, held to the endplates and the main plane; a hydro from each
# endplate's lower node (rep2) to the leading edge lengthens with
# electrics.values.drs and swings the leading edge up by DRS_FLAP_ANGLE
# about the hinge, opening the slot as on the real car. The main plane stays
# put (its leading edge is fixed to the endplates again, as in the F4).
# The flap carries no aero triangles: the main wing's aero covers the whole
# wing and the DRS effect is the calibrated force pair below (thrusters on
# the gearbox: forward = less drag, up = less rear downforce, x (speed /
# 300 km/h)^2 via electrics.values.drsThrust from redbullDRS.lua).
# Rounds 15-18 offered $drs_model 0 (hydros tilting the whole wing) and 1
# (forces); the flap replaces both.
DRS_FLAP_ANGLE = 26.0          # deg the flap turns when open (~55 mm at the leading edge)
FLAP_LE = (2.401, 0.879)       # (y, z) of the flap's leading / trailing edge at the
FLAP_TE = (2.505, 0.962)       # default wing angle (8 deg), from the RB14 mesh
FLAP_X = 0.43
FLAP_NODE_WEIGHT = 0.5
FLAP_TORSION = (80000, 8, 60000, 120000)   # Nm/rad, damping, deform / break torque (Nm)
WING_PIVOT_R = (2.5674, 0.9421)  # the wing flexbodies' pivot (wing angle setting)
FLAP_BEGIN, FLAP_END = "//DRS flap (round 19, f1_setup.py)", "//DRS flap end"


def _flap_pos(y, z):
    """jbeam coordinates of a flap point, turned about the wing pivot with
    the wing angle setting like the wing mesh (small-angle form)."""
    yp, zp = WING_PIVOT_R
    d = "(($wing_angle_R-8)*0.0174533)"
    return ('"$=%.4f-%s*%.4f"' % (y, d, z - zp), '"$=%.4f+%s*%.4f"' % (z, d, y - yp))


def drs_flap():
    import re
    import numpy as np
    f = f"{V}/redbull_wing_R.jbeam"
    text = je._read(f)
    text = re.sub(r'[ \t]*%s.*?%s\r\n' % (re.escape(FLAP_BEGIN), re.escape(FLAP_END)), "", text, flags=re.S)
    E = "\r\n"
    # main plane: leading edge fixed to the endplates again (F4 beams)
    for s_ in "rl":
        text = re.sub(r'          \["rep[123]%s","rwg1%s"\],\r\n' % (s_, s_), "", text)
        k = text.index('          ["rep4%s","rwg1%s"],' % (s_, s_))
        text = text[:k] + "".join('          ["rep%d%s","rwg1%s"],\r\n' % (i, s_, s_) for i in (1, 2, 3)) + text[k:]
    # nodes
    rows = [" " * 9 + FLAP_BEGIN, " " * 9 + '{"nodeWeight":%g},' % FLAP_NODE_WEIGHT,
            " " * 9 + '{"selfCollision":false},', " " * 9 + '{"group":"redbull_wing_R_flap"},']
    for n, (y, z) in (("drf1", FLAP_LE), ("drf2", FLAP_TE)):
        py, pz = _flap_pos(y, z)
        for s_, x in (("r", -FLAP_X), ("", 0.0), ("l", FLAP_X)):
            rows.append(" " * 9 + '["%s%s", %.3f, %s, %s],' % (n, s_, x, py, pz))
    rows += [" " * 9 + '{"selfCollision":true},', " " * 9 + FLAP_END]
    k = text.index("         //--BEAM WING--")
    text = text[:k] + E.join(rows) + E + text[k:]
    # torsion bars across the flap's centre chord (as the main wing has):
    # its six nodes lie nearly in one plane, where beams alone leave the
    # centre free to move out of plane -- the flap flexed in the middle
    tb = [" " * 8 + FLAP_BEGIN,
          " " * 8 + '{"spring":%d, "damp":%d, "deform":%d, "strength":%d},' % FLAP_TORSION,
          " " * 8 + '["drf2r","drf2","drf1","drf1l"],["drf2l","drf2","drf1","drf1r"],'
                    '["drf2r","drf2","drf1","drf1r"],["drf2l","drf2","drf1","drf1l"],',
          " " * 8 + FLAP_END]
    k = text.index("        //rigidify endplates")
    text = text[:k] + E.join(tb) + E + text[k:]
    # beams: the flap frame, and its trailing edge (hinge) held to the wing
    beams = [" " * 10 + FLAP_BEGIN,
             " " * 10 + '{"beamPrecompression":1, "beamType":"|NORMAL", "beamLongBound":1.0, "beamShortBound":1.0},',
             " " * 10 + '{"beamSpring":603000, "beamDamp":60},',       # (spaced: rear_wing() matches the F4's rows)
             " " * 10 + '{"beamDeform":130140, "beamStrength":"FLT_MAX"},',
             " " * 10 + '{"breakGroup":""},']
    frame = [("drf1r", "drf2r"), ("drf1", "drf2"), ("drf1l", "drf2l"), ("drf1r", "drf1"), ("drf1", "drf1l"),
             ("drf2r", "drf2"), ("drf2", "drf2l"), ("drf1r", "drf2"), ("drf2r", "drf1"), ("drf1l", "drf2"),
             ("drf2l", "drf1"), ("drf1r", "drf1l"), ("drf2r", "drf2l")]
    beams.append(" " * 10 + "".join('["%s","%s"],' % b for b in frame))
    beams.append(" " * 10 + '{"beamSpring":600300,"beamDamp":50,"beamDeform":"FLT_MAX","beamStrength":20000},')
    for s_ in "rl":
        beams.append(" " * 10 + '{"breakGroup":"endplates_R%s"},' % s_.upper()
                     + "".join('["drf2%s","%s"],' % (s_, n) for n in ("rep3" + s_, "rep4" + s_, "rwg1" + s_, "rwg2" + s_)))
    beams.append(" " * 10 + '{"breakGroup":""},' + '["drf2","rwg1"],["drf2","rwg2"],')
    beams.append(" " * 10 + FLAP_END)
    k = text.index("          //--REAR WING ENDPLATES--")
    text = text[:k] + E.join(beams) + E + text[k:]
    # hydros: rep2 -> leading edge; factor from the hinge rotation
    import setup_report as sr
    je._write(f, text)
    v = sr.Vehicle("redbull", None)
    th = np.radians(DRS_FLAP_ANGLE)
    rows = []
    for s_ in "rl":
        a, le, te = v.pos["rep2" + s_], v.pos["drf1" + s_], v.pos["drf2" + s_]
        r = le - te
        # leading edge up = rotation about the hinge (x axis) taking -y to +z
        y2 = r[1] * np.cos(th) - r[2] * np.sin(th)
        z2 = r[1] * np.sin(th) * -1 + r[2] * np.cos(th)
        le2 = te + np.array([r[0], y2, z2])
        if le2[2] < le[2]:
            le2 = te + np.array([r[0], r[1] * np.cos(th) + r[2] * np.sin(th), r[1] * np.sin(th) + r[2] * np.cos(th)])
        L0, L1 = np.linalg.norm(le - a), np.linalg.norm(le2 - a)
        rows.append('        ["rep2%s","drf1%s", {"factor":%.4f, "inputSource":"drs", "inputFactor":1, "inRate":5, "outRate":5, '
                    '"beamSpring":600000, "beamDamp":40, "beamDeform":"FLT_MAX", "beamStrength":20000, "breakGroup":"endplates_R%s"}],\r\n'
                    % (s_, s_, (L1 - L0) / L0, s_.upper()))
        lift = le2[2] - le[2]
    text = je._read(f)
    block = ('    "hydros": [\r\n'
             '        ["id1:", "id2:"],\r\n'
             '        //DRS: swings the flap\'s leading edge up about its trailing edge (see tools/rb14/f1_setup.py)\r\n'
             + "".join(rows) + '    ],\r\n')
    text = re.sub(r'    "hydros": \[\r\n        \["id1:", "id2:"\],\r\n        //DRS.*?    \],\r\n', "", text, flags=re.S)
    k = text.index('    "triangles": [')
    text = text[:k] + block + text[k:]
    fw, up = DRS_DRAG_300 / 2, DRS_DOWNFORCE_300 / 2
    rows = "".join('        ["rx1%s", "rx2%s", %d, %d, "drsThrust"],\r\n'
                   '        ["rx4%s", "rx2%s", %d, %d, "drsThrust"],\r\n'
                   % (s_, s_, fw, fw * 1.6, s_, s_, up, up * 1.6) for s_ in "rl")
    block = ('    "thrusters": [\r\n'
             '        ["id1:", "id2:", "factor", "thrustLimit", "control"],\r\n'
             '        //DRS as forces (see tools/rb14/f1_setup.py): forward on rx2 = less drag, up = less downforce\r\n'
             + rows + '    ],\r\n')
    text = re.sub(r'    "thrusters": \[\r\n        \["id1:", "id2:", "factor", "thrustLimit", "control"\],\r\n        //DRS as forces.*?    \],\r\n', "", text, flags=re.S)
    k = text.index('    "triangles": [')
    text = text[:k] + block + text[k:]
    # flexbodies: the flap with the wing's pivot; the RB14 has no beam wing
    # (banned 2014-2021) and no separate wing pillar, so those F4 meshes go
    # (their nodes and aero stay: the F4's lower wing stands in for the
    # diffuser's share of the rear downforce the setup was calibrated with)
    text = re.sub(r'         \["redbull_wing_R_flap".*\r\n', "", text)
    k = text.index('["redbull_wing_B", ["redbull_wing_B"]')
    k = text.rindex("\r\n", 0, k) + 2
    text = text[:k] + ('         ["redbull_wing_R_flap", ["redbull_wing_R_flap"], [], {"pos":{"x": 0.0, "y":%.4f, "z":%.4f}, '
                       '"rot":{"x":"$=$wing_angle_R-8", "y":0, "z":0}}],\r\n' % WING_PIVOT_R) + text[k:]
    text = re.sub(r'(         )(\["redbull_wing_B", \["redbull_wing_B"\])', r'\1// rb14: no beam wing \2', text)
    text = re.sub(r'(         )(\["redbull_wing_R_mounts", )', r'\1// rb14: no wing pillar \2', text)
    je._write(f, text)
    print("DRS flap: opens %.0f deg, leading edge up %.0f mm" % (DRS_FLAP_ANGLE, lift * 1000))


# DRS effect at 300 km/h on Baseline (setup_report "aero DRS open"):
# downforce 21.3 -> 18.1 kN, drag 5.54 -> 4.26 kN
DRS_DRAG_300, DRS_DOWNFORCE_300 = 1280, 3140


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



# ------------------------------------------------ F4 -> F1 migrations
# Values the F4 base still carried after the rounds above (review, round 9).
# Each scales the F4 original (vehicles/fr04), so re-running is safe.
def _scale_f4(name, part, scales, start=None, end=None, when=None):
    """Set every numeric value of the keys in scales (key -> factor) inside
    one part -- optionally only in its "beams" section between the text
    markers start and end -- to the F4 original's value times the factor.
    when(key, f4_value) -> bool can skip values (e.g. weak helper links)."""
    import re
    f = f"{V}/redbull_{name}.jbeam"
    orig = open(f"vehicles/fr04/fr04_{name}.jbeam", encoding="utf-8", newline="").read()
    text = je._read(f)

    def region(src, p):
        a, b = _part_block(src, p)
        if start is not None:
            a = src.index(start, src.index('"beams"', a))
        if end is not None:
            b = src.index(end, a)
        return a, b
    a0, b0 = region(orig, part.replace("redbull", "fr04"))
    a, b = region(text, part)
    block = text[a:b]
    for key, k in scales.items():
        pat = re.compile(r'("%s"\s*:\s*)(\d+(?:\.\d+)?)' % key)
        src = [float(m.group(2)) for m in pat.finditer(orig[a0:b0])]
        if len(pat.findall(block)) != len(src):
            raise ValueError(f"{part}: {key} count differs from the F4 ({len(pat.findall(block))} vs {len(src)})")
        it = iter(src)

        def sub(m):
            x = next(it)
            y = x * k if (when is None or when(key, x)) else x
            return m.group(1) + ("%d" % round(y) if y >= 10 else "%g" % round(y, 3))
        block = pat.sub(sub, block)
    je._write(f, text[:a] + block + text[b:])


# 1. Shift table in the engine part (it overrides the transaxle's; the F4's
# was for a 7,000 rpm four-cylinder): upshift at 12,000 rpm, and each
# downshift point chosen so the lower gear lands at ~11,500 rpm.
SHIFT_UP_RPM = 12000


def shift_logic():
    f = f"{V}/redbull_engine.jbeam"
    g = GEARS["standard"]
    down = [0, 0, 0] + [int(11500 * g[i] / g[i - 1] // 50 * 50) for i in range(1, len(g))]
    je.set_all(f, r'"highShiftDownRPM":\[[^\]]*\]', '"highShiftDownRPM":[%s]' % ",".join(map(str, down)))
    je.set_all(f, r'"highShiftUpRPM":\s*[\d.]+', '"highShiftUpRPM":%d' % SHIFT_UP_RPM)
    je.set_all(f, r'"clutchLaunchStartRPM":\s*[\d.]+', '"clutchLaunchStartRPM":7000')
    je.set_all(f, r'"clutchLaunchTargetRPM":\s*[\d.]+', '"clutchLaunchTargetRPM":7500')


# 2. Tyre carcass: tried 2.5x stiffer in round 9 -- in game the tyres
# vibrated, turned inside out and tore off at spawn (round 9b). The game's
# generated tyre is not something setup_report can model (it rated the
# stiffer tyres the same as the F4's), so the carcass stays at the F4's
# springs and damping, and check_stability() holds every tyre spring to
# the F4's stiffness per kg of tyre node (TYRE_MAX_K_PER_KG).
# Round 11 tried 1.6x (0.85x the F4's stiffness per kg) with carrier
# damping 900 for the front judder: the front suspension broke and the
# wheels fell off at spawn. Both back to round 10's (1.0x / 600).
TYRE_CARCASS = 1.0
TYRE_SPRINGS = {k: TYRE_CARCASS for k in ("wheelTreadBeamSpring", "wheelTreadReinfBeamSpring", "wheelPeripheryBeamSpring",
                                         "wheelPeripheryReinfBeamSpring", "wheelReinfBeamSpring", "wheelSideBeamSpringExpansion")}
TYRE_MAX_K_PER_KG = 1.0         # x the F4's spring / tyre node weight
TYRE_DAMP = 1.0


def tyre_carcass():
    import re
    for axle in ("F", "R"):
        f = f"{W}/redbull_tires_{axle}_13.jbeam"
        orig = je._read(f"vehicles/common/fr04_wheels/fr04_tires_{axle}_13.jbeam")
        text = je._read(f)
        for key, k in TYRE_SPRINGS.items():
            damp = key.replace("Spring", "Damp")
            pat = re.compile(r'\{"%s":(\d+|"[^"]*"),\s*"%s":(\d+)\}' % (key, damp))
            src = pat.findall(orig)
            if len(pat.findall(text)) != len(src) or not src:
                raise ValueError(f"tyres {axle}: {key} rows differ from the F4")
            it = iter(src)
            # front: x the tuning variable $tyre_carcass_F (default 1)
            fmt = (lambda s: '"$=%d*$tyre_carcass_F"' % (int(s) * k)) if axle == "F" else (lambda s: "%d" % (int(s) * k))
            text = pat.sub(lambda m: (lambda s, d: '{"%s":%s,"%s":%d}' % (key, fmt(s), damp, int(d) * TYRE_DAMP))(*next(it)), text)
        je._write(f, text)


# 3. Front wing: ~5 kN of downforce at 300 km/h on the F4's wing beams bent
# it visibly. Stiffer and stronger structure, an ~8 kg wing assembly.
WING_F_STIFF, WING_F_STRENGTH, WING_F_DAMP = 3.0, 4.0, 1.0   # more damping on the 0.35 kg endplates: over the damped limit
WING_F_WEIGHTS = {"wing": 0.5, "wing_inner": 0.8, "endplate": 0.35}
# The nose cone carries it: F4 nose beams bent ~27 mm under that load.
# 1.5x stiffer on 1.5x heavier nodes (the most the 2 kHz solver takes).
# Tip deflection at 300 km/h (6.3 kN, setup_report FEM): 92 mm on the F4
# structure -> 46 mm (centre 34 -> 27). The nose-to-tub mounts stay as they
# were: stiffer, they put the bulkhead nodes over the limit.
NOSE_STIFF, NOSE_WEIGHT = 1.5, 1.5


def front_wing():
    import re
    _scale_f4("wing_F", "redbull_wing_F", {"beamSpring": WING_F_STIFF, "beamDamp": WING_F_DAMP},
              start="//--FRONT WING--", when=lambda key, x: key == "beamDamp" or x >= 50000)
    _scale_f4("wing_F", "redbull_wing_F", {"beamDeform": WING_F_STRENGTH, "beamStrength": WING_F_STRENGTH},
              start="//--FRONT WING--")
    _scale_f4("wing_F", "redbull_wing_F", {"beamSpring": NOSE_STIFF}, start='["id1:"', end="//attach",
              when=lambda key, x: x >= 50000)
    f = f"{V}/redbull_wing_F.jbeam"
    text = je._read(f)
    orig = je._read("vehicles/fr04/fr04_wing_F.jbeam")
    span = lambda s: (s.index("//--FRONT NOSECONE--"), s.index("//enticer/rigidifier node"))
    pat = re.compile(r'("nodeWeight":)([\d.]+)')
    a0, b0 = span(orig)
    it = iter(float(m.group(2)) for m in pat.finditer(orig[a0:b0]))
    a, b = span(text)
    text = text[:a] + pat.sub(lambda m: m.group(1) + "%.2f" % (next(it) * NOSE_WEIGHT), text[a:b]) + text[b:]
    text, n1 = re.subn(r'(\{"nodeWeight":)[\d.]+(\},\r\n         \{"group":"redbull_wing_F"\})',
                       lambda m: m.group(1) + "%g" % WING_F_WEIGHTS["wing"] + m.group(2), text)
    text, n2 = re.subn(r'(\["fwg[12][rl]",[^\]]*\{"nodeWeight":)[\d.]+', lambda m: m.group(1) + "%g" % WING_F_WEIGHTS["wing_inner"], text)
    text, n3 = re.subn(r'(\{"nodeWeight":)[\d.]+(\},\r\n         \{"group":"redbull_endplate_FR"\})',
                       lambda m: m.group(1) + "%g" % WING_F_WEIGHTS["endplate"] + m.group(2), text)
    if (n1, n2, n3) != (1, 4, 1):
        raise ValueError(f"front wing node weights: {n1}, {n2}, {n3} matches")
    je._write(f, text)


# 4. Floor: F4 beams (60-1000 kN/m) carried plank ballast they were never
# sized for; 3x stiffer and stronger. The ballast moved into the tub
# (see ballast()); the floor nodes are back to the F4's weights.
FLOOR_STIFF, FLOOR_STRENGTH = 1.5, 3.0


def floor():
    _scale_f4("floor", "redbull_floor", {"beamSpring": FLOOR_STIFF, "beamDeform": FLOOR_STRENGTH, "beamStrength": FLOOR_STRENGTH},
              start='["id1:"')


# 5. Monocoque: the F4 tub measures ~4,700 Nm/deg front bulkhead to seat
# back (setup_report-style FEM, monocoque_torsion()); a carbon F1 tub is
# many times that. 2x within the 2 kHz solver's limits.
TUB_STIFF, TUB_STRENGTH = 2.0, 2.0
TUB_SOFT = 3.5e6                # only the softer tub beams; the 4-8 MN/m rigids are at the solver's limit


def monocoque():
    # the tub shell and the suspension mounts; not the roll hoop or halo
    for start, end in (("//--MONOCOQUE--", "//hoop rigids"), ("//suspension mounts rigids", "//halo")):
        _scale_f4("body", "redbull_body", {"beamSpring": TUB_STIFF, "beamDeform": TUB_STRENGTH}, start=start, end=end,
                  when=lambda key, x: x > 10000 and (key != "beamSpring" or x <= TUB_SOFT))


def monocoque_torsion(v):
    """Torsional stiffness (Nm/deg) of the tub alone: seat-back nodes held,
    a couple on the front bulkhead's lower nodes."""
    import numpy as np
    body = [r["id"] for p, r in v.section("nodes") if p == "redbull_body"]
    fixed = [n for n in body if n.startswith("rt")]
    free = [n for n in body if n not in fixed]
    idx = {n: i for i, n in enumerate(free)}
    K = np.zeros((3 * len(free),) * 2)
    for _, r in v.section("beams"):
        a, b = r.get("id1:"), r.get("id2:")
        if a not in body or b not in body or "SUPPORT" in str(r.get("beamType", "")):
            continue
        d = v.pos[b] - v.pos[a]
        u = d / np.linalg.norm(d)
        k = v.val(r.get("beamSpring"), 0)
        for x, gx in ((a, -u), (b, u)):
            for y, gy in ((a, -u), (b, u)):
                if x in idx and y in idx:
                    K[3 * idx[x]:3 * idx[x] + 3, 3 * idx[y]:3 * idx[y] + 3] += k * np.outer(gx, gy)
    K += np.eye(len(K)) * 1e-2
    f = np.zeros(len(K))
    f[3 * idx["fx1r"] + 2], f[3 * idx["fx1l"] + 2] = 1000, -1000
    u = np.linalg.solve(K, f)
    w = abs(v.pos["fx1r"][0] - v.pos["fx1l"][0])
    return 1000 * w / math.degrees((u[3 * idx["fx1r"] + 2] - u[3 * idx["fx1l"] + 2]) / w)


# 6. Wheel parts' axle beams: F4 values for 2-4x the loads.
def wheel_beams():
    import re
    for a in ("F", "R"):
        f = f"{W}/redbull_wheels_{a}_13.jbeam"
        je.set_all(f, r'\{"beamDeform":\d+,"beamStrength":\d+\}', '{"beamDeform":%d,"beamStrength":%d}' % (78500 * 3, 434000 * 3))
        je.set_all(f, r'\{"beamSpring":\d+,"beamDamp":\d+\}', '{"beamSpring":%d,"beamDamp":%d}' % (1501000 * 2, 100))
        text = je._read(f)
        text = re.sub(r'("hub(?:Tread|Periphery|Side)BeamDamp":)\d+', r'\g<1>10', text)   # F4's: 40 on 0.45 kg hub nodes ate the damped margin
        je._write(f, text)


# 7. Cooling: sidepod radiators of an F1 car (~0.6 m^2 core, ~8 L of
# coolant), ~10 kg with coolant instead of the F4's 25 kg.
def cooling():
    f = f"{V}/redbull_radiator.jbeam"
    je.set_all(f, r'"radiatorArea":[\d.]+', '"radiatorArea":0.6')
    je.set_all(f, r'"radiatorEffectiveness":\d+', '"radiatorEffectiveness":14000')
    je.set_all(f, r'"coolantVolume":[\d.]+', '"coolantVolume":8')
    import re
    text, n = re.subn(r'(\{"engineGroup":"radiator"\},\r\n         \{"nodeWeight":)[\d.]+', r'\g<1>1.0', je._read(f))
    if n != 1:
        raise ValueError("radiator node weight row not found")
    je._write(f, text)


# 8. Engine damage: thresholds 3x the F4's (~3x the torque and cylinder load).
# 9. Clutch: BeamNG's frictionClutch sizes its capacity from the engine's
# torque; clutchFreePlay / lockSpringCoef are pedal feel and lock-up
# stiffness, not capacity. Left as the F4's (not verifiable offline).
# 11. Sound: the samples stay (BeamNG ships no V6 turbo hybrid set); the
# pitch follows a V6's firing order.
# Round 10: a 2018 V6 hybrid is high-pitched and raspy -- a single exhaust,
# lots of upper harmonics, little bass. Same samples (BeamNG ships no V6
# turbo-hybrid set), re-voiced: less low-end boom, more intake and exhaust,
# upper-mid and treble lifted, the firing-order fundamental brought forward,
# more overrun.
SOUND_ENGINE = {"intakeMuffling": 0.4, "mainGain": 0, "offLoadGain": 0.5, "lowShelfGain": -6, "highShelfGain": 2,
                "eqLowGain": -6, "eqHighGain": 4, "eqHighFreq": 3000, "eqFundamentalGain": 3}
SOUND_EXHAUST = {"mainGain": 6, "offLoadGain": 0.45, "maxLoadMix": 0.8, "lowShelfGain": -12, "highShelfGain": 7,
                 "eqHighGain": 5, "eqHighFreq": 1500, "eqHighWidth": 0.3, "eqFundamentalGain": 2}


def engine_sound():
    import re
    f = f"{V}/redbull_engine.jbeam"
    text = je._read(f)
    for block, vals in (('"soundConfig"', SOUND_ENGINE), ('"soundConfigExhaust"', SOUND_EXHAUST)):
        a = text.index(block + ": {")
        b = text.index("}", a)
        body = text[a:b]
        for key, val in vals.items():
            body, n = re.subn(r'("%s":\s*)-?[\d.]+' % key, lambda m: m.group(1) + "%g" % val, body)
            if n != 1:
                raise ValueError(f"{block}: {key} not found")
        text = text[:a] + body + text[b:]
    je._write(f, text)


def engine_misc():
    f = f"{V}/redbull_engine.jbeam"
    for key, val in (("headGasketDamageThreshold", 4500000), ("pistonRingDamageThreshold", 4500000),
                     ("connectingRodDamageThreshold", 6000000)):
        je.set_all(f, r'"%s":\s*\d+' % key, '"%s":%d' % (key, val))
    je.set_all(f, r'"fundamentalFrequencyCylinderCount":\s*\d+', '"fundamentalFrequencyCylinderCount":6')


# 10. Bodywork panels: 2.5x the F4's deform / break forces (F1 speeds and
# aero loads on the sidepods, engine cover and suspension fairings).
PANEL_STRENGTH = 2.5


def panels():
    for name, part in (("sidepods", "redbull_sidepod_R"), ("sidepods", "redbull_sidepod_L"),
                       ("panels", "redbull_enginecover"), ("panels", "redbull_suscover")):
        _scale_f4(name, part, {"beamDeform": PANEL_STRENGTH, "beamStrength": PANEL_STRENGTH})


# 12. Chase camera for a 5.7 m car (F4 ~4.3 m).
def camera():
    f = f"{V}/redbull_body.jbeam"
    je.set_all(f, r'"distance":[\d.]+,', '"distance":6.8,')
    je.set_all(f, r'"distanceMin":[\d.]+,', '"distanceMin":2.5,')


# 13. Hard travel stops (spring-beam travel; wheel travel / motion ratio):
# ~57 mm bump front, ~64 mm rear, 50 mm droop -- the F4 allowed ~120 mm.
TRAVEL_STOP = {"F": 0.034, "R": 0.037}


def travel_stops():
    je.set_in_part(f"{V}/redbull_suspension_F.jbeam", "redbull_suspension_F",
                   r'"longBoundRange":0\.03,"shortBoundRange":[\d.]+', '"longBoundRange":0.03,"shortBoundRange":%s' % TRAVEL_STOP["F"])
    # rear droop stop x the tuning variable $rear_droop (round 17; default 1)
    je.set_in_part(f"{V}/redbull_suspension_R.jbeam", "redbull_suspension_R",
                   r'"longBoundRange":(?:0\.03|"\$=0\.03\*\$rear_droop"),"shortBoundRange":[\d.]+',
                   '"longBoundRange":"$=0.03*$rear_droop","shortBoundRange":%s' % TRAVEL_STOP["R"])
    # rear driveshaft (halfshaft) end stops x $halfshaft_play (round 17)
    je.set_all(f"{V}/redbull_differential_R.jbeam",
               r'"beamLongBound":(?:0\.05|"\$=0\.05\*\$halfshaft_play"), "beamShortBound":(?:0\.05|"\$=0\.05\*\$halfshaft_play"),"boundZone":0\.1',
               '"beamLongBound":"$=0.05*$halfshaft_play", "beamShortBound":"$=0.05*$halfshaft_play","boundZone":0.1')


# 14. Brakes: carbon pads bite harder (brakeSpring); the rear parking
# torque holds the heavier, higher-torque car on a slope. ABS targets stay
# (2018 F1 had no ABS; the F4's are only used when the player enables it).
def brake_misc():
    f = f"{V}/redbull_brakes.jbeam"
    je.set_all(f, r'\{"brakeSpring":\d+\}', '{"brakeSpring":300}')
    je.set_all(f, r'\{"parkingTorque":1600\}|\{"parkingTorque":3000\}', '{"parkingTorque":3000}')


# 15. scaledragCoef 1.6 (main part) stays: it scales BeamNG's per-triangle
# drag and the aero factors above (setup_report) were solved with it.


# Round 12: front-wheel fix variables (tuning menu, Front Suspension /
# Wheels). Round 13: the defaults are Front Fix 4 -- the best car in the
# round-12 test (tyres 1.3x, 2 kg per corner from the rim to the upright).
FRONT_FIX_VARS = [
    '["$tyre_carcass_F", "range", "x", "Wheels", 1.3, 1.0, 1.8, "Front Tire Carcass Stiffness", '
    '"Tread and sidewall stiffness of the front tires, x the base tire", {"stepDis":0.05, "subCategory":"Front"}]',
    '["$carrier_damp_F", "range", "N/m/s", "Suspension", %d, 300, 1500, "Front Upright Damping", '
    '"Damping of the front wheel carriers (wheel judder)", {"stepDis":50, "subCategory":"Front"}]' % CARRIER_DAMP,
    '["$upright_mass_F", "range", "kg", "Suspension", 2, 0, 5, "Front Upright Mass Shift", '
    '"Mass moved from each front rim to its upright (same corner weight)", {"stepDis":0.5, "subCategory":"Front"}]',
    '["$steer_damper_F", "range", "x", "Suspension", 1.0, 0.2, 2.0, "Steering Damper", '
    '"Damping of the steering motion at the front uprights, x the base", {"stepDis":0.1, "subCategory":"Front"}]',
]


def front_fix_vars():
    import re
    f = f"{V}/redbull_suspension_F.jbeam"
    text = je._read(f)
    a, b = _part_block(text, "redbull_suspension_F")
    block = text[a:b]
    block = re.sub(r'        \["\$(?:tyre_carcass_F|carrier_damp_F|upright_mass_F|steer_damper_F)".*\r\n', "", block)
    i = block.index('        ["$toe_F"')
    i = block.index("\r\n", i) + 2
    block = block[:i] + "".join("        %s,\r\n" % r for r in FRONT_FIX_VARS) + block[i:]
    je._write(f, text[:a] + block + text[b:])


def migrations():
    shift_logic()
    tyre_carcass()
    front_wing()
    floor()
    monocoque()
    wheel_beams()
    cooling()
    engine_misc()
    engine_sound()
    panels()
    camera()
    travel_stops()
    brake_misc()
    front_fix_vars()
    references()
    halo_part()
    exhaust_mesh()

# Round 19: the halo is its own part (slot "redbull_halo" in the body, so a
# configuration can leave it off) on its own nodes, placed on the RB14's
# halo tube (HALO_NODES: pillar foot, pillar top, sides, rear legs). The F4's
# halo nodes (halo / halor / halol) sat on the F4's halo: the rear pair 23 cm
# behind the RB14 halo's legs, so the mesh bent off its nodes. Their beams
# and collision triangles move out of the body with them; halorr / haloll
# (roll structure) stay, and the roll-hoop top node joins the roll hoop's
# mesh group. Runs once on the F4-derived body (idempotent).
HALO_NODES = {      # name: (x, y, z, kg); r/l pairs mirror x
    "halof": (0.0, -0.74, 0.72, 1.0), "halo": (0.0, -0.46, 0.89, 1.0),
    "halor": (-0.29, -0.22, 0.86, 1.0), "halobr": (-0.31, 0.03, 0.83, 1.0)}
HALO_SPRING = 1500000       # N/m: 6 kg of halo nodes (a real halo is ~7 kg) within the solver limit
HALO_BEAMS = [("halof", "halo"), ("halo", "halor"), ("halo", "halol"), ("halor", "halol"), ("halor", "halobr"),
              ("halol", "halobl"), ("halor", "halobl"), ("halol", "halobr"), ("halo", "halobr"), ("halo", "halobl"),
              ("halof", "mt3"), ("halof", "mt1r"), ("halof", "mt1l"), ("halof", "mt2r"), ("halof", "mt2l"),
              ("halo", "mt3"), ("halo", "mt2r"), ("halo", "mt2l"), ("halor", "mt2r"), ("halol", "mt2l"),
              ("halor", "rt4r"), ("halol", "rt4l"), ("halobr", "rt4r"), ("halobl", "rt4l"), ("halobr", "mt2r"),
              ("halobl", "mt2l"), ("halobr", "halorr"), ("halobl", "haloll"), ("halobr", "rt2r"), ("halobl", "rt2l"),
              ("halobr", "rt3r"), ("halobl", "rt3l")]
HALO_TRIS = [("halo", "halol", "halor"), ("halor", "halol", "halobl"), ("halor", "halobl", "halobr"),
             ("halo", "halof", "mt2l"), ("halo", "mt2r", "halof")]


def exhaust_mesh():
    """Round 19: the RB14's own exhaust (tailpipe and wastegate pipes) is the
    exhaust part's mesh (build_model.py); the F4 one was dropped. It runs
    along the centre over the gearbox, so it hangs on the engine's and the
    gearbox's nodes (the F4 exhaust nodes are 0.7 m away)."""
    je.set_all(f"{V}/redbull_exhaust.jbeam",
               r'(?:// rb14: no mesh )?\["redbull_exhaust", \["redbull_exhaust","redbull_engine"\]\],|\["redbull_exhaust", \["redbull_engine","redbull_transaxle"\]\],',
               '["redbull_exhaust", ["redbull_engine","redbull_transaxle"]],')


def halo_part():
    import re
    f = f"{V}/redbull_body.jbeam"
    text = je._read(f)
    # out of the body: the F4 halo nodes, their beams and triangles, the mesh
    text = re.sub(r'         \["halo[rl]?",[^\]]*\],?[^\r\n]*\r\n', "", text)
    text = text.replace('         {"group":["redbull_halo"]},\r\n', "")
    text = re.sub(r'(         //roll hoop\r\n         \{"nodeWeight":3\.5\},\r\n)(?!         \{"group")',
                  r'\1         {"group":["redbull_rollhoop"]},\r\n', text)
    text = re.sub(r'(\["(?:mt2[rl]|mt3|halo(?:rr|ll))",[^\]]*"group":\[[^\]]*?), ?"redbull_halo"', r"\1", text)
    text = text.replace('         ["redbull_halo", ["redbull_halo"]],\r\n', "")
    a = text.find("          //halo\r\n")
    if a >= 0:
        b = text.index("          //spring mount node", a)
        text = text[:a] + "          //halo: the redbull_halo part (round 19)\r\n\r\n" + text[b:]
    m = re.search(r'        //halo\r\n        \{"dragCoef":[\d.]+\},', text)
    a = m.start() if m else -1
    if a >= 0:
        b = text.index("        //hoop", a)
        text = text[:a] + text[b:]
    if '["redbull_halo","redbull_halo", "Halo"]' not in text:
        k = text.index('        ["redbull_steer","redbull_steer", "Steering Wheel"],')
        text = text[:k] + '        ["redbull_halo","redbull_halo", "Halo"],\r\n' + text[k:]
    # the halo part
    text = re.sub(r'\r\n"redbull_halo":\s*\{.*?(?=\r\n"[A-Za-z0-9_]+"\s*:\s*\{|\r\n\}\s*$)', "", text, flags=re.S)
    nodes = []
    for n, (x, y, z, w) in HALO_NODES.items():
        sides = ((n, x),) if x == 0 else ((n, x), (n[:-1] + "l", -x))
        for name, xx in sides:
            nodes.append('         ["%s", %.3f, %.3f, %.3f, {"nodeWeight":%g}],' % (name, xx, y, z, w))
    beams = "".join('["%s","%s"],' % b for b in HALO_BEAMS)
    tris = "".join('["%s", "%s", "%s"],' % t for t in HALO_TRIS)
    part = ('\r\n"redbull_halo": {\r\n'
            '    "information":{\r\n        "authors":"redbull mod (RB14 conversion)",\r\n        "name":"Halo",\r\n        "value":2500,\r\n    },\r\n'
            '    "slotType" : "redbull_halo",\r\n'
            '    "flexbodies":[\r\n        ["mesh", "[group]:", "nonFlexMaterials"],\r\n        ["redbull_halo", ["redbull_halo"]],\r\n    ],\r\n'
            '    "nodes":[\r\n         ["id", "posX", "posY", "posZ"],\r\n'
            '         //on the RB14 halo tube: pillar foot, pillar top, sides, rear legs (f1_setup.py)\r\n'
            '         {"collision":true},\r\n         {"selfCollision":true},\r\n         {"nodeMaterial":"|NM_METAL"},\r\n'
            '         {"frictionCoef":0.5},\r\n         {"group":"redbull_halo"},\r\n' + "\r\n".join(nodes) + '\r\n'
            '         {"group":""},\r\n    ],\r\n'
            '    "beams":[\r\n          ["id1:", "id2:"],\r\n'
            '          {"beamPrecompression":1, "beamType":"|NORMAL", "beamLongBound":1, "beamShortBound":1},\r\n'
            '          {"beamSpring":%d, "beamDamp":80},\r\n          {"beamDeform":120000,"beamStrength":"FLT_MAX"},\r\n' % HALO_SPRING +
            '          {"deformLimitExpansion":2.0},\r\n          ' + beams + '\r\n          {"deformLimitExpansion":""},\r\n    ],\r\n'
            '    "triangles":[\r\n        ["id1:", "id2:", "id3:"],\r\n        {"triangleType":"NORMALTYPE"},\r\n'
            '        {"dragCoef":8},\r\n        {"group":"redbull_halo"},\r\n        {"groundModel":"metal"},\r\n        ' + tris +
            '\r\n        {"group":""},\r\n    ],\r\n},')
    # without the halo: the flush covers over its mounts (build_model.py)
    text = re.sub(r'\r\n"redbull_halo_cover":\s*\{.*?(?=\r\n"[A-Za-z0-9_]+"\s*:\s*\{|\r\n\}\s*$)', "", text, flags=re.S)
    part += ('\r\n"redbull_halo_cover": {\r\n'
             '    "information":{\r\n        "authors":"redbull mod (RB14 conversion)",\r\n        "name":"No Halo (mount covers)",\r\n        "value":0,\r\n    },\r\n'
             '    "slotType" : "redbull_halo",\r\n'
             '    "flexbodies":[\r\n        ["mesh", "[group]:", "nonFlexMaterials"],\r\n        ["redbull_halo_cover", ["redbull_body"]],\r\n    ],\r\n},')
    k = text.rindex("\r\n}")
    text = text[:k].rstrip() + part + text[k:]
    je._write(f, text)


# Broken references inherited from the F4, found by tools/check_mod.py:
# the front spindles take their input from devices no part defines
# (wheelaxleFL / FR: undriven wheels are root devices, input "dummy"); the
# springs' beamPrecompression reads $rideheight_F / _R, which no part
# defines (precompressionRange overrides it; 1 = no precompression); the
# fuel cell's mainTank and fuel nodes name a beam "fuelTank" that did not
# exist (now ft1-rt4l, in the tank's "fuelTank" break group; its beams are
# unbreakable, as in the F4, so behaviour is unchanged).
def references():
    import re
    f = f"{V}/redbull_suspension_F.jbeam"
    for w in ("FL", "FR"):
        je.set_all(f, r'\["shaft", "spindle%s", "(?:wheelaxle%s|dummy)", [01],' % (w, w), '["shaft", "spindle%s", "dummy", 0,' % w)
    for a in ("F", "R"):
        g = f"{V}/redbull_suspension_{a}.jbeam"
        text, n = re.subn(r'("name":"spring_%s[RL]", "beamPrecompression":)(?:"\$=\$rideheight_%s"|1)' % (a, a),
                          lambda m: m.group(1) + "1", je._read(g))
        if n != 2:
            raise ValueError(f"{g}: the two spring rows not found")
        je._write(g, text)
    f = f"{V}/redbull_fueltank.jbeam"
    text = je._read(f)
    text, n = re.subn(r'\["ft1","rt4l"(?:, \{"name":"fuelTank"\})?\]', '["ft1","rt4l", {"name":"fuelTank"}]', text)
    if n != 1:
        raise ValueError("fuel tank beam ft1-rt4l not found")
    je._write(f, text)


# Round 14: the replay showed the rear toe growing with throttle (2.3 ->
# 5.9 deg per side). The drive-torque reaction (DRIVE_REACTION) puts each
# rear wheel's second arm on the engine node across the car; this
# alternative rear wheel-data part ("Gearbox Torque Reaction") keeps both
# arms on the wheel's own side -- the gearbox front-lower node (12 kg with
# its ballast) and the engine's upper front node -- for a test car to
# compare. It is a copy of redbull_wheeldata_R (the rear pressureWheels)
# made after every other edit (remove_alt_parts() takes it out first, so
# re-running is exact).
# Round 18: replayTurns shows the rear axle nodes shifting 2-4 mm on the
# upright as the wheel compresses (toe follows axle height at ~0.17 deg/mm,
# lagging it ~1-1.5 s after a turn). Three graded fixes, all tuning
# variables (Baseline: off / x1): $rear_hub_beam scales the eight axle-node-to-
# upright beams; $rear_brace adds a brace node ahead of and behind the axle
# on each upright (HUB_BRACE_NODES, rigid to rh1 / rh3 / rh4) with beams to
# both axle nodes; $rear_toe_brace adds a torsion bar about the near-vertical
# rw1 -> rh1 axis, which resists toe directly. The block sits between
# HUB_FIX markers so a re-run removes it before stiffness() counts the
# F4's beam rows.
HUB_FIX_BEGIN, HUB_FIX_END = "//hub fix (round 18)", "//hub fix end"
HUB_BRACE_NODES = {"rh6": (-0.632, 2.15, 0.31), "rh7": (-0.632, 1.91, 0.31)}   # right side; x mirrored
# brace nodes (+3 kg unsprung per rear corner; ballast() takes it back)
# and their mounts on the upright: 6 MN/m on 1.5 kg was over the solver
# limit (omega*dt 1.97), 3 MN/m with less damping is under it
HUB_BRACE_WEIGHT = 1.5
# $rear_corner_mass (kg per rear wheel, default 0) comes out of the engine
# ballast (ballast()) and goes to these nodes (share each): the stiffer hub
# variants need it to stay under the solver limit
REAR_CORNER_SHARE = {"rw1": 0.25, "rh1": 0.1, "rh3": 0.1, "rh4": 0.1, "rh6": 0.1, "rh7": 0.1}
HUB_FRAME_SPRING = 3000000
HUB_FRAME_DAMP = 200


def remove_rear_hub_fix():
    import re
    f = f"{V}/redbull_suspension_R.jbeam"
    text = je._read(f)
    text = re.sub(r'[ \t]*%s.*?%s\r?\n' % (re.escape(HUB_FIX_BEGIN), re.escape(HUB_FIX_END)), "", text, flags=re.S)
    text = text.replace('"$=6000000*$rear_link_stiff*$rear_hub_beam"', '"$=6000000*$rear_link_stiff"')
    je._write(f, text)


def rear_hub_fix():
    import re
    f = f"{V}/redbull_suspension_R.jbeam"
    text = je._read(f)
    a, b = _part_block(text, "redbull_suspension_R")
    block = text[a:b]
    # axle-node beams (the "attach to wheel" option row, after stiffness())
    block, n = re.subn(r'(//attach to wheel\r\n\s*\{"optional":true\},\r\n\s*\{"beamSpring":)"\$=6000000\*\$rear_link_stiff"',
                       lambda m: m.group(1) + '"$=6000000*$rear_link_stiff*$rear_hub_beam"', block)
    if n != 1:
        raise ValueError("rear hub fix: axle beam row not found")
    E = "\r\n"
    sides = (("r", "", -1), ("l", "l", 1))
    nodes = [" " * 9 + HUB_FIX_BEGIN + ": upright brace nodes ahead of / behind the axle"]
    for s, _, sign in sides:
        for nd, (x, y, z) in HUB_BRACE_NODES.items():
            nodes.append(' ' * 9 + '["%s%s", %.4f, %.4f, %.4f, {"nodeWeight":"$=%g+%g*$rear_corner_mass", "collision":false, "selfCollision":false}],'
                         % (nd, s, -x * sign if sign > 0 else x, y, z, HUB_BRACE_WEIGHT, REAR_CORNER_SHARE[nd]))
    nodes.append(" " * 9 + HUB_FIX_END)
    k = block.index('//["rh5l"')
    k = block.index("\n", k) + 1
    block = block[:k] + E.join(nodes) + E + block[k:]
    beams = [" " * 10 + HUB_FIX_BEGIN + ": brace nodes rigid on the upright; braces to the axle nodes x $rear_brace",
             " " * 10 + '{"beamDeform":540600,"beamStrength":4800600},',
             " " * 10 + '{"beamSpring":"$=%d*$rear_link_stiff","beamDamp":%d},' % (HUB_FRAME_SPRING, HUB_FRAME_DAMP)]
    for s, _, _ in sides:
        beams.append(" " * 10 + "".join('["%s%s","%s%s"],' % (p, s, q, s) for p, q in (
            ("rh6", "rh1"), ("rh6", "rh3"), ("rh6", "rh4"), ("rh7", "rh1"), ("rh7", "rh3"), ("rh7", "rh4"))))
    beams += [" " * 10 + '{"optional":true},',
              " " * 10 + '{"beamSpring":"$=6000000*$rear_brace","beamDamp":"$=200*$rear_brace"},']
    for s, w, _ in sides:
        beams.append(" " * 10 + '{"breakGroup":"wheel_R%s"},' % s.upper()
                     + "".join('["%s%s","%s"],' % (p, s, q) for p in ("rh6", "rh7") for q in ("rw1" + s, "rw1" + s + s)))
    beams += [" " * 10 + '{"breakGroup":""},', " " * 10 + '{"optional":false},', " " * 10 + HUB_FIX_END]
    k = block.index('//attach to wheel')
    k = block.index('{"optional":false},', k)
    k = block.index("\n", k) + 1
    block = block[:k] + E.join(beams) + E + block[k:]
    tb = [" " * 8 + HUB_FIX_BEGIN + ": toe brace, outer axle node about the upright's rh1 -> rh3 edge x $rear_toe_brace",
          " " * 8 + '{"spring":"$=100000*$rear_toe_brace", "damp":0, "deform":2000000, "strength":4000000},',
          " " * 8 + '["rw1rr", "rh1r", "rh3r", "rh4r"],',
          " " * 8 + '["rw1ll", "rh1l", "rh3l", "rh4l"],',
          " " * 8 + HUB_FIX_END]
    k = block.index('["rw1ll", "rw1l", "rh3l", "rh4l"],')
    k = block.index("\n", k) + 1
    block = block[:k] + E.join(tb) + E + block[k:]
    je._write(f, text[:a] + block + text[b:])


ALT_REACTION = {"R": ("rdiff", "rx1r", "e3r"), "L": ("rdiff", "rx1l", "e3l")}
ALT_PART = "redbull_wheeldata_R_gbx"
ALT_OF = "redbull_wheeldata_R"


def remove_alt_parts():
    import re
    f = f"{V}/redbull_suspension_R.jbeam"
    text = je._read(f)
    text = re.sub(r'"%s"\s*:\s*\{.*?(?=\r?\n"[A-Za-z0-9_]+"\s*:\s*\{|\r?\n\}\s*$)' % ALT_PART, "", text, flags=re.S)
    text = re.sub(r'(\r\n){3,}', "\r\n\r\n", text)
    je._write(f, text)


def alt_parts():
    import re
    f = f"{V}/redbull_suspension_R.jbeam"
    text = je._read(f)
    a, b = _part_block(text, ALT_OF)
    block = text[a:b].rstrip()
    if not block.endswith(","):
        block += ","
    block = block.replace('"%s"' % ALT_OF, '"%s"' % ALT_PART, 1)
    block, n = re.subn(r'("information"\s*:\s*\{[^}]*?"name"\s*:\s*")[^"]*"', lambda m: m.group(1) + 'Rear Wheel Data (Gearbox Torque Reaction)"', block, count=1, flags=re.S)
    if n != 1:
        raise ValueError("alt rear part: information name not found")
    for side in ("R", "L"):
        c, a1, a2 = ALT_REACTION[side]
        block, n = re.subn(r'(\["R%s", "wheel_R%s"[^\]]*?"torqueCoupling:":")[^"]*(", "torqueArm:":")[^"]*(",\s*"torqueArm2:":")[^"]*"' % (side, side),
                           lambda m: m.group(1) + c + m.group(2) + a1 + m.group(3) + a2 + '"', block)
        if n != 1:
            raise ValueError(f"alt rear part: wheel R{side} row not found")
    text = text[:b].rstrip("\r\n") + ("" if text[:b].rstrip().endswith(",") else ",") + "\r\n" + block + "\r\n" + text[b:].lstrip("\r\n")
    je._write(f, text)
    import jbeam
    jbeam.load(f)     # still valid


if __name__ == "__main__":
    os.chdir(REPO)
    remove_alt_parts()
    remove_rear_hub_fix()
    round16_vars()
    migrations()
    stiffness()
    torque_paths()
    rear_hub_fix()
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
    alt_parts()
    configs()
    check_stability()
    print("applied: mass, wheels, tyres, fuel, suspension, power unit, gearbox, brakes, ERS/DRS")
