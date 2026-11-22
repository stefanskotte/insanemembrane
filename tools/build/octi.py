"""Octilinear top copper: every trace segment exactly 0, 45 or 90 degrees (runs after heal.py, before tidy.py).

The user's rule: route in clean 45-degree steps only, never small (< 45 degree) bends along the way.

1. Topology: tracks are split wherever another track ends on their interior, so every attachment point
   (pad, via, junction, loose end) is a polyline end. Ends never move, except an end inside its pad, which may
   slide along its own line as long as it stays inside the pad.
2. Each polyline is simplified (Douglas-Peucker) and every run is given the nearest of the 8 directions.
   Lines go through their run's midpoint, the first/last through the fixed ends, and vertices are the
   intersections of neighbouring lines. Runs that collapse or reverse are dropped and the fit is redone.
   Several simplification tolerances are tried; the candidate closest to the original that keeps
   clearance is kept.
3. Fallback (only if no clean fit keeps clearance): each simplified segment is replaced by its two-piece
   0/90 + 45 decomposition between the same two vertices.
Usage: python octi.py <scan-data dir>   (rewrites routing.json)
"""
import json
import math
import sys
from collections import defaultdict
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree
from octilib import DIRS, MIN_SEG, clean, cross2, decompose, fit, intersect, is_octi, nearest_dir

from geomlib import contact_items, led_items, on_contact, x_contact_in
D = sys.argv[1]
G = json.load(open(f"{D}/board_geom.json"))
R = json.load(open(f"{D}/routing.json"))
PADS = json.load(open(f"{D}/pads_final.json"))["pads"]
CLEAR, EDGE_CLEAR, MAX_MOVE, MIN_SEG = 0.25, 0.30, 0.45, 0.15
TOLS = (0.10, 0.18, 0.28, 0.40, 0.06)


DIRS = [np.array([math.cos(math.radians(a)), math.sin(math.radians(a))]) for a in range(0, 360, 45)]
board_in = Polygon(G["board_outline"][0]).buffer(-EDGE_CLEAR)

# ---------------------------------------------------------------- pads (incl. tail contacts and LED pads)
pad_items = [(p["net"], Polygon(p["poly"])) for p in PADS]
pad_items += contact_items(G) + led_items(G)

top = [t for t in R["tracks"] if t["layer"] == "F.Cu" and len(t["pts"]) > 1]
rest = [t for t in R["tracks"] if not (t["layer"] == "F.Cu" and len(t["pts"]) > 1)]

# ---------------------------------------------------------------- 1. split at interior attachments
def split_at_interior(tracks):
    for _ in range(20):
        ends = [(t["net"], np.array(e, float)) for t in tracks for e in (t["pts"][0], t["pts"][-1])]
        ends += [(v["net"], np.array(v["pos"], float)) for v in R["vias"]]
        did = False
        for t in list(tracks):
            P = [np.array(p, float) for p in t["pts"]]
            for net, e in ends:
                if net != t["net"] or min(np.hypot(*(e - P[0])), np.hypot(*(e - P[-1]))) < 0.05:
                    continue
                for k in range(len(P) - 1):
                    a, b = P[k], P[k + 1]
                    ab = b - a; L2 = ab @ ab
                    if L2 < 1e-12:
                        continue
                    s = np.clip((e - a) @ ab / L2, 0, 1)
                    q = a + s * ab
                    if np.hypot(*(q - e)) < 0.05:
                        q = e if np.hypot(*(q - e)) < 0.05 else q
                        p1 = [x.tolist() for x in P[:k + 1]] + [q.tolist()]
                        p2 = [q.tolist()] + [x.tolist() for x in P[k + 1:]]
                        tracks.remove(t)
                        for pp in (p1, p2):
                            if LineString(pp).length > 1e-4:
                                tracks.append(dict(t, pts=pp))
                        did = True
                        break
                if did:
                    break
            if did:
                break
        if not did:
            return tracks
    return tracks


def split_all(tracks):
    # repeated single splits are slow on 500 tracks; loop until no more change
    n = -1
    while n != len(tracks):
        n = len(tracks)
        tracks = split_at_interior(tracks)
    return tracks




