# Ordering insanemembrane A500 rev A from JLCPCB (flex)

Upload: `a500/fab/insanemembrane-a500-jlc-gerbers.zip` at https://cart.jlcpcb.com/quote and choose **Flex PCB**.

## Order form settings
| Field | Value |
|---|---|
| Base material | Flex (polyimide) |
| Layers | 2 |
| Dimensions | ~134.5 × 441.1 mm (auto-detected from the outline; within JLC's standard 234 mm) |
| PCB qty | 5 (minimum) |
| FPC thickness | **0.11 mm** |
| Copper | 0.5 oz (18 µm) |
| Coverlay colour | any (yellow is standard) |
| Silkscreen | white |
| Surface finish | ENIG, **2 µ"** gold |
| Stiffener | **PI**, **bottom side only**, on the finger tab: 7.86 mm from the finger tips × the full tab width (39.2 mm), as drawn on `insanemembrane-a500-User_1.gbr` |
| Gold fingers / total thickness at fingers | **0.40 mm** (as measured on the original). Enter 0.40 as the gold-finger total and let JLC pick the PI. JLC's thickest PI (0.25 mm) gives ≈ 0.36 mm, which is fine for the keyboard's FFC connector. |
| Outline tolerance | standard (±0.1 mm) |

**Remark for JLC** (161 characters; the field cuts off at about 190):
> PI stiffener BOTTOM side only, 7.86 x 39.2mm on the finger tab (layer User_1). Total at gold fingers 0.40mm (0.36 OK). 31 top fingers share one coverlay opening.

## Before ordering
1. Print `a500/fab/insanemembrane-a500-1to1-fit-check.pdf` at **100 % / Actual size** (2 A4 pages).
   - Check the 100 mm bar on each page.
   - Tape the pages together using the crosses.
   - Lay the original membrane on top: the outline, holes, pads and finger tab should line up.
2. Optional: open `a500/kicad/insanemembrane-a500.kicad_pcb` in KiCad 10 (DRC is clean).

## What's in the files
- **F.Cu (top, contact side):**
  - 96 key pad pairs + the Caps Lock LED pads.
  - 31 gold fingers, 0.80 × 8.5 mm at 1.25 mm pitch.
  - The original silver traces, all at 0/45/90°.
- **B.Cu (bottom):** the original printed crossover bridges (60), as copper.
- **PTH drill:** 120 vias, 0.35 mm, tented.
- **NPTH drill:** 27 × Ø6.5, 1 × Ø6.0, 1 × Ø3.2, 2 × 6×8 mm slots.
- **F.Mask:** coverlay openings — 0.3 mm windows around the pads, and the finger window 7.5 mm from the tip.
- **User_1:** the stiffener outline.
