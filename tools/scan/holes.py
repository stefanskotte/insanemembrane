"""Detect through-holes (white blobs inside the green membrane) in a scan."""
import json
import sys
import cv2
import numpy as np

PXMM = 600 / 25.4


def membrane_mask(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    green = (hsv[..., 1] > 50) & (hsv[..., 0] > 55) & (hsv[..., 0] < 105)
    m = green.astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    return m


def detect(path):
    img = cv2.imread(path)
    m = membrane_mask(img)
    # holes = regions not green, fully enclosed by green
    inv = cv2.bitwise_not(m)
    n, lab, stats, cent = cv2.connectedComponentsWithStats(inv, 8)
    H, W = m.shape
    holes = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if x == 0 or y == 0 or x + w >= W or y + h >= H:
            continue
        if area < 200 or area > 200000:
            continue
        cnt, _ = cv2.findContours((lab[y:y+h, x:x+w] == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        c = max(cnt, key=cv2.contourArea)
        per = cv2.arcLength(c, True)
        circ = 4 * np.pi * area / per**2
        # white check: holes show the white lid/paper behind
        mean = img[lab == i].mean(axis=0) if area < 50000 else img[y:y+h, x:x+w][lab[y:y+h, x:x+w] == i].mean(axis=0)
        if mean.min() < 170:
            continue
        holes.append(dict(cx=float(cent[i][0]), cy=float(cent[i][1]),
                          w_mm=w / PXMM, h_mm=h / PXMM, d_eq_mm=2 * np.sqrt(area / np.pi) / PXMM,
                          circ=round(float(circ), 3)))
    return holes


if __name__ == "__main__":
    for p in sys.argv[1:-1]:
        hs = detect(p)
        json.dump(hs, open(sys.argv[-1] + "/" + p.split("/")[-1].replace(".tiff", "") + "-holes.json", "w"))
        print(p, len(hs))
        for h in sorted(hs, key=lambda h: h["cy"]):
            print(f"  ({h['cx']/PXMM:6.1f},{h['cy']/PXMM:6.1f}) mm  {h['w_mm']:.2f}x{h['h_mm']:.2f}  d_eq={h['d_eq_mm']:.2f}  circ={h['circ']}")
