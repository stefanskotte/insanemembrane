# A500 Flex Membrane — Design Spec (draft, for approval)

Status: approved by the user 2026-11-22 ("thats good, proceed"); built as rev A the same day (see "As built" at the end).
Method: the same as the A1200 rev A, as built and approved. See `a1200/docs/design-spec.md`, "As built".

## 1. Goal
A drop-in replacement for the Mitsumi **A-500(E) 56 A619B** Amiga 500 keyboard membrane, made as a 2-layer
polyimide flex PCB. It must fit with no changes to the keyboard, and its finger tab plugs straight into the FFC
connector on the keyboard's controller PCB. Deliverable: a JLCPCB flex package that can be ordered as it is.

## 2. Board / JLC order settings
| Item | Value |
|---|---|
| Type | Flex (FPC), 2 layers |
| Thickness | 0.11 mm (25 µm PI) |
| Copper | 18 µm (0.5 oz) both sides |
| Coverlay | PI coverlay both sides |
| Finish | ENIG, 2 µ" gold |
| Stiffener | PI on the **bottom** (back) only, **7.86 mm from the finger tips × the full tab width (39.2 mm)**. Target total at the fingers **0.40 mm**, as measured on the original. This is entered as the gold-finger total so JLC picks the PI. Their thickest PI, 0.25 mm, gives ≈ 0.36 mm, which the keyboard's FFC connector tolerates. |
| Size | **~140 × 442 mm**, within JLC's standard 234 mm, so no oversize review this time |
| Outline | laser cut, ±0.1 mm |

## 3. Outline and holes (copied from the scan)
- Body: stepped outline, 139.9 × 442.1 mm, with the narrow upper section and a step where the finger tab sits.
- Finger tab: on the long edge at the step. It sticks out **9.7 mm** from the body edge and is **39.2 mm** wide.
- Holes (front-scan frame):
  - 27 × Ø6.5
  - 1 × Ø6.0
  - 2 × 6.0 × 8.0 mm slots
  - 1 × Ø3.2
- The Y-scale correction measured on this scanner for the A1200 is checked again against the rulers in these scans.
- Check before ordering: a 1:1 PDF printed and laid under the original. This worked well for the A1200.

## 4. Key contacts
- **96 keys**, with two carbon pads each. The pads are about 4.0 × 3.5 mm, the same octagon shape as on the A1200. The pad centres are 7.2 mm apart on a 45° diagonal.
- **Caps Lock LED:** one pad pair 4.0 mm apart near the top, at (106, 46). It's larger than a key pair and is kept as its own footprint.
- Pads are extended 0.75 mm towards their partner where there is room. Like the A1200, this is adaptive, keeping ≥ 0.25 mm from other nets.
- Coverlay windows are 0.30 mm around each pad.

## 5. Netlist
- There is no third-party netlist this time. **The nets come from the original itself:**
  - silver traces from the back scan,
  - plus the printed crossover bridges,
  - traced from each pad to its finger.
- Cross-check: every key pair must join exactly two different fingers, i.e. one row and one column, and no finger may short to another.
- I'll also compare against a published A500 keyboard matrix if one can be found.
- Anything unclear is checked with a multimeter on the original. You'd do that.

## 6. Routing (same rules as the A1200 rev A)
- **1:1 replica of the original routing:**
  - Top copper = the silver traces.
  - Bottom copper = the printed crossover bridges, with tented vias where the bridges land.
- **All traces exactly 0°/45°/90°** (`octi.py`), with bridges as fewest-bend paths.
- Traces 0.30 mm, ≥ 0.25 mm clearance, 0.3 mm from the edge and holes.
- Traces run straight into the fingers in the method you used to hand-route the A1200 tail: a 45° diagonal extended to the finger's y, then one straight line.

## 7. Finger tab
- **31 fingers, 1.25 mm pitch** (measured 1.2517 mm), at the scanned positions.
- On the top (carbon) side, as on the original.
- Gold fingers are **0.80 mm wide** (the original carbon is 0.94 mm; 0.80 gives a safer gap for gold), start 0.35 mm from the tip, and run 9.5 mm long.
- One coverlay opening over the fingers.

## 8. Extras carried over from the A1200
- The hidden watermark, with its own private key in `a500/docs/watermark/`.
- The licence line on the silkscreen: CC BY-NC-SA 4.0.
- A rev label.