def merge_degree2(tracks):
    """Two traces of one net that just meet end to end (no third trace, via or pad there) become one polyline,
    so that meeting point is free to move like any other bend."""
    def key(e):
        return (round(e[0] / 0.03), round(e[1] / 0.03))
    for _ in range(2000):
        deg = defaultdict(list)
        for ti, t in enumerate(tracks):
            for end in (0, -1):
                deg[(t["net"], key(t["pts"][end]))].append((ti, end))
        done = False
        for (net, k), lst in deg.items():
            if len(lst) != 2 or lst[0][0] == lst[1][0]:
                continue
            e = np.array(tracks[lst[0][0]]["pts"][lst[0][1]])
            if any(v["net"] == net and np.hypot(*(np.array(v["pos"]) - e)) < 0.1 for v in R["vias"]):
                continue
            if any(n == net and poly.distance(Point(e)) < 0.05 for n, poly in pad_items):
                continue
            (ta, ea), (tb, eb) = lst
            A = tracks[ta]["pts"] if ea == -1 else tracks[ta]["pts"][::-1]
            B = tracks[tb]["pts"] if eb == 0 else tracks[tb]["pts"][::-1]
            merged = dict(tracks[ta], pts=A + B[1:])
            tracks = [t for ti, t in enumerate(tracks) if ti not in (ta, tb)] + [merged]
            done = True
            break
        if not done:
            return tracks
    return tracks


def snap_overlaps(tracks):
    """An end that only overlaps another trace of its net (within the trace width, not on a pad or via) is moved
    exactly onto that trace, so the split below makes it a real junction that can't drift apart."""
    snapped = 0
    for t in tracks:
        for end in (0, -1):
            e = np.array(t["pts"][end], float); pt = Point(e)
            if any(v["net"] == t["net"] and np.hypot(*(np.array(v["pos"]) - e)) < 0.1 for v in R["vias"]):
                continue
            if any(n == t["net"] and poly.distance(pt) < 0.01 for n, poly in pad_items):
                continue
            if any(o is not t and o["net"] == t["net"] and min(np.hypot(*(np.array(o["pts"][0]) - e)),
                                                                np.hypot(*(np.array(o["pts"][-1]) - e))) < 0.05
                   for o in tracks):
                continue
            best = None
            for o in tracks:
                if o is t or o["net"] != t["net"]:
                    continue
                L = LineString(o["pts"]); dd = L.distance(pt)
                if dd < 0.32 and (best is None or dd < best[0]):
                    best = (dd, L.interpolate(L.project(pt)))
            if best and best[0] > 1e-4:
                q = best[1]
                t["pts"][end] = [q.x, q.y]; snapped += 1
    return snapped


def dedupe(tracks):
    seen, out = set(), []
    for t in tracks:
        k = (t["net"], tuple(sorted([tuple(np.round(t["pts"][0], 3)), tuple(np.round(t["pts"][-1], 3))])),
             round(LineString(t["pts"]).length, 3))
        if k not in seen:
            seen.add(k); out.append(t)
    return out


n_dup = len(top)
top = dedupe(top)
n_dup -= len(top)
n_snap = snap_overlaps(top)
n0 = len(top)
top = merge_degree2(top)
n1 = len(top)
top = split_all(top)
print(f"topology: {n_dup} duplicate traces dropped, {n_snap} overlapping ends snapped onto their trace; {n0} traces, {n0 - n1} end-to-end joins merged, {len(top)} pieces after splitting at junctions")

# ---------------------------------------------------------------- 2. octilinear fit




def end_pad(net, e):
    pt = Point(e)
    for n, poly in pad_items:
        if n == net and poly.buffer(-0.05).contains(pt):
            return poly.buffer(-0.05)
    return None










# other-net copper: pads + vias + all tracks (updated as we go)
geoms = {}
def tgeom(i):
    return LineString(top[i]["pts"]).buffer(top[i]["w"] / 2)


def touches(net, pts, w):
    g = LineString(pts).buffer(w / 2 - 0.01)
    return {j for j in tree.query(g) if meta[j][0] != "t" and meta[j][2] == net and g.intersects(static[j])}


