"""Tidy the replica's copper (runs after octi.py, which has already made every top trace 0/45/90 degrees).

3. Bottom bridges: straight like the printed bars, made 0/45/90 too (one 45-degree bend or jog where a bar
   runs at an odd angle), keeping CLEAR from the other bridges.
4. Tail entry, the user's hand-routing method (see below).
Usage: python tidy.py <scan-data dir>   (rewrites routing.json)
"""
import json
import math
import sys
from collections import defaultdict
import numpy as np
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree
from octilib import clean, decompose, fit, is_octi

from geomlib import x_contact_in as x_contact_in_of, contact_items
D = sys.argv[1]
G = json.load(open(f"{D}/board_geom.json"))
R = json.load(open(f"{D}/routing.json"))
PADS = json.load(open(f"{D}/pads_final.json"))["pads"]
BUNDLE_X, TAPER = 155.0, 25.0
SNAP_DEG, MAX_MOVE, CLEAR = 5.0, 0.12, 0.25
TW = 0.30
tl = G["tail"]
BAND_M = G.get("entry_band_margin", 1.0)
band = (tl["cy"] - tl["width"] / 2 - BAND_M, tl["cy"] + tl["width"] / 2 + BAND_M)
ALLOW_VERT = G.get("entry_allow_vertical", False)   # A500: traces climb into the tab from below
pins = {str(p["pin"]): p for p in G["pins"]}
x_contact_in = x_contact_in_of(G)

# ---------------------------------------------------------------- 2. straighten
def snap_angle(a):
    q = round(a / 45.0) * 45.0
    return q if abs(a - q) <= SNAP_DEG else None


def intersect(p, d1, q, d2):
    A = np.array([[d1[0], -d2[0]], [d1[1], -d2[1]]])
    if abs(np.linalg.det(A)) < 1e-9:
        return None
    s = np.linalg.solve(A, np.array(q) - np.array(p))
    return np.array(p) + s[0] * np.array(d1)


def straighten(pts):
    P = [np.array(p, float) for p in pts]
    if len(P) < 2:
        return None
    segs = []
    for a, b in zip(P[:-1], P[1:]):
        v = b - a
        L = np.hypot(*v)
        if L < 1e-6:
            continue
        ang = math.degrees(math.atan2(v[1], v[0]))
        s = snap_angle(ang)
        th = math.radians(s if s is not None else ang)
        segs.append(dict(a=a, b=b, d=np.array([math.cos(th), math.sin(th)]), snapped=s is not None))
    if not segs:
        return None
    # merge consecutive segments with the same snapped direction
    merged = [segs[0]]
    for s in segs[1:]:
        m = merged[-1]
        if s["snapped"] and m["snapped"] and np.allclose(s["d"], m["d"], atol=1e-6):
            m["b"] = s["b"]
        else:
            merged.append(s)
    # anchor lines: first through its start, last through its end, middle through midpoints
    anchors = []
    for i, s in enumerate(merged):
        if i == 0:
            anchors.append(s["a"])
        elif i == len(merged) - 1:
            anchors.append(s["b"])
        else:
            anchors.append((s["a"] + s["b"]) / 2)
    if len(merged) == 1:
        s = merged[0]
        # single segment: keep the start, project the end onto the snapped direction
        L = np.dot(s["b"] - s["a"], s["d"])
        return [s["a"].tolist(), (s["a"] + L * s["d"]).tolist()]
    out = [merged[0]["a"]]
    for i in range(len(merged) - 1):
        x = intersect(anchors[i], merged[i]["d"], anchors[i + 1], merged[i + 1]["d"])
        if x is None:
            return None
        out.append(x)
    out.append(merged[-1]["b"])
    return [o.tolist() for o in out]


def hausdorff(a, b):
    return LineString(a).hausdorff_distance(LineString(b))


# other-net copper index (pads + vias + tracks), rebuilt lazily per net
def copper_by_net():
    by = defaultdict(list)
    for i, t in enumerate(R["tracks"]):
        if t["layer"] == "F.Cu" and len(t["pts"]) > 1:
            by[t["net"]].append(LineString(t["pts"]).buffer(t["w"] / 2))
    for v in R["vias"]:
        by[v["net"]].append(Point(v["pos"]).buffer(0.35))
    for p in PADS:
        by[p["net"]].append(Polygon(p["poly"]))
    return by


# ---------------------------------------------------------------- 3. bottom bridges: straight like the printed bars
DIRS = [np.array([math.cos(math.radians(k)), math.sin(math.radians(k))]) for k in range(0, 360, 45)]


