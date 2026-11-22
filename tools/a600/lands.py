"""A600: find the round silver landing spots (bridge ends) in the seam-free silver mask.

Opening with a ~1.1 mm disc keeps blobs (spots, pad rims, fingers); spots are the round ones of 1.2-2.2 mm.
Usage: python lands.py <silver_conn.npy> <out lands.npy>   -> rows (x mm, y mm, diameter mm)
"""
import sys
import cv2
import numpy as np

PX = 600 / 25.4
TAIL_X0 = 176.0
m = np.load(sys.argv[1]).astype(np.uint8)
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(1.1 * PX),) * 2)
o = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
n, lab, st, ce = cv2.connectedComponentsWithStats(o, 8)
out = []
for i in range(1, n):
    x, y, w, h, a = st[i]
    if x > TAIL_X0 * PX and 140 * PX < y < 192 * PX:   # tail only
        continue
    d = 2 * np.sqrt(a / np.pi) / PX
    if not 1.3 < d < 3.0 or max(w, h) / max(1, min(w, h)) > 1.35:
        continue
    out.append((ce[i][0] / PX, ce[i][1] / PX, d))
out = np.array(out)
# the silver under each key pad is as big as a landing spot on the A600: drop anything at a pad
import json, os
_F = json.load(open(os.path.join(os.path.dirname(sys.argv[2]), "features.json")))
_P = np.array([[p["x"], p["y"]] for p in _F["pads"]])
out = out[np.min(np.linalg.norm(out[:, None, :2] - _P[None], axis=2), axis=1) > 1.0]
np.save(sys.argv[2], out)
print("landing spots:", len(out), "diameter median %.2f" % np.median(out[:, 2]))
