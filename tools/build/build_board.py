"""Stage 2: build the KiCad board (unrouted) from board_geom.json. Run with KiCad's bundled python.

Usage: <kicad python> build_board.py <board_geom.json> <out.kicad_pcb>
"""
import json
import math
import sys
import pcbnew

G = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
ROUTE = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None   # replica routing
VIA_D, VIA_DRILL = 0.70, 0.35
import os
PADS = {(p["ref"], p["num"]): p for p in json.load(open(os.path.join(os.path.dirname(sys.argv[3]), "pads_final.json")))["pads"]} if ROUTE else None
mm = pcbnew.FromMM
V = lambda x, y: pcbnew.VECTOR2I(mm(x), mm(y))

LED_NETS = ("31", "9")   # [upper-left pad, lower-right pad] - traced on the original membrane
TRACK_W, CLEAR = 0.30, 0.25
MASK_MARGIN = 0.30      # coverlay window around key pads (as on the original)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geomlib import contact as _contact
_c = _contact(G)
FINGER_W, FINGER_FROM_END, FINGER_LEN = _c["w"], _c["from_end"], _c["len"]
COVERLAY_END = G.get("coverlay_end", 7.5)      # coverlay starts this far from the tail end
STIFFENER_LEN = G.get("stiffener", {}).get("len", 35.0)
LABEL = G.get("label", "insanemembrane - A1200 Mitsumi 56C774A replacement - rev A")
STIFF_NOTE = G.get("stiffener_note", "Stiffener: PI 0.10mm bottom, 35mm from tail end. Total at contacts 0.21mm")
STIFF_TEXT = G.get("stiffener_text", "PI STIFFENER 0.10 mm, BOTTOM SIDE")

board = pcbnew.BOARD()
ds = board.GetDesignSettings()
ds.m_TrackMinWidth = mm(0.15)
ds.m_MinClearance = mm(0.2)
ds.m_ViasMinSize = mm(0.5)
ds.m_MinThroughDrill = mm(0.25)
ds.m_CopperEdgeClearance = mm(0.3)
ds.SetBoardThickness(mm(0.11))

nets = {}
for i in range(1, 32):
    n = pcbnew.NETINFO_ITEM(board, f"PIN{i:02d}")
    board.Add(n)
    nets[str(i)] = n

# ---- outline -------------------------------------------------------------------------------
def add_poly(layer, pts, width=0.1, fill=False):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_POLY)
    s.SetLayer(layer)
    s.SetPolyPoints([V(x, y) for x, y in pts])
    s.SetWidth(mm(width))
    s.SetFilled(fill)
    board.Add(s)
    return s


def add_rect(layer, x0, y0, x1, y1, width=0.1, fill=False):
    return add_poly(layer, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], width, fill)


outline = G["board_outline"][0]
for i in range(len(outline) - 1):
    s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
    s.SetLayer(pcbnew.Edge_Cuts)
    s.SetStart(V(*outline[i])); s.SetEnd(V(*outline[i + 1]))
    s.SetWidth(mm(0.05))
    board.Add(s)


# ---- helpers for footprints ----------------------------------------------------------------
def new_fp(ref, value, x, y):
    fp = pcbnew.FOOTPRINT(board)
    fp.SetReference(ref); fp.SetValue(value)
    fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
    fp.SetPosition(V(x, y))
    board.Add(fp)
    return fp


def smd_pad(fp, num, net, cx, cy, w, h, angle_deg, chamfer=0.0, mask_margin=None):
    p = pcbnew.PAD(fp)
    p.SetNumber(num)
    p.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    lset = pcbnew.LSET(); lset.AddLayer(pcbnew.F_Cu); lset.AddLayer(pcbnew.F_Mask)
    p.SetLayerSet(lset)
    if chamfer > 0:
        p.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_CHAMFERED_RECT)
        p.SetChamferRectRatio(pcbnew.F_Cu, chamfer / min(w, h))
        p.SetChamferPositions(pcbnew.F_Cu, 15)  # all four corners
    else:
        p.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_RECTANGLE)
    p.SetSize(pcbnew.F_Cu, V(w, h))
    fp.Add(p)
    p.SetPosition(V(cx, cy))
    p.SetOrientation(pcbnew.EDA_ANGLE(-angle_deg, pcbnew.DEGREES_T))
    if mask_margin is not None:
        p.SetLocalSolderMaskMargin(mm(mask_margin))
    if net is not None:
        p.SetNet(net)
    return p


