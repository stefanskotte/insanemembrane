"""Replica routing: vectorise the original membrane's silver layer + bridges into board copper.

Connectivity/nets: labelled conductor mask (pads included), joined by bridges, tail and pad joints,
checked against the skielek matrix.  Geometry: centre lines of the traces; every centre-line pixel
inherits the net of the labelled region it lies in, so geometry noise cannot create wrong connections.

Top copper (F.Cu)  = original silver traces.  Bottom copper (B.Cu) = original printed bridges,
with a via at every bridge tap.  Tail = straight 1.25 mm-pitch traces from the scan cut to the contacts.

Usage: python replica.py <project dir> <conn_mask.npy> <out routing.json> [geo_mask.npy]
Output coordinates: FINAL BOARD mm (same frame as board_geom.json).
"""
import json
import sys
from collections import defaultdict, Counter, deque
import cv2
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

PX = 600 / 25.4
proj, mask_path, OUT = sys.argv[1:4]
GEO_MASK = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4].endswith('.npy') else mask_path
D = f"{proj}/a1200/docs/scan-data"
G = json.load(open(f"{D}/board_geom.json"))
km = json.load(open(f"{D}/keymap.json"))
jumps = json.load(open(f"{D}/jumpers.json"))["jumpers"]
manual = json.load(open(f"{D}/manual_traces.json"))["traces"]

TAIL_CUT_X = 166.0          # front-frame x: scanned tail traces stop here, synthetic ones continue
TAIL_Y = (146.0, 190.5)
TRACE_W = 0.30
NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

tr = G["transform"]
th = np.radians(-tr["tilt_deg"])
Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
pivot, shift = np.array(tr["pivot"]), np.array(tr["shift"])
F = lambda p: ((np.asarray(p, float) - pivot) @ Rm.T) * [1.0, tr["yscale"]] + shift

# ---------------------------------------------------------------- conductor mask + labels
m = np.load(mask_path).astype(np.uint8)
for t in manual:
    cv2.polylines(m, [(np.array(t["path"]) * PX).astype(np.int32)], False, 1, int(0.35 * PX))
m[:, int(TAIL_CUT_X * PX):] = 0
cond = cv2.erode(m, np.ones((5, 5), np.uint8))           # separates traces that touch in the scan
n, lab = cv2.connectedComponents(cond, 8)


def comp(x, y, r):
    X, Y, R = int(x * PX), int(y * PX), max(1, int(r * PX))
    w = lab[Y - R:Y + R + 1, X - R:X + R + 1]
    c = Counter(w[w > 0].ravel().tolist()).most_common(1)
    return c[0][0] if c else 0


parent = {}
def find(a):
    parent.setdefault(a, a)
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
def union(a, b):
    parent[find(a)] = find(b)


nets_of = {k["ref"]: set(s.strip("/") for s in k["nets"]) for k in km["keys"]}
terms = []   # (name, comp, expected nets, pos)
for k in km["keys"]:
    for side in ("pad_a", "pad_b"):
        terms.append((f"{k['ref']}|{side}", comp(*k[side], 0.9), nets_of[k["ref"]], np.array(k[side])))
led = km["unassigned_pairs"][0]
terms.append(("LED|0", comp(*led[0], 0.9), {"31"}, np.array(led[0])))
terms.append(("LED|1", comp(*led[1], 0.9), {"9"}, np.array(led[1])))

# tail: components crossing the cut line, sorted by y -> pin 1..31 (pin 1 = smallest y)
col = lab[int(TAIL_Y[0] * PX):int(TAIL_Y[1] * PX), int((TAIL_CUT_X - 0.8) * PX)]
tail = []
prev = 0
for i, c in enumerate(col):
    if c and c != prev and (not tail or tail[-1][0] != c):
        tail.append((int(c), TAIL_Y[0] + i / PX))
    prev = c
print(f"tail traces at the cut line: {len(tail)} (expect 31)")
for p, (c, y) in enumerate(tail[:31]):
    terms.append((f"pin{p+1}", c, {str(p + 1)}, np.array([TAIL_CUT_X - 0.8, y])))

# bridges: join all taps of a bridge
jtaps = []
for ji, jm in enumerate(jumps):
    tp = jm.get("taps") or [jm["path"][0], jm["path"][-1]]
    cs = [comp(*t, 0.8) for t in tp]
    jtaps.append((tp, cs))
    good = [c for c in cs if c]
    for c in good[1:]:
        union(good[0], c)
