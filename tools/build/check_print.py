"""1:1 fit-check print: outline, holes, key pads, LED pads and tail contacts, tiled on A4 pages.

Print at 100 % ("Actual size"). Check the 100 mm bar on each page, tape the pages together using the
crosses, and lay the original membrane on top: holes and pads should line up.
Usage: python check_print.py <board_geom.json> <out.pdf>
"""
import json
import math
import sys
from PIL import Image, ImageDraw, ImageFont

G = json.load(open(sys.argv[1]))
DPI = 300
S = DPI / 25.4
PAGE_W, PAGE_H = 210.0, 297.0
MARGIN = 12.0
OVERLAP = 15.0
PAD = G["pad"]
_c = G.get("contact", dict(from_end=0.35, len=6.35, w=0.75))
FINGER_W, FINGER_FROM_END, FINGER_LEN = _c["w"], _c["from_end"], _c["len"]

x0, y0, x1, y1 = G["bbox"]
x0 -= 3; y0 -= 3; x1 += 3; y1 += 3
uw, uh = PAGE_W - 2 * MARGIN, PAGE_H - 2 * MARGIN - 10   # usable, minus a footer
nx = math.ceil((x1 - x0 - OVERLAP) / (uw - OVERLAP))
ny = math.ceil((y1 - y0 - OVERLAP) / (uh - OVERLAP))


def chamfer_rect(cx, cy, w, h, c, ang):
    pts = [(-w/2 + c, -h/2), (w/2 - c, -h/2), (w/2, -h/2 + c), (w/2, h/2 - c), (w/2 - c, h/2), (-w/2 + c, h/2),
           (-w/2, h/2 - c), (-w/2, -h/2 + c)]
    a = math.radians(ang)
    return [(cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)) for x, y in pts]


def shapes():
    """yield (kind, data) in board mm"""
    yield "poly_outline", G["board_outline"][0]
    for h in G["holes"]:
        yield "hole", h
    pl = PAD["away"] + PAD["toward"]
    sh = (PAD["toward"] - PAD["away"]) / 2
    for k in G["keys"]:
        (ax, ay), (bx, by) = k["a"], k["b"]
        L = math.hypot(bx - ax, by - ay); ux, uy = (bx - ax) / L, (by - ay) / L
        yield "pad", chamfer_rect(ax + ux * sh, ay + uy * sh, pl, 2 * PAD["half_w"], PAD["chamfer"], k["angle"])
        yield "pad", chamfer_rect(bx - ux * sh, by - uy * sh, pl, 2 * PAD["half_w"], PAD["chamfer"], k["angle"])
        yield "label", ((ax + bx) / 2, (ay + by) / 2, k["name"])
    if "led_pads" in G:
        for lp in G["led_pads"]:
            yield "pad", chamfer_rect(lp["pos"][0], lp["pos"][1], lp["size"][0], lp["size"][1], lp.get("chamfer", 0.0), lp["angle"])
    else:
        (l1x, l1y), (l2x, l2y) = G["led"]
        ang = math.degrees(math.atan2(l2y - l1y, l2x - l1x))
        for x, y in G["led"]:
            yield "pad", chamfer_rect(x, y, 2.4, 2.6, 0.35, ang)
    for p in G["pins"]:
        xe = p["x_end"]
        yield "pad", chamfer_rect(xe - FINGER_FROM_END - FINGER_LEN / 2, p["y"], FINGER_LEN, FINGER_W, 0, 0)


try:
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(2.2 * S))
    small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", int(1.3 * S))
except OSError:
    font = small = ImageFont.load_default()

