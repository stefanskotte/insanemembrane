"""A500 stage 1: turn scan measurements into clean board geometry (mm, KiCad coordinates).

Front-scan frame = carbon side seen face-on = KiCad top view (F.Cu), y down.
Corrections: rotate out the body tilt (measured from the long edges), scale y by the scanner's Y dpi
(600/599.7, ruler-measured on this scanner for the A1200), shift so the body's top-left corner sits at ORIGIN.
The finger tab is rebuilt as a clean rectangle perpendicular to the body edge; its 31 fingers sit at an exact
1.25 mm pitch centred on the measured finger centre.

Usage: python geometry.py <a500 scan-data dir> <out board_geom.json>
"""
import json
import sys
import numpy as np
from shapely.geometry import Polygon, Point, box
from shapely import affinity
from shapely.ops import unary_union

D, OUT = sys.argv[1], sys.argv[2]
PX = 600 / 25.4
feat = json.load(open(f"{D}/features.json"))
holes = json.load(open(f"{D}/front-holes.json"))
NL = json.load(open(f"{D}/netlist.json"))
YSCALE = 600 / 599.7
ORIGIN = np.array([20.0, 20.0])
PAD_EXT = 0.75
PITCH, N_PINS = 1.25, 31
# finger tab, front frame (measured: design-notes.md)
TAB_TIP_X, TAB_Y0, TAB_Y1 = 150.88, 312.29, 351.49
FINGER_Y0, FINGER_PITCH_SCAN = 313.224, 1.2517
CONTACT = dict(from_end=0.35, len=8.5, w=0.80)      # spec 7 said 9.5; 8.5 keeps the inner end clear of the root fillets
COVERLAY_END = 7.5                                   # coverlay opening from the tip
STIFFENER = dict(len=7.86, side="bottom")            # user-measured
LED_IDX = None

outline_raw = np.array(feat["outline"])
# ---- tilt from the two long edges (vertices with x near the min / max of the upper body) -----------
# length-weighted tilt of the long near-vertical outline segments (> 100 mm)
segs = []
for i in range(len(outline_raw)):
    p, q = outline_raw[i], outline_raw[(i + 1) % len(outline_raw)]
    d = q - p
    L = np.hypot(*d)
    if L > 100 and abs(d[0]) < 0.05 * L:
        if d[1] < 0:
            d = -d
        segs.append((np.degrees(np.arctan2(d[0], d[1])), L, p.round(1).tolist(), q.round(1).tolist()))
for sg in segs:
    print("  long edge %.3f deg, %.0f mm, %s -> %s" % sg)
TILT_DEG = float(sum(a_ * l_ for a_, l_, _, _ in segs) / sum(l_ for _, l_, _, _ in segs))
print(f"body tilt (from the long edges): correcting {TILT_DEG:.3f} deg")
th = np.radians(TILT_DEG)              # rotate points so the edges become vertical
Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
pivot = outline_raw.min(0)


def T(p):
    p = (np.asarray(p, float) - pivot) @ Rm.T
    return p * [1.0, YSCALE]


def orthogonalise(P0):
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


# ---- body (the scanned outline without the clear finger tab) --------------------------------------
body = Polygon(T(outline_raw)).buffer(0)
pads = feat["pads"]
wins = [Point(*T([p["x"], p["y"]])).buffer(2.75) for p in pads]
body = unary_union([body] + [w.intersection(body.envelope) for w in wins])
body = body.buffer(0.6, join_style=2).buffer(-0.6, join_style=2)
# the green print stops 5 mm short of the tab tip: cut the stub of tab the outline picked up back to the body edge
tab_zone = Polygon([T(p) for p in ((141.6, TAB_Y0 - 2.0), (160, TAB_Y0 - 2.0), (160, TAB_Y1 + 2.0), (141.6, TAB_Y1 + 2.0))])
body = body.difference(tab_zone)
_P = np.array(body.exterior.coords)[:-1]
_P = flatten_runs(flatten_runs(_P, 1), 0)
body = Polygon(orthogonalise(_P)).buffer(0).simplify(0.05)
shift = ORIGIN - np.array(body.bounds[:2])
body = affinity.translate(body, *shift)