def rule_area(pts, layers, no_tracks, no_vias, name):
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowTracks(no_tracks)
    z.SetDoNotAllowVias(no_vias)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    z.SetZoneName(name)
    o = z.Outline(); o.NewOutline()
    for x, y in pts:
        o.Append(mm(x), mm(y))
    board.Add(z)


def rot_rect(cx, cy, ux, uy, half_len, half_w):
    vx, vy = -uy, ux
    return [(cx + sx * half_len * ux + sy * half_w * vx, cy + sx * half_len * uy + sy * half_w * vy)
            for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]


# ---- keys ----------------------------------------------------------------------------------
pd = G["pad"]
pad_len = pd["away"] + pd["toward"]              # along the key axis
pad_shift = (pd["toward"] - pd["away"]) / 2       # geometric centre offset toward the partner
for k in G["keys"]:
    ax, ay = k["a"]; bx, by = k["b"]
    ux, uy = (bx - ax), (by - ay)
    L = math.hypot(ux, uy); ux, uy = ux / L, uy / L
    mx, my = (ax + bx) / 2, (ay + by) / 2
    fp = new_fp(k["ref"], k["name"], mx, my)
    ang = k["angle"]
    if ROUTE:
        for num in ("1", "2"):
            q = PADS[(k["ref"], num)]
            smd_pad(fp, num, nets[q["net"]], q["centre"][0], q["centre"][1], q["length"], 2 * pd["half_w"], q["angle"],
                    pd["chamfer"], q["mask"])
    else:
        smd_pad(fp, "1", nets[k["net_a"]], ax + ux * pad_shift, ay + uy * pad_shift, pad_len, 2 * pd["half_w"], ang,
                pd["chamfer"], MASK_MARGIN)
        smd_pad(fp, "2", nets[k["net_b"]], bx - ux * pad_shift, by - uy * pad_shift, pad_len, 2 * pd["half_w"], ang,
                pd["chamfer"], MASK_MARGIN)
    gap_half = L / 2 - pd["toward"]               # half the gap between the pads
    # nothing on top between the pads (the rubber bar lands here)
    if not ROUTE:   # the original routes traces between pads (under its insulating coat), so no keep-out in the replica
        rule_area(rot_rect(mx, my, ux, uy, gap_half - 0.05, pd["half_w"] + 0.4), [pcbnew.F_Cu], True, True,
                  f"bar_{k['ref']}")
    # no vias anywhere in the contact zone
    if not ROUTE:
        rule_area(rot_rect(mx, my, ux, uy, L / 2 + pd["away"] + 0.4, pd["half_w"] + 0.6), [pcbnew.F_Cu, pcbnew.B_Cu],
                  False, True, f"novia_{k['ref']}")
    t = pcbnew.PCB_TEXT(board)   # key name on the fab layer for reference
    t.SetText(k["name"]); t.SetLayer(pcbnew.F_Fab); t.SetPosition(V(mx, my))
    t.SetTextSize(V(1.2, 1.2)); t.SetTextThickness(mm(0.15))
    board.Add(t)

# ---- caps lock LED pads ---------------------------------------------------------------------
(l1x, l1y), (l2x, l2y) = G["led"]
ux, uy = l2x - l1x, l2y - l1y
L = math.hypot(ux, uy); ux, uy = ux / L, uy / L
fp = new_fp("D1", "CAPS_LED", (l1x + l2x) / 2, (l1y + l2y) / 2)
ang = math.degrees(math.atan2(uy, ux))
if "led_pads" in G:
    for num, lp in zip(("1", "2"), G["led_pads"]):
        smd_pad(fp, num, nets[lp["net"]], lp["pos"][0], lp["pos"][1], lp["size"][0], lp["size"][1], lp["angle"],
                lp.get("chamfer", 0.0), MASK_MARGIN)
