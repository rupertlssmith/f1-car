#!/usr/bin/env python3
"""Analyse a BeamNG replay (.rpl) of the redbull mod.

    python3 tools/rb14/replay_analysis.py "f1 stearing.rpl" [--csv out.csv]

Needs numpy and msgpack (pip install msgpack).

The .rpl format (as found in BeamNG 0.3x, reverse-engineered here, not
documented by BeamNG): an Ogg container with one logical stream (serial
1337) whose granule position is the time in microseconds. Each Ogg packet
is a sequence of MessagePack values: a header (format version 12, packet
type, frame counter), then the frame. Packet 1 also carries the scene
(level path, vehicle model and config, a 116 kB state blob); every packet
ends with a map of JSON strings -- "electrics", "sensors" (roll, pitch, yaw,
g-forces gx / gy / gz, position), "engineInfo", "powertrainDeviceData"
(per-device output torque / angular velocity) and "wheelThermalData".
Frames come every ~31 ms.

The report covers:
  performance   speed, acceleration (from the speed trace and the g sensor),
                drive power at the rear wheels, the resistance it implies
                (drive force - mass x acceleration), peak g
  steering      steering input against the front and rear wheel angles
                measured by the redbull steering check (lua/controller/
                redbullSteerCheck.lua, key J -- recorded whether or not the
                readout is shown): rear toe and net rear steer, and the yaw
                rate the car has with the steering centred after each hard
                turn (the "doesn't re-centre" check)
"""
import argparse
import csv
import json
import math
import struct
import sys

import numpy as np

try:
    import msgpack
except ImportError:
    sys.exit("replay_analysis: the 'msgpack' package is required (pip install msgpack)")

MASS = 777.0          # kg, the car with 60 L of fuel (setup_report)


def packets(path):
    """[(granule position, packet bytes)] from an Ogg file."""
    d = open(path, "rb").read()
    pos, cur, out = 0, b"", []
    while pos < len(d):
        if d[pos:pos + 4] != b"OggS":
            raise ValueError(f"{path}: not an Ogg page at byte {pos}")
        _, _, gpos, _, _, _, nseg = struct.unpack_from("<BBqIIIB", d, pos + 4)
        segs = d[pos + 27:pos + 27 + nseg]
        p = pos + 27 + nseg
        for s in segs:
            cur += d[p:p + s]
            p += s
            if s < 255:
                out.append((gpos, cur))
                cur = b""
        pos = p
    return out


def frames(path):
    """One dict per frame: time (s), the electrics, sensors and powertrain."""
    out = []
    for gpos, p in packets(path):
        u = msgpack.Unpacker(raw=False, strict_map_key=False)
        u.feed(p)
        objs = list(u)
        if not objs or not isinstance(objs[-1], dict) or "electrics" not in objs[-1]:
            continue
        last = objs[-1]
        try:
            out.append(dict(t=gpos / 1e6, e=json.loads(last["electrics"]), s=json.loads(last["sensors"]),
                            pt=json.loads(last.get("powertrainDeviceData") or "{}").get("devices", {})))
        except (ValueError, TypeError):
            continue
    return out


def slope(y, t, half=0.15):
    """dy/dt over a +-half second window. Some frames share (almost) a
    timestamp, so frame-to-frame derivatives blow up -- a 0.3 s window keeps
    them honest (round 15: the per-frame yaw rate read ~20x too high)."""
    out = np.full(len(t), math.nan)
    lo = np.searchsorted(t, t - half)
    hi = np.searchsorted(t, t + half, side="right") - 1
    ok = (t[hi] - t[lo]) > half
    out[ok] = (y[hi[ok]] - y[lo[ok]]) / (t[hi[ok]] - t[lo[ok]])
    return out


