"""A600 replica routing: vectorise the original's silver traces + bridges into board copper.

Connectivity comes from netlist.py (run in-process on the same mask), so every centre-line piece inherits the
net of the conductor it lies on - geometry noise cannot create wrong connections.
Top copper (F.Cu) = silver traces.  Bottom copper (B.Cu) = printed bridges, with a via at every bridge end.
Finger traces: the scanned trace stops at the tab root (CUT_X); a straight run continues to the finger,
which tidy.py then rebuilds with the user's method (45-degree diagonal extended to the finger's y, one level line).

Usage: python replica.py <silver_geo.npy> <a600 scan-data dir>      -> writes <scan-data>/routing.json
Output coordinates: final board mm (board_geom.json frame).
"""
import contextlib
import io
import json
import os
import runpy
import sys
from collections import Counter, defaultdict
import cv2
import numpy as np
from scipy import ndimage
from shapely.geometry import LineString, Point

MASK, D = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.abspath(__file__))
_argv = sys.argv
sys.argv = ["netlist.py", MASK, D]
_buf = io.StringIO()
with contextlib.redirect_stdout(_buf):
    g = runpy.run_path(os.path.join(HERE, "netlist.py"), run_name="__main__")
sys.argv = _argv
lab, find, comp, PX, m = g["lab"], g["find"], g["comp"], g["PX"], g["m"]
pin_of_group, pads, pad_pin, NLkeys = g["pin_of_group"], g["pads"], g["pad_pin"], g["keys"]
fingers = g["fingers"]
G = json.load(open(f"{D}/board_geom.json"))
jumps = json.load(open(f"{D}/jumpers.json"))["jumpers"]

CUT_X = 200.0            # front-frame x: scanned tail traces stop here (the netlist mask is cut at 200)
TAB_Y = (144.0, 188.0)
TRACE_W, BRIDGE_W = 0.30, 0.40
NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

tr = G["transform"]
th = np.radians(tr["rot_deg"])
Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
pivot, shift = np.array(tr["pivot"]), np.array(tr["shift"])
F = lambda p: ((np.asarray(p, float) - pivot) @ Rm.T) * [1.0, tr["yscale"]] + shift

group_net = {r: str(ps[0]) for r, ps in pin_of_group.items() if len(ps) == 1}
net_of_comp = lambda c: group_net.get(find(c)) if c else None

# ---------------------------------------------------------------- centre lines
geo = m.copy()
geo[int(TAB_Y[0] * PX):int(TAB_Y[1] * PX), int(CUT_X * PX):] = 0
# pads and landing spots out of the line geometry (at their known positions - NOT "anything wide": the A600
# has ~1 mm wide traces along the edges); the lines end at their rims and are re-attached below
for p_ in pads:
    r_ = 2.7 if p_["area"] > 12 else 2.15       # LED pads are bigger
    cv2.circle(geo, (int(p_["x"] * PX), int(p_["y"] * PX)), int(r_ * PX), 0, -1)
_L = np.load(f"{D}/lands.npy")     # x, y, measured diameter
for j_ in jumps:
    for t_ in j_["taps"]:
        # A600 spots are ~2.25 mm and some are teardrop-shaped: clear the whole rim, sized from the spot itself
        k_ = int(np.argmin(np.hypot(_L[:, 0] - t_[0], _L[:, 1] - t_[1])))
        d_ = _L[k_, 2] if np.hypot(_L[k_, 0] - t_[0], _L[k_, 1] - t_[1]) < 1.0 else 2.25
        r_ = min(2.0, max(1.5, d_ / 2 + 0.6))
        cv2.circle(geo, (int(t_[0] * PX), int(t_[1] * PX)), int(r_ * PX), 0, -1)
