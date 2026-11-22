#!/bin/bash
# A600: rebuild the replica board from the scans: masks -> bridges -> netlist -> geometry -> routing -> board -> DRC -> fab.
# Needs the project venv (.venv: numpy, opencv-contrib-python-headless, scipy, shapely, pillow) and KiCad 10.
set -euo pipefail
cd "$(dirname "$0")/../.."
PYV=${PYV:-.venv/bin/python}
KPY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3
CLI=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
W=a600/build; D=a600/docs/scan-data; PCB=a600/kicad/insanemembrane-a600.kicad_pcb
mkdir -p $W a600/kicad a600/fab
[ -f $W/silver_conn.npy ] || $PYV tools/a600/silvermask.py . $W/silver_conn.npy 225
[ -f $W/silver_geo.npy ]  || $PYV tools/a600/silvermask.py . $W/silver_geo.npy 195
$PYV tools/a600/lands.py $W/silver_conn.npy $D/lands.npy
$PYV tools/a600/bridges.py a600/docs/scan-front-stitched.png $D/lands.npy $D
$PYV tools/a600/netlist.py $W/silver_geo.npy $D | grep -v "^   pad"
$PYV tools/a600/geometry.py $D $D/board_geom.json
$PYV tools/a600/replica.py $W/silver_geo.npy $D
$PYV tools/build/pads.py $D
$PYV tools/build/heal.py $D
$PYV tools/build/octi.py $D
$PYV tools/build/tidy.py $D
$PYV tools/build/drop_loops.py $D
$PYV tools/build/straighten.py $D
$PYV tools/build/pads.py $D
$KPY tools/build/build_board.py $D/board_geom.json $PCB $D/routing.json 2>&1 | grep -v wxApp
$CLI pcb drc --format json -o $W/drc.json $PCB >/dev/null 2>&1 || true
$PYV tools/build/drc_report.py $W/drc.json 6

# ---- fab package for JLC ------------------------------------------------------------------------
rm -rf a600/fab/gerbers && mkdir -p a600/fab/gerbers
$CLI pcb export gerbers --layers F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts,User.1 \
    --subtract-soldermask -o a600/fab/gerbers/ $PCB >/dev/null
$CLI pcb export drill --format excellon --excellon-separate-th --excellon-units mm -o a600/fab/gerbers/ $PCB >/dev/null
rm -f a600/fab/insanemembrane-a600-jlc-gerbers.zip
(cd a600/fab/gerbers && zip -q ../insanemembrane-a600-jlc-gerbers.zip *.gtl *.gbl *.gts *.gbs *.gto *.gbo *.gm1 *.gbr *.drl)
$PYV tools/build/check_print.py $D/board_geom.json a600/fab/insanemembrane-a600-1to1-fit-check.pdf
for side in top bottom; do
  $CLI pcb render --side $side --width 1400 --height 1400 --background opaque --quality basic \
      -o a600/fab/render-$side.png $PCB >/dev/null 2>&1 || true
done
echo "fab package: $(unzip -l a600/fab/insanemembrane-a600-jlc-gerbers.zip | tail -1)"