def series(F):
    num = lambda x: float(x) if isinstance(x, (int, float)) else math.nan
    e = lambda k: np.array([num(f["e"].get(k)) for f in F])
    s = lambda k: np.array([num(f["s"].get(k)) for f in F])

    def wheel_power():
        out = []
        for f in F:
            p = 0.0
            for w in ("spindleRL", "spindleRR"):
                dv = f["pt"].get(w, {})
                p += (dv.get("outputTorque") or [0])[0] * (dv.get("outputAV") or [0])[0]
            out.append(p)
        return np.array(out)
    def dev(name, key):
        return np.array([num((f["pt"].get(name, {}).get(key) or [math.nan])[0]) for f in F])
    t = np.array([f["t"] for f in F])
    px = np.array([num(f["s"].get("position", {}).get("x")) for f in F])
    py = np.array([num(f["s"].get("position", {}).get("y")) for f in F])
    d = dict(t=t, kmh=e("airspeed") * 3.6, ms=e("airspeed"), wheelspeed=e("wheelspeed"),
             throttle=e("throttle"), throttle_in=e("throttle_input"), brake=e("brake"), gear=e("gear"),
             rpm=e("rpm"), ers=e("ersDeploy"), tc=e("tcActive"),
             steer_in=e("steering_input"), FL=e("steerAngleFL"), FR=e("steerAngleFR"),
             RL=e("steerAngleRL"), RR=e("steerAngleRR"), roll_chassis=e("chassisRoll"),
             wingL=e("wingTipL"), wingR=e("wingTipR"), rear_speed_diff=e("rearSpeedDiff"),
             gx=s("gx"), gy=s("gy"), wheel_kw=wheel_power() / 1000,
             yaw_rate=np.degrees(slope(np.unwrap(s("yaw")), t)),
             roll_abs=np.degrees(s("roll")), pitch_abs=np.degrees(s("pitch")), drs=e("drs"),
             torque_RL=dev("spindleRL", "outputTorque"), torque_RR=dev("spindleRR", "outputTorque"))
    # ground speed from the recorded positions (cross-check of airspeed / wheelspeed)
    pz = np.array([num(f["s"].get("position", {}).get("z")) for f in F])
    step = np.sqrt(np.diff(px) ** 2 + np.diff(py) ** 2 + np.diff(pz) ** 2) / np.diff(t)
    d["pos_kmh"] = np.concatenate([[step[0]], step]) * 3.6
    d["px"], d["py"], d["pz"] = px, py, pz
    d["front_net"] = (d["FL"] + d["FR"]) / 2          # + = steered left
    d["rear_net"] = (d["RL"] + d["RR"]) / 2           # + = rear wheels steered left
    d["rear_toe"] = (d["RR"] - d["RL"]) / 2           # + = toe-in, per side
    # acceleration from the speed trace (smoothed over ~0.3 s)
    d["accel_g"] = slope(d["ms"], t) / 9.81
    return d


