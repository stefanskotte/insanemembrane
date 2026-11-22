"""A500: find the round silver landing spots (bridge ends) in the seam-free silver mask.

Opening with a ~1.1 mm disc keeps blobs (spots, pad rims, fingers); spots are the round ones of 1.2-2.2 mm.
Usage: python lands.py <silver_conn.npy> <out lands.npy>   -> rows (x mm, y mm, diameter mm)
"""
import sys
import cv2
import numpy as np

PX = 600 / 25.4
m = np.load(sys.argv[1]).astype(np.uint8)
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(1.1 * PX),) * 2)
o = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
n, lab, st, ce = cv2.connectedComponentsWithStats(o, 8)
out = []
for i in range(1, n):
    x, y, w, h, a = st[i]
    if x > 140.0 * PX and 309 * PX < y < 355 * PX:   # finger tab only
        continue
    d = 2 * np.sqrt(a / np.pi) / PX
    if not 1.2 < d < 2.3 or max(w, h) / max(1, min(w, h)) > 1.35:
        continue
    out.append((ce[i][0] / PX, ce[i][1] / PX, d))
out = np.array(out)
np.save(sys.argv[2], out)
print("landing spots:", len(out), "diameter median %.2f" % np.median(out[:, 2]))
