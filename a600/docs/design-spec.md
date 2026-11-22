# A600 Flex Membrane — Design Spec (draft, for approval)

Status: approved by the user 2026-11-22 ("its good, proceed"); built as rev A the same day (see "As built").
Method: the same as the A1200 rev A and A500 rev A, as built and approved.

## 1. Goal
A drop-in replacement for the Mitsumi **A300-B 30M 56C471B** (CM-2) Amiga 600 keyboard membrane, made as a 2-layer
polyimide flex PCB, ordered from JLCPCB as it is.

## 2. Board / JLC order settings
| Item | Value |
|---|---|
| Type | Flex (FPC), 2 layers, 0.11 mm, 18 µm copper, PI coverlay both sides, ENIG 2 µ" |
| Stiffener | PI on the **bottom** (behind the contacts), **100 mm from the tail end** × the full tail width (39.0 mm). On the original the stiffener alone is 0.30 mm, so the total there is ≈ 0.40–0.43 mm. Order it as a gold-finger total of 0.41 mm and let JLC pick the PI. Their thickest PI, 0.25 mm, gives ≈ 0.36–0.38 mm. |
| Size | **≈ 249.8 × 318 mm**: the body is 118.3 × 317.5 mm, plus the shortened tail. This is at JLC's 250 mm maximum, over the 234 mm standard, so it may be reviewed or quoted higher (like the A1200 at 237 mm). |
| Outline | laser cut, ±0.1 mm |

## 3. Outline and holes
- The body outline is copied from the scan, with its tilt corrected, the Y scale corrected (600/599.7) and straight edges made exact.
- The outer corners are rounded to R 1.2 mm, as on the A500 original, and the inner corners have 1 mm fillets.
- The tail is a clean rectangle, perpendicular to the body edge, at the scanned position.
- Holes: 13 × Ø6.5, 1 × Ø6.0, 2 slots of 6 × 8 mm, at the scanned positions.
- Check before ordering: a 1:1 fit-check PDF.

## 4. Keys
- **78 keys**, each a pad pair 7.16 mm apart at 45°, using the measured pad shape (≈ 4.1 × 3.25 mm).
- Pads are extended up to 0.75 mm towards their partner wherever they keep ≥ 0.25 mm from other nets.
- Coverlay windows are 0.30 mm around each pad.
- **Caps Lock LED:** one pad pair 4.0 mm apart, on pins 4 and 9.

## 5. Netlist: traced from the original (done, all checks pass)
- 30 tail pins.
- Rows: 1, 2, 3, 5, 7.
- Columns: 15–29.
- 7 modifier keys, one each on pins 6, 8, 10–14, with pin 30 as their common.
- LED: pins 4 and 9.
- 158/158 pads each sit on exactly one pin. No shorts, no bad keys.

## 6. Routing: the same rules as the A1200 and A500
- **1:1 replica:**
  - Top copper = the silver traces.
  - Bottom copper = the 35 printed bridges, with tented vias where they land.
- **All copper exactly 0°/45°/90°.** Bridges take the fewest bends.
- Traces are 0.30 mm with ≥ 0.25 mm clearance (0.20 minimum), 0.3 mm from the edge and holes.
- Into the tail, your method: the 45° diagonal is extended to the trace's own y, then one straight line.
  The 30 tail traces then run straight and parallel along the tail at 1.25 mm pitch.

## 7. Tail
- **Shortened from 180 to ≈ 131.5 mm**, measured from the body edge to the end (your choice, to fit JLC's size limit). The length is taken out of the plain middle section, so the contact end and the 100 mm stiffener stay as on the original.
- Width 39.0 mm. **30 contacts at 1.25 mm pitch** at the scanned position: 1.35 / 1.16 mm from the edges.
- Gold contacts are 0.80 × 6.35 mm, starting 0.35 mm from the end, on the same side as the key pads. The original carbon contacts are ~0.85 mm wide.
- One coverlay opening, 7.5 mm long, over the contacts. Pin 1 is the contact nearest the top of the board, matching the trace order.

## 8. Extras
- The licence line on the silkscreen (CC BY-NC-SA 4.0) and a rev label.
- The hidden watermark, with its own private key in `a600/docs/watermark/` (kept out of the repo).

## 9. Deliverables
- KiCad project in `a600/kicad/`.
- JLC package in `a600/fab/`: Gerber + drill zip, the stiffener on User_1, and order notes with a remark under 190 characters.
- 1:1 fit-check PDF.

## 10. Risks / assumptions
- **Tail length:** 131.5 mm must reach the A600's keyboard connector. You chose this.
- **Thickness:** may come out at 0.36–0.38 mm against the original's ~0.41 mm.
- **Size:** 249.8 mm is at JLC's limit, so they may review it.

---

## As built — rev A (2026-11-22)
Status: **built.** KiCad DRC clean: 0 violations, 0 unconnected. Order package: `a600/fab/` (`JLC-ORDER.md`).
Rebuild: `tools/a600/make.sh`.

- **Size and tail:** the board is 249.8 × 316.9 mm. The tail is **131.7 mm** long (shortened from 180 mm and capped so the board stays ≤ 249.8 mm), 39.0 mm wide, and centred on its traces.
- **Contacts:** 30 contacts, 0.80 × 6.35 mm at 1.25 mm pitch, starting 0.35 mm from the end.
- **Stiffener:** PI on the bottom, 100 mm from the end, target 0.41 mm total.
- **Routing:**
  - All 2,173 segments are exactly 0°/45°/90°.
  - 35 bridges (34 with one bend, 1 straight) with 69 tented vias. A spot shared by two bridges gets one via.
- **Tail entry:** 8 traces use your diagonal method.
  - The other traces arrive as a horizontal bundle at a slightly wider pitch than the tail.
  - On the original they squeeze onto the 1.25 mm pitch with small steps just inside the tail root. That's kept here, as clean 45° steps.
  - Lining each trace up with its contact earlier would cut through its neighbours, which are still on the wider pitch.
- **Outline:**
  - Outer corners R 1.2 mm; the two tail-end corners stay square because the contacts are near the edge.
  - Inner corners 1 mm.
  - The half-round notches on the left edge are copied from the scan.
- **Pads:** 130 pads extended +0.75 mm, 24 by +0.5 mm, 2 by +0.25 mm.
  - LED pads 2.8 × 4.6 mm (the original is ≈ 3.0 × 4.9 mm).
- **Silkscreen:** the label "insanemembrane A600 (56C471B) rev A" plus the licence line, running vertically where the original's MITSUMI text is.
- **Watermark:** private key in `a600/docs/watermark/README-PRIVATE.md`.
- **1:1 fit-check PDF:** `a600/fab/insanemembrane-a600-1to1-fit-check.pdf` (4 A4 pages).
- **Fit check passed (2026-11-22):** the user printed the 1:1 PDF and laid the original on top. These line up:
  - holes, key pads and LED pads,
  - the half-round edge notches and the notched corner shapes,
  - the straight edges and the tail root.
  A ≤ 0.3 mm sliver of printed line beside some top holes is most likely the camera angle.
- **Squares around vias removed (2026-11-23, spotted by the user at pin 21):** the A600's landing spots are about 2.25 mm, some of them teardrop-shaped. Their silver rims were being traced as tiny rings of track, which the 45° step turned into ~1 mm squares around 76 vias.
  - The replica step now clears each spot's whole rim, sized from the spot's measured diameter.
  - A new cleanup stage, `tools/build/drop_loops.py`, removes any remaining small loop at a via, but only if every net stays connected exactly as before.
  - Result: 0 squares left at vias. DRC is clean and all copper is still 0/45/90°.
