"""Straighten wiggles: replace runs of short 0/45/90 pieces by the simplest 0/45/90 path (straight, or one bend).

The user's rule (A600 hand edits, 2026-11-23):
- a 45-degree line with a small sideways step in it becomes one straight line (PIN22);
- a twisting chain into a via becomes the long 45-degree run, extended until it lines up with the via,
  then one straight run in (PIN05).

Each trace is cut into chains between fixed points: pads, contacts, vias and junctions (vertices where 3+ pieces
meet), plus the chain's own ends. Along a chain, the longest window P[i]..P[j] that can be replaced by a straight
line or a single bend is taken first. A replacement must:
- stay within MAX_DEV of the original window (Hausdorff);
- keep max(0.20, min(0.25, the window's own clearance)) from other nets;
- keep 0.3 mm from the board edge and the holes.
Of the two bend orders, the one closer to the original wins, so a long 45-degree run is kept and extended.
Usage: python straighten.py <scan-data dir>   (rewrites routing.json; run after tidy.py / drop_loops.py)
"""
import json
import math
import sys
from collections import defaultdict
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.strtree import STRtree
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from geomlib import contact_items, led_items

MAX_DEV, CLEAR, MIN_CLEAR, EDGE = 0.6, 0.25, 0.20, 0.30
D = sys.argv[1]
R = json.load(open(f"{D}/routing.json"))
G = json.load(open(f"{D}/board_geom.json"))
P = json.load(open(f"{D}/pads_final.json"))["pads"]
DIRS = [np.array([math.cos(math.radians(k)), math.sin(math.radians(k))]) for k in range(0, 360, 45)]

keep_in = Polygon(G["board_outline"][0])
for h in G["holes"]:
    if h["shape"] == "circle":
        keep_in = keep_in.difference(Point(h["x"], h["y"]).buffer(h["d"] / 2))
    else:
        r = min(h["w"], h["h"]) / 2; e = (max(h["w"], h["h"]) - min(h["w"], h["h"])) / 2
        seg = [(h["x"], h["y"] - e), (h["x"], h["y"] + e)] if h["h"] >= h["w"] else [(h["x"] - e, h["y"]), (h["x"] + e, h["y"])]
        keep_in = keep_in.difference(LineString(seg).buffer(r))
keep_in = keep_in.buffer(-EDGE)

fixed_geoms = [(p["net"], Polygon(p["poly"])) for p in P] + contact_items(G) + led_items(G)
via_pts = [(v["net"], Point(v["pos"])) for v in R["vias"]]

top = [t for t in R["tracks"] if t["layer"] == "F.Cu" and len(t["pts"]) == 2]
other = [t for t in R["tracks"] if not (t["layer"] == "F.Cu" and len(t["pts"]) == 2)]
key = lambda p: (round(p[0], 4), round(p[1], 4))


