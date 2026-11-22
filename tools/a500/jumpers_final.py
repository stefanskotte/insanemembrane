"""A500: final bridge (jumper) list = automatic clean pairs + hand-read ones.

Automatic: a wide-bar component on the front scan containing exactly two landing spots.
Manual: docs/scan-data/manual_jumpers.json, each {"path": [[x,y],...], "note": "..."} in front-frame mm,
read off gridded close-ups. Manual entries replace automatic ones that share a landing spot.
Usage: python jumpers_final.py <front.png> <lands.npy> <scan-data dir>
"""
import json
import sys
import cv2
import numpy as np

PX = 600 / 25.4
BAR_DISC = 0.60   # A500 bars are ~0.9 mm wide (A1200: ~1.2 mm, disc 0.85)
f = cv2.imread(sys.argv[1])
lands = np.load(sys.argv[2])[:, :2]
D = sys.argv[3]
hf = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
H, S, V = [hf[..., i].astype(int) for i in range(3)]
dark = ((V < 158) & (S > 80) & (H > 72) & (H < 100)).astype(np.uint8)
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(BAR_DISC * PX), int(BAR_DISC * PX)))
bars = cv2.morphologyEx(dark, cv2.MORPH_OPEN, k)
n, lab = cv2.connectedComponents(bars, 8)

members = {}
for li, (x, y) in enumerate(lands):
    X, Y, R = int(x * PX), int(y * PX), int(0.6 * PX)
    w = lab[Y - R:Y + R, X - R:X + R]
    vals, cnt = np.unique(w[w > 0], return_counts=True)
    members.setdefault(int(vals[cnt.argmax()]) if len(vals) else 0, []).append(li)

from collections import deque
NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
DS = 3


def geo_path(c, p, q):
    """centre-ish path inside bar component c from point p to q (mm), simplified"""
    ys, xs = np.where(lab == c)
    x0, y0 = xs.min(), ys.min()
    m = (lab[y0:ys.max() + 1, x0:xs.max() + 1] == c).astype(np.uint8)
    # bias toward the centre line: walk on the bar eroded as far as it stays connected
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    core = (dt > 0.22 * PX).astype(np.uint8)
    md = cv2.resize(core, (max(1, m.shape[1] // DS), max(1, m.shape[0] // DS)), interpolation=cv2.INTER_NEAREST)
    to_px = lambda pt: (int((pt[1] * PX - y0) / DS), int((pt[0] * PX - x0) / DS))
    def nearest(pt):
        pp = np.argwhere(md)
        t = np.array(to_px(pt))
        return tuple(pp[np.argmin(np.hypot(*(pp - t).T))])
    s_, t_ = nearest(p), nearest(q)
    prev = {s_: None}; dq = deque([s_])
    while dq:
        u = dq.popleft()
        if u == t_:
            break
        for dy, dx in NB:
            v = (u[0] + dy, u[1] + dx)
            if 0 <= v[0] < md.shape[0] and 0 <= v[1] < md.shape[1] and md[v] and v not in prev:
                prev[v] = u; dq.append(v)
    if t_ not in prev:
        return [list(p), list(q)]
    path = []; u = t_
    while u is not None:
        path.append(((u[1] * DS + x0 + DS / 2) / PX, (u[0] * DS + y0 + DS / 2) / PX)); u = prev[u]
    arr = np.array(path[::-1], np.float32)
    poly = cv2.approxPolyDP((arr * 100).reshape(-1, 1, 2), 25, False)[:, 0, :] / 100
    poly = poly.tolist()
    poly[0], poly[-1] = list(p), list(q)
    return poly


auto = []
leftover = []
for c, lis in members.items():
    if c and len(lis) in (2, 3):
        L = [lands[i] for i in lis]
        if len(L) == 3:   # chain: middle spot = the one with the smallest summed distance to the others
            mid = int(np.argmin([sum(np.linalg.norm(L[i] - L[j]) for j in range(3)) for i in range(3)]))
            ends = [i for i in range(3) if i != mid]
            seq = [L[ends[0]], L[mid], L[ends[1]]]
        else:
            seq = L
        path = []
        for u, v in zip(seq[:-1], seq[1:]):
            seg = geo_path(c, u, v)
            path += seg if not path else seg[1:]
        auto.append(dict(path=path, taps=[s_.tolist() for s_ in seq], source="auto"))
    else:
        leftover += lis

try:
    manual = json.load(open(f"{D}/manual_jumpers.json"))["jumpers"]
except FileNotFoundError:
    manual = []
used_by_manual = [np.array(p) for m in manual for p in (m["path"][0], m["path"][-1])]
final = [j for j in auto if all(min(np.linalg.norm(np.array(e) - u) for u in used_by_manual) > 1.5
                                 for e in (j["path"][0], j["path"][-1]))] if used_by_manual else list(auto)
final += [dict(path=m["path"], source="manual", note=m.get("note", "")) for m in manual]
covered = [np.array(p) for j in final for p in (j["path"][0], j["path"][-1])]
unhandled = [lands[i].tolist() for i in leftover if all(np.linalg.norm(lands[i] - u) > 1.5 for u in covered)]
print(f"auto pairs {len(auto)}, manual {len(manual)}, final {len(final)}; landing spots still unhandled: {len(unhandled)}")
for u in unhandled:
    print("   ", np.round(u, 1).tolist())
json.dump(dict(jumpers=final, unhandled=unhandled), open(f"{D}/jumpers.json", "w"), indent=1)
