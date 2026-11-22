"""Stage 1: turn scan measurements into clean board geometry (mm, KiCad coordinates).

Front-scan frame = carbon side seen face-on = KiCad top view (F.Cu), y down.
Corrections: rotate out the 0.08 deg body tilt, scale y by 600/599.7 (ruler-measured scan Y scale),
shift so the body's top-left corner sits at ORIGIN.

Usage: python geometry.py <scan-data dir> <out.json>
"""
import json
import sys
import numpy as np
from shapely.geometry import Polygon, box
from shapely import affinity
from shapely.ops import unary_union

D = sys.argv[1]
OUT = sys.argv[2]
TRACE_MASK = sys.argv[3] if len(sys.argv) > 3 else None   # silver_conn.npy: centre the tail on its traces
feat = json.load(open(f"{D}/features.json"))
holes = json.load(open(f"{D}/front-holes.json"))
km = json.load(open(f"{D}/keymap.json"))
tail = json.load(open(f"{D}/tailgeom.json"))
conn = json.load(open(f"{D}/connectivity.json"))
PX = 600 / 25.4

TILT_DEG = 0.08          # body long edges measured at 89.92 deg
YSCALE = 600 / 599.7     # scanner Y dpi from rulers B (599.6-599.8)
ORIGIN = np.array([20.0, 20.0])
PAD_EXT = 0.75           # agreed pad extension toward partner (mm)
TAIL_W = 40.2
TAIL_SHORTEN = 10.0   # user: the original tail has ~10 mm spare (it bows when plugged in)
PITCH = 1.25
N_PINS = 31

th = np.radians(-TILT_DEG)
Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
outline_raw = np.array(feat["outline"])
pivot = outline_raw.min(0)


def T(p):
    p = (np.asarray(p, float) - pivot) @ Rm.T
    p = p * [1.0, YSCALE]
    return p


# ---- body outline ---------------------------------------------------------------------------
def orthogonalise(P0):
    """snap long, near-axis edges exactly horizontal/vertical"""
    P = P0.copy(); n = len(P)
    for i in range(n):
        a, b = P0[i], P0[(i + 1) % n]
        d = b - a
        if np.hypot(*d) < 8:
            continue
        ang = np.degrees(np.arctan2(d[1], d[0])) % 180
        if min(ang, 180 - ang) < 1.5:
            y = (a[1] + b[1]) / 2; P[i, 1] = y; P[(i + 1) % n, 1] = y
        elif abs(ang - 90) < 1.5:
            x = (a[0] + b[0]) / 2; P[i, 0] = x; P[(i + 1) % n, 0] = x
    return P


def flatten_runs(P0, axis, tol=0.6, min_span=15.0):
    """runs of consecutive vertices within tol of their median (in `axis`) spanning > min_span along the
    other axis are a straight edge: set them all to the median"""
    P = P0.copy(); n = len(P); i = 0
    other = 1 - axis
    while i < n:
        j = i
        while j + 1 < n and abs(P[j + 1, axis] - np.median(P[i:j + 2, axis])) < tol:
            j += 1
        if j > i and abs(P[j, other] - P[i, other]) > min_span:
            P[i:j + 1, axis] = np.median(P[i:j + 1, axis])
        i = j + 1
    return P


body = Polygon(T(outline_raw)).buffer(0)
# pads near the edge: their white coverlay windows merged with the paper in the scan and carved
# false notches into the outline - fill every pad window back in
from shapely.geometry import Point as _Pt
wins = []
for k in km["keys"]:
    for side in ("pad_a", "pad_b"):
        wins.append(_Pt(*T(k[side])).buffer(2.75))
body = unary_union([body] + [w.intersection(body.envelope) for w in wins])
body = body.buffer(0.6, join_style=2).buffer(-0.6, join_style=2)   # close the seams the fill leaves
_P = np.array(body.exterior.coords)[:-1]
_P = flatten_runs(flatten_runs(_P, 1), 0)
body = Polygon(orthogonalise(_P)).buffer(0)
body = body.simplify(0.05)
shift = ORIGIN - np.array(body.bounds[:2])
body = affinity.translate(body, *shift)


def F(p):
    """front-frame point -> final board coords"""
    return T(p) + shift


