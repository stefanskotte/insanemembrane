"""A600: pair landing spots into crossover bridges by testing the straight line between them.

On the A600 the traces crossing a bridge merge neighbouring bars in any blob mask, so instead each candidate
pair of landing spots (2-45 mm apart) is tested directly: along the line between them the front scan must be
bar-dark at the centre AND +-0.3 mm to each side (a bar is ~0.9 mm wide, a trace ~0.4 mm), for >= 96 % of it.
Pairs whose line passes another landing spot are skipped (those are chains, found as two shorter pairs).
Manual bridges (bent ones): a600/docs/scan-data/manual_jumpers.json {"jumpers": [{"path": [[x,y],...], "note": ""}]}.
Usage: python bridges.py <front.png> <lands.npy> <scan-data dir> [debug.png]
"""
import json
import sys
import cv2
import numpy as np

PX = 600 / 25.4
f = cv2.imread(sys.argv[1])
L = np.load(sys.argv[2])[:, :2]
D = sys.argv[3]
hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV).astype(np.int16)
dark = ((hsv[..., 2] < 160) & (hsv[..., 1] > 80) & (hsv[..., 0] > 72) & (hsv[..., 0] < 100))
# fill pin-holes so a bar is solid
dark = cv2.morphologyEx(dark.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)) > 0


def score(a, b):
    v = b - a
    Ln = np.linalg.norm(v)
    u = v / Ln
    n = np.array([-u[1], u[0]])
    ts = np.arange(1.0, Ln - 1.0, 0.1)
    if len(ts) < 3:
        return 0.0
    ok = 0
    for t in ts:
        p = a + u * t
        good = True
        for off in (0.0, -0.3, 0.3):
            q = (p + n * off) * PX
            if not dark[int(round(q[1])), int(round(q[0]))]:
                good = False
                break
        ok += good
    return ok / len(ts)


cand = []
for i in range(len(L)):
    for j in range(i + 1, len(L)):
        d = np.linalg.norm(L[i] - L[j])
        if not 2.0 < d < 45.0:
            continue
        # skip if another land lies on the segment
        v = L[j] - L[i]
        t = np.clip(((L - L[i]) @ v) / (v @ v), 0, 1)
        dist = np.linalg.norm(L[i] + t[:, None] * v - L, axis=1)
        dist[[i, j]] = 99
        if dist.min() < 1.0:
            continue
        s = score(L[i], L[j])
        if s >= 0.96:
            cand.append((s, d, i, j))
cand.sort(key=lambda c: (-c[0], c[1]))
deg = np.zeros(len(L), int)
pairs = []
for s, d, i, j in cand:
    if deg[i] >= 2 or deg[j] >= 2:
        continue
    pairs.append((i, j, s)); deg[i] += 1; deg[j] += 1
try:
    manual = json.load(open(f"{D}/manual_jumpers.json"))["jumpers"]
except FileNotFoundError:
    manual = []
for m_ in manual:
    for e in (m_["path"][0], m_["path"][-1]):
        deg[np.argmin(np.linalg.norm(L - np.array(e), axis=1))] += 1
# ---- pass 2: bent bridges between leftover spots: shortest path through the bar core --------------------
from collections import deque
DS = 3
core = cv2.erode(dark.astype(np.uint8), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.55 * PX),) * 2))
cs = cv2.resize(core, (core.shape[1] // DS, core.shape[0] // DS), interpolation=cv2.INTER_NEAREST)
left = [k for k in range(len(L)) if deg[k] == 0]
NB8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def bfs(k, rad_mm=40):
    sx, sy = (L[k] * PX / DS).astype(int)
    R = int(rad_mm * PX / DS)
    y0, x0 = max(0, sy - R), max(0, sx - R)
    sub = cs[y0:sy + R, x0:sx + R].copy()
    # landing spots themselves are round and solid: open a disc around every leftover spot
    for q in left:
        qx, qy = (L[q] * PX / DS).astype(int) - [x0, y0]
        if 0 <= qx < sub.shape[1] and 0 <= qy < sub.shape[0]:
            cv2.circle(sub, (int(qx), int(qy)), int(0.8 * PX / DS), 1, -1)
    dist = np.full(sub.shape, -1, np.int32); prev = {}
    st_ = (sy - y0, sx - x0); dist[st_] = 0; dq = deque([st_])
    while dq:
        p = dq.popleft()
        for dy, dx in NB8:
            q = (p[0] + dy, p[1] + dx)
            if 0 <= q[0] < sub.shape[0] and 0 <= q[1] < sub.shape[1] and sub[q] and dist[q] < 0:
                dist[q] = dist[p] + 1; prev[q] = p; dq.append(q)
    return dist, prev, (x0, y0)


reach = {}
for k in left:
    dist, prev, (x0, y0) = bfs(k)
    for q in left:
        if q == k:
            continue
        qx, qy = (L[q] * PX / DS).astype(int) - [x0, y0]
        if 0 <= qx < dist.shape[1] and 0 <= qy < dist.shape[0] and dist[qy, qx] > 0:
            plen = dist[qy, qx] * DS / PX
            path = [(qy, qx)]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            arr = np.array([((x + x0) * DS / PX, (y + y0) * DS / PX) for y, x in path[::-1]], np.float32)
            reach[(k, q)] = (plen, arr)
bent = []
for (k, q), (plen, arr) in sorted(reach.items(), key=lambda kv: kv[1][0]):
    if deg[k] or deg[q] or k > q and (q, k) in reach:
        continue
    if plen > 1.8 * np.linalg.norm(L[k] - L[q]) + 3:
        continue
    poly = cv2.approxPolyDP((arr * 100).reshape(-1, 1, 2), 30, False)[:, 0, :] / 100
    poly = poly.tolist(); poly[0], poly[-1] = L[k].tolist(), L[q].tolist()
    bent.append(dict(path=poly, taps=[L[k].tolist(), L[q].tolist()], source="bent", length=round(plen, 1)))
    deg[k] += 1; deg[q] += 1
print(f"bent bridges found through the bar core: {len(bent)}")
for b_ in bent:
    print("   ", np.round(b_["taps"], 1).tolist(), "path length", b_["length"])

final = [dict(path=[L[i].tolist(), L[j].tolist()], taps=[L[i].tolist(), L[j].tolist()], source="auto", score=round(s, 3))
         for i, j, s in pairs] + bent
for m in manual:
    final.append(dict(path=m["path"], taps=m.get("taps") or [m["path"][0], m["path"][-1]], source="manual", note=m.get("note", "")))
covered = [np.array(t) for j in final for t in j["taps"]]
unhandled = [L[k].tolist() for k in range(len(L)) if all(np.linalg.norm(L[k] - c) > 1.0 for c in covered)]
print(f"straight bridges {len(pairs)} (spots used twice = chains: {int((deg == 2).sum())}), manual {len(manual)}; "
      f"landing spots unhandled: {len(unhandled)}")
for u in unhandled:
    print("   ", np.round(u, 1).tolist())
json.dump(dict(jumpers=final, unhandled=unhandled), open(f"{D}/jumpers.json", "w"), indent=1)
if len(sys.argv) > 4:
    vis = cv2.resize(f, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    for j in final:
        cv2.polylines(vis, [(np.array(j["path"]) * PX / 4).astype(np.int32)], False, (0, 0, 255), 2)
    for u in unhandled:
        cv2.circle(vis, tuple((np.array(u) * PX / 4).astype(int)), 10, (255, 0, 255), 2)
    cv2.imwrite(sys.argv[4], vis)