for c in range(1, n):
    find(c)

# pads whose own region touches no trace: join the trace component that ends within 0.45 mm of it
def group_terms():
    gt = defaultdict(list)
    for name, c, e, pos in terms:
        if c:
            gt[find(c)].append((name, e))
    return gt


gt = group_terms()
isolated = [(name, c, e, pos) for name, c, e, pos in terms if c and len(gt[find(c)]) == 1 and not name.startswith("pin")]


def decided_net(cc):
    items = gt.get(find(cc), [])
    if not items:
        return None
    inter = set.intersection(*(ee for _, ee in items))
    return next(iter(inter)) if len(inter) == 1 else None


pad_joints = []
by_name = {name: (c, e, pos) for name, c, e, pos in terms}
for name, c, e, pos in isolated:
    req = set(e)
    if "|" in name and not name.startswith("LED"):
        ref, side = name.split("|")
        other = by_name[f"{ref}|{'pad_b' if side == 'pad_a' else 'pad_a'}"]
        on_ = decided_net(other[0]) if other[0] else None
        if on_:
            req = set(e) - {on_}
    own = (lab == c)
    ring = cv2.dilate(own.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(1.2 * PX),) * 2)) > 0
    cand = Counter(lab[ring & ~own & (lab > 0)].ravel().tolist())
    ok = []
    for cc, k in cand.items():
        dn = decided_net(cc)
        if k > 3 and dn is not None and dn in req:
            ys_, xs_ = np.nonzero((lab == cc) & ring)
            dmin = np.min(np.hypot(xs_ / PX - pos[0], ys_ / PX - pos[1]))
            ok.append((dmin, cc))
    if ok:
        ok.sort()
        union(c, ok[0][1]); pad_joints.append((name, c, ok[0][1]))
    else:
        print(f"  pad joint unresolved: {name} (needs net {sorted(req)}), candidates {len(cand)}")
print(f"pad joints closed across the carbon rim: {len(pad_joints)} of {len(isolated)}")

gt = group_terms()
group_net, conflicts, undecided = {}, [], []
for g, items in gt.items():
    inter = set.intersection(*(e for _, e in items))
    if len(inter) == 1:
        group_net[g] = next(iter(inter))
    elif not inter:
        conflicts.append([nm for nm, _ in items])
    else:
        undecided.append([nm for nm, _ in items])
net_groups = defaultdict(set)
for g, nt in group_net.items():
    net_groups[nt].add(g)
split = {k: len(v) for k, v in net_groups.items() if len(v) > 1}
print(f"conflicts: {len(conflicts)}, undecided terminals: {len(undecided)}, nets in >1 piece: {split}")
for c_ in conflicts:
    print("  CONFLICT", c_[:8])
for u in undecided:
    print("  UNDECIDED", u)

# ---------------------------------------------------------------- centre lines (geometry only)
thick = cv2.morphologyEx(m, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(1.2 * PX),) * 2))
gm = np.load(GEO_MASK).astype(np.uint8)
for t in manual:
    cv2.polylines(gm, [(np.array(t["path"]) * PX).astype(np.int32)], False, 1, int(0.35 * PX))
gm[:, int(TAIL_CUT_X * PX):] = 0
geo = cv2.erode(gm, np.ones((5, 5), np.uint8)) & cond
geo[cv2.dilate(thick, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.25 * PX),) * 2)) > 0] = 0
sk = (cv2.ximgproc.thinning(geo * 255, thinningType=cv2.ximgproc.THINNING_GUOHALL) > 0).astype(np.uint8)
cnt = ndimage.convolve(sk, np.ones((3, 3), np.uint8), mode="constant") - 1
cnt[sk == 0] = 0
node = (sk > 0) & (cnt != 2)
nlab_n, nlab = cv2.connectedComponents(node.astype(np.uint8), connectivity=8)
ys, xs = np.nonzero(sk)
on = set(zip(ys.tolist(), xs.tolist()))
visited = set()
polys = []
for y0, x0 in zip(*np.nonzero(node)):
    for dy, dx in NB:
        p = (y0 + dy, x0 + dx)
        if p not in on or p in visited or nlab[p] == nlab[y0, x0] and nlab[p] != 0:
            continue
        path = [(y0, x0), p]
        visited.add(p)
        cur, prv = p, (y0, x0)
        while nlab[cur] == 0:
            nxt = [(cur[0] + a, cur[1] + b) for a, b in NB if (cur[0] + a, cur[1] + b) in on
                   and (cur[0] + a, cur[1] + b) != prv and (cur[0] + a, cur[1] + b) not in visited]
            if not nxt:
                break
            # prefer 4-neighbours to stay on the line
            nxt.sort(key=lambda q: abs(q[0] - cur[0]) + abs(q[1] - cur[1]))
            prv, cur = cur, nxt[0]
            if nlab[cur] == 0:
                visited.add(cur)
            path.append(cur)
        polys.append(path)
