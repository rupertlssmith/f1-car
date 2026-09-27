"""Coordinate map from the Carbonworks F4 (the jbeam we start from) onto the
Red Bull RB14 model. Both use BeamNG axes: x left(+)/right(-), y nose(-) to
tail(+), z up; metres.

The F4 is 4.4 m long with a 2.73 m wheelbase; the RB14 is 5.4 m with 3.555 m,
and its proportions differ (longer nose and engine bay, shorter cockpit), so a
single scale factor does not fit. Instead the map is piecewise-linear:

  y' = Y(y)            through matching stations along the car
  x' = sign(x) X_y(|x|) through matching width breakpoints; the breakpoints
                       themselves are interpolated between x-stations along y
  z' = Z_y(z)          likewise for heights (this carries the RB14's rake)

Every piece is monotonic, so the map never folds space: a beam cannot turn
inside out, only stretch. All RB14 figures were measured from rb14.glb
(see plans/rb14-model-swap.md); F4 figures from its jbeam and F4.dae.
"""
import numpy as np

# --- along the car: F4 y -> RB14 y --------------------------------------
Y_STATIONS = [
    (-2.20, -2.72),     # front wing leading edge / nose tip
    (-1.79, -1.963),    # front wing trailing edge
    (-1.1709, -1.5247), # front axle
    (-0.456, -0.40),    # steering wheel
    (0.47, 0.42),       # roll hoop / airbox
    (1.5625, 2.03),     # rear axle
    (2.35, 2.70),       # tail (crash structure, rear wing)
]

# --- across the car: at F4 y, |x| breakpoints F4 -> RB14 ----------------
# Every station has the same number of breakpoints so they interpolate.
_WING = [(0.10, 0.18), (0.40, 0.50), (0.703, 0.91), (1.00, 1.20)]
_FRONT_AXLE = [(0.20, 0.21), (0.62, 0.637), (0.73, 0.7925), (0.84, 0.948)]
_MIDCAR = [(0.30, 0.33), (0.55, 0.62), (0.701, 0.807), (1.00, 1.15)]
_REAR_AXLE = [(0.18, 0.21), (0.579, 0.586), (0.715, 0.789), (0.85, 0.992)]
_TAIL = [(0.10, 0.10), (0.30, 0.36), (0.454, 0.53), (0.70, 0.85)]
X_STATIONS = [
    (-2.20, _WING),
    (-1.79, _WING),
    (-1.45, _FRONT_AXLE),   # the front suspension lives in -1.45..-0.78
    (-0.78, _FRONT_AXLE),
    (-0.40, _MIDCAR),       # cockpit, sidepods, floor
    (1.20, _MIDCAR),
    (1.30, _REAR_AXLE),     # rear suspension and gearbox
    (1.90, _REAR_AXLE),
    (2.35, _TAIL),
]

# --- heights: at F4 y, z breakpoints F4 -> RB14 --------------------------
# floor (plank) -> RB14 raked floor; hub height; cockpit rim / chassis top;
# halo top (only differs from a straight rim-to-hoop blend in the cockpit);
# roll hoop.
def _z(floor, hub, rim, hoop, halo=None):
    if halo is None:  # no halo here: keep rim..hoop straight
        halo = rim + (0.85 - 0.58) / (0.97 - 0.58) * (hoop - rim)
    return [(0.02, floor), (0.2755, hub), (0.58, rim), (0.85, halo), (0.97, hoop), (1.50, hoop + 0.55)]

Z_STATIONS = [
    (-2.20, _z(0.02, 0.26, 0.60, 1.00)),   # front wing and the low 2018 nose tip
    (-1.79, _z(0.03, 0.29, 0.64, 1.05)),
    (-1.1709, _z(0.05, 0.336, 0.68, 1.15)),
    (-0.63, _z(0.064, 0.336, 0.71, 1.18, halo=0.905)),  # front of the floor, cockpit
    (0.10, _z(0.085, 0.336, 0.71, 1.18, halo=0.905)),
    (0.47, _z(0.095, 0.336, 0.71, 1.18)),
    (1.5625, _z(0.14, 0.336, 0.66, 1.03)),  # rear of the plank (rake: +8 cm)
    (2.35, _z(0.14, 0.336, 0.66, 1.02)),
]


def _interp_stations(stations, y):
    """Breakpoint list at y, linearly blended between stations."""
    ys = [s[0] for s in stations]
    if y <= ys[0]:
        return stations[0][1]
    if y >= ys[-1]:
        return stations[-1][1]
    i = np.searchsorted(ys, y) - 1
    t = (y - ys[i]) / (ys[i + 1] - ys[i])
    a, b = stations[i][1], stations[i + 1][1]
    return [((1 - t) * p[0] + t * q[0], (1 - t) * p[1] + t * q[1]) for p, q in zip(a, b)]


def _piecewise(v, pts, origin=(0.0, 0.0)):
    """Monotonic piecewise-linear map through origin + pts, extrapolating
    with the end slopes."""
    xs = [origin[0]] + [p[0] for p in pts]
    ys = [origin[1]] + [p[1] for p in pts]
    if v <= xs[0]:
        return ys[0] + (v - xs[0]) * (ys[1] - ys[0]) / (xs[1] - xs[0])
    if v >= xs[-1]:
        return ys[-1] + (v - xs[-1]) * (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
    return float(np.interp(v, xs, ys))


def map_y(y):
    return _piecewise(y, Y_STATIONS[1:], origin=Y_STATIONS[0])


def map_x(x, y):
    s = 1.0 if x >= 0 else -1.0
    return s * _piecewise(abs(x), _interp_stations(X_STATIONS, y))


def map_z(z, y):
    return _piecewise(z, _interp_stations(Z_STATIONS, y))


def map_point(p):
    """F4 point -> RB14 point. x and z breakpoints are looked up at the
    point's F4 y."""
    x, y, z = p
    return (map_x(x, y), map_y(y), map_z(z, y))


def map_points(P):
    return np.array([map_point(p) for p in np.asarray(P, dtype=float)])


def local_slope(axis, p, h=1e-4):
    """d(mapped coordinate)/d(coordinate) along one axis at p; used to
    rescale jbeam expressions like "$=($wing_angle_F*0.003)+0.14"."""
    p = np.asarray(p, dtype=float)
    d = np.zeros(3)
    d[axis] = h
    a = map_point(p - d)[axis]
    b = map_point(p + d)[axis]
    return (b - a) / (2 * h)
