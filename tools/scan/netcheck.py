"""Full connectivity check of the original membrane: silver traces + bridges vs the skielek netlist.

Union-find over silver components (back scan) joined by bridges (bars.json). Every key pad, LED pad and
tail contact must land in a group with exactly one net, and every net must be one group.
Usage: python netcheck.py <back-mirrored.png> <scan-data dir>
"""
import json
import sys
from collections import Counter, defaultdict
import cv2
import numpy as np

PX = 600 / 25.4
img = cv2.imread(sys.argv[1])
D = sys.argv[2]
km = json.load(open(f"{D}/keymap.json"))
conn = json.load(open(f"{D}/connectivity.json"))

silver = np.load(sys.argv[3])  # seam-free mask from silvermask.py
silver = cv2.erode(silver, np.ones((5, 5), np.uint8))
n, lab = cv2.connectedComponents(silver, 8)
np.save(f"{D}/../../tools/build/.silver_labels_shape.npy", np.array(lab.shape)) if False else None


def comp(x, y, r=0.7):
    X, Y, R = int(x * PX), int(y * PX), int(r * PX)
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


# bridges: every tap point of one bridge is joined (ends + middle taps)
jumps = json.load(open(f"{D}/jumpers.json"))["jumpers"]
bar_end_comps = []
for jm in jumps:
    taps = jm.get("taps") or [jm["path"][0], jm["path"][-1]]
    cs = [comp(*t_, r=0.8) for t_ in taps]
    bar_end_comps.append((jm, cs))
    good = [c for c in cs if c]
    for c in good[1:]:
        union(good[0], c)
dead = [[round(v, 1) for v in t_] for jm, cs in bar_end_comps for t_, c in zip(jm.get("taps") or [jm["path"][0], jm["path"][-1]], cs) if not c]
print("bridge taps with no silver under them:", dead)

# terminals with their expected nets
terms = []
nets_of = {k["ref"]: [s.strip("/") for s in k["nets"]] for k in km["keys"]}
for k in km["keys"]:
    for side in ("pad_a", "pad_b"):
        terms.append((f"{k['ref']}/{k['name']}/{side}", comp(*k[side], r=0.9), set(nets_of[k["ref"]])))
led = km["unassigned_pairs"][0]
terms.append(("LED/upper-left", comp(*led[0], r=0.9), {"31"}))
terms.append(("LED/lower-right", comp(*led[1], r=0.9), {"9"}))
for i, c in enumerate(conn["tail_comps"]):
    terms.append((f"TAIL/pin{i+1}", c, {str(i + 1)}))

groups = defaultdict(list)
for name, c, exp in terms:
    groups[find(c) if c else ("none", name)].append((name, exp))

conflicts, net_groups = 0, defaultdict(set)
for g, mem in groups.items():
    common = set.intersection(*(e for _, e in mem))
    if not common:
        conflicts += 1
        print("CONFLICT:", [(n_, sorted(e)) for n_, e in mem][:12])
    elif len(common) == 1:
        net_groups[next(iter(common))].add(g)
split = {n_: len(gs) for n_, gs in net_groups.items() if len(gs) > 1}
undecided = [mem for g, mem in groups.items() if len(set.intersection(*(e for _, e in mem))) > 1]
print(f"groups: {len(groups)}, conflicts: {conflicts}")
print(f"nets split into several groups (open in the scan analysis): {split}")
print(f"pads not tied to a specific net (isolated): {len(undecided)}")
for mem in undecided[:12]:
    print("   ", [m[0] for m in mem])

# ---- where are the opens? closest approach between the pieces of each split net / isolated pad -------
from scipy.spatial import cKDTree
members = defaultdict(set)
for c in range(1, n):
    members[find(c)].add(c)
pix = {}
def pts_of(g):
    if g not in pix:
        m = np.isin(lab, list(members[g]))
        p = np.argwhere(m)[::3]
        pix[g] = (p[:, ::-1] / PX)
    return pix[g]
report = []
for net, gs in sorted(net_groups.items()):
    gs = list(gs)
    if len(gs) < 2:
        continue
    for i in range(len(gs)):
        for j in range(i + 1, len(gs)):
            A, B = pts_of(gs[i]), pts_of(gs[j])
            if len(A) == 0 or len(B) == 0:
                continue
            d, idx = cKDTree(A).query(B, k=1)
            k = int(np.argmin(d))
            report.append((net, float(d[k]), B[k].round(1).tolist(), A[idx[k]].round(1).tolist()))
for r in sorted(report, key=lambda r: r[1]):
    print(f"  net {r[0]:>2}: pieces {r[1]:.2f} mm apart at {r[2]} / {r[3]}")

if len(sys.argv) > 4:   # list the terminals in each piece of the given nets
    for net in sys.argv[4].split(","):
        for g in net_groups.get(net, []):
            print(f"net {net} piece:", [m[0] for m in groups[g]])