sk = (cv2.ximgproc.thinning(geo * 255, thinningType=cv2.ximgproc.THINNING_GUOHALL) > 0).astype(np.uint8)
cnt = ndimage.convolve(sk, np.ones((3, 3), np.uint8), mode="constant") - 1
cnt[sk == 0] = 0
node = (sk > 0) & (cnt != 2)
_, nlab = cv2.connectedComponents(node.astype(np.uint8), connectivity=8)
ys, xs = np.nonzero(sk)
on = set(zip(ys.tolist(), xs.tolist()))
visited, polys = set(), []
for y0, x0 in zip(*np.nonzero(node)):
    for dy, dx in NB:
        p = (y0 + dy, x0 + dx)
        if p not in on or p in visited or nlab[p] == nlab[y0, x0] and nlab[p] != 0:
            continue
        path = [(y0, x0), p]; visited.add(p)
        cur, prv = p, (y0, x0)
        while nlab[cur] == 0:
            nxt = [(cur[0] + a, cur[1] + b) for a, b in NB if (cur[0] + a, cur[1] + b) in on
                   and (cur[0] + a, cur[1] + b) != prv and (cur[0] + a, cur[1] + b) not in visited]
            if not nxt:
                break
            nxt.sort(key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))
            prv, cur = cur, nxt[0]
            if nlab[cur] == 0:
                visited.add(cur)
            path.append(cur)
        polys.append(path)
segs = []
for path in polys:
    arr = np.array([[p[1], p[0]] for p in path], np.float32) / PX
    L = float(np.sum(np.linalg.norm(np.diff(arr, axis=0), axis=1)))
    labs = [lab[p] for p in path if lab[p] > 0]
    if not labs:
        continue
    c = Counter(labs).most_common(1)[0][0]
    poly = cv2.approxPolyDP((arr * 1000).reshape(-1, 1, 2), 40, False)[:, 0, :] / 1000
    segs.append(dict(pts=[q.tolist() for q in poly], len=L, net=net_of_comp(c), free=[cnt[path[0]] == 1, cnt[path[-1]] == 1]))
