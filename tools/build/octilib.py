"""Shared 0/45/90-degree geometry helpers (octi.py for top traces, tidy.py for bottom bridges)."""
import math
import numpy as np
from shapely.geometry import LineString, Point

MIN_SEG = 0.15
DIRS = [np.array([math.cos(math.radians(a)), math.sin(math.radians(a))]) for a in range(0, 360, 45)]


def cross2(u, w):
    return u[0] * w[1] - u[1] * w[0]


def nearest_dir(v):
    return int(np.argmax([v @ d for d in DIRS]))


def intersect(p, d1, q, d2):
    A = np.array([[d1[0], -d2[0]], [d1[1], -d2[1]]])
    if abs(np.linalg.det(A)) < 1e-9:
        return None
    s = np.linalg.solve(A, q - p)
    return p + s[0] * d1


def fit(pts, tol, padA, padB):
    line = LineString(pts)
    S = [np.array(p) for p in line.simplify(tol, preserve_topology=False).coords]
    if len(S) < 2:
        return None
    A, B = S[0], S[-1]
    runs = []  # [dir index, start vertex, end vertex]
    for a, b in zip(S[:-1], S[1:]):
        if np.hypot(*(b - a)) < 1e-6:
            continue
        k = nearest_dir(b - a)
        if runs and runs[-1][0] == k:
            runs[-1][2] = b
        else:
            runs.append([k, a, b])
    for _ in range(30):
        if not runs:
            return None
        n = len(runs)
        anchors = []
        for i, (k, a, b) in enumerate(runs):
            if i == 0 and padA is None:
                anchors.append(A)
            elif i == n - 1 and padB is None:
                anchors.append(B)
            else:
                anchors.append((a + b) / 2)
        if n == 1 and padA is None and padB is None:
            return None                       # one off-angle segment between two fixed points: fallback
        if n == 1:
            anc = anchors[0]
            d = DIRS[runs[0][0]]
            pa = A if padA is None else anc + ((A - anc) @ d) * d
            pb = B if padB is None else anc + ((B - anc) @ d) * d
            # a fixed end must lie on the line
            if padA is None and np.hypot(*((A - anc) - ((A - anc) @ d) * d)) > 1e-6:
                return None
            out = [pa, pb]
        else:
            out = []
            first_d = DIRS[runs[0][0]]
            if padA is None:
                out.append(A)
            else:
                out.append(anchors[0] + ((A - anchors[0]) @ first_d) * first_d)
            bad = None
            for i in range(n - 1):
                x = intersect(anchors[i], DIRS[runs[i][0]], anchors[i + 1], DIRS[runs[i + 1][0]])
                if x is None:
                    bad = i; break
                out.append(x)
            if bad is not None:
                # consecutive parallel runs (opposite): give up on this tolerance
                return None
            last_d = DIRS[runs[-1][0]]
            if padB is None:
                out.append(B)
            else:
                out.append(anchors[-1] + ((B - anchors[-1]) @ last_d) * last_d)
        # check every segment keeps its direction and a sensible length
        drop = None
        for i, (p, q) in enumerate(zip(out[:-1], out[1:])):
            v = q - p
            L = v @ DIRS[runs[i][0]]
            if L < MIN_SEG and not (n == 1):
                drop = i; break
            if L <= 1e-6:
                return None
        if drop is None:
            if padA is not None and not padA.contains(Point(out[0])):
                return None
            if padB is not None and not padB.contains(Point(out[-1])):
                return None
            return [o for o in out]
        # remove the collapsed run, merge neighbours with the same direction
        del runs[drop]
        m = []
        for r in runs:
            if m and m[-1][0] == r[0]:
                m[-1][2] = r[2]
            else:
                m.append(r)
        runs = m
    return None


def decompose(pts, tol):
    """Fallback: vertices kept, every segment -> straight + 45 (order that stays closer)."""
    S = [np.array(p) for p in LineString(pts).simplify(tol, preserve_topology=False).coords]
    out = [S[0]]
    for a, b in zip(S[:-1], S[1:]):
        v = b - a
        k = nearest_dir(v)
        if abs(cross2(DIRS[k], v)) < 1e-6:
            out.append(b); continue
        # the two directions bracketing v
        ang = math.degrees(math.atan2(v[1], v[0])) % 360
        k1 = int(ang // 45) % 8; k2 = (k1 + 1) % 8
        M = np.array([DIRS[k1], DIRS[k2]]).T
        al, be = np.linalg.solve(M, v)
        u1, u2 = al * DIRS[k1], be * DIRS[k2]
        main, diag = (u1, u2) if al >= be else (u2, u1)
        opts = [[a + u1, b], [a + u2, b],                         # one bend, either order
                [a + main / 2, a + main / 2 + diag, b]]          # one 45-degree jog in the middle
        seg = LineString([a, b])
        best = min(opts, key=lambda o: LineString([a] + o).hausdorff_distance(seg))
        out += best
    return out


def clean(out):
    out = [np.array(p) for p in out]
    res = [out[0]]
    for p in out[1:]:
        if np.hypot(*(p - res[-1])) > 1e-6:
            res.append(p)
    # merge collinear
    i = 1
    while i < len(res) - 1:
        u = res[i] - res[i - 1]; w = res[i + 1] - res[i]
        if abs(cross2(u, w)) < 1e-6 * np.hypot(*u) * np.hypot(*w) and u @ w > 0:
            del res[i]
        else:
            i += 1
    return [p.tolist() for p in res]


def is_octi(pts):
    for a, b in zip(pts[:-1], pts[1:]):
        v = np.array(b) - np.array(a)
        L = np.hypot(*v)
        if L < 1e-6:
            continue
        ang = math.degrees(math.atan2(v[1], v[0])) % 45
        if min(ang, 45 - ang) > 0.01:
            return False
    return True