# ---- tail: clean rectangle, perpendicular to the body edge -------------------------------
e_a = [F(p) for p in tail["edge_a"]]
e_b = [F(p) for p in tail["edge_b"]]
end_x = (e_a[0][0] + e_b[0][0]) / 2 - TAIL_SHORTEN
tail_cy = (e_a[0][1] + e_a[1][1] + e_b[0][1] + e_b[1][1]) / 4
body_right_at_tail = max(x for x, y in body.exterior.coords if abs(y - tail_cy) < TAIL_W / 2)
if TRACE_MASK:
    # the scanned tail lay ~0.2 deg skewed, so the ideal perpendicular tail drifts off its traces; on the
    # original the tail is centred on them. Measure the 31 traces where they run parallel at the tail root
    import cv2 as _cv2
    _m = np.load(TRACE_MASK)
    _fx = 164.5   # front-frame x just inside the tail root (traces parallel at 1.2544 mm here)
    _col = _m[int(146 * PX):int(191 * PX), int(_fx * PX) - 2:int(_fx * PX) + 3].max(1)
    _idx = np.where(_col)[0]
    _runs = [r for r in np.split(_idx, np.where(np.diff(_idx) > 2)[0] + 1) if len(r) >= 4]
    if len(_runs) == 31:
        _ys = [F([_fx, 146 + r.mean() / PX])[1] for r in _runs]
        print(f"tail centred on its traces: moved {np.mean(_ys) - tail_cy:+.3f} mm "
              f"(trace pitch at the root {np.mean(np.diff(_ys)):.4f} mm)")
        tail_cy = float(np.mean(_ys))
    else:
        print(f"WARNING: found {len(_runs)} tail traces at the root, tail left as measured")
tail_rect = box(body_right_at_tail - 2.0, tail_cy - TAIL_W / 2, end_x, tail_cy + TAIL_W / 2)
board = unary_union([body, tail_rect])
board = board.buffer(1.0, join_style=1).buffer(-1.0, join_style=1)  # 1 mm fillets in inner corners
# larger rounded corners where the tail joins the body (user, 2026-11-15): only those two inner corners,
# the rest of the outline is unchanged
TAIL_FILLET = 2.0
_closed = board.buffer(TAIL_FILLET, join_style=1).buffer(-TAIL_FILLET, join_style=1)
_zone = unary_union([box(body_right_at_tail - TAIL_FILLET - 3, y - TAIL_FILLET - 3,
                         body_right_at_tail + TAIL_FILLET + 3, y + TAIL_FILLET + 3)
                     for y in (tail_cy - TAIL_W / 2, tail_cy + TAIL_W / 2)])
board = unary_union([board, _closed.difference(board).intersection(_zone)]).buffer(0)
board = board.simplify(0.02)

# pins: pin 1 at smallest y (verified against the silver traces)
pins = []
for k in range(N_PINS):
    y = tail_cy + (k - (N_PINS - 1) / 2) * PITCH
    pins.append(dict(pin=k + 1, x_end=end_x, y=y))

# ---- holes -------------------------------------------------------------------------------
H = []
for h in holes:
    if h["d_eq_mm"] < 5:
        continue
    c = F([h["cx"] / PX, h["cy"] / PX])
    if abs(h["w_mm"] - h["h_mm"]) > 1.0:   # slot
        H.append(dict(x=c[0], y=c[1], shape="oval", w=6.0, h=8.0 if h["h_mm"] > h["w_mm"] else 6.0,
                      ww=8.0 if h["w_mm"] > h["h_mm"] else 6.0))
    else:
        d = 6.0 if h["d_eq_mm"] < 6.2 else 6.5
        H.append(dict(x=c[0], y=c[1], shape="circle", d=d))
# drop duplicates (holes seen twice in the overlap)
uniq = []
for h in H:
    if all(np.hypot(h["x"] - u["x"], h["y"] - u["y"]) > 2 for u in uniq):
        uniq.append(h)
H = uniq

# ---- keys --------------------------------------------------------------------------------
vecs = []
for k in km["keys"]:
    a, b = F(k["pad_a"]), F(k["pad_b"])
    vecs.append(b - a)
