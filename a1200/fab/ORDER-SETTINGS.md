# JLCPCB order settings — all three membranes

You are in the **A1200** folder. The same summary is kept next to each membrane's fab package:
- A1200: `a1200/fab/ORDER-SETTINGS.md`
- A500: `a500/fab/ORDER-SETTINGS.md`
- A600: `a600/fab/ORDER-SETTINGS.md`

Full instructions for each board, including what is in the files, are in its `JLC-ORDER.md`.

Upload each zip at https://cart.jlcpcb.com/quote and choose **Flex PCB**.

## Order form
| Setting | A1200 rev A | A500 rev A | A600 rev A |
|---|---|---|---|
| Original membrane | Mitsumi 56C774A | Mitsumi A-500(E) 56 A619B | Mitsumi A300-B 30M 56C471B |
| Gerber zip to upload | `a1200/fab/insanemembrane-a1200-jlc-gerbers.zip` | `a500/fab/insanemembrane-a500-jlc-gerbers.zip` | `a600/fab/insanemembrane-a600-jlc-gerbers.zip` |
| Product | Flex PCB | Flex PCB | Flex PCB |
| Base material | Polyimide | Polyimide | Polyimide |
| Layers | 2 | 2 | 2 |
| Dimensions (auto-detected) | 237.0 × 440.0 mm ⚠ over 234 mm standard | 134.5 × 441.1 mm | 249.8 × 316.9 mm ⚠ over 234 mm standard, at the 250 mm max |
| PCB qty | 5 (minimum) | 5 (minimum) | 5 (minimum) |
| FPC thickness | **0.11 mm** | **0.11 mm** | **0.11 mm** |
| Copper | 0.5 oz (18 µm) | 0.5 oz (18 µm) | 0.5 oz (18 µm) |
| Coverlay colour | any (yellow standard) | any (yellow standard) | any (yellow standard) |
| Silkscreen | white | white | white |
| Surface finish | ENIG, **2 µ"** | ENIG, **2 µ"** | ENIG, **2 µ"** |
| Stiffener material | **PI** | **PI** | **PI** |
| Stiffener side | **bottom** (behind the contacts) | **bottom** (behind the fingers) | **bottom** (behind the contacts) |
| Stiffener area (layer User_1) | 35 × 40.2 mm at the tail end | 7.86 × 39.2 mm on the finger tab | 100 × 39 mm at the tail end |
| Stiffener thickness / gold-finger total | PI 0.10 mm → **0.21 mm total** | **0.40 mm total** (JLC picks PI; ≈0.36 OK) | **0.41 mm total** (JLC picks PI; ≈0.36–0.38 OK) |
| Outline tolerance | standard ±0.1 mm | standard ±0.1 mm | standard ±0.1 mm |
| Contacts | 31 × 0.75 × 6.35 mm, 1.25 mm pitch | 31 × 0.80 × 8.5 mm, 1.25 mm pitch | 30 × 0.80 × 6.35 mm, 1.25 mm pitch |
| Vias (tented, 0.35 mm) | 72 | 120 | 69 |
| NPTH holes | 26 × Ø6.5, 1 × Ø6.0, 2 slots 6×8 | 27 × Ø6.5, 1 × Ø6.0, 1 × Ø3.2, 2 slots 6×8 | 13 × Ø6.5, 1 × Ø6.0, 2 slots 6×8 |
| 1:1 fit-check print | `a1200/fab/insanemembrane-a1200-1to1-fit-check.pdf` (4 pages) | `a500/fab/insanemembrane-a500-1to1-fit-check.pdf` (2 pages) | `a600/fab/insanemembrane-a600-1to1-fit-check.pdf` (4 pages) |
| Fit check | passed 2026-11-15 | passed 2026-11-22 | passed 2026-11-22 |

## Remark for JLC (paste into the order notes; the field cuts off at about 190 characters)
**A1200** (125 characters):
> PI stiffener 0.10mm, BOTTOM side, 35 x 40.2mm at tail end (layer User_1). Total at contacts 0.21mm +/-0.03 for FFC connector.

**A500** (161 characters):
> PI stiffener BOTTOM side only, 7.86 x 39.2mm on the finger tab (layer User_1). Total at gold fingers 0.40mm (0.36 OK). 31 top fingers share one coverlay opening.

**A600** (158 characters):
> PI stiffener BOTTOM side only, 100 x 39mm at the tail end (layer User_1). Total at gold contacts 0.41mm (0.36 OK). 30 top contacts share one coverlay opening.

## Notes
- **Size (A1200 and A600):** both are over JLC's 234 mm standard width, so JLC may review them or quote them higher.
  - The A1200 can be cut back to 234 mm by shortening its tail 3 mm more: `TAIL_SHORTEN` in `tools/a1200/geometry.py` → 13.0, then rebuild.
  - The A600 is already at the 250 mm maximum. Its tail is shortened from the original's 180 mm to 131.7 mm.
- **Total thickness (A500 and A600):** the originals measure 0.40 / ~0.41 mm. Enter that as the gold-finger total and let JLC choose the PI.
  - Their thickest PI (0.25 mm) gives about 0.36–0.38 mm, which the keyboard connectors take.
- **Before ordering:**
  1. Print the fit-check PDF at **100 % / Actual size** and check the 100 mm bar on each page.
  2. For the A600, check that the 131.7 mm tail reaches the keyboard connector.
- **All three boards** are 1:1 replicas of the original routing, with all copper at 0/45/90°.
  Each has KiCad DRC clean, a CC BY-NC-SA 4.0 licence line on the silkscreen, and a watermark.
