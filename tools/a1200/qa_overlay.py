"""QA: draw the replica copper over the original scan, in board coordinates.

Usage: python qa_overlay.py <project dir> <x0> <y0> <x1> <y1> <out.png> [scale]
Region in board mm. Red = top copper, blue = bottom copper, yellow = vias, magenta = pads, white = outline.
"""
import json
import sys
import cv2
import numpy as np

PX = 600 / 25.4
proj = sys.argv[1]
x0, y0, x1, y1 = map(float, sys.argv[2:6])
out = sys.argv[6]
sc = float(sys.argv[7]) if len(sys.argv) > 7 else 1.0
D = f"{proj}/a1200/docs/scan-data"
G = json.load(open(f"{D}/board_geom.json"))
R = json.load(open(f"{D}/routing.json"))
pads = json.load(open(f"{D}/pads_final.json")) if __import__("os").path.exists(f"{D}/pads_final.json") else None
tr = G["transform"]
th = np.radians(-tr["tilt_deg"])
Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
A = np.diag([1.0, tr["yscale"]]) @ Rm                        # board = A (p - pivot) + shift
c = np.array(tr["shift"]) - A @ np.array(tr["pivot"])
# front px -> region px
M = np.hstack([A, ((c - [x0, y0]) * PX)[:, None]])
W, H = int((x1 - x0) * PX), int((y1 - y0) * PX)
img = cv2.warpAffine(cv2.imread(f"{proj}/a1200/docs/scan-front-stitched.png"), M, (W, H), borderValue=(255, 255, 255))
img = (img * 0.6 + 255 * 0.4).astype(np.uint8)
P = lambda p: (int((p[0] - x0) * PX), int((p[1] - y0) * PX))
cv2.polylines(img, [np.array([P(p) for p in G["board_outline"][0]], np.int32)], True, (255, 255, 255), 3)
for t in R["tracks"]:
    col = (0, 0, 230) if t["layer"] == "F.Cu" else (230, 80, 0)
    cv2.polylines(img, [np.array([P(p) for p in t["pts"]], np.int32)], False, col, max(1, int(t["w"] * PX)))
for v in R["vias"]:
    cv2.circle(img, P(v["pos"]), int(0.35 * PX), (0, 220, 255), -1)
if pads:
    for pp in pads["pads"]:
        cv2.polylines(img, [np.array([P(p) for p in pp["poly"]], np.int32)], True, (255, 0, 255), 2)
cv2.imwrite(out, cv2.resize(img, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA))