def F(p):
    return T(p) + shift


# ---- finger tab --------------------------------------------------------------------------------
c_scan = np.array([TAB_TIP_X, (TAB_Y0 + TAB_Y1) / 2])
fy_mid_scan = FINGER_Y0 + FINGER_PITCH_SCAN * 15
tip = F([TAB_TIP_X, fy_mid_scan])
end_x = float(tip[0])
fing_cy = float(F([TAB_TIP_X, fy_mid_scan])[1])   # same x as the tab edges (fingers run parallel to them)
tab_cy = float(F(c_scan)[1])
tab_w = (TAB_Y1 - TAB_Y0) * YSCALE
from shapely.geometry import LineString as _LS
_hit = body.intersection(_LS([(0, tab_cy), (1000, tab_cy)]))
root_x = float(_hit.bounds[2])   # body edge on the tab's centre line
print(f"tab: root x {root_x:.2f}, tip x {end_x:.2f} (sticks out {end_x - root_x:.2f} mm), width {tab_w:.2f}, "
      f"centre y {tab_cy:.2f}; finger centre y {fing_cy:.2f} (offset {fing_cy - tab_cy:+.2f})")
tab = box(root_x - 2.0, tab_cy - tab_w / 2, end_x, tab_cy + tab_w / 2)
board = unary_union([body, tab]).buffer(1.0, join_style=1).buffer(-1.0, join_style=1)   # 1 mm inner fillets
# outer corners rounded R 1.2 like the original (user, 2026-11-22, from the fit-check print); the tab tip
# corners stay square because fingers 1 / 31 sit ~0.6 mm from the tab edge
OUTER_R = 1.2
_tipzone = box(end_x - 3.0, tab_cy - tab_w / 2 - 3.0, end_x + 1.0, tab_cy + tab_w / 2 + 3.0)
_rounded = board.buffer(-OUTER_R, join_style=1).buffer(OUTER_R, join_style=1)
board = unary_union([_rounded, board.intersection(_tipzone)]).buffer(0)
board = board.simplify(0.02)
pins = [dict(pin=k + 1, x_end=end_x, y=fing_cy + (k - (N_PINS - 1) / 2) * PITCH) for k in range(N_PINS)]

# ---- holes ----------------------------------------------------------------------------------------
H = []
for h in holes:
    if h["d_eq_mm"] < 2.5:
        continue
    c = F([h["cx"] / PX, h["cy"] / PX])
    if abs(h["w_mm"] - h["h_mm"]) > 1.0:
        H.append(dict(x=c[0], y=c[1], shape="oval", w=6.0, h=8.0 if h["h_mm"] > h["w_mm"] else 6.0,
                      ww=8.0 if h["w_mm"] > h["h_mm"] else 6.0))
    else:
        d = 3.2 if h["d_eq_mm"] < 4 else (6.0 if h["d_eq_mm"] < 6.2 else 6.5)
        H.append(dict(x=c[0], y=c[1], shape="circle", d=d))
uniq = []
for h in H:
    if all(np.hypot(h["x"] - u["x"], h["y"] - u["y"]) > 2 for u in uniq):
        uniq.append(h)
H = uniq

# ---- keys + LED --------------------------------------------------------------------------------------
keys, led = [], None
vecs = []
for k in NL["keys"]:
    a, b = pads[k["a"]], pads[k["b"]]
    vecs.append(F([b["x"], b["y"]]) - F([a["x"], a["y"]]))
vecs = np.array(vecs)
sep = np.hypot(*vecs.T)
is_led = sep < 5.5
spacing = float(np.mean(sep[~is_led]))
ang = np.degrees(np.arctan2(vecs[:, 1], vecs[:, 0])) % 180
ang_main = float(np.median(ang[~is_led]))
print(f"pad spacing {spacing:.3f} mm, main axis {ang_main:.2f} deg; keys on the other diagonal: "
      f"{int(np.sum(np.abs(np.abs(ang[~is_led] - ang_main) - 90) < 20))}")