def clearance_ok(i, new, need, orig=None):
    g = LineString(new).buffer(top[i]["w"] / 2)
    if orig is not None and not touches(top[i]["net"], orig, top[i]["w"]) <= touches(top[i]["net"], new, top[i]["w"]):
        return False          # must still reach every pad and via the original piece reached
    if not board_in.contains(LineString(new)):
        # allowed only where the original already was outside the inner board (heal nudged those)
        if not LineString(new).within(board_in.union(LineString(top[i]["pts"]).buffer(0.01))):
            return False
    net = top[i]["net"]
    for j in tree.query(g.buffer(need)):
        kind, idx, n = meta[j]
        if n == net:
            continue
        other = tgeom(idx) if kind == "t" else static[j]
        if g.distance(other) < need - 1e-6:
            return False
    return True


static, meta = [], []
for n, poly in pad_items:
    static.append(poly); meta.append(("p", None, n))
for v in R["vias"]:
    static.append(Point(v["pos"]).buffer(0.35)); meta.append(("v", None, v["net"]))
for i, t in enumerate(top):
    # index the original geometry swollen by MAX_MOVE so later moves are still found by the query
    static.append(tgeom(i).buffer(MAX_MOVE + 0.1)); meta.append(("t", i, t["net"]))
tree = STRtree(static)


def orig_clear(i):
    g = tgeom(i)
    net = top[i]["net"]
    best = 9.0
    for j in tree.query(g.buffer(CLEAR + 0.3)):
        kind, idx, n = meta[j]
        if n == net:
            continue
        other = tgeom(idx) if kind == "t" else static[j]
        best = min(best, g.distance(other))
    return best


stats = defaultdict(int)
NEED, ORIG = {}, {}
worst = []


def candidates(pts, padA, padB):
    cands = []
    for tol in TOLS:
        for pa, pb in ((padA, padB), (None, None)):
            f = fit(pts, tol, pa, pb)
            if f is None:
                continue
            f = clean(f)
            h = LineString(f).hausdorff_distance(LineString(pts))
            if h <= MAX_MOVE and is_octi(f):
                cands.append((len(f) + 4 * h, h, f))
    cands.sort(key=lambda c: c[0])
    return cands


def solve(i, pts, padA, padB, need, depth=0):
    """Clean fit of the whole piece; else split at the middle vertex and solve the halves; else decompose."""
    for _, h, f in candidates(pts, padA, padB):
        if clearance_ok(i, f, need, pts):
            return f, "fit"
    S = LineString(pts).simplify(0.05, preserve_topology=False).coords
    if depth < 6 and len(S) >= 3:
        # split at the simplified vertex nearest the middle of the piece (a real bend of the trace)
        L = LineString(pts)
        mid = min(range(1, len(S) - 1), key=lambda k: abs(L.project(Point(S[k])) - L.length / 2))
        cut = np.array(S[mid])
        k = int(np.argmin([np.hypot(*(np.array(p) - cut)) for p in pts]))
        if 0 < k < len(pts) - 1:
            a = solve(i, pts[:k + 1], padA, None, need, depth + 1)
            b = solve(i, pts[k:], None, padB, need, depth + 1)
            if a and b:
                kind = "split" if a[1] != "decompose" and b[1] != "decompose" else "decompose"
                return clean(a[0] + b[0][1:]), kind
    for tol in (0.10, 0.05, 0.02):
        f = clean(decompose(pts, tol))
        if is_octi(f) and clearance_ok(i, f, need, pts):
            return f, "decompose"
    return None


for i, t in enumerate(top):
    pts = t["pts"]
    ORIG[i] = pts
    if is_octi(pts):
        stats["already"] += 1; continue
    need = max(0.20, min(CLEAR, orig_clear(i)))
    NEED[i] = need; ORIG[i] = pts
    padA = end_pad(t["net"], pts[0]); padB = end_pad(t["net"], pts[-1])
    r = solve(i, pts, padA, padB, need)
    if not r and G.get("octi_fallback_move"):
        # last resort (A500): allow a larger move, at DRC clearance, for a piece nothing else fits
        _mm = MAX_MOVE
        MAX_MOVE = G["octi_fallback_move"]
        r = solve(i, pts, padA, padB, 0.20)
        MAX_MOVE = _mm
        if r:
            stats["fallback"] += 1
    if r:
        f, kind = r
        h = LineString(f).hausdorff_distance(LineString(pts))
        t["pts"] = f; stats[kind] += 1; worst.append((h, t["net"], f[0]))
    else:
        stats["left"] += 1
        worst.append((-1, t["net"], pts[0]))

