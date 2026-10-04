#!/usr/bin/env python3
"""Front-wheel wobble and balance from a BeamNG replay (redbull mod).

    python3 tools/rb14/handling_analysis.py <replay>.rpl

Resamples the replay to an even 25 Hz (frames come every ~34 ms, some in
bursts) and reports:

  WOBBLE   band-passed front-wheel angles (sn_FL_toe / sn_FR_toe, from the
           axle nodes): episodes, their frequency, and what moves with them
           (driver input, rack, each track rod, wheel loads), split into the
           driver band (0.5-2 Hz) and the shimmy band (5-9 Hz); how the
           shimmy scales with lateral / longitudinal g and steering angle.
  BALANCE  yaw rate against the geometric yaw rate (speed x steer /
           wheelbase), and front / rear slip angles from the recorded path
           (body slip = course - heading).
  BOUNCE   4-6.5 Hz wheel-load fluctuation by speed.
  WHEELS   lock-ups and wheelspin from the spindle speeds.

Note: at ~29 frames/s anything faster than ~14 Hz would alias into the
bands above.
"""
import argparse
import os
import sys

import numpy as np
from scipy.signal import butter, coherence, sosfiltfilt, welch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import replay_analysis as ra  # noqa: E402

FS = 25.0
WHEELBASE, CG_TO_FRONT = 3.555, 1.92        # m (setup_report, Baseline)
KEYS = ("sn_FL_toe", "sn_FR_toe", "sn_rack", "sn_FL_tierod", "sn_FR_tierod", "steering_input",
        "sn_load_FL", "sn_load_FR", "sn_load_RL", "sn_load_RR", "airspeed", "throttle", "brake")


def load(path):
    fr = list(ra.frames(path))
    t = np.array([f["t"] for f in fr])
    T = np.arange(t[0], t[-1], 1 / FS)

    def num(v):
        return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else np.nan

    def rs(v):
        ok = ~np.isnan(v)
        return np.interp(T, t[ok], v[ok]) if ok.any() else np.full(len(T), np.nan)
    D = {k: rs(np.array([num(f["e"].get(k)) for f in fr])) for k in KEYS}
    for k in ("gx", "gy"):                      # gx lateral, gy longitudinal (+ = braking)
        D[k] = rs(np.array([num(f["s"].get(k)) for f in fr]))
    D["yaw"] = rs(np.degrees(np.unwrap([num(f["s"].get("yaw")) for f in fr])))
    for a in "xy":
        D["p" + a] = rs(np.array([num(f["s"].get("position", {}).get(a)) for f in fr]))
    av = {k: np.array([num((f["pt"].get("spindle" + k, {}).get("outputAV") or [np.nan])[0]) for f in fr])
          for k in ("FL", "FR", "RL", "RR")}
    raw = dict(t=t, av=av, v=np.array([num(f["e"].get("airspeed")) for f in fr]),
               brake=np.array([num(f["e"].get("brake")) or 0 for f in fr]),
               throttle=np.array([num(f["e"].get("throttle")) or 0 for f in fr]))
    return T, D, raw


def bp(v, lo, hi):
    return sosfiltfilt(butter(4, [lo, hi], btype="band", fs=FS, output="sos"), v)


def lp(v, hi):
    return sosfiltfilt(butter(3, hi, btype="low", fs=FS, output="sos"), v)


def env(v, w=0.6):
    n = int(w * FS)
    return np.sqrt(np.convolve(v ** 2, np.ones(n) / n, mode="same"))


def wobble(T, D):
    print("WOBBLE (front-wheel angle, deg; + = left)")
    spd = D["airspeed"] * 3.6
    sig = {"FL wheel": D["sn_FL_toe"], "FR wheel": D["sn_FR_toe"], "rack": D["sn_rack"],
           "driver input": D["steering_input"], "FL track rod": D["sn_FL_tierod"],
           "FR track rod": D["sn_FR_tierod"], "front load": (D["sn_load_FL"] + D["sn_load_FR"]) / 1000,
           "rear load": (D["sn_load_RL"] + D["sn_load_RR"]) / 1000}
    print("  spectrum peaks 1-12 Hz:", ", ".join(
        "%s %.1f Hz" % (k, (lambda f, P: f[(f >= 1) & (f <= 12)][np.argmax(P[(f >= 1) & (f <= 12)])])(
            *welch(v - np.mean(v), fs=FS, nperseg=256))) for k, v in sig.items()))
    print("  coherence with the wheel's angle, 6-8 Hz (shimmy) and 0.7-1.5 Hz (driver band):")
    for w in ("FL wheel", "FR wheel"):
        row = []
        for k in ("driver input", "rack", "FL track rod", "FR track rod", "front load"):
            f, C = coherence(sig[w], sig[k], fs=FS, nperseg=128)
            row.append("%s %.2f / %.2f" % (k, C[(f >= 6) & (f <= 8)].mean(), C[(f >= 0.7) & (f <= 1.5)].mean()))
        print("    %s ~ %s" % (w, "; ".join(row)))
    w7 = np.maximum(env(bp(D["sn_FL_toe"], 5, 9)), env(bp(D["sn_FR_toe"], 5, 9)))
    lat, lon = np.abs(lp(D["gx"], 2)) / 9.81, -lp(D["gy"], 2) / 9.81
    steer = np.abs(lp((D["sn_FL_toe"] + D["sn_FR_toe"]) / 2, 2))

    def tab(name, x, edges):
        out = []
        for a, b in zip(edges[:-1], edges[1:]):
            m = (x >= a) & (x < b)
            if m.sum() > 20:
                out.append("%g-%g: %.2f" % (a, b, np.mean(w7[m])))
        print("  shimmy 5-9 Hz RMS by %s: %s" % (name, "  ".join(out)))
    tab("|lateral g|", lat, [0, 0.5, 1.5, 2.5, 3.5, 6])
    tab("long. g (+ accel)", lon, [-6, -2, -0.5, 0.3, 1, 3])
    tab("|steer| deg", steer, [0, 1, 3, 6, 10, 25])
    tab("speed km/h", spd, [0, 100, 150, 200, 250, 340])
    print("  worst moments:")
    sm = np.convolve(w7, np.ones(25) / 25, mode="same")
    taken = []
    for i in np.argsort(-sm):
        if all(abs(i - j) > 60 for j in taken):
            taken.append(i)
            print("    t %6.1f s  %4.0f km/h  lat %+.1f g  long %+.1f g  steer %+5.1f deg  throttle %.2f brake %.2f"
                  "  shimmy %.1f deg RMS" % (T[i], spd[i], lp(D["gx"], 2)[i] / 9.81, lon[i],
                                             (D["sn_FL_toe"][i] + D["sn_FR_toe"][i]) / 2, D["throttle"][i],
                                             D["brake"][i], w7[i]))
        if len(taken) >= 6:
            break


