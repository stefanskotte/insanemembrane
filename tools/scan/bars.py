"""Find crossover bridges as wide dark bars on the front scan; each bar's ends are its connection points.

Traces are ~0.35 mm wide, bridge bars ~1.2 mm: opening with a ~0.85 mm disc keeps only bars (+ round
landing spots). Each bar is thinned to a centre-line graph; short spurs are pruned; the remaining
end points are where the bridge touches the silver layer.
Usage: python bars.py <front.png> <keymap.json> <out.json> [debug.png]
"""
import json
import sys
from collections import defaultdict, deque
import cv2
import numpy as np

PX = 600 / 25.4
f = cv2.imread(sys.argv[1])
km = json.load(open(sys.argv[2]))
hf = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
H, S, V = [hf[..., i].astype(int) for i in range(3)]
dark = ((V < 158) & (S > 80) & (H > 72) & (H < 100)).astype(np.uint8)
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.85 * PX), int(0.85 * PX)))
bars = cv2.morphologyEx(dark, cv2.MORPH_OPEN, k)
bars[:, int(161.0 * PX):] = 0   # tail + dark reinforcement strips at the tail root are not bridges
n, lab, st, ce = cv2.connectedComponentsWithStats(bars, 8)
NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def graph(sk):
    pts = set(map(tuple, np.argwhere(sk)))
    deg = {p: sum((p[0] + dy, p[1] + dx) in pts for dy, dx in NB) for p in pts}
    return pts, deg


def prune(sk, min_len):
    """remove end branches shorter than min_len pixels (repeat until stable)"""
    for _ in range(4):
        pts, deg = graph(sk)
        ends = [p for p, d in deg.items() if d == 1]
        changed = False
        for e in ends:
            path = [e]; prev = None; cur = e
            while True:
                nbs = [(cur[0] + dy, cur[1] + dx) for dy, dx in NB if (cur[0] + dy, cur[1] + dx) in pts and (cur[0] + dy, cur[1] + dx) != prev]
                nbs = [q for q in nbs if q not in path]
                if len(nbs) != 1 or deg.get(nbs[0], 0) > 2:
                    break
                prev, cur = cur, nbs[0]; path.append(cur)
                if len(path) > min_len:
                    break
            if len(path) <= min_len and len(pts) > len(path) + 5:
                for p in path:
                    sk[p] = False
                changed = True
        if not changed:
            break
    return sk


def polyline(sk, a, b):
    prev = {a: None}; q = deque([a])
    while q:
        p = q.popleft()
        if p == b:
            break
        for dy, dx in NB:
            nb = (p[0] + dy, p[1] + dx)
            if 0 <= nb[0] < sk.shape[0] and 0 <= nb[1] < sk.shape[1] and sk[nb] and nb not in prev:
                prev[nb] = p; q.append(nb)
    path = []; p = b
    while p is not None:
        path.append(p); p = prev.get(p)
    return path[::-1]


DS = 3  # work at 200 dpi for the geodesic search


def geodesic(mask, src):
    dist = np.full(mask.shape, -1, np.int32); prev = {}
    dist[src] = 0; q = deque([src])
    while q:
        p = q.popleft()
        for dy, dx in NB:
            nb = (p[0] + dy, p[1] + dx)
            if 0 <= nb[0] < mask.shape[0] and 0 <= nb[1] < mask.shape[1] and mask[nb] and dist[nb] < 0:
                dist[nb] = dist[p] + 1; prev[nb] = p; q.append(nb)
    return dist, prev


def trace_back(prev, src, dst):
    path = [dst]
    while path[-1] != src:
        path.append(prev[path[-1]])
    return path[::-1]


out = []
skipped = []
for c in range(1, n):
    x0, y0, w, h, area = st[c]
    amm = area / PX ** 2
    if amm < 3.0:
        continue
    m = (lab[y0:y0 + h, x0:x0 + w] == c).astype(np.uint8)
    md = cv2.resize(m, (max(1, w // DS), max(1, h // DS)), interpolation=cv2.INTER_NEAREST)
    pts = np.argwhere(md)
    if len(pts) == 0:
        continue
    d0, _ = geodesic(md, tuple(pts[0]))
    A = tuple(np.unravel_index(np.argmax(d0), d0.shape))
    dA, prevA = geodesic(md, A)
    B = tuple(np.unravel_index(np.argmax(dA), dA.shape))
    Lmm = dA[B] * DS / PX
    width = amm / max(Lmm, 0.1)
    if amm > 250 or width > 2.6 or Lmm < 2.5:
        skipped.append((round(float(ce[c][0] / PX), 1), round(float(ce[c][1] / PX), 1), round(amm, 1), round(width, 2)))
        continue
    dB, prevB = geodesic(md, B)
    ends = [A, B]
    mind = np.minimum(np.where(dA >= 0, dA, 10**9), np.where(dB >= 0, dB, 10**9))
    mind[md == 0] = -1
    C = tuple(np.unravel_index(np.argmax(mind), mind.shape))
    # third end: far from both A and B and not on the A-B path (beyond 3 mm off the path)
    pathAB = trace_back(prevA, A, B)
    on = np.zeros_like(md); [on.__setitem__(p, 1) for p in pathAB]
    don = cv2.distanceTransform((1 - on).astype(np.uint8), cv2.DIST_L2, 3)
    if don[C] * DS / PX > 3.0:
        ends.append(C)
    to_mm = lambda q: ((q[1] * DS + x0 + DS / 2) / PX, (q[0] * DS + y0 + DS / 2) / PX)
    paths = []
    for e in ends[1:]:
        pp = trace_back(prevA, A, e)
        arr = np.array([to_mm(q) for q in pp], np.float32)
        poly = cv2.approxPolyDP((arr * 100).reshape(-1, 1, 2), 20, False)[:, 0, :] / 100
        paths.append(poly.tolist())
    out.append(dict(bar=int(c), ends=[to_mm(e) for e in ends], paths=paths, width_mm=round(width, 2), length_mm=round(Lmm, 1)))
print("skipped (not bar-like):", skipped)
print(f"bars: {len(out)}; ends per bar: {dict(sorted(defaultdict(int, {k_: sum(len(o['ends']) == k_ for o in out) for k_ in range(2, 7)}).items()))}")
json.dump(dict(bars=out), open(sys.argv[3], "w"), indent=1)

if len(sys.argv) > 4:
    vis = cv2.resize(f, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    vis[cv2.resize(bars, None, fx=0.25, fy=0.25) > 0] = (0, 200, 255)
    for o in out:
        for p in o["paths"]:
            cv2.polylines(vis, [(np.array(p) * PX / 4).astype(np.int32)], False, (0, 0, 255), 2)
        for e in o["ends"]:
            cv2.circle(vis, tuple((np.array(e) * PX / 4).astype(int)), 6, (255, 0, 0), 2)
    cv2.imwrite(sys.argv[4], vis)