else:
    smd_pad(fp, "1", nets[LED_NETS[0]], l1x, l1y, 2.4, 2.6, ang, 0.35, MASK_MARGIN)
    smd_pad(fp, "2", nets[LED_NETS[1]], l2x, l2y, 2.4, 2.6, ang, 0.35, MASK_MARGIN)
if not ROUTE:
    rule_area(rot_rect((l1x + l2x) / 2, (l1y + l2y) / 2, ux, uy, 2.9, 1.9), [pcbnew.F_Cu, pcbnew.B_Cu], False, True, "novia_LED")

# ---- tail contacts --------------------------------------------------------------------------
tl = G["tail"]
end_x = tl["end_x"]
fp = new_fp("J1", "CN13_TAIL_31P_1.25", end_x - FINGER_FROM_END - FINGER_LEN / 2, tl["cy"])
for p in G["pins"]:
    smd_pad(fp, str(p["pin"]), nets[str(p["pin"])], end_x - FINGER_FROM_END - FINGER_LEN / 2, p["y"],
            FINGER_LEN, FINGER_W, 0.0, 0.0, 0.0)
# coverlay ends COVERLAY_END from the tail end: one window over all contacts, part of the J1 footprint
# (all contacts in one window is normal for a connector tail -> allow mask bridges in this footprint)
win = pcbnew.PCB_SHAPE(fp, pcbnew.SHAPE_T_POLY)
win.SetLayer(pcbnew.F_Mask)
win.SetPolyPoints([V(x, y) for x, y in ((end_x - COVERLAY_END, tl["cy"] - tl["width"] / 2 - 1), (end_x + 1, tl["cy"] - tl["width"] / 2 - 1),
                                         (end_x + 1, tl["cy"] + tl["width"] / 2 + 1), (end_x - COVERLAY_END, tl["cy"] + tl["width"] / 2 + 1))])
win.SetFilled(True); win.SetWidth(0)
fp.Add(win)
fp.SetAllowSolderMaskBridges(True)
# keep routing away from the bare contact area on top
_hw = G.get("contact_keepout_halfw", 25)
rule_area([(end_x - COVERLAY_END, tl["cy"] - _hw), (end_x + 1, tl["cy"] - _hw), (end_x + 1, tl["cy"] + _hw),
           (end_x - COVERLAY_END, tl["cy"] + _hw)], [pcbnew.F_Cu, pcbnew.B_Cu], False, True, "novia_contacts")
# stiffener (bottom side), documented on User.1 + fab note
add_rect(pcbnew.User_1, end_x - STIFFENER_LEN, tl["cy"] - tl["width"] / 2, end_x, tl["cy"] + tl["width"] / 2, 0.1, False)
for layer, txt, dy in ((pcbnew.User_1, STIFF_TEXT, 0), (pcbnew.F_Fab, STIFF_NOTE, G.get("stiffener_note_dy", -23))):
    t = pcbnew.PCB_TEXT(board); t.SetText(txt); t.SetLayer(layer)
    t.SetPosition(V(end_x - STIFFENER_LEN / 2, tl["cy"] + dy)); t.SetTextSize(V(1.5, 1.5)); t.SetTextThickness(mm(0.2))
    board.Add(t)
# pin 1 marker
t = pcbnew.PCB_TEXT(board); t.SetText("1"); t.SetLayer(pcbnew.F_SilkS)
t.SetPosition(V(G.get("pin1_marker_x", end_x - COVERLAY_END - 2.0), G["pins"][0]["y"])); t.SetTextSize(V(1.0, 1.0)); t.SetTextThickness(mm(0.15))
board.Add(t)

# ---- holes (NPTH) ---------------------------------------------------------------------------
for i, h in enumerate(G["holes"]):
    fp = new_fp(f"H{i+1}", "NPTH", h["x"], h["y"])
    p = pcbnew.PAD(fp)
    p.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    p.SetLayerSet(pcbnew.PAD.UnplatedHoleMask())
    if h["shape"] == "circle":
        p.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_CIRCLE)
        p.SetSize(pcbnew.F_Cu, V(h["d"], h["d"]))
        p.SetDrillSize(V(h["d"], h["d"]))
    else:
        p.SetShape(pcbnew.F_Cu, pcbnew.PAD_SHAPE_OVAL)
        p.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_OBLONG)
        p.SetSize(pcbnew.F_Cu, V(h["ww"], h["h"]))
        p.SetDrillSize(V(h["ww"], h["h"]))
    fp.Add(p)
    p.SetPosition(V(h["x"], h["y"]))