def balance(T, D):
    print("BALANCE")
    vx, vy = np.gradient(lp(D["px"], 3), 1 / FS), np.gradient(lp(D["py"], 3), 1 / FS)
    v = np.hypot(vx, vy)
    spd = v * 3.6
    course = np.degrees(np.unwrap(np.arctan2(vy, vx)))
    yawd = lp(D["yaw"], 3)
    st = lp((D["sn_FL_toe"] + D["sn_FR_toe"]) / 2, 3)
    straight = (np.abs(st) < 0.7) & (spd > 200)
    beta = ((course - yawd) + 180) % 360 - 180
    beta -= np.median(beta[straight]) if straight.any() else 0
    r = np.radians(np.gradient(yawd, 1 / FS))
    aF, aR = beta + np.degrees(CG_TO_FRONT * r / np.maximum(v, 1)) - st, \
        beta - np.degrees((WHEELBASE - CG_TO_FRONT) * r / np.maximum(v, 1))
    lat = np.abs(lp(D["gx"], 2)) / 9.81
    m = (np.abs(st) > 2) & (spd > 60)
    ratio = r[m] / (v[m] * np.radians(st[m]) / WHEELBASE)
    for lo, hi in ((60, 130), (130, 200), (200, 340)):
        mm = (spd[m] >= lo) & (spd[m] < hi)
        if mm.sum() > 10:
            print("  %d-%d km/h: yaw rate / geometric %.2f (1 = neutral, < 1 understeer)" % (lo, hi, np.median(np.abs(ratio[mm]))))
    for lo, hi in ((1, 2), (2, 3), (3, 4), (4, 6)):
        mm = (lat >= lo) & (lat < hi) & (spd > 80)
        if mm.sum() > 10:
            print("  %d-%d g: slip angle front %.1f / rear %.1f deg, steer %.1f deg, body slip %.1f deg (%.0f s, ~%.0f km/h)"
                  % (lo, hi, np.median(np.abs(aF[mm])), np.median(np.abs(aR[mm])), np.median(np.abs(st[mm])),
                     np.median(np.abs(beta[mm])), mm.sum() / FS, np.median(spd[mm])))


def bounce(T, D):
    print("BOUNCE (4-6.5 Hz wheel-load RMS, kN)")
    spd = D["airspeed"] * 3.6
    fb = env(bp((D["sn_load_FL"] + D["sn_load_FR"]) / 1000, 4, 6.5))
    rb = env(bp((D["sn_load_RL"] + D["sn_load_RR"]) / 1000, 4, 6.5))
    for lo, hi in ((0, 150), (150, 220), (220, 270), (270, 340)):
        m = (spd >= lo) & (spd < hi)
        if m.any():
            print("  %d-%d km/h: front %.2f, rear %.2f (mean loads F %.1f, R %.1f)"
                  % (lo, hi, fb[m].mean(), rb[m].mean(), np.mean((D["sn_load_FL"] + D["sn_load_FR"])[m]) / 1000,
                     np.mean((D["sn_load_RL"] + D["sn_load_RR"])[m]) / 1000))


def wheels(raw):
    print("WHEELS (spindle speed vs airspeed, 0.335 m radius)")
    dt = np.median(np.diff(raw["t"]))
    for k, av in raw["av"].items():
        slip = (np.abs(av) * 0.335 - raw["v"]) / np.maximum(raw["v"], 1)
        lock = (raw["brake"] > 0.3) & (raw["v"] > 15) & (slip < -0.15)
        spin = (raw["throttle"] > 0.5) & (raw["v"] > 5) & (slip > 0.15)
        print("  %s: locked (>15%% under braking) %.1f s, wheelspin >15%% %.1f s" % (k, lock.sum() * dt, spin.sum() * dt))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("replay")
    a = ap.parse_args()
    T, D, raw = load(a.replay)
    print("REPLAY %.1f s, resampled to %.0f Hz" % (T[-1] - T[0], FS))
    wobble(T, D)
    balance(T, D)
    bounce(T, D)
    wheels(raw)


if __name__ == "__main__":
    main()
