"""Silver-trace mask of the original membrane's back side, in the front frame, without a stitching seam.

The two back scans are warped into the front frame separately; where they overlap their masks are
OR-ed, so traces crossing the overlap stay continuous despite the ~0.13 mm registration offset.
Usage: python silvermask.py <project dir> <out.npy> [vmax]   (uint8, 1 = silver, full 600 dpi front frame)
"""
import json
import sys
import cv2
import numpy as np

PX = 600 / 25.4
proj, out = sys.argv[1], sys.argv[2]
VMAX = int(sys.argv[3]) if len(sys.argv) > 3 else 225   # 225: connectivity mask, 195: geometry mask (drops white windows)
T = json.load(open(f"{proj}/docs/scan-data/transforms.json"))
W, H = 5100, int(round((478.4 + 12) * PX))


def affine(key, mirror_w=None):
    R = np.array(T[key]["R"]); t = np.array(T[key]["t"]) * PX
    M = np.hstack([R, t[:, None]])
    if mirror_w:
        M = M @ np.array([[-1, 0, mirror_w], [0, 1, 0], [0, 0, 1]], float)
    return M


def silver_of(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    S, V = hsv[..., 1], hsv[..., 2]
    m = ((S < 60) & (V > 95) & (V < VMAX)).astype(np.uint8)   # silver 150-175; white coverlay windows 205+
    white = ((V > 205) & (S < 35)).astype(np.uint8)
    nw, wl, wst, _ = cv2.connectedComponentsWithStats(white, 8)
    bigw = np.isin(wl, [i for i in range(1, nw) if wst[i, 4] > 15 * PX * PX]).astype(np.uint8)
    m[cv2.dilate(bigw, np.ones((13, 13), np.uint8)) > 0] = 0
    return m


Mbl = affine("top-left<-back-left", 5100)
A = np.vstack([affine("top-left<-top-right"), [0, 0, 1]])
Mbr = (A @ np.vstack([affine("top-right<-back-right", 5100), [0, 0, 1]]))[:2]
L = cv2.warpAffine(cv2.imread(f"{proj}/back-left.tiff"), Mbl, (W, H), borderValue=(255, 255, 255))
R = cv2.warpAffine(cv2.imread(f"{proj}/back-right.tiff"), Mbr, (W, H), borderValue=(255, 255, 255))
inL = cv2.warpAffine(np.ones((7016, 5100), np.uint8), Mbl, (W, H)) > 0
inR = cv2.warpAffine(np.ones((7016, 5100), np.uint8), Mbr, (W, H)) > 0
# shrink each scan's valid area a little so its own paper edge / rulers don't count
inL = cv2.erode(inL.astype(np.uint8), np.ones((41, 41), np.uint8)) > 0
inR = cv2.erode(inR.astype(np.uint8), np.ones((41, 41), np.uint8)) > 0
sL, sR = silver_of(L), silver_of(R)
seam = int(240 * PX)
m = np.zeros((H, W), np.uint8)
m[:seam] = sL[:seam]
m[seam:] = sR[seam:]
band = slice(int(225 * PX), int(255 * PX))
m[band] = ((sL[band] & inL[band]) | (sR[band] & inR[band])).astype(np.uint8)
np.save(out, m)
print("saved", out, m.shape, "silver px", int(m.sum()))