## 9. Deliverables
1. KiCad project in `a500/kicad/`, with the stitched scans as reference.
2. JLC package in `a500/fab/`:
   - Gerber + drill zip,
   - the stiffener drawn on User_1,
   - order settings, plus a remark short enough for JLC's ~190-character field.
3. 1:1 check PDF.

## 10. Risks / assumptions
- **Stiffener total:** may come out at 0.36 mm rather than 0.40. That's acceptable for the FFC connector (agreed 2026-11-22).
- **Netlist from tracing only:** there is no independent netlist, so the self-checks in §5 and a multimeter check on doubtful spots carry more weight than on the A1200.
- **Bending:** the membrane must not be creased across keys. ENIG nickel is stiff.

---

## As built — rev A (2026-11-22)
Status: **built.** KiCad DRC clean: 0 violations, 0 unconnected. Order package: `a500/fab/` (see `JLC-ORDER.md`).
Rebuild everything from the scans: `tools/a500/make.sh`.

Changes from the draft, all following decisions already agreed or measured:
- **Stiffener:** PI on the back only, 7.86 mm from the finger tips (measured by the user), full tab width.
  The target total at the fingers is 0.40 mm; 0.36 mm is acceptable (user: the FFC connector on the keyboard PCB will take it).
- **Gold fingers:** 0.80 × **8.5 mm** (the spec said 9.5), starting 0.35 mm from the tip.
  At 9.5 mm their inner ends ran into the 1 mm fillets at the tab root.
  8.5 mm still runs past both the 7.5 mm coverlay opening and the 7.86 mm stiffener.
  The row is centred on the measured finger centre, 0.11 mm off the tab centre, as on the original.
- **Netlist traced from the original:**
  - 31/31 fingers; 194/194 pads, each on exactly one finger; no shorts; every key on two different pins.
  - Rows: pins 1, 2, 3, 4, 5, 7.
  - Columns: pins 15–29.
  - Modifiers: 7 keys, one line each on pins 6, 8, 10–14, with pin 30 as their common.
  - LED: pins 9 and 31.
  - Details are in `design-notes.md`.
- **Routing:** a 1:1 replica of the original.
  - Top copper = the silver traces, including the ~1 mm wide traces along the edges.
  - Bottom copper = 60 printed bridges (straight, bent and 4 read by hand), with 120 tented vias.
  - **All 3,514 segments are exactly 0°/45°/90°**, following the user's rule. One trace needed a larger move (≤ 0.8 mm, at ≥ 0.20 mm clearance) to get there.
  - One bridge uses two bends (45°, straight, 45°); the others use one or none.
- **Finger entry:** 26 traces use the user's A1200 tail method: the 45° diagonal is extended to the finger's y, then one level line. Traces that arrive vertically go straight up to their finger's y, then level.
  Pins 16, 28, 29, 30 and 31 keep their routed entry (already 0/45/90°), because the new line would come within 0.2 mm of a neighbour.
- **Pads:** 137 pads are extended +0.75 mm, 40 by +0.5 mm, 15 by +0.25 mm, each keeping ≥ 0.25 mm from other nets.
- **LED pads:** 2.8 × 4.6 mm rectangles, measured as 2.95 × 4.95 mm on the original.
- **Holes:** 27 × Ø6.5, 1 × Ø6.0, 1 × Ø3.2, 2 slots of 6 × 8 mm.
- **Size:** 134.5 × 441.1 mm after removing the 0.60° skew the membrane had on the scanner.
- **Silkscreen:** the label and the CC BY-NC-SA 4.0 licence line, running vertically where the original has its MITSUMI logo.
- **Watermark:** decoy vias and microtext with their own code. The key is private, in `a500/docs/watermark/README-PRIVATE.md`.
- **1:1 fit-check PDF:** `a500/fab/insanemembrane-a500-1to1-fit-check.pdf` (2 A4 pages).
- **Fit check passed (2026-11-22):** the user printed the 1:1 PDF and laid the original on top. The holes, slots, pads, finger tab and straight edges line up. A 0.5 mm offset in one photo turned out to be the camera angle when the same corner was shot from straight above.
- **Outer corners rounded R 1.2 mm (2026-11-22, user)**, to match the original's rounded corners seen in the fit check.
  The two corners at the tab tip stay square, because fingers 1 and 31 sit about 0.6 mm from the tab edge. DRC is still clean and all copper still 0/45/90°.