# closed loops without nodes are ignored (none expected on a membrane)
print(f"centre-line pieces: {len(polys)}")

segs = []
for path in polys:
    arr = np.array([[p[1], p[0]] for p in path], np.float32) / PX
    L = float(np.sum(np.linalg.norm(np.diff(arr, axis=0), axis=1)))
    # net from the labelled conductor under the line (majority vote)
    labs = [lab[p] for p in path if lab[p] > 0]
    if not labs:
        continue
    c = Counter(labs).most_common(1)[0][0]
    net = group_net.get(find(c))
    end_free = [cnt[path[0]] == 1, cnt[path[-1]] == 1]
    poly = cv2.approxPolyDP((arr * 1000).reshape(-1, 1, 2), 50, False)[:, 0, :] / 1000
    segs.append(dict(pts=[q.tolist() for q in poly], len=L, net=net, comp=int(c), free=end_free))
if len(sys.argv) > 5:   # DEBUG_ORPHANS: draw pieces without a net
    vis = cv2.resize(cv2.imread(f"{proj}/a1200/docs/scan-front-stitched.png"), None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    for s_ in segs:
        col = (0, 0, 255) if s_["net"] is None else (0, 160, 0)
        cv2.polylines(vis, [(np.array(s_["pts"]) * PX / 4).astype(np.int32)], False, col, 2)
    cv2.imwrite(sys.argv[5], vis)
# drop short dangling spurs (thinning artefacts at blob edges)
segs = [s for s in segs if not ((s["free"][0] or s["free"][1]) and s["len"] < 0.7)]
segs = [s for s in segs if s["len"] >= 0.3]
nonet = sum(1 for s in segs if s["net"] is None)
print(f"pieces kept: {len(segs)}, without a net: {nonet} (total length {sum(s['len'] for s in segs if s['net'] is None):.1f} mm)")

# ---------------------------------------------------------------- attach free ends (net-aware)
pad_net_now = {}
for name, c, e, pos in terms:
    if "|" in name:
        pad_net_now[name] = group_net.get(find(c)) if c else None
pads_pos = [(name, pos, pad_net_now.get(name)) for name, c, e, pos in terms if "|" in name]
tap_pos = []
for ji, (tp, cs) in enumerate(jtaps):
    jn = {group_net.get(find(c)) for c in cs if c} - {None}
    for t in tp:
        tap_pos.append((ji, np.array(t), next(iter(jn)) if len(jn) == 1 else None))
tracks = []
free_ends = []   # (track idx, end, point, net)
for s in segs:
    if s["net"] is None:
        continue
    pts = [np.array(p) for p in s["pts"]]
    for end, idx in ((0, 0), (1, -1)):
        if not s["free"][end]:
            continue
        pt = pts[idx]
        best = None
        for name, pos, pn in pads_pos:
            d = np.linalg.norm(pos - pt)
            if pn == s["net"] and d < 3.2 and (best is None or d < best[0]):
                best = (d, pos)
        for ji, pos, jn in tap_pos:
            d = np.linalg.norm(pos - pt)
            if jn == s["net"] and d < 1.9 and (best is None or d < best[0]):
                best = (d, pos)
        if best is not None:
            if end == 0:
                pts.insert(0, best[1])
            else:
                pts.append(best[1])
        else:
            free_ends.append((len(tracks), end, pt, s["net"]))
    tracks.append(dict(net=s["net"], layer="F.Cu", w=TRACE_W, pts=[q for q in pts]))
# join facing loose ends of the same net (breaks in the scanned trace)
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
print(f"loose ends: {len(free_ends)}, joined in pairs: {joins}, left loose: {len(free_ends) - 2 * joins}")
for t in tracks:
    t["pts"] = [F(q).tolist() for q in t["pts"]]

# bridges -> bottom copper + vias
vias = []
for ji, (jm, (tp, cs)) in enumerate(zip(jumps, jtaps)):
    nets = {group_net.get(find(c)) for c in cs if c} - {None}
    if len(nets) != 1:
        print("  bridge without a single net:", ji, nets, np.round(tp, 1).tolist())
        continue
    net = nets.pop()
    path = np.array(jm["path"], np.float32)
    path = cv2.approxPolyDP((path * 1000).reshape(-1, 1, 2), 400, False)[:, 0, :] / 1000
    tracks.append(dict(net=net, layer="B.Cu", w=0.40, pts=[F(p).tolist() for p in path]))
    for t in tp:
        vias.append(dict(net=net, pos=F(t).tolist()))

# every via must meet top copper of its net: if no top track touches it, join the nearest same-net point
from shapely.geometry import LineString as _LS, Point as _P
top_by_net = defaultdict(list)
for t in tracks:
    if t["layer"] == "F.Cu" and len(t["pts"]) > 1:
        top_by_net[t["net"]].append(_LS(t["pts"]))
via_joins = 0
for v in vias:
    pv = _P(v["pos"])
    lines = top_by_net.get(v["net"], [])
    if any(l.distance(pv) < 0.05 for l in lines):
        continue
    best = None
    for l in lines:
        d = l.distance(pv)
        if d < 2.6 and (best is None or d < best[0]):
            best = (d, l.interpolate(l.project(pv)))
    if best:
        tracks.append(dict(net=v["net"], layer="F.Cu", w=TRACE_W, pts=[v["pos"], [best[1].x, best[1].y]]))
        via_joins += 1
print(f"vias joined to their top trace: {via_joins}")

# tail: scanned trace end at the cut -> straight run to the contact
pins = {p["pin"]: p for p in G["pins"]}
x_contact_inner = G["tail"]["end_x"] - 0.35 - 6.35
tail_tracks = 0
for p, (c, y) in enumerate(tail[:31]):
    ys_, xs_ = np.nonzero(sk[int((y - 1) * PX):int((y + 1) * PX), int((TAIL_CUT_X - 3) * PX):int((TAIL_CUT_X - 0.3) * PX)])
    if len(xs_) == 0:
        start = np.array([TAIL_CUT_X - 1.0, y])
    else:
        k = np.argmax(xs_)
        start = np.array([(xs_[k] + int((TAIL_CUT_X - 3) * PX)) / PX, (ys_[k] + int((y - 1) * PX)) / PX])
    s0 = F(start)
    yp = pins[p + 1]["y"]
    x_join = max(s0[0] + 3.0, G["tail"]["root_x"] + 3.0)
    tracks.append(dict(net=str(p + 1), layer="F.Cu", w=TRACE_W, pts=[s0.tolist(), [x_join, yp], [x_contact_inner + 0.6, yp]]))
    tail_tracks += 1

# pad nets as routed
pad_net = {}
for name, c, e, pos in terms:
    if "|" in name:
        pad_net[name] = group_net.get(find(c)) if c else None
for k in km["keys"]:
    a, b = f"{k['ref']}|pad_a", f"{k['ref']}|pad_b"
    ns = sorted(nets_of[k["ref"]])
    if pad_net.get(a) is None and pad_net.get(b):
        pad_net[a] = ns[0] if pad_net[b] == ns[1] else ns[1]
    if pad_net.get(b) is None and pad_net.get(a):
        pad_net[b] = ns[0] if pad_net[a] == ns[1] else ns[1]
print(f"tracks: top {sum(t['layer']=='F.Cu' for t in tracks)}, bottom {sum(t['layer']=='B.Cu' for t in tracks)}, "
      f"vias {len(vias)}, tail traces {tail_tracks}; pads with a routed net {sum(v is not None for v in pad_net.values())}/{len(pad_net)}")
json.dump(dict(tracks=tracks, vias=vias, pad_net=pad_net, split=split, conflicts=conflicts), open(OUT, "w"))