def octi_paths(a, b):
    """straight if a->b is on a 0/45/90 direction, else the two one-bend paths"""
    v = b - a
    ang = math.degrees(math.atan2(v[1], v[0])) % 360
    if min(ang % 45, 45 - ang % 45) < 0.01:
        return [[a, b]]
    k1 = int(ang // 45) % 8; k2 = (k1 + 1) % 8
    al, be = np.linalg.solve(np.array([DIRS[k1], DIRS[k2]]).T, v)
    u1, u2 = al * DIRS[k1], be * DIRS[k2]
    return [[a, a + u1, b], [a, a + u2, b]]


def straighten_net(net, segs, tree, geoms, gnet):
    """segs: list of [p, q] (np arrays) of this net; returns the new list"""
    deg = defaultdict(int)
    for p, q in segs:
        deg[key(p)] += 1; deg[key(q)] += 1
    def anchored(p):
        if deg[key(p)] != 2:
            return True
        P_ = Point(p)
        return any(n == net and g.distance(P_) < 0.05 for n, g in fixed_geoms) or \
               any(n == net and vp.distance(P_) < 0.05 for n, vp in via_pts)
    # chains between anchors
    adj = defaultdict(list)
    for i, (p, q) in enumerate(segs):
        adj[key(p)].append((i, q)); adj[key(q)].append((i, p))
    used, chains = set(), []
    for i, (p, q) in enumerate(segs):
        if i in used:
            continue
        # walk both ways from this segment to anchors
        def walk(start, prev_seg):
            pts, cur, ps = [], start, prev_seg
            while not anchored(cur):
                nxt = [(j, r) for j, r in adj[key(cur)] if j != ps]
                if len(nxt) != 1 or nxt[0][0] in used:
                    break
                ps, cur = nxt[0][0], nxt[0][1]
                used.add(ps); pts.append(cur)
            return pts
        used.add(i)
        back = walk(p, i)
        fwd = walk(q, i)
        chains.append(list(reversed(back)) + [p, q] + fwd)
    def end_pad(p):
        P_ = Point(p)
        for n, g in fixed_geoms:
            if n == net and g.distance(P_) < 0.05:
                return g
        return None
    out = []
    for C in chains:
        C = [np.array(c, float) for c in C]
        if end_pad(C[0]) is not None and end_pad(C[-1]) is None:
            C = C[::-1]                                        # the pad end last, so it can be run into
        pad_end = end_pad(C[-1])
        pad_in = pad_end.buffer(-0.2) if pad_end is not None else None
        i, res = 0, [C[0]]
        while i < len(C) - 1:
            done = False
            for j in range(len(C) - 1, i + 1, -1):           # longest window first
                orig = LineString(C[i:j + 1])
                ob = orig.buffer(0.15)
                oc = 9.0                                       # the window's own clearance
                for k in tree.query(ob.buffer(0.5)):
                    if gnet[k] != net:
                        oc = min(oc, ob.distance(geoms[k]) + 0.0)
                need = max(MIN_CLEAR, min(CLEAR, oc))
                best = None
                cands = octi_paths(C[i], C[j])
                if j == len(C) - 1 and pad_in is not None and not pad_in.is_empty:
                    # the user's PIN22 fix: a straight run on into the pad instead of a step at its edge
                    for d_ in DIRS:
                        ray = LineString([C[i], C[i] + d_ * 40])
                        hit = ray.intersection(pad_in)
                        if not hit.is_empty:
                            q = min([np.array(c) for g_ in getattr(hit, "geoms", [hit]) for c in g_.coords],
                                    key=lambda c: np.hypot(*(c - C[i])))
                            cands.append([C[i], q])
                for path in cands:
                    if len(path) >= j - i + 1:                 # must be simpler than what it replaces
                        continue
                    if any(np.hypot(*(b - a)) < 0.05 for a, b in zip(path[:-1], path[1:])):
                        continue
                    L = LineString(path)
                    if j == len(C) - 1 and pad_end is not None:
                        # inside the pad the copper is the pad: compare only what lies outside it
                        Lo, Oo = L.difference(pad_end), orig.difference(pad_end)
                        dev = Lo.hausdorff_distance(Oo) if not (Lo.is_empty or Oo.is_empty) else L.hausdorff_distance(orig)
                    else:
                        dev = L.hausdorff_distance(orig)
                    if dev > MAX_DEV:
                        continue
                    g = L.buffer(0.15)
                    if not keep_in.contains(g):
                        continue
                    if any(gnet[k] != net and g.distance(geoms[k]) < need - 1e-6 for k in tree.query(g.buffer(need + 0.1))):
                        continue
                    rank = (len(path), dev)                    # fewest pieces first (the user's edits), then closest
                    if best is None or rank < best[0]:
                        best = (rank, path)
                if best:
                    res += [np.array(p) for p in best[1][1:]]
                    i = j; done = True
                    break
            if not done:
                res.append(C[i + 1]); i += 1
        out += [[a, b] for a, b in zip(res[:-1], res[1:]) if np.hypot(*(b - a)) > 1e-6]
    return out


by = defaultdict(list)
for t in top:
    by[t["net"]].append([np.array(t["pts"][0], float), np.array(t["pts"][1], float)])
width = {t["net"]: t["w"] for t in top}
before = sum(len(v) for v in by.values())


def index():
    geoms, gnet = [], []
    for n, ss in by.items():
        for p, q in ss:
            geoms.append(LineString([p, q]).buffer(width[n] / 2)); gnet.append(n)
    for n, g in fixed_geoms:
        geoms.append(g); gnet.append(n)
    for n, vp in via_pts:
        geoms.append(vp.buffer(0.35)); gnet.append(n)
    return STRtree(geoms), geoms, gnet


for net in sorted(by, key=lambda n: int(n)):
    tree, geoms, gnet = index()
    by[net] = straighten_net(net, by[net], tree, geoms, gnet)
after = sum(len(v) for v in by.values())
R["tracks"] = other + [dict(net=n, layer="F.Cu", w=width[n], pts=[p.tolist(), q.tolist()]) for n, ss in by.items() for p, q in ss]
json.dump(R, open(f"{D}/routing.json", "w"))
print(f"straighten: top segments {before} -> {after} ({before - after} wiggle pieces merged)")