def octi_options(a, b):
    """Ways to go from a to b in 0/45/90 pieces: straight if already on a direction, else one bend (either
    order) or a 45-degree jog in the middle; closest to the straight line first."""
    a, b = np.array(a, float), np.array(b, float)
    v = b - a
    ang = math.degrees(math.atan2(v[1], v[0])) % 360
    off = min(ang % 45, 45 - ang % 45)
    if off < 0.01:
        return [[a, b]]
    k1 = int(ang // 45) % 8; k2 = (k1 + 1) % 8
    al, be = np.linalg.solve(np.array([DIRS[k1], DIRS[k2]]).T, v)
    u1, u2 = al * DIRS[k1], be * DIRS[k2]
    main, diag = (u1, u2) if al >= be else (u2, u1)
    opts = [[a, a + u1, b], [a, a + u2, b], [a, a + main / 2, a + main / 2 + diag, b]]
    # two bends with the 45-degree part split around the straight run, or the straight run split at other points
    # (only reached when every one-bend option fails, e.g. the A500's S-shaped bridges)
    for f_ in (0.25, 0.5, 0.75):
        opts.append([a, a + diag * f_, a + diag * f_ + main, b])
        if f_ != 0.5:
            opts.append([a, a + main * f_, a + main * f_ + diag, b])
    return sorted(opts, key=lambda o: LineString(o).hausdorff_distance(LineString([a, b])))


bot = [t for t in R["tracks"] if t["layer"] == "B.Cu"]
vias = [Point(v["pos"]).buffer(0.35) for v in R["vias"]]
via_net = [v["net"] for v in R["vias"]]
# copper must stay EDGE_CLEAR inside the outline and away from the holes
keep_in = Polygon(G["board_outline"][0])
for h in G["holes"]:
    if h["shape"] == "circle":
        keep_in = keep_in.difference(Point(h["x"], h["y"]).buffer(h["d"] / 2))
    else:
        r = min(h["w"], h["h"]) / 2; e = (max(h["w"], h["h"]) - min(h["w"], h["h"])) / 2
        seg = [(h["x"], h["y"] - e), (h["x"], h["y"] + e)] if h["h"] >= h["w"] else [(h["x"] - e, h["y"]), (h["x"] + e, h["y"])]
        keep_in = keep_in.difference(LineString(seg).buffer(r))
keep_in = keep_in.buffer(-0.30)


def bridge_ok(t, path):
    line = LineString(path)
    if not keep_in.contains(line.buffer(t["w"] / 2)):
        return False
    g = line.buffer(t["w"] / 2)
    if any(o is not t and o["net"] != t["net"] and g.distance(LineString(o["pts"]).buffer(o["w"] / 2)) < CLEAR
           for o in bot):
        return False
    return not any(n != t["net"] and g.distance(vg) < CLEAR for vg, n in zip(vias, via_net))


def bridge_candidates(t):
    """Fewest bends first: the direct via-to-via path (straight, one bend, or a middle jog), then clean
    0/45/90 fits of the printed bar's path at decreasing simplification; the old per-segment
    decomposition only as a last resort."""
    a, b = np.array(t["pts"][0], float), np.array(t["pts"][-1], float)
    orig = LineString(t["pts"])
    cands = []
    for o in octi_options(a, b):
        cands.append([p.tolist() for p in o])
    for tol in (1.5, 0.8, 0.4, 0.2, 0.1):
        f = fit(t["pts"], tol, None, None)
        if f is not None:
            f = clean(f)
            if is_octi(f):
                cands.append(f)
    cands.sort(key=lambda c: (len(c), orig.hausdorff_distance(LineString(c))))
    for tol in (0.1, 0.05):
        f = clean(decompose(t["pts"], tol))
        if is_octi(f):
            cands.append(f)
    return cands


bdone = bleft = 0
nbends = []
for t in bot:
    for c in bridge_candidates(t):
        if bridge_ok(t, c):
            t["pts"] = c; bdone += 1; nbends.append(len(c) - 2)
            break
    else:
        bleft += 1
from collections import Counter
print(f"bridges: {bdone} in 0/45/90 pieces (bends per bridge: {dict(sorted(Counter(nbends).items()))}), "
      f"{bleft} left as they were (no room)")


# ---------------------------------------------------------------- 4. tail entry (the user's hand-routing method)
# Each tail trace: the 45-degree diagonal it arrives on is extended/shortened along its own direction until it
# reaches its contact's y; from there ONE straight level line runs to the contact. A trace that arrives level
# already (within LEVEL_TOL) gets one straight line from the start of its level run to the contact.
# No jogs, no tapers. (Matches kicad/handrouted/, 2026-11-15.)
EPS, LEVEL_TOL = 0.03, 0.15
segs = []
for t in R["tracks"]:
    if t["layer"] != "F.Cu" or len(t["pts"]) < 2:
        continue
    for p, q in zip(t["pts"][:-1], t["pts"][1:]):
        if np.hypot(q[0] - p[0], q[1] - p[1]) > 1e-6:
            segs.append(dict(net=t["net"], w=t["w"], a=np.array(p, float), b=np.array(q, float)))
other_tracks = [t for t in R["tracks"] if t["layer"] != "F.Cu"]
in_band = lambda y: band[0] < y < band[1]
x_root = tl["root_x"]
x_end = x_contact_in + 0.6
same = lambda u, v: np.hypot(*(u - v)) < EPS
done_diag, done_level, problems = 0, 0, []
_pending = list(pins.items())
for _pass in range(6):   # a net that would crowd a not-yet-straightened neighbour is retried in the next pass
    problems, _retry = [p_ for p_ in problems if "crowd" not in p_[1]], []   # keep the other problems; crowded ones are retried
    for net, pin in _pending:
        yp = pin["y"]
        mine = [s_ for s_ in segs if s_["net"] == net]
        start = None
        for s_ in mine:
            lo, hi = sorted([s_["a"], s_["b"]], key=lambda v: v[0])
            if lo[0] <= x_root - 0.5 < hi[0] and in_band(lo[1]) and in_band(hi[1]):
                start = (s_, lo); break
        if start is None:
            problems.append((net, "no trace at the tail root")); continue
        chain, cur, diag = [start[0]], start[1], None
        for _ in range(80):
            nxt = [s_ for s_ in mine if all(s_ is not c for c in chain) and (same(s_["a"], cur) or same(s_["b"], cur))]
            nxt = [s_ for s_ in nxt if min(s_["a"][0], s_["b"][0]) < cur[0] - 1e-4 or
                   (ALLOW_VERT and abs(s_["a"][0] - s_["b"][0]) < 1e-4)]      # continues to the left (or straight down/up)
            if len(nxt) != 1:
                break
            s_ = nxt[0]
            far = s_["a"] if same(s_["b"], cur) else s_["b"]
            dx, dy = cur[0] - far[0], cur[1] - far[1]
            if abs(dy) > 0.2 * abs(dx) + 0.05:
                diag = (s_, far, cur); break
            chain.append(s_); cur = far
        removed = list(chain)
        if diag is not None:
            s_d, A, B = diag
            t_ = (yp - A[1]) / (B[1] - A[1]) if abs(B[1] - A[1]) > 1e-9 else -1
            if t_ < 0.05:
                problems.append((net, f"diagonal too short to reach y={yp:.2f}")); continue
            C = A + t_ * (B - A)
            removed.append(s_d)
            new_line = [A, C, np.array([x_end, yp])]
            done_diag += 1
        else:
            if abs(cur[1] - yp) > LEVEL_TOL:
                problems.append((net, f"arrives level but {cur[1] - yp:+.2f} mm off its contact")); continue
            new_line = [cur, np.array([x_end, yp])]
            done_level += 1
        # the new line must keep DRC clearance from every other net (A500: long diagonals can cut across a bundle)
        _nl = LineString(new_line).buffer(TW / 2)
        _other = [LineString([o["a"], o["b"]]).buffer(o["w"] / 2) for o in segs if o["net"] != net]
        _other += [Polygon(pp["poly"]) for pp in PADS if pp["net"] != net] + [Point(v["pos"]).buffer(0.35) for v in R["vias"] if v["net"] != net]
        _other += [g_ for n_, g_ in contact_items(G) if n_ != net]
        if any(_nl.distance(o_) < 0.2 - 1e-6 for o_ in _other):
            problems.append((net, "new entry line would crowd another net: kept as routed"))
            _retry.append((net, pin))
            if diag is not None:
                done_diag -= 1
            else:
                done_level -= 1
            continue
        removed += [s_ for s_ in mine if all(s_ is not r for r in removed) and min(s_["a"][0], s_["b"][0]) >= x_root - 0.5 - EPS and in_band(s_["a"][1])]
        rem_geom = unary_union([LineString([r["a"], r["b"]]) for r in removed])
        segs = [s_ for s_ in segs if all(s_ is not r for r in removed)]
        for p, q in zip(new_line[:-1], new_line[1:]):
            if np.hypot(*(q - p)) > 1e-6:
                segs.append(dict(net=net, w=TW, a=np.array(p, float), b=np.array(q, float)))
        nl = LineString(new_line)
        for s_ in [s_ for s_ in segs if s_["net"] == net]:      # branches that met the old run: drop onto the new line
            for end in ("a", "b"):
                P = Point(s_[end])
                if rem_geom.distance(P) < EPS and nl.distance(P) > EPS:
                    q = nl.interpolate(nl.project(P))
                    segs.append(dict(net=net, w=TW, a=s_[end].copy(), b=np.array([q.x, q.y])))
    if not _retry or len(_retry) == len(_pending):
        break
    _pending = _retry
print(f"tail entry: {done_diag} diagonals extended to their contact's y, {done_level} level traces run straight in; "
      f"problems: {problems}")
R["tracks"] = other_tracks + [dict(net=s_["net"], layer="F.Cu", w=s_["w"], pts=[s_["a"].tolist(), s_["b"].tolist()]) for s_ in segs]
json.dump(R, open(f"{D}/routing.json", "w"))
