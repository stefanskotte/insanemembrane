"""A500: derive the netlist from the original itself (silver traces + bridges), with self-checks.

Union-find over silver components (seam-free back mask, front frame) joined by every bridge.
Terminals: the 31 finger traces (crossing x = FINGER_X, pin 1 = smallest y), 194 carbon pads.
Checks: each finger in its own group (no shorts), every pad in a group with exactly one finger,
the two pads of a key on different fingers. Writes netlist.json (pad -> pin, key -> pin pair).
Usage: python netlist.py <silver_conn.npy> <scan-data dir> [debug.png]
"""
import json
import sys
from collections import Counter, defaultdict
import cv2
import numpy as np

PX = 600 / 25.4
D = sys.argv[2]
FINGER_X, FINGER_Y = 139.0, (311.0, 353.0)
ERODE = 1
EDGE_BAND = 0.35   # mm
FINGER_CUT = 143.5
FINGER_Y0, FINGER_PITCH, FINGER_SAMPLE_X = 313.224, 1.2517, 142.0
m = np.load(sys.argv[1]).astype(np.uint8)
try:
    for t in json.load(open(f"{D}/manual_traces.json"))["traces"]:
        cv2.polylines(m, [(np.array(t["path"]) * PX).astype(np.int32)], False, 1, int(0.35 * PX))
except FileNotFoundError:
    pass
# the cut edge of the film scans grey and reads as "silver": drop a thin band along the outline
# (film = anything not paper-white; the clear finger tab is handled separately below)
_f = cv2.imread(f"{D}/../scan-front-stitched.png", cv2.IMREAD_GRAYSCALE)
film = cv2.morphologyEx((_f < 215).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
film = cv2.erode(film, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (int(2 * EDGE_BAND * PX) | 1,) * 2))
m &= film
# finger tab: keep the finger roots (x 139.5-143.5), cut thin gaps between neighbouring fingers, drop the rest
FY = [FINGER_Y0 + FINGER_PITCH * i for i in range(31)]
ty0, ty1 = int((FY[0] - 1.5) * PX), int((FY[-1] + 1.5) * PX)
m[ty0:ty1, int(FINGER_CUT * PX):] = 0
for y in FY[:-1]:
    yc = int((y + FINGER_PITCH / 2) * PX)
    m[yc - 2:yc + 3, int(141.4 * PX):int(FINGER_CUT * PX)] = 0   # finger tab itself (stiffener haze merges the fingers in the scan)
cond = cv2.erode(m, np.ones((ERODE, ERODE), np.uint8)) if ERODE > 1 else m   # A500 traces ~0.25 mm
n, lab = cv2.connectedComponents(cond, 8)


def comp(x, y, r):
    X, Y, R = int(x * PX), int(y * PX), max(1, int(r * PX))
    w = lab[Y - R:Y + R + 1, X - R:X + R + 1]
    c = Counter(w[w > 0].ravel().tolist()).most_common(1)
    return c[0][0] if c else 0


parent = {}
def find(a):
    parent.setdefault(a, a)
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
def union(a, b):
    parent[find(a)] = find(b)


jumps = json.load(open(f"{D}/jumpers.json"))["jumpers"]
dead = []
for j in jumps:
    cs = [comp(*t, 0.8) for t in j["taps"]]
    if not all(cs):
        dead.append(np.round(j["taps"], 1).tolist())
    good = [c for c in cs if c]
    for c in good[1:]:
        union(good[0], c)
print("bridge ends with no silver under them:", dead)

# carbon pads conduct: every silver piece that runs under a pad's carbon joins that pad
front = cv2.imread(f"{D}/../scan-front-stitched.png")
hsv = cv2.cvtColor(front, cv2.COLOR_BGR2HSV)
carbon = ((hsv[..., 2] < 125) & (hsv[..., 1] < 110)).astype(np.uint8)
carbon = cv2.morphologyEx(carbon, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
nc, clab = cv2.connectedComponents(carbon, 8)
F = json.load(open(f"{D}/features.json"))
pad_joins = 0
for p in F["pads"]:
    X, Y = int(p["x"] * PX), int(p["y"] * PX)
    R = int(3.0 * PX)
    cw = clab[Y - R:Y + R, X - R:X + R]
    cid = cw[R, R]
    if not cid:
        continue
    under = cv2.erode((cw == cid).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
    cnt = Counter(lab[Y - R:Y + R, X - R:X + R][under].ravel().tolist())
    ids = [c for c, k in cnt.items() if c and k >= 20]   # really under the carbon, not grazing its edge
    for c in ids[1:]:
        union(ids[0], c); pad_joins += 1
print("silver pieces joined under carbon pads:", pad_joins)

# fingers
fingers = []
for i, y in enumerate(FY):
    c = comp(FINGER_SAMPLE_X, y, 0.25)
    fingers.append((int(c), y))
print("fingers found on the tab: %d of 31" % sum(1 for c, y in fingers if c), [i + 1 for i, (c, y) in enumerate(fingers) if not c])
pin_of_group = defaultdict(list)
for p, (c, y) in enumerate(fingers):
    if c:
        pin_of_group[find(c)].append(p + 1)
shorts = {g: ps for g, ps in pin_of_group.items() if len(ps) > 1}
print("finger shorts (fingers joined to each other):", list(shorts.values()))

pads = F["pads"]
pad_pin, problems = {}, []
for i, p in enumerate(pads):
    c = comp(p["x"], p["y"], 0.9)
    ps = pin_of_group.get(find(c)) if c else None
    pad_pin[i] = ps[0] if ps and len(ps) == 1 else None
    if pad_pin[i] is None:
        problems.append((i, round(p["x"], 1), round(p["y"], 1), "no silver" if not c else ("short" if ps else "no finger")))
print(f"pads: {len(pads)}, tied to one finger: {sum(v is not None for v in pad_pin.values())}")
for pr in problems:
    print("   pad", pr)
keys, bad = [], []
for k in F["keys"]:
    a, b = pad_pin[k["a"]], pad_pin[k["b"]]
    keys.append(dict(cx=k["cx"], cy=k["cy"], a=k["a"], b=k["b"], pins=[a, b]))
    if a is None or b is None or a == b:
        bad.append((round(k["cx"], 1), round(k["cy"], 1), a, b))
print(f"keys: {len(keys)}, bad: {len(bad)}", bad)
# matrix view: which pins pair with which
pairs = Counter(tuple(sorted(k["pins"])) for k in keys if None not in k["pins"])
dup = {p: c for p, c in pairs.items() if c > 1}
print("pin pairs used by more than one key (would be the same key electrically!):", dup)
usage = Counter(p for k in keys for p in k["pins"] if p)
print("pin usage:", dict(sorted(usage.items())))
json.dump(dict(fingers=[dict(pin=p + 1, y=y) for p, (c, y) in enumerate(fingers)], pad_pin={str(k): v for k, v in pad_pin.items()},
               keys=keys, shorts=list(shorts.values()), problems=problems), open(f"{D}/netlist.json", "w"), indent=1)
