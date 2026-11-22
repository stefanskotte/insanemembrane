#!/bin/bash
# A1200: rebuild the replica board from the scans: masks -> geometry -> routing -> pads -> heal -> octi -> tidy -> board -> DRC -> fab.
# Needs the project venv (.venv: numpy, opencv-contrib-python-headless, scipy, shapely, pillow) and KiCad 10.
set -euo pipefail
cd "$(dirname "$0")/../.."
PYV=${PYV:-.venv/bin/python}
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
W=${WORK:-a1200/build}; D=a1200/docs/scan-data; PCB=a1200/kicad/insanemembrane-a1200.kicad_pcb
mkdir -p "$W" a1200/kicad a1200/fab

[ -f "$W/silver_conn.npy" ] || $PYV tools/a1200/silvermask.py . "$W/silver_conn.npy" 225
[ -f "$W/silver_geo.npy" ]  || $PYV tools/a1200/silvermask.py . "$W/silver_geo.npy" 195
$PYV tools/a1200/geometry.py $D $D/board_geom.json "$W/silver_conn.npy"
$PYV tools/a1200/replica.py . "$W/silver_conn.npy" $D/routing.json "$W/silver_geo.npy" | grep -v UNDECIDED
$PYV tools/build/pads.py $D
$PYV tools/build/heal.py $D
$PYV tools/build/octi.py $D
$PYV tools/build/tidy.py $D
$PYV tools/build/pads.py $D
$KPY tools/build/build_board.py $D/board_geom.json $PCB $D/routing.json 2>&1 | grep -v wxApp
$CLI pcb drc --format json -o "$W/drc.json" $PCB >/dev/null 2>&1 || true
$PYV tools/build/drc_report.py "$W/drc.json" 4

# ---- fab package for JLC ------------------------------------------------------------------------
rm -rf a1200/fab/gerbers && mkdir -p a1200/fab/gerbers
$CLI pcb export gerbers --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts,User.1 \
    --subtract-soldermask -o a1200/fab/gerbers/ $PCB >/dev/null
$CLI pcb export drill --format excellon --excellon-separate-th --excellon-units mm -o a1200/fab/gerbers/ $PCB >/dev/null
rm -f a1200/fab/insanemembrane-*jlc-gerbers.zip
(cd a1200/fab/gerbers && zip -q ../insanemembrane-a1200-jlc-gerbers.zip *.gtl *.gbl *.gts *.gbs *.gto *.gbo *.gm1 *.gbr *.drl)
rm -f a1200/fab/insanemembrane-1to1-fit-check.pdf
$PYV tools/build/check_print.py $D/board_geom.json a1200/fab/insanemembrane-a1200-1to1-fit-check.pdf
for side in top bottom; do
  $CLI pcb render --side $side --width 1400 --height 1400 --background opaque --quality basic \
      -o a1200/fab/render-$side.png $PCB >/dev/null 2>&1 || true
done
echo "fab package: $(unzip -l a1200/fab/insanemembrane-a1200-jlc-gerbers.zip | tail -1)"