n = 0
for k, v, led_ in zip(NL["keys"], vecs, is_led):
    pa_, pb_ = pads[k["a"]], pads[k["b"]]
    a, b = F([pa_["x"], pa_["y"]]), F([pb_["x"], pb_["y"]])
    if led_:
        la = float(np.degrees(np.arctan2(*(b - a)[::-1])))   # pair axis; pads are 2.8 along it x 4.6 across (original 2.95 x 4.95)
        led = dict(pads=[dict(net=str(k["pins"][0]), pos=a.tolist(), size=[2.8, 4.6], angle=la, chamfer=0.4),
                         dict(net=str(k["pins"][1]), pos=b.tolist(), size=[2.8, 4.6], angle=la, chamfer=0.4)])
        continue
    n += 1
    mid = (a + b) / 2
    a_k = np.degrees(np.arctan2(v[1], v[0])) % 180
    ax_ = ang_main if min(abs(a_k - ang_main), 180 - abs(a_k - ang_main)) < 20 else ang_main + 90   # one key sits on the other diagonal
    u = np.array([np.cos(np.radians(ax_)), np.sin(np.radians(ax_))])
    if np.dot(u, b - a) < 0:
        u = -u
    pa, pb = mid - u * spacing / 2, mid + u * spacing / 2
    keys.append(dict(ref=f"K{n}", name=f"K{n}", a=pa.tolist(), b=pb.tolist(),
                     angle=float(np.degrees(np.arctan2(u[1], u[0]))), net_a=str(k["pins"][0]), net_b=str(k["pins"][1])))
print(f"keys: {len(keys)}, LED pads: {[(p['net'], np.round(p['pos'], 2).tolist()) for p in led['pads']]}")

LABEL_POS = F([150.0, 150.0]).tolist()
geom = dict(
    board_outline=[list(board.exterior.coords)],
    board_holes_in_outline=[list(i.coords) for i in board.interiors],
    holes=H, keys=keys, led=[p["pos"] for p in led["pads"]], led_pads=led["pads"], pins=pins,
    tail=dict(end_x=end_x, cy=tab_cy, width=tab_w, root_x=root_x),
    contact=CONTACT, coverlay_end=COVERLAY_END, stiffener=STIFFENER,
    pad=dict(away=1.35, toward0=1.40, toward=1.40 + PAD_EXT, half_w=1.92, chamfer=0.55),
    bbox=list(board.bounds),
    transform=dict(pivot=pivot.tolist(), rot_deg=TILT_DEG, yscale=YSCALE, shift=shift.tolist()),
    model="A500",
    print_title="insanemembrane A500 rev A",
    entry_band_margin=6.0, entry_allow_vertical=True, octi_fallback_move=0.8,
    pin1_marker_x=end_x - CONTACT["from_end"] - CONTACT["len"] - 1.0,
    label="insanemembrane - A500 Mitsumi A-500(E) 56 A619B replacement - rev A",
    label_pos=LABEL_POS, label_angle=90,
    stiffener_text="PI STIFFENER, BOTTOM SIDE - total 0.40 mm at fingers",
    stiffener_note="Stiffener: PI bottom, 7.86mm from finger tips, full tab width. Total at fingers 0.40mm (min 0.36)",
    stiffener_note_dy=-(tab_w / 2 + 3), contact_keepout_halfw=tab_w / 2 + 3,
    watermark="a500/docs/watermark/watermark.json",
)
json.dump(geom, open(OUT, "w"), indent=1)
bx = board.bounds
print(f"board {bx[2]-bx[0]:.2f} x {bx[3]-bx[1]:.2f} mm; holes {len(H)}: "
      f"{sum(h['shape']=='circle' and h['d']==6.5 for h in H)}x6.5, {sum(h['shape']=='circle' and h['d']==6.0 for h in H)}x6.0, "
      f"{sum(h['shape']=='circle' and h['d']==3.2 for h in H)}x3.2, {sum(h['shape']=='oval' for h in H)} slots")
