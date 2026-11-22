"""Measure the connector tail in a tail scan (tail runs horizontally, end on the left)."""
import sys
import cv2
import numpy as np

PX = 600 / 25.4
img = cv2.imread(sys.argv[1])
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
# "film" = anything not paper-white (green film, grey carbon)
film = ((hsv[..., 1] > 45) | (hsv[..., 2] < 150)).astype(np.uint8)
film = cv2.morphologyEx(film, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))

H, W = film.shape
# rows covered by film at a column well inside the tail-only region
def edges_at(x):
    col = film[:, x]
    ys = np.where(col)[0]
    # longest run
    runs = np.split(ys, np.where(np.diff(ys) > 3)[0] + 1)
    r = max(runs, key=len)
    return r[0], r[-1]

# find tail end: leftmost column with a film run of 20-60 mm
xs = range(int(25 * PX), W, 2)
tail_cols = []
for x in xs:
    if film[:, x].sum() < 50:
        continue
    a, b = edges_at(x)
    w = (b - a + 1) / PX
    tail_cols.append((x, a, b, w))
tail_end = next(x for x, a, b, w in tail_cols if 20 < w < 60)
# body edge: first column where width jumps above 100 mm
body = next(x for x, a, b, w in tail_cols if x > tail_end and w > 100)
print(f"tail end x={tail_end/PX:.2f} mm, body edge x={body/PX:.2f} mm -> free tail length {(body-tail_end)/PX:.2f} mm")
for frac in (0.03, 0.1, 0.3, 0.5, 0.7, 0.9):
    x = int(tail_end + frac * (body - tail_end))
    a, b = edges_at(x)
    print(f"  width at {frac:4.0%} along: {(b-a+1)/PX:.2f} mm  (y {a/PX:.2f}..{b/PX:.2f})")

# conductor pitch: take rows through the tail at a column in the middle, profile across the width
xm = int(tail_end + 0.6 * (body - tail_end))
a, b = edges_at(xm)
prof = gray[a + 10:b - 10, xm - 40:xm + 40].mean(axis=1)
prof = prof - prof.mean()
n = len(prof) * 16
spec = np.abs(np.fft.rfft(prof, n=n))
f = np.fft.rfftfreq(n)
band = (f > 1 / 60) & (f < 1 / 15)
fp = f[band][spec[band].argmax()]
print(f"conductor pitch (mid tail, FFT): {1/fp/PX:.4f} mm")
# count conductors with peak finding on dark/light lines
p = np.convolve(prof, np.ones(5) / 5, mode="same")
sign = 1 if np.abs(p.max()) > np.abs(p.min()) else -1
q = sign * p
pk = [i for i in range(1, len(q) - 1) if q[i] > q[i - 1] and q[i] >= q[i + 1] and q[i] > 0.4 * q.max()]
merged = []
for i in pk:
    if merged and i - merged[-1] < 10:
        continue
    merged.append(i)
print(f"line count across width at mid tail: {len(merged)}, mean spacing {np.diff(merged).mean()/PX:.4f} mm" if len(merged) > 2 else "")

# carbon finger region at the tail end: grey, low saturation, dark
x0 = tail_end
seg = hsv[a:b, x0:x0 + int(15 * PX)]
grey = (seg[..., 1] < 70) & (seg[..., 2] < 170)
colfrac = grey.mean(axis=0)
gx = np.where(colfrac > 0.2)[0]
if len(gx):
    print(f"grey (carbon) fingers: from {gx[0]/PX:.2f} to {gx[-1]/PX:.2f} mm from tail end -> {(gx[-1]-gx[0])/PX:.2f} mm long")
    xc = x0 + (gx[0] + gx[-1]) // 2
    a2, b2 = edges_at(xc)
    row = (hsv[a2:b2, xc - 15:xc + 15, 1] < 70).mean(axis=1) > 0.5
    runs = np.split(np.where(row)[0], np.where(np.diff(np.where(row)[0]) > 2)[0] + 1)
    runs = [r for r in runs if len(r) > 5]
    ws = [len(r) / PX for r in runs]
    cs = [r.mean() for r in runs]
    print(f"  fingers counted: {len(runs)}, finger width {np.median(ws):.3f} mm, pitch {np.median(np.diff(cs))/PX:.4f} mm, "
          f"first..last centre span {(cs[-1]-cs[0])/PX:.2f} mm")
    print(f"  first finger centre {(a2 + cs[0] - a2 - 0) / PX:.2f} mm from tail edge, last {(b2 - a2 - cs[-1]) / PX:.2f} mm from other edge")