pages = []
for j in range(ny):
    for i in range(nx):
        ox = x0 + i * (uw - OVERLAP)
        oy = y0 + j * (uh - OVERLAP)
        img = Image.new("L", (int(PAGE_W * S), int(PAGE_H * S)), 255)
        d = ImageDraw.Draw(img)
        P = lambda x, y: ((x - ox + MARGIN) * S, (y - oy + MARGIN) * S)
        for kind, data in shapes():
            if kind == "poly_outline":
                d.line([P(*p) for p in data], fill=0, width=max(1, int(0.2 * S)))
            elif kind == "hole":
                if data["shape"] == "circle":
                    r = data["d"] / 2
                    d.ellipse([P(data["x"] - r, data["y"] - r), P(data["x"] + r, data["y"] + r)], outline=0, width=int(0.2 * S))
                    d.line([P(data["x"] - 1, data["y"]), P(data["x"] + 1, data["y"])], fill=0, width=1)
                    d.line([P(data["x"], data["y"] - 1), P(data["x"], data["y"] + 1)], fill=0, width=1)
                else:
                    w, h = data["ww"], data["h"]
                    d.rounded_rectangle([P(data["x"] - w / 2, data["y"] - h / 2), P(data["x"] + w / 2, data["y"] + h / 2)],
                                        radius=min(w, h) / 2 * S, outline=0, width=int(0.2 * S))
            elif kind == "pad":
                d.polygon([P(*p) for p in data], fill=110)
            elif kind == "label":
                x, y, t = data
                d.text(P(x, y + 3.2), t, fill=0, font=small, anchor="mm")
        # clear the margins so tiles join cleanly, then draw the frame of the usable area
        d.rectangle([0, 0, img.width, MARGIN * S], fill=255)
        d.rectangle([0, (PAGE_H - MARGIN - 10) * S, img.width, img.height], fill=255)
        d.rectangle([0, 0, MARGIN * S, img.height], fill=255)
        d.rectangle([(PAGE_W - MARGIN) * S, 0, img.width, img.height], fill=255)
        d.rectangle([MARGIN * S, MARGIN * S, (PAGE_W - MARGIN) * S, (PAGE_H - MARGIN - 10) * S], outline=160, width=2)
        # alignment crosses on a 10 mm board grid inside the overlap bands
        for gx in range(int(ox // 10) * 10, int(ox + uw) + 10, 10):
            for gy in range(int(oy // 10) * 10, int(oy + uh) + 10, 10):
                in_ovx = gx - ox < OVERLAP or ox + uw - gx < OVERLAP
                in_ovy = gy - oy < OVERLAP or oy + uh - gy < OVERLAP
                if (in_ovx or in_ovy) and 0 < gx - ox < uw and 0 < gy - oy < uh and gx % 50 == 0 and gy % 50 == 0:
                    cx, cy = P(gx, gy)
                    d.line([cx - 3 * S, cy, cx + 3 * S, cy], fill=0, width=2)
                    d.line([cx, cy - 3 * S, cx, cy + 3 * S], fill=0, width=2)
                    d.text((cx + 1 * S, cy + 1 * S), f"{gx},{gy}", fill=0, font=small)
        # 100 mm scale bar + footer
        fy = (PAGE_H - MARGIN - 4) * S
        d.line([MARGIN * S, fy, (MARGIN + 100) * S, fy], fill=0, width=int(0.3 * S))
        for t in range(0, 101, 10):
            d.line([(MARGIN + t) * S, fy - 1.5 * S, (MARGIN + t) * S, fy], fill=0, width=2)
        d.text(((MARGIN + 102) * S, fy - 1.2 * S), f"100 mm - must measure 100.0 mm | page {len(pages)+1}/{nx*ny} "
               f"(col {i+1}, row {j+1})", fill=0, font=small)
        d.text((MARGIN * S, (MARGIN - 6) * S), G.get("print_title", "insanemembrane rev A") + " - 1:1 fit check - print at 100% / Actual size",
               fill=0, font=font)
        pages.append(img)

pages[0].save(sys.argv[2], save_all=True, append_images=pages[1:], resolution=DPI)
print(f"{len(pages)} pages ({nx} x {ny}) -> {sys.argv[2]}")
