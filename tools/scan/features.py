"""Extract outline, holes and carbon pads from the stitched front image (mm, front frame)."""
import json
import sys
import cv2
import numpy as np

PX = 600 / 25.4
img = cv2.imread(sys.argv[1])
outdir = sys.argv[2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, W = img.shape[:2]

# ---- outline -----------------------------------------------------------
film = ((hsv[..., 1] > 45) & (hsv[..., 0] > 50) & (hsv[..., 0] < 105)).astype(np.uint8)
film = cv2.morphologyEx(film, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
n, lab, st, _ = cv2.connectedComponentsWithStats(film, 8)
big = 1 + np.argmax(st[1:, cv2.CC_STAT_AREA])
mem = (lab == big).astype(np.uint8)
cnts, hier = cv2.findContours(mem, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
outer = max(cnts, key=cv2.contourArea)
mem = np.zeros_like(mem); cv2.drawContours(mem, [outer], -1, 1, -1)
poly = cv2.approxPolyDP(outer, 0.15 * PX, True)[:, 0, :] / PX
x, y, w, h = cv2.boundingRect(outer)
print(f"membrane bbox: {w/PX:.2f} x {h/PX:.2f} mm, area {cv2.contourArea(outer)/PX**2:.0f} mm^2, outline vertices {len(poly)}")

# ---- pads (dark grey carbon) ----------------------------------------------
dark = ((hsv[..., 2] < 125) & (hsv[..., 1] < 110)).astype(np.uint8) & mem
dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
n, lab, st, cen = cv2.connectedComponentsWithStats(dark, 8)
pads = []
for i in range(1, n):
    a = st[i, cv2.CC_STAT_AREA] / PX**2
    if not 6 < a < 20:
        continue
    m = (lab[st[i, 1]:st[i, 1] + st[i, 3], st[i, 0]:st[i, 0] + st[i, 2]] == i).astype(np.uint8)
    c, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    (rcx, rcy), (rw, rh), ang = cv2.minAreaRect(c[0])
    pads.append(dict(x=cen[i][0] / PX, y=cen[i][1] / PX, area=a, w=max(rw, rh) / PX, h=min(rw, rh) / PX, ang=ang))
areas = np.array([p["area"] for p in pads])
print(f"pads: {len(pads)}  area median {np.median(areas):.2f} mm^2 (p10 {np.percentile(areas,10):.2f}, p90 {np.percentile(areas,90):.2f})")
print(f"  pad size median {np.median([p['w'] for p in pads]):.2f} x {np.median([p['h'] for p in pads]):.2f} mm (min-area rect)")

# pair pads into keys: mutual nearest neighbours
P = np.array([[p["x"], p["y"]] for p in pads])
D = np.linalg.norm(P[:, None] - P[None], axis=2) + np.eye(len(P)) * 1e9
nn = D.argmin(1)
keys, used = [], set()
for i, j in enumerate(nn):
    if nn[j] == i and i < j:
        keys.append((i, j)); used |= {i, j}
single = [i for i in range(len(P)) if i not in used]
sep = np.array([D[i, j] for i, j in keys])
print(f"keys (mutual-nearest pad pairs): {len(keys)}; unpaired pads: {len(single)}")
print(f"  pad-pair centre spacing median {np.median(sep):.2f} mm (min {sep.min():.2f}, max {sep.max():.2f})")
ang = np.array([np.degrees(np.arctan2(P[j, 1] - P[i, 1], P[j, 0] - P[i, 0])) % 180 for i, j in keys])
print(f"  pair axis angle median {np.median(ang):.1f} deg")
for i in single:
    print(f"  unpaired pad at ({P[i,0]:.1f},{P[i,1]:.1f}) area {pads[i]['area']:.1f}")

json.dump(dict(outline=poly.tolist(), pads=pads,
               keys=[dict(cx=float((P[i, 0] + P[j, 0]) / 2), cy=float((P[i, 1] + P[j, 1]) / 2), a=int(i), b=int(j)) for i, j in keys]),
          open(f"{outdir}/features.json", "w"), indent=1)

# debug overlay
vis = cv2.resize(img, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
cv2.polylines(vis, [(poly * PX / 4).astype(np.int32)], True, (0, 0, 255), 2)
for i, j in keys:
    cv2.line(vis, tuple((P[i] * PX / 4).astype(int)), tuple((P[j] * PX / 4).astype(int)), (255, 0, 255), 3)
for i in single:
    cv2.circle(vis, tuple((P[i] * PX / 4).astype(int)), 12, (0, 0, 255), 3)
cv2.imwrite(f"{outdir}/features-debug.png", vis)