# ---------------------------------------------------------------- 4. remove small jogs
# A short diagonal between two parallel runs is a sideways step: slide one of the runs onto the other's line
# (its far vertex slides along the segment before it) so the trace runs straight through.
JOG_MAX = 0.8


def unit(v):
    return v / np.hypot(*v)


def jog_fix(pts, k):
    P = [np.array(p) for p in pts]
    d = unit(P[k] - P[k - 1])
    outs = []
    if k - 1 >= 1:      # move run k-1 onto run k+1's line
        X = intersect(P[k - 2], unit(P[k - 1] - P[k - 2]), P[k + 1], d)
        if X is not None and (X - P[k - 2]) @ unit(P[k - 1] - P[k - 2]) > MIN_SEG and (P[k + 1] - X) @ d > MIN_SEG:
            outs.append(P[:k - 1] + [X] + P[k + 1:])
    if k + 2 <= len(P) - 2:   # move run k+1 onto run k-1's line
        e = unit(P[k + 3] - P[k + 2])
        X = intersect(P[k], d, P[k + 3], e)
        if X is not None and (X - P[k]) @ d > MIN_SEG and (P[k + 3] - X) @ e > MIN_SEG:
            outs.append(P[:k + 1] + [X] + P[k + 3:])
    return [clean(o) for o in outs]


def find_jog(pts):
    P = [np.array(p) for p in pts]
    for k in range(1, len(P) - 2):
        L = np.hypot(*(P[k + 1] - P[k]))
        u, w = unit(P[k] - P[k - 1]), unit(P[k + 2] - P[k + 1])
        if L < JOG_MAX and u @ w > 0.999:
            yield k


fixed_jogs = 0
for _ in range(4):
    changed = False
    for i, t in enumerate(top):
        need = max(0.20, min(CLEAR, NEED.get(i, CLEAR)))
        for k in list(find_jog(t["pts"])):
            ok = False
            for cand in jog_fix(t["pts"], k):
                if is_octi(cand) and LineString(cand).hausdorff_distance(LineString(ORIG[i])) <= MAX_MOVE \
                        and clearance_ok(i, cand, need, ORIG[i]):
                    t["pts"] = cand; fixed_jogs += 1; changed = ok = True
                    break
            if ok:
                break   # indices changed: rescan this trace next pass
    if not changed:
        break
left_jogs = sum(len(list(find_jog(t["pts"]))) for t in top)
print(f"jogs: {fixed_jogs} small sideways steps removed, {left_jogs} left (no room without crowding another net)")

# ---------------------------------------------------------------- 5. connectivity must be unchanged
def components(tracks):
    by = defaultdict(list)
    for t in tracks:
        by[t["net"]].append(LineString(t["pts"]).buffer(t["w"] / 2 - 0.01))
    for v in R["vias"]:
        by[v["net"]].append(Point(v["pos"]).buffer(0.3))
    for n, poly in pad_items:
        by[n].append(poly)
    out = {}
    for n, gs in by.items():
        par = list(range(len(gs)))
        def f(a):
            while par[a] != a:
                par[a] = par[par[a]]; a = par[a]
            return a
        tr = STRtree(gs)
        for a, g in enumerate(gs):
            for b in tr.query(g):
                if b > a and g.intersects(gs[b]):
                    par[f(a)] = f(b)
        out[n] = len({f(a) for a in range(len(gs))})
    return out


c_before = components([t for t in R["tracks"] if t["layer"] == "F.Cu" and len(t["pts"]) > 1])
c_after = components(top)
diff = {n: (c_before[n], c_after.get(n)) for n in c_before if c_before[n] != c_after.get(n)}
print("connectivity: unchanged on every net" if not diff else f"CONNECTIVITY CHANGED (before, after): {diff}")
if diff:
    sys.exit(1)

R["tracks"] = top + rest
json.dump(R, open(f"{D}/routing.json", "w"))
worst.sort(key=lambda w: -w[0])
print(f"octilinear: {dict(stats)}; largest moves: " +
      ", ".join(f"net {n} {h:.2f} mm @({p[0]:.0f},{p[1]:.0f})" for h, n, p in worst[:6]))
left = [w for w in worst if w[0] < 0]
if left:
    print("NOT octilinear (no candidate kept clearance):", [(n, [round(c, 1) for c in p]) for _, n, p in left])
