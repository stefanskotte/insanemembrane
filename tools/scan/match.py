"""Estimate the rigid transform between two overlapping scans (SIFT + RANSAC)."""
import sys
import cv2
import numpy as np

DS = 4  # work at 150 dpi


def load(p):
    g = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
    return cv2.resize(g, None, fx=1 / DS, fy=1 / DS, interpolation=cv2.INTER_AREA)


def mask_membrane(p):
    """Only use features on the green membrane, not on the paper rulers."""
    c = cv2.imread(p)
    c = cv2.resize(c, None, fx=1 / DS, fy=1 / DS, interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV)
    m = ((hsv[..., 1] > 60) & (hsv[..., 0] > 60) & (hsv[..., 0] < 100)).astype(np.uint8) * 255
    return cv2.erode(m, np.ones((15, 15), np.uint8))


a, b = sys.argv[1], sys.argv[2]
ga, gb = load(a), load(b)
ma, mb = mask_membrane(a), mask_membrane(b)
sift = cv2.SIFT_create(8000)
ka, da = sift.detectAndCompute(ga, ma)
kb, db = sift.detectAndCompute(gb, mb)
bf = cv2.BFMatcher()
good = [m for m, n in bf.knnMatch(da, db, k=2) if m.distance < 0.75 * n.distance]
pa = np.float32([ka[m.queryIdx].pt for m in good])
pb = np.float32([kb[m.trainIdx].pt for m in good])
M, inl = cv2.estimateAffinePartial2D(pb, pa, method=cv2.RANSAC, ransacReprojThreshold=2.0, maxIters=20000)
n = int(inl.sum()) if inl is not None else 0
print(f"{a} <- {b}: matches={len(good)} inliers={n}")
if M is not None:
    s = np.hypot(M[0, 0], M[1, 0])
    ang = np.degrees(np.arctan2(M[1, 0], M[0, 0]))
    print(f"  rot={ang:.3f} deg scale={s:.5f} tx={M[0,2]*DS:.1f}px ty={M[1,2]*DS:.1f}px (full-res)")
    err = np.abs((pb[inl.ravel() == 1] @ M[:, :2].T + M[:, 2]) - pa[inl.ravel() == 1])
    print(f"  median reproj err={np.median(np.hypot(*err.T))*DS:.2f}px full-res")
    np.save(sys.argv[3], M) if len(sys.argv) > 3 else None
