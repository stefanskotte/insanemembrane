"""Check skielek's netlist against the base (silver) layer of the original membrane.

Silver traces seen from the back form connected groups. Pads in one group must share a net,
and the trace order across the tail tells us which end is pin 1.
Usage: python connectivity.py <back-mirrored.png> <keymap.json> <outdir>
"""
import json
import sys
from collections import defaultdict, Counter
import cv2
import numpy as np

PX = 600 / 25.4
img = cv2.imread(sys.argv[1])
km = json.load(open(sys.argv[2]))
out = sys.argv[3]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]

# silver: low saturation, mid-high value (beige/grey), not paper white
silver = ((S < 60) & (V > 95) & (V < 225)).astype(np.uint8)
# Blended rims around big white areas (holes, paper outside the membrane) look like silver and
# would short neighbouring traces together: cut a band around every large white region.
white = ((V > 205) & (S < 35)).astype(np.uint8)
nw, wl, wst, _ = cv2.connectedComponentsWithStats(white, 8)
bigw = np.isin(wl, [i for i in range(1, nw) if wst[i, 4] > 15 * PX * PX]).astype(np.uint8)
silver[cv2.dilate(bigw, np.ones((13, 13), np.uint8)) > 0] = 0
silver = cv2.morphologyEx(silver, cv2.MORPH_ERODE, np.ones((5, 5), np.uint8))
n, lab = cv2.connectedComponents(silver, connectivity=8)
print("silver components:", n - 1)


def comp_at(x, y, r=0.6):
    X, Y, R = int(x * PX), int(y * PX), int(r * PX)
    w = lab[Y - R:Y + R + 1, X - R:X + R + 1]
    vals = Counter(w[w > 0].ravel().tolist())
    return vals.most_common(1)[0][0] if vals else 0


# pads -> component; each key has nets [n1, n2] but we don't yet know which pad is which net
pad_items = []
for k in km["keys"]:
    for side in ("pad_a", "pad_b"):
        pad_items.append((k["ref"], k["name"], side, k[side], comp_at(*k[side])))
missing = [p for p in pad_items if p[4] == 0]
print("pads without silver contact found:", len(missing))

# tail traces: sample across the tail stub near the body edge
x_tail = 167.0
col = silver[int(147.0 * PX):int(189.5 * PX), int(x_tail * PX) - 3:int(x_tail * PX) + 4].max(axis=1)
runs, i = [], 0
while i < len(col):
    if col[i]:
        j = i
        while j < len(col) and col[j]:
            j += 1
        if j - i >= 3:
            runs.append((147.0 + (i + j) / 2 / PX))
        i = j
    else:
        i += 1
print("traces across the tail at x=%.0f: %d" % (x_tail, len(runs)))
tail = [(y, comp_at(x_tail, y, 0.15)) for y in runs]

# group pads by component
groups = defaultdict(list)
for ref, name, side, pos, c in pad_items:
    if c:
        groups[c].append((ref, name, side))
tail_comp = {c: idx for idx, (y, c) in enumerate(tail)}

# For each candidate pin numbering, every component touching tail trace idx has net /pin.
nets_of = {k["ref"]: [n.strip("/") for n in k["nets"]] for k in km["keys"]}
for label, pin_of in (("pin1 at smallest y", lambda idx: idx + 1), ("pin1 at largest y", lambda idx: len(tail) - idx)):
    good = bad = 0
    detail = []
    for c, idx in tail_comp.items():
        pin = str(pin_of(idx))
        for ref, name, side in groups.get(c, []):
            if pin in nets_of[ref]:
                good += 1
            else:
                bad += 1; detail.append((pin, ref, name, nets_of[ref]))
    print(f"{label}: pads consistent {good}, inconsistent {bad}")
    if bad and bad < 15:
        for d in detail:
            print("   ", d)

json.dump(dict(tail_traces_y=runs, tail_comps=[int(c) for _, c in tail],
               groups={int(c): v for c, v in groups.items()}), open(f"{out}/connectivity.json", "w"), indent=1)
cv2.imwrite(f"{out}/silver-mask-preview.png", cv2.resize(silver * 255, None, fx=0.2, fy=0.2, interpolation=cv2.INTER_AREA))
