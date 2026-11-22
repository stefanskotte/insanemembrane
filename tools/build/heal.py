"""Final routing clean-up in board coordinates (runs after pads.py).

1. Keep top copper >= EDGE_CLEAR from the board edge (nudge vertices inward).
2. Remove tiny dangling scraps.
3. Join the pieces of each net: closest pair of points between pieces, if < MAX_JOIN mm and the new
   segment keeps CLEAR from every other net. Anything left is reported.
Usage: python heal.py <scan-data dir>   (rewrites routing.json)
"""
import json
import sys
from collections import defaultdict
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points, unary_union

from geomlib import contact_items, led_items, on_contact, x_contact_in
D = sys.argv[1]
G = json.load(open(f"{D}/board_geom.json"))
R = json.load(open(f"{D}/routing.json"))
PADS = json.load(open(f"{D}/pads_final.json"))["pads"]
EDGE_CLEAR, CLEAR, MAX_JOIN = 0.30, 0.25, 3.0

board = Polygon(G["board_outline"][0])

# 1. edge clearance
moved = 0
for t in R["tracks"]:
    if t["layer"] != "F.Cu":
        continue
    inner = board.buffer(-(EDGE_CLEAR + t["w"] / 2 + 0.02))
    for i, p in enumerate(t["pts"]):
        pt = Point(p)
        if not inner.contains(pt):
            q = nearest_points(inner.exterior, pt)[0]
            # only nudge (small moves); a point far outside is a real problem to report
            if pt.distance(q) < 0.6:
                t["pts"][i] = [q.x, q.y]; moved += 1
print(f"edge: vertices nudged inward: {moved}")

# copper items per net (top layer + vias + pads)
def items():
    it = defaultdict(list)   # net -> list of (kind, geom)
    for i, t in enumerate(R["tracks"]):
        if t["layer"] == "F.Cu" and len(t["pts"]) > 1:
            it[t["net"]].append(("track", i, LineString(t["pts"]).buffer(t["w"] / 2, cap_style=1)))
    for v in R["vias"]:
        it[v["net"]].append(("via", None, Point(v["pos"]).buffer(0.35)))
    for p in PADS:
        it[p["net"]].append(("pad", None, Polygon(p["poly"])))
    for net_, g_ in contact_items(G) + led_items(G):
        it[net_].append(("pad", None, g_))
    return it


def pieces(lst):
    n = len(lst); parent = list(range(n))
    def f(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]; a = parent[a]
        return a
    for i in range(n):
        for j in range(i + 1, n):
            if lst[i][2].distance(lst[j][2]) < 0.005:
                parent[f(i)] = f(j)
    groups = defaultdict(list)
    for i in range(n):
        groups[f(i)].append(i)
    return list(groups.values())


# 2. remove tiny dangling scraps: track < 0.5 mm that touches nothing at one end
it = items()
drop = set()
for net, lst in it.items():
    for k, (kind, idx, g) in enumerate(lst):
        if kind != "track":
            continue
        t = R["tracks"][idx]
        L = LineString(t["pts"]).length
        if L >= 0.5:
            continue
        ends = [Point(t["pts"][0]), Point(t["pts"][-1])]
        touch = [any(o[2].distance(e) < 0.01 for j, o in enumerate(lst) if j != k) for e in ends]
        if not all(touch):
            drop.add(idx)
R["tracks"] = [t for i, t in enumerate(R["tracks"]) if i not in drop]
print(f"tiny dangling scraps removed: {len(drop)}")

# 3. join pieces of each net
joins, left = 0, []
for rnd in range(6):
    it = items()
    others_cache = {}
    changed = False
    for net, lst in it.items():
        grp = pieces(lst)
        if len(grp) < 2:
            continue
        other = unary_union([g for n2, l2 in it.items() if n2 != net for _, _, g in l2])
        geoms = [unary_union([lst[i][2] for i in g]) for g in grp]
        main = max(range(len(geoms)), key=lambda i: geoms[i].area)
        for gi, gg in enumerate(geoms):
            if gi == main:
                continue
            # nearest other piece of the same net
            best = None
            for gj, hh in enumerate(geoms):
                if gj == gi:
                    continue
                d = gg.distance(hh)
                if best is None or d < best[0]:
                    best = (d, hh)
            if best is None or best[0] > MAX_JOIN:
                left.append((net, round(best[0], 2) if best else None, [round(v, 1) for v in gg.centroid.coords[0]]))
                continue
            p, q = nearest_points(gg, best[1])
            seg = LineString([(p.x, p.y), (q.x, q.y)])
            if seg.length < 1e-3:
                continue
            if seg.buffer(0.15).distance(other) < CLEAR:
                left.append((net, round(best[0], 2), [round(p.x, 1), round(p.y, 1)], "blocked"))
                continue
            # extend slightly into both pieces so the joint is solid
            R["tracks"].append(dict(net=net, layer="F.Cu", w=0.30, pts=[[p.x, p.y], [q.x, q.y]]))
            joins += 1; changed = True
    if not changed:
        break
    left = []
print(f"joins added: {joins}")
print(f"pieces left unjoined: {len(left)}")
for l in left[:20]:
    print("   ", l)
# 4. prune dead-end copper (a track end touching nothing carries no signal); repeat until stable
def endpoints_touch(net, pt, skip):
    P = Point(pt)
    for i, t in enumerate(R["tracks"]):
        if i == skip or t["net"] != net or len(t["pts"]) < 2:
            continue
        if LineString(t["pts"]).distance(P) < t["w"] / 2 + 0.01:
            return True
    for v in R["vias"]:
        if v["net"] == net and Point(v["pos"]).distance(P) < 0.36:
            return True
    for p in PADS:
        if p["net"] == net and Polygon(p["poly"]).distance(P) < 0.01:
            return True
    if on_contact(G, net, P):
        return True
    if any(n_ == net and g_.distance(P) < 1e-6 for n_, g_ in led_items(G)):
        return True
    return False


pruned = 0
for _ in range(10):
    kill = []
    for i, t in enumerate(R["tracks"]):
        if t["layer"] != "F.Cu" or len(t["pts"]) < 2:
            continue
        if LineString(t["pts"]).length > 6.0:
            continue
        a = endpoints_touch(t["net"], t["pts"][0], i)
        b = endpoints_touch(t["net"], t["pts"][-1], i)
        if not (a and b):
            kill.append(i)
    if not kill:
        break
    R["tracks"] = [t for i, t in enumerate(R["tracks"]) if i not in set(kill)]
    pruned += len(kill)
print(f"dead-end pieces pruned: {pruned}")
json.dump(R, open(f"{D}/routing.json", "w"))
