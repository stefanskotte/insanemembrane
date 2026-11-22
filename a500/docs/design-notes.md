# A500 membrane (Mitsumi "A-500(E) 56 A619B") — working notes

Started 2026-11-22. Approach: same as the A1200 rev A (1:1 replica of the original routing, 2-layer flex).

## Scans
- `a500-top-left/right.tiff` = carbon side (front), `a500-bottom-left/right.tiff` = silver side (back). 600 dpi.
- The right-hand scans are rotated 180° relative to the left-hand ones. The stitching handles this.
- Registration by holes (`tools/a500/register.py` → `a500/docs/scan-data/transforms.json`):
  - top halves: 7 holes, 0.04 mm rms
  - front↔back: 18–19 holes, 0.11–0.15 mm rms
- Stitched images (`tools/a500/stitch.py`):
  - `a500/docs/scan-front-stitched.png`
  - `a500/docs/scan-back-mirrored-into-front-frame.png` (back mirrored into the front frame)

## First measurements
- Single sheet, ~155 × 465 mm, stepped outline. No tail: the connector is a short tab on the long edge, at the step.
- Connector: 31 fingers, 1.25 mm pitch (measured 1.2517 mean), ~0.94 mm wide (carbon over silver), span 37.55 mm.
  The fingers are on the carbon (top) side.
- **Stiffener: yes, on the back side only** (user, 2026-11-22). Measured total at the fingers: **0.40 mm**.
  The back scan shows two edges: the green print stops 5.3 mm from the finger tips, and there is a hazy band
  (adhesive?) about 8.3 mm from the tips. **Stiffener length 7.86 mm from the finger tips, measured by the user.** This matches the scan edge at about 8 mm. It covers the full width of the tab.
  - Replacement plan: a PI stiffener on the bottom, with a target total of 0.40 mm at the fingers.
  - JLC's thickest PI is 0.25 mm. In JLC's own example, a 0.11 mm FPC needs a 0.2 PI for a 0.30 total, so
    0.25 PI gives roughly 0.35–0.36 mm.
  - So: enter 0.40 mm as the gold-finger total on the order form and let JLC pick. If they can't reach it,
    the options are FR4 0.2 mm or 0.25 PI (~0.36 mm).
- Holes: mostly Ø6.5, plus Ø6.0, 6×8 slots, a Ø3.2 hole and a small Ø1.0 marker. Full list is in the scan-data *-holes.json files.

## Features from the stitched front scan (front frame, mm)
- Body bbox 139.9 × 442.1 (x 39.3–179.1, y 18.4–460.4). `tools/scan/features.py` → `scan-data/features.json`.
  Its outline misses the finger tab, because the film between the fingers is clear.
- Finger tab:
  - Tip at x 150.88. The body edge is at x ≈ 141.2, so the tab sticks out 9.7 mm. It spans y 312.29–351.49 (39.2 mm).
  - The green print stops at x ≈ 145.8.
  - Fingers: 31, centres from y 313.224 to 350.774, pitch 1.2517. The dark carbon runs from x 140.42 to 150.58.
- Pads: 194, area median 10.2 mm², 4.04 × 3.47 mm.
  - 96 key pairs, 7.2 mm apart at 44.4°.
  - The LED pair at (106.0, 45.7) is 4.0 mm apart, with larger pads (12.9 mm²).
- Holes (`scan-data/front-holes.json`): 27 × Ø6.5, 1 × Ø6.0 (53.9, 239.0), slots 6×8 at (160.7, 39.9) and (109.4, 382.6),
  Ø3.2 at (55.2, 99.0).

## Netlist (2026-11-22): derived from the original, all checks pass
Pipeline:
1. `tools/a500/silvermask.py` → `a500/build/silver_{conn,geo}.npy`.
2. `tools/a500/lands.py`: 124 landing spots.
3. `tools/a500/bridges.py`: 51 straight + 5 bent (traced along the bar core) + 4 hand-read bridges
   (`scan-data/manual_jumpers.json`, read from the back-side insulating strips). The 4 spots left over are blobs where traces meet, not bridges.
4. `tools/a500/netlist.py <silver_geo.npy>` → `scan-data/netlist.json`.

What differs from the A1200:
- The traces are ~0.25 mm, so the mask is not eroded at all.
- The geometry mask (V < 195) is used for connectivity, because the brighter one joined the LED pads through the white coverlay-window rims.
- A 0.35 mm band along the outline is dropped.
- On the tab, thin cuts between neighbouring fingers stop them merging in the scan.
- Traces that run under a pad's carbon join that pad.

Result:
- 31/31 fingers, 194/194 pads on exactly one finger.
- 0 bad keys, 0 finger shorts, no two keys with the same pin pair.

Matrix (pin 1 = finger at the smallest y, y = 313.2):
- Rows: pins **1, 2, 3, 4, 5, 7**. Each has 15 keys, except row 3, which has 14.
- Columns: pins **15–29** (15 columns).
- Modifiers: 7 keys, each on its own line (pins 6, 8, 10, 11, 12, 13, 14), with **pin 30** as their common.
- Caps Lock LED: pins **9 and 31**. These are the same two pin numbers as the A1200's LED.
- 89 matrix keys + 7 modifiers = 96 keys.
