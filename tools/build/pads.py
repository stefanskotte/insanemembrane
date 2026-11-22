"""Per-pad extension toward the partner pad (max 0.75 mm) and coverlay window, limited by the routing.

The original routes traces between many pad pairs, so the extension is the largest of
0.75 / 0.5 / 0.25 / 0 mm that keeps 0.25 mm copper clearance to other-net top traces.
Coverlay window margin = min(0.30, clearance - 0.05), so a window never exposes another net.
Usage: python pads.py <scan-data dir>   -> writes pads_final.json
"""
import json
import sys
import numpy as np
from shapely.geometry import LineString, Polygon, Point
from shapely.strtree import STRtree

D = sys.argv[1]
G = json.load(open(f"{D}/board_geom.json"))
R = json.load(open(f"{D}/routing.json"))
pd = G["pad"]
AWAY, TOWARD0, HW, CH = pd["away"], pd.get("toward0", 1.27), pd["half_w"], pd["chamfer"]
CLEAR = 0.25

geoms, gnet = [], []
for t in R["tracks"]:
    if t["layer"] != "F.Cu" or len(t["pts"]) < 2:
        continue
    geoms.append(LineString(t["pts"]).buffer(t["w"] / 2, cap_style=1)); gnet.append(t["net"])
tree = STRtree(geoms)


def pad_poly(c, u, toward):
    v = np.array([-u[1], u[0]])
    loc = [(-AWAY + CH, -HW), (toward - CH, -HW), (toward, -HW + CH), (toward, HW - CH), (toward - CH, HW),
           (-AWAY + CH, HW), (-AWAY, HW - CH), (-AWAY, -HW + CH)]
    return Polygon([c + a * u + b * v for a, b in loc])


def other_dist(poly, net):
    best = 99.0
    for i in tree.query(poly.buffer(1.0)):
        if gnet[i] != net:
            best = min(best, poly.distance(geoms[i]))
    return best


out, stats = [], {0.75: 0, 0.5: 0, 0.25: 0, 0.0: 0}
tight = []
for k in G["keys"]:
    a, b = np.array(k["a"]), np.array(k["b"])
    u = (b - a) / np.linalg.norm(b - a)
    for c, uu, net, num in ((a, u, R["pad_net"][f"{k['ref']}|pad_a"], "1"), (b, -u, R["pad_net"][f"{k['ref']}|pad_b"], "2")):
        chosen = None
        for ext in (0.75, 0.5, 0.25, 0.0):
            poly = pad_poly(c, uu, TOWARD0 + ext)
            d = other_dist(poly, net)
            if d >= CLEAR:
                chosen = (ext, poly, d); break
        if chosen is None:
            poly = pad_poly(c, uu, TOWARD0)
            chosen = (0.0, poly, other_dist(poly, net))
            tight.append((k["name"], num, round(chosen[2], 3)))
        ext, poly, d = chosen
        stats[ext] += 1
        mask = float(np.clip(d - 0.05, 0.0, 0.30))
        out.append(dict(ref=k["ref"], num=num, net=net, ext=ext, mask=mask, clearance=d,
                        centre=(c + uu * ((TOWARD0 + ext) - AWAY) / 2).tolist(),
                        length=AWAY + TOWARD0 + ext, angle=float(np.degrees(np.arctan2(uu[1], uu[0]))),
                        poly=[list(p) for p in poly.exterior.coords]))
print("pad extensions:", {f"{k} mm": v for k, v in stats.items()})
print("pads closer than 0.25 mm to another net even unextended:", tight)
masks = np.array([p["mask"] for p in out])
print(f"coverlay window margin: full 0.30 on {np.sum(masks >= 0.299)} pads, reduced on {np.sum(masks < 0.299)} (min {masks.min():.2f})")
json.dump(dict(pads=out), open(f"{D}/pads_final.json", "w"), indent=1)
