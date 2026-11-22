"""Detect all carbon pads in the stitched front scan, pair them, and match pairs to skielek keys.

Usage: python keymap.py <front.png> <skielek.json> <outdir>
Writes <outdir>/keymap.json
"""
import json
import sys
import itertools
import cv2
import numpy as np

PX = 600 / 25.4
img = cv2.imread(sys.argv[1])
sk = json.load(open(sys.argv[2]))
out = sys.argv[3]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# membrane polygon (green), slightly dilated, to reject ruler marks
green = ((hsv[..., 1] > 45) & (hsv[..., 0] > 50) & (hsv[..., 0] < 105)).astype(np.uint8)
green = cv2.morphologyEx(green, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
c = max(cv2.findContours(green, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea)
mem = np.zeros(green.shape, np.uint8)
cv2.drawContours(mem, [c], -1, 1, -1)
mem = cv2.dilate(mem, np.ones((71, 71), np.uint8))  # pads touching the edge band

dark = ((hsv[..., 2] < 125) & (hsv[..., 1] < 60)).astype(np.uint8)
dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
n, lab, st, cen = cv2.connectedComponentsWithStats(dark, 8)
pads = []
for i in range(1, n):
    a = st[i, 4] / PX**2
    w, h = st[i, 2] / PX, st[i, 3] / PX
    if not (6 < a < 20 and w < 6 and h < 6):
        continue
    if not mem[int(cen[i][1]), int(cen[i][0])]:
        continue
    pads.append([cen[i][0] / PX, cen[i][1] / PX, a])
P = np.array(pads)
print("pads detected:", len(P))

# pairing: greedy minimum distance among pairs whose separation is 3.5..8 mm
D = np.linalg.norm(P[:, None, :2] - P[None, :, :2], axis=2)
cand = sorted((abs(D[i, j] - 7.16), i, j) for i, j in itertools.combinations(range(len(P)), 2) if 3.5 < D[i, j] < 8.5)
used, pairs = set(), []
for _, i, j in cand:
    if i in used or j in used:
        continue
    pairs.append((i, j)); used |= {i, j}
single = [i for i in range(len(P)) if i not in used]
mid = np.array([(P[i, :2] + P[j, :2]) / 2 for i, j in pairs])
print("pairs:", len(pairs), "singles:", len(single))

# skielek keys
keys = [k for k in sk if k["ref"].startswith("K")]
K = np.array([[k["x"], k["y"]] for k in keys])
print("skielek keys:", len(keys))

# try 8 orientations, ICP translation+rotation
best = None
for rot in range(4):
    for mir in (False, True):
        Q = K.copy()
        if mir:
            Q[:, 0] = -Q[:, 0]
        th = rot * np.pi / 2
        R0 = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
        Q = Q @ R0.T
        if rot == 1 and not mir:  # known: F-row along the tail edge, keypad at far end
            Q = np.c_[229.5 - K[:, 1], K[:, 0] - 38.0]
        else:
            Q += mid.mean(0) - Q.mean(0)
        for _ in range(60):
            d = np.linalg.norm(Q[:, None] - mid[None], axis=2)
            nn = d.argmin(1)
            ok = d[np.arange(len(Q)), nn] < 6
            if ok.sum() < 10:
                break
            A, B = Q[ok], mid[nn[ok]]
            ca, cb = A.mean(0), B.mean(0)
            U, _, Vt = np.linalg.svd((A - ca).T @ (B - cb))
            R = (U @ Vt).T
            if np.linalg.det(R) < 0:
                Vt[-1] *= -1; R = (U @ Vt).T
            Q = (Q - ca) @ R.T + cb
        d = np.linalg.norm(Q[:, None] - mid[None], axis=2)
        nn = d.argmin(1); dd = d[np.arange(len(Q)), nn]
        score = (dd < 3).sum()
        if best is None or score > best[0] or (score == best[0] and np.median(dd) < best[1]):
            best = (score, np.median(dd), rot, mir, Q, nn, dd)
score, med, rot, mir, Q, nn, dd = best
print(f"best orientation rot={rot*90} mirror={mir}: {score}/{len(keys)} keys within 3 mm, median {med:.2f} mm")

# one-to-one assignment (Hungarian-like greedy on distance)
d = np.linalg.norm(Q[:, None] - mid[None], axis=2)
order = sorted((d[k, m], k, m) for k in range(len(keys)) for m in range(len(mid)) if d[k, m] < 8)
ka, ma, assign = set(), set(), {}
for dist, k, m in order:
    if k in ka or m in ma:
        continue
    assign[k] = m; ka.add(k); ma.add(m)
res = []
for k, key in enumerate(keys):
    nets = sorted({nm for num, nm in key["pads"] if num in ("1", "2")})
    m = assign.get(k)
    e = dict(ref=key["ref"], name=key["val"], nets=nets, pred=Q[k].tolist())
    if m is not None:
        i, j = pairs[m]
        e.update(pad_a=P[i, :2].tolist(), pad_b=P[j, :2].tolist(), mid=mid[m].tolist(), err=float(d[k, m]))
    res.append(e)
errs = np.array([r["err"] for r in res if "err" in r])
print(f"assigned {len(errs)}/{len(keys)}; offset error median {np.median(errs):.2f}, max {errs.max():.2f} mm")
for r in res:
    if "err" not in r or r["err"] > 2.5:
        print("  CHECK", r["ref"], r["name"], "pred", np.round(r["pred"], 1), "err", round(r.get("err", -1), 2))
left_pairs = [pairs[m] for m in range(len(mid)) if m not in ma]
for i, j in left_pairs:
    print(f"  unassigned pair ({P[i,0]:.1f},{P[i,1]:.1f})-({P[j,0]:.1f},{P[j,1]:.1f}) d={D[i,j]:.2f}")
for i in single:
    print(f"  single pad ({P[i,0]:.1f},{P[i,1]:.1f}) area {P[i,2]:.1f}")
json.dump(dict(keys=res, unassigned_pairs=[[P[i, :2].tolist(), P[j, :2].tolist()] for i, j in left_pairs],
               singles=[P[i, :2].tolist() for i in single], orientation=dict(rot=rot * 90, mirror=mir)),
          open(f"{out}/keymap.json", "w"), indent=1)
