"""Render a board region from board_geom.json + routing.json + pads_final.json (for checking by eye).
Usage: python render_area.py <scan-data dir> x0 y0 x1 y1 px_per_mm out.png [routing.json]"""
import json, sys
from PIL import Image, ImageDraw
sys.path.insert(0, __file__.rsplit("/", 1)[0])
from geomlib import contact_items, led_items
D = sys.argv[1]; x0, y0, x1, y1, k = map(float, sys.argv[2:7]); out = sys.argv[7]
R = json.load(open(sys.argv[8] if len(sys.argv) > 8 else f"{D}/routing.json"))
G = json.load(open(f"{D}/board_geom.json")); P = json.load(open(f"{D}/pads_final.json"))["pads"]
import os
W_, H_ = int((x1 - x0) * k), int((y1 - y0) * k)
UNDER = os.environ.get("UNDERLAY")   # path to a front-frame 600 dpi scan: drawn faded underneath
if UNDER:
    import cv2, numpy as np
    PX = 600 / 25.4
    tr = G["transform"]
    th = np.radians(tr["rot_deg"] if "rot_deg" in tr else -tr["tilt_deg"])
    Rm = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    Minv = Rm.T @ np.diag([1.0, 1.0 / tr["yscale"]])          # board -> scan (mm), linear part
    tvec = np.array(tr["pivot"]) - Minv @ np.array(tr["shift"])
    # output pixel (u, v) -> board (x0 + u/k, y0 + v/k) -> scan px
    A = PX * Minv @ np.diag([1 / k, 1 / k]); b = PX * (Minv @ np.array([x0, y0]) + tvec)
    img = cv2.imread(UNDER)
    und = cv2.warpAffine(img, np.hstack([A, b[:, None]]), (W_, H_), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    und = (und.astype(float) * 0.55).astype("uint8")
    im = Image.fromarray(cv2.cvtColor(und, cv2.COLOR_BGR2RGB))
else:
    im = Image.new("RGB", (W_, H_), (24, 28, 36))
d = ImageDraw.Draw(im)
NOFILL = os.environ.get("OUTLINE_ONLY")
f = lambda p: ((p[0] - x0) * k, (p[1] - y0) * k)
o = G["board_outline"][0]; d.line([f(q) for q in o] + [f(o[0])], fill=(230, 230, 230), width=2)
for h in G["holes"]:
    r = (h.get("d") or h.get("w", 6)) / 2
    d.ellipse([f((h["x"] - r, h["y"] - r)), f((h["x"] + r, h["y"] + r))], outline=(200, 200, 200), width=2)
for p in P: d.polygon([f(q) for q in p["poly"]], fill=(150, 40, 60))
for net, g in contact_items(G) + led_items(G): d.polygon([f(q) for q in g.exterior.coords], fill=(200, 160, 40))
for lay, col in (("B.Cu", (60, 130, 230)), ("F.Cu", (230, 60, 60))):
    for t in R["tracks"]:
        if t["layer"] == lay and len(t["pts"]) > 1:
            d.line([f(q) for q in t["pts"]], fill=col, width=max(1, int(t["w"] * k * (0.4 if NOFILL else 1))))
for v in R["vias"]:
    c = f(v["pos"]); r = 0.35 * k; d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=(240, 240, 120))
if k >= 15:
    for t in R["tracks"]:
        if t["layer"] == "F.Cu" and t["pts"]:
            q = t["pts"][len(t["pts"]) // 2]
            if x0 < q[0] < x1 and y0 < q[1] < y1: d.text(f(q), t["net"], fill=(255, 255, 255))
im.save(out)
