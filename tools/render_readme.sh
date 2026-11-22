#!/bin/bash
# Re-render the README images for one or more membranes (low CPU priority).
# Usage: tools/render_readme.sh a1200 a500 a600
set -euo pipefail
cd "$(dirname "$0")/.."
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
TMP=$(mktemp -d)
for m in "$@"; do
  PCB=$m/kicad/insanemembrane-$m.kicad_pcb
  case $m in a1200) Z=7.80; PAN="1.063,-0.889,0";; a500) Z=7.82; PAN="1.060,-0.889,0";; a600) Z=5.62; PAN="3.797,-0.889,0";; esac
  nice -n 15 $CLI pcb render --side top --width 1600 --height 1000 --background opaque --quality high --perspective --rotate "-35,0,-20" --zoom 0.95 -o docs/images/$m-3d.png $PCB >/dev/null 2>&1
  nice -n 15 $CLI pcb render --side top --width 1400 --height 900 --background opaque --quality high --zoom $Z --pan "$PAN" -o docs/images/$m-detail.png $PCB >/dev/null 2>&1
  nice -n 15 $CLI pcb render --side top --width 3000 --height 3000 --background transparent --quality high -o $TMP/$m-top-hi.png $PCB >/dev/null 2>&1
  nice -n 15 $CLI pcb render --side top --width 4000 --height 4000 --background transparent --quality basic -o $TMP/$m-mid.png $PCB >/dev/null 2>&1
  .venv/bin/python - "$m" "$TMP" <<'PY'
import json, sys
from PIL import Image
m, T = sys.argv[1], sys.argv[2]
D = f"{m}/docs/scan-data"
G = json.load(open(f"{D}/board_geom.json")); bx = G["bbox"]; tl = G["tail"]
con = G.get("contact", dict(from_end=0.35, len=6.35))
im = Image.open(f"{T}/{m}-top-hi.png").convert("RGBA"); x0, y0, x1, y1 = im.split()[3].point(lambda v: 255 if v > 10 else 0).getbbox()
full = im.crop((x0 - 10, y0 - 10, x1 + 10, y1 + 10)); full.thumbnail((1100, 1100)); full.save(f"docs/images/{m}-top.png")
im = Image.open(f"{T}/{m}-mid.png").convert("RGBA"); x0, y0, x1, y1 = im.split()[3].point(lambda v: 255 if v > 10 else 0).getbbox()
sx = (x1 - x0) / (bx[2] - bx[0]); sy = (y1 - y0) / (bx[3] - bx[1]); P = lambda x, y: (x0 + (x - bx[0]) * sx, y0 + (y - bx[1]) * sy)
(a0, b0), (a1, b1) = P(tl["end_x"] - con["from_end"] - con["len"] - 18, tl["cy"] - tl["width"] / 2 - 4), P(tl["end_x"] + 3, tl["cy"] + tl["width"] / 2 + 4)
cr = im.crop((int(a0), int(b0), int(a1), int(b1))); bg = Image.new("RGBA", cr.size, (255, 255, 255, 255)); bg.alpha_composite(cr)
bg.convert("RGB").save(f"docs/images/{m}-contacts.png")
print(m, "README images updated")
PY
done
rm -rf "$TMP"
