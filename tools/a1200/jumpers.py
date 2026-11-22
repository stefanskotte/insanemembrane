"""Pair the round silver landing spots into crossover bridges (jumpers).

A bridge is printed over a dark-green insulating strip; seen from the back, the straight line between
its two landing spots never crosses plain light-turquoise film. Pairs are chosen greedily by that score.
Usage: python jumpers.py <back-mirrored.png> <lands.npy> <out.json> [debug.png]
"""
import json
import sys
import cv2
import numpy as np

PX = 600 / 25.4
img = cv2.imread(sys.argv[1])
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
lands = np.load(sys.argv[2])[:, :2]
plain = ((hsv[..., 1] > 125) & (hsv[..., 2] > 165)).astype(np.uint8)   # bare light turquoise film


def score(p, q, r_land=1.1):
    d = np.linalg.norm(q - p)
    n = max(int(d * 10), 2)
    ts = np.linspace(0, 1, n)
    pts = p[None] + (q - p)[None] * ts[:, None]
    keep = (np.linalg.norm(pts - p, axis=1) > r_land) & (np.linalg.norm(pts - q, axis=1) > r_land)
    pts = pts[keep]
    if len(pts) == 0:
        return 1.0
    # sample a small cross-section so a 1 px offset doesn't matter
    vals = []
    for x, y in pts:
        X, Y = int(x * PX), int(y * PX)
        vals.append(plain[Y - 2:Y + 3, X - 2:X + 3].mean() < 0.5)
    return float(np.mean(vals))


N = len(lands)
cand = []
for i in range(N):
    for j in range(i + 1, N):
        d = np.linalg.norm(lands[i] - lands[j])
        if 1.5 < d < 80:
            sc = score(lands[i], lands[j])
            if sc > 0.9:
                cand.append((-sc, d, i, j))
cand.sort()
used, pairs = set(), []
for negsc, d, i, j in cand:
    if i in used or j in used:
        continue
    pairs.append(dict(a=lands[i].tolist(), b=lands[j].tolist(), score=-negsc, length=d))
    used |= {i, j}
left = [lands[i].tolist() for i in range(N) if i not in used]
print(f"jumpers paired: {len(pairs)}; unpaired lands: {len(left)}")
for p in sorted(pairs, key=lambda p: p["score"])[:8]:
    print(f"  lowest scores: ({p['a'][0]:.1f},{p['a'][1]:.1f})-({p['b'][0]:.1f},{p['b'][1]:.1f}) "
          f"len {p['length']:.1f} score {p['score']:.3f}")
for l in left:
    print(f"  unpaired land ({l[0]:.1f},{l[1]:.1f})")
json.dump(dict(jumpers=pairs, unpaired=left), open(sys.argv[3], "w"), indent=1)

if len(sys.argv) > 4:
    vis = cv2.resize(img, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    for p in pairs:
        a = tuple(int(v * PX / 4) for v in p["a"]); b = tuple(int(v * PX / 4) for v in p["b"])
        cv2.line(vis, a, b, (0, 0, 255), 3)
    for l in left:
        cv2.circle(vis, tuple(int(v * PX / 4) for v in l), 15, (255, 0, 255), 3)
    cv2.imwrite(sys.argv[4], vis)
