"""Measure tail edges, end and contact centres in the tail scan and map them into the front frame.

Usage: python tailgeom.py <back-tail.tiff> <front-holes.json> <back-tail-holes.json> <out.json>
(back-tail.tiff is the carbon side, same side as the stitched front image.)
"""
import json
import sys
import cv2
import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
PX = 600 / 25.4


def load(path):
    hs = [h for h in json.load(open(path)) if h["d_eq_mm"] > 5]
    return np.array([[h["cx"], h["cy"]] for h in hs]) / PX


def rigid(src, dst):
    cs, cd = src.mean(0), dst.mean(0)
    U, _, Vt = np.linalg.svd((src - cs).T @ (dst - cd))
    R = (U @ Vt).T
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1; R = (U @ Vt).T
    return R, cd - R @ cs


def ransac(A, B, tol=0.5):
    import itertools
    best = (0, None)
    for i, j in itertools.permutations(range(len(B)), 2):
        dB = np.linalg.norm(B[i] - B[j])
        if dB < 30:
            continue
        for k, l in itertools.permutations(range(len(A)), 2):
            if abs(np.linalg.norm(A[k] - A[l]) - dB) > 0.4:
                continue
            R, t = rigid(B[[i, j]], A[[k, l]])
            d = np.linalg.norm((B @ R.T + t)[:, None] - A[None], axis=2)
            pairs = [(bi, d[bi].argmin()) for bi in range(len(B)) if d[bi].min() < tol]
            if len(pairs) > best[0]:
                best = (len(pairs), pairs)
    bi, ai = zip(*best[1])
    return rigid(B[list(bi)], A[list(ai)])


img = cv2.imread(sys.argv[1])
A, B = load(sys.argv[2]), load(sys.argv[3])
R, t = ransac(A, B)
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
film = (((hsv[..., 1] > 45) & (hsv[..., 0] > 50) & (hsv[..., 0] < 105)) | ((hsv[..., 2] < 150) & (hsv[..., 1] < 90))).astype(np.uint8)
film[:, :int(25 * PX)] = 0
film = cv2.morphologyEx(film, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
Hh, W = film.shape

# tail columns in the tail scan: tail runs along image x, end on the left
cols = []
for x in range(int(30 * PX), W, 4):
    ys = np.where(film[:, x])[0]
    if len(ys) == 0:
        continue
    runs = np.split(ys, np.where(np.diff(ys) > 3)[0] + 1)
    r = max(runs, key=len)
    cols.append((x, r[0], r[-1]))
tail_end_x = next(x for x, a, b in cols if 20 < (b - a) / PX < 60)
body_x = next(x for x, a, b in cols if x > tail_end_x and (b - a) / PX > 100)
# straight part of the tail: fit both edges between 5% and 85% of its length
sel = [(x, a, b) for x, a, b in cols if tail_end_x + 0.05 * (body_x - tail_end_x) < x < tail_end_x + 0.85 * (body_x - tail_end_x)]
xs = np.array([s[0] for s in sel]) / PX
ea = np.polyfit(xs, np.array([s[1] for s in sel]) / PX, 1)
eb = np.polyfit(xs, np.array([s[2] for s in sel]) / PX, 1)
# tail end: leftmost film column in the tail band, refined per row
band = film[int(np.polyval(ea, tail_end_x / PX) * PX) + 20:int(np.polyval(eb, tail_end_x / PX) * PX) - 20, :]
ends = [np.argmax(r > 0) for r in band if r.any()]
end_x = np.median(ends) / PX

# contact fingers: grey carbon near the tail end
seg_x0 = int(end_x * PX)
xc = seg_x0 + int(3.0 * PX)
ya, yb = int(np.polyval(ea, xc / PX) * PX), int(np.polyval(eb, xc / PX) * PX)
row = (hsv[ya:yb, xc - 15:xc + 15, 1] < 70).mean(axis=1) > 0.5
idx = np.where(row)[0]
runs = [r for r in np.split(idx, np.where(np.diff(idx) > 2)[0] + 1) if len(r) > 5]
centres_y = [(ya + r.mean()) / PX for r in runs]
print(f"fingers {len(runs)}, pitch {np.median(np.diff(centres_y)):.4f} mm")


def to_front(x, y):
    return (np.array([x, y]) @ R.T + t).tolist()


# key points along each edge and the end, mapped into the front frame
L = (body_x / PX - end_x)
geo = dict(
    edge_a=[to_front(x, np.polyval(ea, x)) for x in (end_x, end_x + L)],
    edge_b=[to_front(x, np.polyval(eb, x)) for x in (end_x, end_x + L)],
    end_mid=to_front(end_x, (np.polyval(ea, end_x) + np.polyval(eb, end_x)) / 2),
    fingers=[to_front(end_x + 3.0, y) for y in centres_y],
    width=float(np.mean([np.polyval(eb, x) - np.polyval(ea, x) for x in xs])),
    rotation_deg=float(np.degrees(np.arctan2(R[1, 0], R[0, 0]))),
)
print(json.dumps({k: (np.round(v, 2).tolist() if k != "fingers" else f"{len(v)} pts") for k, v in geo.items()}, indent=1))
json.dump(geo, open(sys.argv[4], "w"), indent=1)