segs = [s for s in segs if not ((s["free"][0] or s["free"][1]) and s["len"] < 0.6)]
segs = [s for s in segs if s["len"] >= 0.25]
nonet = [s for s in segs if s["net"] is None]
if os.environ.get("DEBUG_NONET"):
    vis = cv2.resize(cv2.imread(f"{D}/../scan-back-mirrored-into-front-frame.png"), None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    for s_ in segs:
        cv2.polylines(vis, [(np.array(s_["pts"]) * PX / 4).astype(np.int32)], False, (0, 0, 255) if s_["net"] is None else (0, 140, 0), 3)
    cv2.imwrite(os.environ["DEBUG_NONET"], vis)
print(f"centre-line pieces: {len(segs)}, without a net: {len(nonet)} ({sum(s['len'] for s in nonet):.1f} mm, dropped)")

# ---------------------------------------------------------------- terminals to attach free ends to
term = []   # (pos, net, radius)
for i, p in enumerate(pads):
    if pad_pin[i]:
        term.append((np.array([p["x"], p["y"]]), str(pad_pin[i]), 3.8))   # trace ends sit on the carbon tab, up to ~3.5 mm out
taps = []
for j in jumps:
    cs = [comp(*t, 0.8) for t in j["taps"]]
    nets = {net_of_comp(c) for c in cs if c} - {None}
    j["net"] = nets.pop() if len(nets) == 1 else None
    for t in j["taps"]:
        taps.append((np.array(t), j["net"]))
        term.append((np.array(t), j["net"], 2.6))

tracks, free_ends = [], []
for s in segs:
    if s["net"] is None:
        continue
    pts = [np.array(p) for p in s["pts"]]
    for end, idx in ((0, 0), (1, -1)):
        if not s["free"][end]:
            continue
        pt = pts[idx]
        best = None
        for pos, nt, r in term:
            d = np.linalg.norm(pos - pt)
            if nt == s["net"] and d < r and (best is None or d < best[0]):
                best = (d, pos)
        if best is not None:
            pts.insert(0, best[1]) if end == 0 else pts.append(best[1])
        else:
            free_ends.append((len(tracks), end, pt, s["net"]))
    tracks.append(dict(net=s["net"], layer="F.Cu", w=TRACE_W, pts=pts))
used, joins = set(), 0
for i, (ti, e, p, nt) in enumerate(free_ends):
    if i in used:
        continue
    best = None
    for j, (tj, e2, q, n2) in enumerate(free_ends):
        if j <= i or j in used or n2 != nt or tj == ti:
            continue
        d = np.linalg.norm(q - p)
        if d < 2.5 and (best is None or d < best[0]):
            best = (d, j, q)
    if best:
        used |= {i, best[1]}; joins += 1
        tracks.append(dict(net=nt, layer="F.Cu", w=TRACE_W, pts=[p, best[2]]))
loose = [(round(float(p[0]), 1), round(float(p[1]), 1), nt) for i, (ti, e, p, nt) in enumerate(free_ends) if i not in used]
print(f"loose ends: {len(free_ends)}, joined in pairs: {joins}, left loose: {len(loose)}")

# finger traces: last scanned point near the cut -> straight on to the finger (rebuilt by tidy step 4)
pins = {p["pin"]: p for p in G["pins"]}
x_contact_in = G["tail"]["end_x"] - G["contact"]["from_end"] - G["contact"]["len"]
fin = 0
for i, (c, y) in enumerate(fingers):
    net = str(i + 1)
    best = None
    for t in tracks:
        if t["net"] != net or t["layer"] != "F.Cu":
            continue
        for k in (0, -1):
            q = t["pts"][k]
            if q[0] > CUT_X - 2.0 and TAB_Y[0] - 3 < q[1] < TAB_Y[1] + 3 and (best is None or q[0] > best[0]):
                best = q
    if best is None:
        print("  finger", net, "has no scanned trace reaching the tab root"); continue
    s0 = F(best)
    yp = pins[i + 1]["y"]
    tracks.append(dict(net=net, layer="F.Cu", w=TRACE_W, pts=["F", s0.tolist(), [max(s0[0] + 1.0, G["tail"]["root_x"] + 0.5), yp],
                                                              [x_contact_in + 0.6, yp]]))
    fin += 1
for t in tracks:
    if t["pts"] and isinstance(t["pts"][0], str):
        t["pts"] = t["pts"][1:]                       # already in board coordinates
    else:
        t["pts"] = [F(q).tolist() for q in t["pts"]]

# bridges -> bottom copper + vias; via must meet top copper of its net
vias = []
for j in jumps:
    if j["net"] is None:
        print("  bridge without a single net:", np.round(j["taps"], 1).tolist()); continue
    tracks.append(dict(net=j["net"], layer="B.Cu", w=BRIDGE_W, pts=[F(p).tolist() for p in j["path"]]))
    for t in j["taps"]:
        vias.append(dict(net=j["net"], pos=F(t).tolist()))
_uv = []
for v in vias:     # a spot shared by two bridges (a chain) gets one via
    if not any(u["net"] == v["net"] and np.hypot(u["pos"][0] - v["pos"][0], u["pos"][1] - v["pos"][1]) < 0.05 for u in _uv):
        _uv.append(v)
vias = _uv
top_by_net = defaultdict(list)
for t in tracks:
    if t["layer"] == "F.Cu" and len(t["pts"]) > 1:
        top_by_net[t["net"]].append(LineString(t["pts"]))
vj = 0
for v in vias:
    pv = Point(v["pos"])
    lines = top_by_net.get(v["net"], [])
    if any(l.distance(pv) < 0.05 for l in lines):
        continue
    best = None
    for l in lines:
        d = l.distance(pv)
        if d < 2.6 and (best is None or d < best[0]):
            best = (d, l.interpolate(l.project(pv)))
    if best:
        tracks.append(dict(net=v["net"], layer="F.Cu", w=TRACE_W, pts=[v["pos"], [best[1].x, best[1].y]])); vj += 1
print(f"vias joined to their top trace: {vj}")

# pad nets (key refs as in board_geom: K1.. in netlist order, LED skipped)
pad_net, n = {}, 0
for k in NLkeys:
    a, b = pads[k["a"]], pads[k["b"]]
    if np.hypot(a["x"] - b["x"], a["y"] - b["y"]) < 5.5:
        continue
    n += 1
    pad_net[f"K{n}|pad_a"], pad_net[f"K{n}|pad_b"] = str(k["pins"][0]), str(k["pins"][1])
for gk in G["keys"]:
    assert pad_net[f"{gk['ref']}|pad_a"] == gk["net_a"] and pad_net[f"{gk['ref']}|pad_b"] == gk["net_b"], gk["ref"]
print(f"tracks: top {sum(t['layer']=='F.Cu' for t in tracks)}, bottom {sum(t['layer']=='B.Cu' for t in tracks)}, "
      f"vias {len(vias)}, finger traces {fin}/31")
json.dump(dict(tracks=tracks, vias=vias, pad_net=pad_net, split={}, conflicts=[], loose=loose),
          open(f"{D}/routing.json", "w"))
