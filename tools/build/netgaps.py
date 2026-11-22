"""List each net's unconnected copper pieces and the gap between them (any routing stage).
Usage: python netgaps.py <scan-data dir> [routing.json] [pads_final.json]"""
import json, sys
from collections import defaultdict
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import nearest_points
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from geomlib import contact_items, led_items
D = sys.argv[1]
R = json.load(open(sys.argv[2] if len(sys.argv) > 2 else f"{D}/routing.json"))
P = json.load(open(sys.argv[3] if len(sys.argv) > 3 else f"{D}/pads_final.json"))["pads"]
G = json.load(open(f"{D}/board_geom.json"))
items = defaultdict(list)   # net -> [(layerset, geom, label)]
for t in R["tracks"]:
    if len(t["pts"]) > 1:
        items[t["net"]].append(({t["layer"]}, LineString(t["pts"]).buffer(t["w"] / 2), f"{t['layer']} track"))
for v in R["vias"]:
    items[v["net"]].append(({"F.Cu", "B.Cu"}, Point(v["pos"]).buffer(0.35), "via"))
for p in P:
    items[p["net"]].append(({"F.Cu"}, Polygon(p["poly"]), f"pad {p['ref']}.{p['num']}"))
for n, g in contact_items(G) + led_items(G):
    items[n].append(({"F.Cu"}, g, "contact/LED"))
total = 0
for net, its in sorted(items.items(), key=lambda kv: int(kv[0])):
    par = list(range(len(its)))
    def f(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    for i in range(len(its)):
        for j in range(i + 1, len(its)):
            if its[i][0] & its[j][0] and its[i][1].distance(its[j][1]) < 1e-3:
                par[f(i)] = f(j)
    groups = defaultdict(list)
    for i in range(len(its)):
        groups[f(i)].append(i)
    if len(groups) < 2:
        continue
    gl = list(groups.values())
    main = max(gl, key=len)
    for g in gl:
        if g is main:
            continue
        total += 1
        best = None
        for i in g:
            for j in main:
                d = its[i][1].distance(its[j][1])
                if best is None or d < best[0]:
                    best = (d, i, j)
        d, i, j = best
        a, b = nearest_points(its[i][1], its[j][1])
        print(f"net {net:>2}: piece of {len(g)} ({its[i][2]}) {d:.2f} mm from the rest ({its[j][2]}) at ({a.x:.1f},{a.y:.1f})")
print("separate pieces:", total)
