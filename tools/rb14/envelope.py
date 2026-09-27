"""Body envelope of the RB14: which points are hidden inside its bodywork.

Samples the body shell's surfaces (every ~1 cm) into two height maps on a
2 cm grid - the highest surface over each (x, y) and the widest surface at
each (y, z) - and calls a point "outside" if it is above the first or wider
than the second. Used to decide which carried-over F4 internals would show
through the RB14 bodywork.
"""
import numpy as np

RES = 0.02
SHELL = {"redbull_paint", "redbull_carbon1", "redbull_detail", "decals", "generics", "halo",
         "redbull_carbon3", "generics_cockpit"}


def _sample(tris, spacing=0.01):
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    n = np.maximum(1, (area / spacing ** 2).astype(int))
    idx = np.repeat(np.arange(len(tris)), n)
    r1, r2 = np.random.default_rng(0).random((2, len(idx)))
    s = np.sqrt(r1)
    return (1 - s)[:, None] * a[idx] + (s * (1 - r2))[:, None] * b[idx] + (s * r2)[:, None] * c[idx]


class Envelope:
    def __init__(self, prims, x_shift=0.0, wheel_centres=((-1.5247, 0.336), (2.03, 0.336))):
        tris = np.concatenate([p["pos"][p["tri"]] for p in prims if p["material"] in SHELL])
        tris = tris + np.array([x_shift, 0, 0])
        P = _sample(tris)
        for cy, cz in wheel_centres:   # uprights/brake ducts inside the wheels
            P = P[~((np.hypot(P[:, 1] - cy, P[:, 2] - cz) < 0.36) & (np.abs(P[:, 0]) > 0.5))]
        self.top = self._grid(P[:, 0], P[:, 1], P[:, 2])
        self.side = self._grid(P[:, 1], P[:, 2], np.abs(P[:, 0]))

    @staticmethod
    def _grid(a, b, v):
        ka = np.floor(a / RES).astype(np.int64)
        kb = np.floor(b / RES).astype(np.int64)
        key = ka * 100003 + kb
        order = np.argsort(key)
        key, v = key[order], v[order]
        uniq, start = np.unique(key, return_index=True)
        return dict(zip(uniq.tolist(), np.maximum.reduceat(v, start).tolist()))

    def _lookup(self, grid, a, b):
        ka, kb = np.floor(a / RES).astype(np.int64), np.floor(b / RES).astype(np.int64)
        best = np.full(len(a), -1.0)
        for da in (-1, 0, 1):
            for db in (-1, 0, 1):
                k = (ka + da) * 100003 + (kb + db)
                best = np.maximum(best, np.array([grid.get(int(x), -1.0) for x in k]))
        return best

    def outside(self, V, margin=0.005):
        V = np.asarray(V)
        t = self._lookup(self.top, V[:, 0], V[:, 1])
        s = self._lookup(self.side, V[:, 1], V[:, 2])
        return (V[:, 2] > t + margin) | (np.abs(V[:, 0]) > s + margin)
