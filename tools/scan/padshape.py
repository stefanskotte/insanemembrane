"""Average all key pads (aligned to their pair axis) into one canonical pad outline.

Output polygon is in mm in the pad's own frame: +x points toward the partner pad.
Usage: python padshape.py <front.png> <keymap.json> <out.json>
"""
import json
import sys
import cv2
import numpy as np

PX = 600 / 25.4
img = cv2.imread(sys.argv[1])
km = json.load(open(sys.argv[2]))
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
dark = ((hsv[..., 2] < 125) & (hsv[..., 1] < 60)).astype(np.float32)

R = int(4 * PX)
acc = np.zeros((2 * R, 2 * R), np.float32)
n = 0
for k in km["keys"]:
    a, b = np.array(k["pad_a"]), np.array(k["pad_b"])
    for p, q in ((a, b), (b, a)):
        ang = np.degrees(np.arctan2(q[1] - p[1], q[0] - p[0]))
        cx, cy = p * PX
        M = cv2.getRotationMatrix2D((cx, cy), ang, 1.0)  # rotate so p->q points along +x
        M[:, 2] += [R - cx, R - cy]
        patch = cv2.warpAffine(dark, M, (2 * R, 2 * R), flags=cv2.INTER_LINEAR)
        # keep only the component under the centre (drop the black trace tabs further out)
        m = (patch > 0.5).astype(np.uint8)
        nl, lab = cv2.connectedComponents(m)
        m = (lab == lab[R, R]).astype(np.float32)
        acc += m
        n += 1
avg = acc / n
mask = (avg > 0.5).astype(np.uint8)
mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((7, 7), np.uint8))
c = max(cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[0], key=cv2.contourArea)
poly = cv2.approxPolyDP(c, 0.08 * PX, True)[:, 0, :]
pts = (poly - [R, R]) / PX
pts[:, 1] *= -1  # image y-down -> keep y-down for KiCad; leave as image convention
pts[:, 1] *= -1
x, y, w, h = cv2.boundingRect(c)
print(f"pads averaged: {n}; outline {len(pts)} vertices; bbox {w/PX:.2f} (along axis) x {h/PX:.2f} mm; "
      f"area {cv2.contourArea(c)/PX**2:.2f} mm2")
print("extent toward partner (+x): %.2f mm, away: %.2f mm" % (pts[:, 0].max(), -pts[:, 0].min()))
print(np.round(pts, 2).tolist())
json.dump(dict(polygon_mm=np.round(pts, 3).tolist(), n=n), open(sys.argv[3], "w"))
cv2.imwrite(sys.argv[3].replace(".json", ".png"), (avg * 255).astype(np.uint8))
