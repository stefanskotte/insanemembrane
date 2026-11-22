"""Drop small closed loops of top copper that hang off a via (scan artefacts of big landing spots).

A landing spot's silver rim can survive as a ring of centre line; after the 0/45/90 fit it is a little square
around the via. Every loop smaller than MAX_AREA whose centre is within NEAR mm of a same-net via is removed,
segment by segment, and kept removed only if the net's pads / vias / contacts stay connected exactly as before.
Usage: python drop_loops.py <scan-data dir>   (rewrites routing.json; run after tidy.py)
"""
import json
import sys
from collections import defaultdict
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from geomlib import contact_items, led_items

MAX_AREA, NEAR = 3.0, 1.2
D = sys.argv[1]
R = json.load(open(f"{D}/routing.json"))
G = json.load(open(f"{D}/board_geom.json"))
P = json.load(open(f"{D}/pads_final.json"))["pads"]
terminals = defaultdict(list)            # net -> fixed copper (pads, contacts, LED)
for p in P:
    terminals[p["net"]].append(Polygon(p["poly"]))
for n, g in contact_items(G) + led_items(G):
    terminals[n].append(g)


def groups(net, tracks):
    """connected groups of this net's terminals and vias, as a frozenset of frozensets of item labels"""
    items = [("t%d" % i, {"F.Cu"}, g) for i, g in enumerate(terminals[net])]
    items += [("v%d" % i, {"F.Cu", "B.Cu"}, Point(v["pos"]).buffer(0.35)) for i, v in enumerate(R["vias"]) if v["net"] == net]
    items += [(None, {t["layer"]}, LineString(t["pts"]).buffer(t["w"] / 2)) for t in tracks if t["net"] == net and len(t["pts"]) > 1]
    par = list(range(len(items)))
    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i][1] & items[j][1] and items[i][2].distance(items[j][2]) < 1e-3:
                par[f(i)] = f(j)
    g = defaultdict(set)
    for i, it in enumerate(items):
        if it[0]:
            g[f(i)].add(it[0])
    return frozenset(frozenset(s) for s in g.values())


tracks = R["tracks"]
by_net = defaultdict(list)
for i, t in enumerate(tracks):
    if t["layer"] == "F.Cu" and len(t["pts"]) > 1:
        by_net[t["net"]].append(i)
dropped, kept = 0, 0
remove = set()
for net, idx in by_net.items():
    vias = [Point(v["pos"]) for v in R["vias"] if v["net"] == net]
    if not vias:
        continue
    loops = [p for p in polygonize(unary_union([LineString(tracks[i]["pts"]) for i in idx]))
             if p.area < MAX_AREA and min(p.centroid.distance(v) for v in vias) < NEAR]
    if not loops:
        continue
    before = groups(net, tracks)
    for loop in loops:
        ring = loop.exterior
        cand = [i for i in idx if i not in remove and all(ring.distance(Point(q)) < 1e-3 for q in tracks[i]["pts"])]
        if not cand:
            continue
        trial = [t for k, t in enumerate(tracks) if k not in remove and k not in cand]
        if groups(net, trial) == before:
            remove.update(cand); dropped += 1
        else:
            kept += 1
R["tracks"] = [t for k, t in enumerate(tracks) if k not in remove]
json.dump(R, open(f"{D}/routing.json", "w"))
print(f"via loops dropped: {dropped} ({len(remove)} segments); kept because they carry a connection: {kept}")