# ---- labels ---------------------------------------------------------------------------------
t = pcbnew.PCB_TEXT(board)
t.SetText(LABEL)
_lx, _ly = G.get("label_pos", (tl["end_x"] - 60, tl["cy"]))
_lang = G.get("label_angle", 0)
t.SetLayer(pcbnew.F_SilkS); t.SetTextSize(V(1.5, 1.5)); t.SetTextThickness(mm(0.2))
t.SetTextAngle(pcbnew.EDA_ANGLE(_lang, pcbnew.DEGREES_T))
t.SetPosition(V(_lx, _ly)); board.Add(t)
t = pcbnew.PCB_TEXT(board)
t.SetText("Licence: CC BY-NC-SA 4.0 - non-commercial use only")
t.SetLayer(pcbnew.F_SilkS); t.SetTextSize(V(1.2, 1.2)); t.SetTextThickness(mm(0.18))
t.SetTextAngle(pcbnew.EDA_ANGLE(_lang, pcbnew.DEGREES_T))
_dx, _dy = (2.6 * math.sin(math.radians(_lang)), 2.6 * math.cos(math.radians(_lang)))
t.SetPosition(V(_lx + _dx, _ly + _dy)); board.Add(t)

if ROUTE:
    lay = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
    nt = 0
    for t in ROUTE["tracks"]:
        pts = t["pts"]
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            if math.hypot(x1 - x0, y1 - y0) < 1e-4:
                continue
            tk = pcbnew.PCB_TRACK(board)
            tk.SetStart(V(x0, y0)); tk.SetEnd(V(x1, y1))
            tk.SetWidth(mm(t["w"])); tk.SetLayer(lay[t["layer"]]); tk.SetNet(nets[t["net"]])
            board.Add(tk); nt += 1
    for v in ROUTE["vias"]:
        via = pcbnew.PCB_VIA(board)
        via.SetPosition(V(*v["pos"])); via.SetDrill(mm(VIA_DRILL)); via.SetWidth(pcbnew.F_Cu, mm(VIA_D))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); via.SetNet(nets[v["net"]])
        board.Add(via)
    # remove dead-end segments (leaves of the copper graph carry no signal), using KiCad's connectivity
    removed = 0
    for _ in range(40):
        board.BuildConnectivity()
        conn = board.GetConnectivity()
        dead = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and conn.TestTrackEndpointDangling(t, False)]
        if not dead:
            break
        for t in dead:
            board.Remove(t); removed += 1
    print("routing: segments", nt - removed, "vias", len(ROUTE["vias"]), "dead-end segments removed", removed)

# ---- watermark (private, optional): decoy "vias" + copper microtext, see docs/watermark/ ----------
WM = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", *G.get("watermark", "a1200/docs/watermark/watermark.json").split("/"))
if os.path.exists(WM):
    W = json.load(open(WM))
    for x, y in W["decoys"]:          # 0.70 mm copper dots on both layers, no hole, no net: look like tented vias
        for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            c = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_CIRCLE)
            c.SetLayer(layer); c.SetCenter(V(x, y)); c.SetEnd(V(x + W["decoy_d"] / 2, y))
            c.SetFilled(True); c.SetWidth(0)
            board.Add(c)
    for m in W["microtext"]:
        t = pcbnew.PCB_TEXT(board); t.SetText(m["text"])
        t.SetLayer(pcbnew.F_Cu if m["layer"] == "F.Cu" else pcbnew.B_Cu)
        t.SetMirrored(m["layer"] == "B.Cu")
        t.SetTextSize(V(m["size"], m["size"])); t.SetTextThickness(mm(m["stroke"]))
        t.SetPosition(V(m["x"], m["y"]))
        board.Add(t)
    print("watermark:", len(W["decoys"]), "decoys,", len(W["microtext"]), "microtexts")

board.SetFileName(OUT)
pcbnew.SaveBoard(OUT, board)
print("saved", OUT, "footprints", len(board.GetFootprints()), "zones", board.GetAreaCount())
