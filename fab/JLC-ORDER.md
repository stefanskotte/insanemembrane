# Ordering insanemembrane rev A from JLCPCB (flex)

Upload: `fab/insanemembrane-jlc-gerbers.zip` at https://cart.jlcpcb.com/quote and choose **Flex PCB**.

## Order form settings
| Field | Value |
|---|---|
| Base material | Flex (polyimide) |
| Layers | 2 |
| Dimensions | ~237 × 440 mm (auto-detected from the outline) |
| PCB qty | 5 (minimum) |
| FPC thickness | **0.11 mm** |
| Copper | 0.5 oz (18 µm) |
| Coverlay colour | any (yellow is standard) |
| Silkscreen | white |
| Surface finish | ENIG, **2 µ"** gold |
| Stiffener | **PI, 0.10 mm**, on the **bottom side**. The area is drawn on `insanemembrane-User_1.gbr` (tail end, 35 mm). Add the note below |
| Gold fingers / total thickness at contacts | 0.11 + 0.10 = **0.21 mm** (original measured 0.2 mm) |
| Outline tolerance | standard (±0.1 mm) |

**Remark for JLC (the order-notes field cuts off at ~190 characters, so keep it this short):**
> PI stiffener 0.10mm, BOTTOM side, 35 x 40.2mm at tail end (layer User_1). Total at contacts 0.21mm +/-0.03 for FFC connector.

## Size
The board is ~237 mm wide, 3 mm over JLC's standard flex maximum of 234 × 490 mm (the absolute limit is 250 mm).
If the quote refuses it or adds a large surcharge: shorten the tail 3 more mm (`TAIL_SHORTEN` in
`tools/build/geometry.py` → 13.0) and rebuild with `tools/build/make.sh`.

## Before ordering
1. Print `fab/insanemembrane-1to1-fit-check.pdf` at **100 % / Actual size**. Check the 100 mm bar on every page,
   tape the 4 pages together using the crosses, and lay the original membrane on top: holes, slots and pads should line up.
2. Recommended: multimeter test of a plunger's rubber bar on any gold-plated pad pair (see design notes).
3. Open `kicad/insanemembrane.kicad_pcb` in KiCad 10 if you want to look it over (DRC is clean).

## What's in the files
- F.Cu (top, contact side): key pads, LED pads, tail contacts, all the original silver traces.
- B.Cu (bottom): the original printed crossover bridges, as copper.
- PTH drill: 72 vias, 0.35 mm, tented (covered by coverlay on both sides).
- NPTH drill: 26 × Ø6.5, 1 × Ø6.0, 2 × 6×8 mm slots (G85).
- F.Mask: coverlay openings (pads ~0.3 mm window, tail contacts 7.5 mm from the end).
