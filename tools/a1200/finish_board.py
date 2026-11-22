"""Stage 4: import the Freerouting session into a freshly built board and save.

Usage: <kicad python> finish_board.py <unrouted.kicad_pcb> <routed.ses> <out.kicad_pcb>
"""
import sys
import pcbnew

src, ses, out = sys.argv[1:4]
b = pcbnew.LoadBoard(src)
ok = pcbnew.ImportSpecctraSES(b, ses)
print("SES import:", ok)
tracks = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
print(f"tracks {len(tracks)}, vias {len(vias)}, "
      f"top {sum(t.GetLayer()==pcbnew.F_Cu for t in tracks)}, bottom {sum(t.GetLayer()==pcbnew.B_Cu for t in tracks)}")
pcbnew.SaveBoard(out, b)
print("saved", out)