def report(d):
    t = d["t"]
    print("REPLAY  %.1f s, %d frames, every %.0f ms" % (t[-1] - t[0], len(t), 1000 * np.median(np.diff(t))))
    print("\nPERFORMANCE")
    # top speed averaged over 0.5 s: single frames spike (some frames share a
    # timestamp), so per-frame position speeds are noisy too
    k = np.nanargmax(d["kmh"])
    w = (t > t[k] - 0.25) & (t < t[k] + 0.25)
    i, j = np.where(w)[0][[0, -1]]
    path = np.nansum(np.sqrt(np.diff(d["px"][i:j + 1]) ** 2 + np.diff(d["py"][i:j + 1]) ** 2 + np.diff(d["pz"][i:j + 1]) ** 2))
    print("  top speed %.0f km/h (airspeed, 0.5 s mean; %.0f from distance covered, wheel speed %.0f) at %.1f s, "
          "gear %.0f, %.0f rpm, DRS %s; peak lateral %.2f g, braking %.2f g (g sensor)"
          % (np.nanmean(d["kmh"][w]), path / (t[j] - t[i]) * 3.6, np.nanmean(d["wheelspeed"][w]) * 3.6, t[k],
             d["gear"][k], d["rpm"][k], "open" if d["drs"][k] > 0.5 else "shut",
             np.nanmax(np.abs(d["gx"])) / 9.81, np.nanmax(d["gy"]) / 9.81))
    full = d["throttle_in"] > 0.95
    for lo, hi in ((80, 120), (120, 160), (160, 200), (200, 240), (240, 280), (280, 320), (320, 360)):
        m = full & (d["kmh"] > lo) & (d["kmh"] < hi)
        if m.sum() < 5:
            continue
        v = np.nanmean(d["ms"][m])
        a = np.nanmean(d["accel_g"][m])
        kw = np.nanmean(d["wheel_kw"][m])
        resist = kw * 1000 / v - MASS * a * 9.81
        print("  full throttle %3d-%3d km/h: accel %.2f g (speed trace) / %.2f g (sensor), rear-wheel power %3.0f kW, "
              "%4.0f rpm, TC trimming %2.0f%%, slip %+.1f%% -> resistance %.1f kN (CdA-equivalent %.2f m2)"
              % (lo, hi, a, -np.nanmean(d["gy"][m]) / 9.81, kw, np.nanmean(d["rpm"][m]),
                 100 * np.nanmean(d["tc"][m] > 0), 100 * np.nanmean(d["wheelspeed"][m] / d["ms"][m] - 1),
                 resist / 1000, resist / (0.5 * 1.225 * v * v)))
    print("\nSTEERING / REAR AXLE (angles in deg, + = left; toe + = toe-in per side)")
    still = d["kmh"] < 2
    if still.any():
        print("  at rest: front L %+.2f R %+.2f, rear L %+.2f R %+.2f -> rear toe %.2f, rear net %+.2f"
              % tuple(np.nanmean(d[k][still]) for k in ("FL", "FR", "RL", "RR", "rear_toe", "rear_net")))
    straight = (d["kmh"] > 100) & (np.abs(d["steer_in"]) < 0.02)
    if straight.any():
        print("  straights: rear toe %.2f..%.2f (corr. with throttle %.2f), rear net %+.2f..%+.2f, front net %+.2f..%+.2f"
              % (np.nanmin(d["rear_toe"][straight]), np.nanmax(d["rear_toe"][straight]),
                 np.corrcoef(d["rear_toe"][straight], d["throttle"][straight])[0, 1],
                 np.nanmin(d["rear_net"][straight]), np.nanmax(d["rear_net"][straight]),
                 np.nanmin(d["front_net"][straight]), np.nanmax(d["front_net"][straight])))
    # hard turns: |input| > 0.5; then the next 4 s with the steering centred
    hard = np.abs(d["steer_in"]) > 0.5
    ends = [i for i in range(1, len(t)) if hard[i - 1] and not hard[i]]
    first = t[np.argmax(hard)] if hard.any() else t[-1]
    pre = (t < first) & (d["kmh"] > 60) & (np.abs(d["steer_in"]) < 0.05)
    if pre.sum() > 10:
        print("  before any hard turn (steering centred, %d frames): yaw rate %+.1f deg/s, rear net %+.2f, "
              "rear wheel-speed L-R %+.2f%%" % (pre.sum(), np.nanmean(d["yaw_rate"][pre]), np.nanmean(d["rear_net"][pre]),
                                                np.nanmean(d["rear_speed_diff"][pre])))
    for i in ends:
        side = "left" if d["front_net"][i - 1] > 0 else "right"
        w = (t > t[i] + 0.3) & (t < t[i] + 4.0) & (np.abs(d["steer_in"]) < 0.05)
        if w.sum() < 10:
            continue
        print("  after the hard %s turn ending at %.1f s (steering centred, %d frames): front net %+.2f, "
              "rear net %+.2f (max %+.2f), yaw rate %+.1f deg/s, rear wheel-speed L-R %+.2f%%; "
              "rear net back under 0.3 deg after %.1f s"
              % (side, t[i], w.sum(), np.nanmean(d["front_net"][w]), np.nanmean(d["rear_net"][w]),
                 d["rear_net"][w][np.nanargmax(np.abs(d["rear_net"][w]))], np.nanmean(d["yaw_rate"][w]),
                 np.nanmean(d["rear_speed_diff"][w]),
                 next((t[j] - t[i] for j in np.where(t > t[i] + 0.3)[0] if abs(d["rear_net"][j]) < 0.3), math.nan)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("replay")
    ap.add_argument("--csv", help="write the per-frame series to this CSV")
    args = ap.parse_args()
    d = series(frames(args.replay))
    report(d)
    if args.csv:
        keys = list(d)
        with open(args.csv, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(keys)
            for i in range(len(d["t"])):
                w.writerow(["%.5g" % d[k][i] for k in keys])
        print(f"\nper-frame series written to {args.csv}")


if __name__ == "__main__":
    main()