vecs = np.array(vecs)
ang = np.degrees(np.arctan2(vecs[:, 1], vecs[:, 0]))
main = np.abs(ang - np.median(ang)) < 20
spacing = float(np.mean(np.hypot(*vecs.T)))
ang_main = float(np.degrees(np.arctan2(vecs[main, 1].mean(), vecs[main, 0].mean())))
print(f"pad spacing {spacing:.3f} mm, main axis {ang_main:.2f} deg, odd-orientation keys: "
      f"{[k['name'] for k, m in zip(km['keys'], main) if not m]}")

# net per pad from the original silver traces
groups = conn["groups"]
tail_comps = conn["tail_comps"]
comp_of = {}
for g, mem in groups.items():
    for ref, name, side in mem:
        comp_of[(ref, side)] = int(g)
pin_of_comp = {c: i + 1 for i, c in enumerate(tail_comps)}
nets_of = {k["ref"]: [s.strip("/") for s in k["nets"]] for k in km["keys"]}
group_net = {}
for g, mem in groups.items():
    g = int(g)
    if g in pin_of_comp:
        group_net[g] = str(pin_of_comp[g])
    elif len(mem) >= 2:
        common = set.intersection(*(set(nets_of[r]) for r, _, _ in mem))
        if len(common) == 1:
            group_net[g] = common.pop()

keys = []
undetermined = 0
for k, m in zip(km["keys"], main):
    a, b = F(k["pad_a"]), F(k["pad_b"])
    mid = (a + b) / 2
    angle = ang_main if m else ang_main + 90 * np.sign(np.degrees(np.arctan2(*(b - a)[::-1])) - ang_main)
    u = np.array([np.cos(np.radians(angle)), np.sin(np.radians(angle))])
    if np.dot(u, b - a) < 0:
        u = -u
    pa, pb = mid - u * spacing / 2, mid + u * spacing / 2
    n1, n2 = nets_of[k["ref"]]
    na = group_net.get(comp_of.get((k["ref"], "pad_a")))
    nb = group_net.get(comp_of.get((k["ref"], "pad_b")))
    if na is None and nb is not None:
        na = n1 if nb == n2 else n2
    if nb is None and na is not None:
        nb = n1 if na == n2 else n2
    if na is None:
        na, nb = n1, n2
        undetermined += 1
    assert {na, nb} == {n1, n2}, (k["ref"], na, nb, n1, n2)
    keys.append(dict(ref=k["ref"], name=k["name"], a=pa.tolist(), b=pb.tolist(),
                     angle=float(np.degrees(np.arctan2(u[1], u[0]))), net_a=na, net_b=nb))
print(f"keys: {len(keys)}; pad nets taken from the original traces for {len(keys) - undetermined}, "
      f"free choice (both pads unconnected in scan) for {undetermined}")

# ---- caps lock LED pads -------------------------------------------------------------------
led = [F(p) for p in km["unassigned_pairs"][0]]

geom = dict(
    board_outline=[list(board.exterior.coords)],
    board_holes_in_outline=[list(i.coords) for i in board.interiors],
    holes=H, keys=keys, led=[p.tolist() for p in led], pins=pins,
    tail=dict(end_x=end_x, cy=tail_cy, width=TAIL_W, root_x=body_right_at_tail),
    pad=dict(away=1.45, toward=1.27 + PAD_EXT, half_w=1.90, chamfer=0.55),
    bbox=list(board.bounds),
    transform=dict(pivot=pivot.tolist(), tilt_deg=TILT_DEG, yscale=YSCALE, shift=shift.tolist()),
    watermark="a1200/docs/watermark/watermark.json",
    print_title="insanemembrane A1200 rev A",
)
json.dump(geom, open(OUT, "w"), indent=1)
bx = board.bounds
print(f"board {bx[2]-bx[0]:.2f} x {bx[3]-bx[1]:.2f} mm; holes {len(H)} "
      f"({sum(h['shape']=='circle' and h['d']==6.5 for h in H)}x6.5, "
      f"{sum(h['shape']=='circle' and h['d']==6.0 for h in H)}x6.0, {sum(h['shape']=='oval' for h in H)} slot); "
      f"LED pads {np.round(led,2).tolist()}; tail end x {end_x:.2f}, centre y {tail_cy:.2f}")
