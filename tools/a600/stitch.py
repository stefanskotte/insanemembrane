"""A600: stitch left/right scans into one 600 dpi image per side, in the top-left frame."""
import json
import sys
import cv2
import numpy as np

PX = 600 / 25.4
S, proj = sys.argv[1], sys.argv[2]
T = json.load(open(f"{S}/transforms.json"))


def affine(key, mirror_w=None):
    R = np.array(T[key]["R"]); t = np.array(T[key]["t"]) * PX
    M = np.hstack([R, t[:, None]])
    if mirror_w:  # pre-mirror source x: x' = W - x
        F = np.array([[-1, 0, mirror_w], [0, 1, 0], [0, 0, 1]], float)
        M = M @ F
    return M


def membrane(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 1] > 45) & (hsv[..., 0] > 50) & (hsv[..., 0] < 105)).astype(np.uint8)
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))


def build(left, right, Mright, seam_y_mm, out, Mleft=None):
    L = cv2.imread(f"{proj}/{left}.tiff")
    R = cv2.imread(f"{proj}/{right}.tiff")
    H = int(round(400 * PX)); W = L.shape[1]
    if Mleft is not None:
        L = cv2.warpAffine(L, Mleft, (W, H), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    else:
        L = cv2.copyMakeBorder(L, 0, H - L.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    Rw = cv2.warpAffine(R, Mright, (W, H), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    seam = int(seam_y_mm * PX)
    canvas = L.copy()
    canvas[seam:] = Rw[seam:]
    cv2.imwrite(f"{proj}/{out}", canvas)
    # overlap check: difference of membrane masks in overlap band
    band = slice(int(150 * PX), int(240 * PX))
    ml, mr = membrane(L[band]), membrane(Rw[band])
    both = (ml | mr).sum()
    print(out, "overlap mask disagreement:", f"{(ml ^ mr).sum() / max(both,1) * 100:.2f}%")
    return canvas


front = build("a600-top-left", "a600-top-right", affine("a600-top-left<-a600-top-right"), 195, "a600/docs/scan-front-stitched.png")
# back side: map back scans into the FRONT frame (mirrored) so both sides overlay exactly
W = 5100
Mbl = affine("a600-top-left<-a600-bottom-right", W)
Mbr = affine("a600-top-right<-a600-bottom-left", W)
# compose top-left<-top-right with top-right<-back-right(mirrored)
A = np.vstack([affine("a600-top-left<-a600-top-right"), [0, 0, 1]])
Mbr_full = (A @ np.vstack([Mbr, [0, 0, 1]]))[:2]
back = build("a600-bottom-right", "a600-bottom-left", Mbr_full, 195, "a600/docs/scan-back-mirrored-into-front-frame.png", Mleft=Mbl)
