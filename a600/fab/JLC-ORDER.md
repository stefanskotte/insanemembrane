# Ordering insanemembrane A600 rev A from JLCPCB (flex)

Upload: `a600/fab/insanemembrane-a600-jlc-gerbers.zip` at https://cart.jlcpcb.com/quote and choose **Flex PCB**.

## Order form settings
| Field | Value |
|---|---|
| Base material | Flex (polyimide) |
| Layers | 2 |
| Dimensions | **249.8 × 316.9 mm** (auto-detected). Over JLC's 234 mm standard and inside their 250 mm maximum, so they may review it or quote it higher. |
| PCB qty | 5 (minimum) |
| FPC thickness | **0.11 mm** |
| Copper | 0.5 oz (18 µm) |
| Coverlay colour | any (yellow is standard) |
| Silkscreen | white |
| Surface finish | ENIG, **2 µ"** gold |
| Stiffener | **PI**, **bottom side only**, 100 mm from the tail end × the full tail width (39 mm), as drawn on `insanemembrane-a600-User_1.gbr` |
| Gold fingers / total thickness at contacts | **0.41 mm**. The original's stiffener alone is 0.30 mm. Enter 0.41 as the gold-finger total and let JLC pick the PI; their thickest (0.25 mm) gives ≈ 0.36–0.38 mm. |
| Outline tolerance | standard (±0.1 mm) |

**Remark for JLC** (158 characters; the field cuts off at about 190):
> PI stiffener BOTTOM side only, 100 x 39mm at the tail end (layer User_1). Total at gold contacts 0.41mm (0.36 OK). 30 top contacts share one coverlay opening.

## Before ordering
1. Print `a600/fab/insanemembrane-a600-1to1-fit-check.pdf` at **100 % / Actual size** (4 A4 pages).
   - Check the 100 mm bar on each page.
   - Tape the pages together using the crosses.
   - Lay the original on top. The body, holes and pads should line up.
   - The printed tail is the shortened one (131.7 mm against the original's 180 mm), so the original's tail runs about 48 mm past it.
2. Check that a 131.7 mm tail reaches the A600's keyboard connector.

## What's in the files
- **F.Cu (top):**
  - 78 key pad pairs + the Caps Lock LED pads.
  - 30 gold contacts, 0.80 × 6.35 mm at 1.25 mm pitch.
  - The original silver traces, all at 0/45/90°.
- **B.Cu (bottom):** the original printed crossover bridges (35), as copper.
- **PTH drill:** 69 vias, 0.35 mm, tented.
- **NPTH drill:** 13 × Ø6.5, 1 × Ø6.0, 2 × 6×8 mm slots.
- **F.Mask:** coverlay openings — 0.3 mm windows around the pads, and the contact window 7.5 mm from the end.
- **User_1:** the stiffener outline.
