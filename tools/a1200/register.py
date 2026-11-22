"""Register scans to each other using the through-hole centres (rigid, optional mirror)."""
import itertools
import json
import sys
import numpy as np

PX = 600 / 25.4
S = sys.argv[1]


def load(name, mirror_w=None):
    hs = json.load(open(f"{S}/{name}-holes.json"))
    hs = [h for h in hs if h["d_eq_mm"] > 5]  # drop slivers
    p = np.array([[h["cx"], h["cy"]] for h in hs]) / PX
    if mirror_w:
        p[:, 0] = mirror_w - p[:, 0]
    return p, hs


def rigid(src, dst):
    """Least-squares rotation+translation src->dst (Kabsch, no scale/reflection)."""
    cs, cd = src.mean(0), dst.mean(0)
    U, _, Vt = np.linalg.svd((src - cs).T @ (dst - cd))
    R = (U @ Vt).T
    if np.linalg.det(R) < 0:
        Vt[-1] *= -1
        R = (U @ Vt).T
    return R, cd - R @ cs


def ransac(A, B, tol=0.5):
    best = (0, None)
    for i, j in itertools.permutations(range(len(B)), 2):
        dB = np.linalg.norm(B[i] - B[j])
        if dB < 30:
            continue
        for k, l in itertools.permutations(range(len(A)), 2):
            if abs(np.linalg.norm(A[k] - A[l]) - dB) > 0.4:
                continue
            R, t = rigid(B[[i, j]], A[[k, l]])
            T = B @ R.T + t
            d = np.linalg.norm(T[:, None] - A[None], axis=2)
            pairs = [(bi, d[bi].argmin()) for bi in range(len(B)) if d[bi].min() < tol]
            if len(pairs) > best[0]:
                best = (len(pairs), pairs)
    pairs = best[1]
    bi, ai = zip(*pairs)
    R, t = rigid(B[list(bi)], A[list(ai)])
    res = np.linalg.norm(B[list(bi)] @ R.T + t - A[list(ai)], axis=1)
    return R, t, len(pairs), res


W = 5100 / PX
out = {}
for a, b, mir in [("top-left", "top-right", False),
                  ("top-left", "back-left", True),
                  ("top-right", "back-right", True),
                  ("back-left", "back-right", False)]:
    A, _ = load(a)
    B, _ = load(b, W if mir else None)
    R, t, n, res = ransac(A, B)
    ang = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
    print(f"{a:10s} <- {b:11s}{' (mirrored)' if mir else '':11s} matched {n:2d} holes, rot {ang:8.3f} deg, "
          f"t=({t[0]:7.2f},{t[1]:7.2f}) mm, residual rms {np.sqrt((res**2).mean()):.3f} mm max {res.max():.3f} mm")
    out[f"{a}<-{b}"] = dict(R=R.tolist(), t=t.tolist(), mirror=mir)
json.dump(out, open(f"{S}/transforms.json", "w"), indent=1)
