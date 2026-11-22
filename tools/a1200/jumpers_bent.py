"""Follow the insulating strip from each unpaired landing spot to its far end (bent bridges).

The strip (dark green, seen from the back) is thinned to a centre line; we walk it from the land to the
farthest reachable point and report that point plus the simplified path.
Usage: python jumpers_bent.py <back-mirrored.png> <jumpers.json> <lands.npy>  (updates jumpers.json)
"""
import json
import sys
from collections import deque
import cv2
import numpy as np

PX = 600 / 25.4
img = cv2.imread(sys.argv[1])
J = json.load(open(sys.argv[2]))
lands = np.load(sys.argv[3])[:, :2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, S, V = hsv[..., 0].astype(int), hsv[..., 1].astype(int), hsv[..., 2].astype(int)
silver = (S < 60) & (V > 95) & (V < 225)
diel = (H > 50) & (H < 95) & (S > 45) & (V > 80) & (V < 166)
# the strip runs under base traces (seen as silver from the back) - count those as strip too
strip = (diel | silver).astype(np.uint8)


def walk(land, R=40):
    """Thin the strip around the land (window R mm) and return the farthest point + path (mm)."""
    x0, y0 = int((land[0] - R) * PX), int((land[1] - R) * PX)
    x0, y0 = max(x0, 0), max(y0, 0)
    sub = strip[y0:y0 + int(2 * R * PX), x0:x0 + int(2 * R * PX)].copy()
    d_only = diel[y0:y0 + sub.shape[0], x0:x0 + sub.shape[1]].astype(np.uint8)
    # keep only strip pixels that are within 0.9 mm of genuine dielectric (bars are ~1.2-1.6 mm wide)
    near = cv2.dilate(cv2.morphologyEx(d_only, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8)),
                      cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(0.9 * PX), int(0.9 * PX))))
    sub &= near
    lx, ly = int(land[0] * PX) - x0, int(land[1] * PX) - y0
    cv2.circle(sub, (lx, ly), int(1.2 * PX), 1, -1)
    n, lab = cv2.connectedComponents(sub, 8)
    comp = (lab == lab[ly, lx]).astype(np.uint8) * 255
    sk = cv2.ximgproc.thinning(comp) > 0
    pts = np.argwhere(sk)
    if len(pts) == 0:
        return None
    start = tuple(pts[np.argmin(np.hypot(pts[:, 0] - ly, pts[:, 1] - lx))])
    prev = {start: None}
    q = deque([start]); last = start
    while q:
        p = q.popleft(); last = p
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nb = (p[0] + dy, p[1] + dx)
                if nb != p and 0 <= nb[0] < sk.shape[0] and 0 <= nb[1] < sk.shape[1] and sk[nb] and nb not in prev:
                    prev[nb] = p; q.append(nb)
    path = []
    p = last
    while p is not None:
        path.append(((p[1] + x0) / PX, (p[0] + y0) / PX)); p = prev[p]
    path = path[::-1]
    poly = cv2.approxPolyDP(np.array(path, np.float32).reshape(-1, 1, 2) * 100, 0.25 * 100, False)[:, 0, :] / 100
    return poly


new = []
still = []
unp = [np.array(u) for u in J["unpaired"]]
done = set()
for i, u in enumerate(unp):
    if i in done:
        continue
    poly = walk(u)
    if poly is None:
        still.append(u.tolist()); continue
    end = poly[-1]
    # snap the far end to another unpaired land / any land if close
    dl = [np.linalg.norm(end - w) for w in unp]
    j = int(np.argmin([d if k != i else 1e9 for k, d in enumerate(dl)]))
    length = float(np.sum(np.linalg.norm(np.diff(poly, axis=0), axis=1)))
    if dl[j] < 2.0:
        done |= {i, j}
        poly[-1] = unp[j]; poly[0] = u
        new.append(dict(a=u.tolist(), b=unp[j].tolist(), path=poly.tolist(), length=length, kind="bent, land-land"))
    else:
        done.add(i)
        poly[0] = u
        new.append(dict(a=u.tolist(), b=end.tolist(), path=poly.tolist(), length=length, kind="bent, land-open-end"))
for n_ in new:
    print(f"  {n_['kind']}: ({n_['a'][0]:.1f},{n_['a'][1]:.1f}) -> ({n_['b'][0]:.1f},{n_['b'][1]:.1f}) "
          f"len {n_['length']:.1f}, {len(n_['path'])} pts")
print("bent bridges:", len(new), "still unresolved:", len(still))
J["bent"] = new
J["unresolved"] = still
json.dump(J, open(sys.argv[2], "w"), indent=1)
