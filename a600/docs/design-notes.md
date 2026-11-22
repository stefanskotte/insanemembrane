# A600 membrane (Mitsumi "A300-B 30M 56C471B", CM-2) — working notes

Started 2026-11-22. Approach: the same as the A1200 rev A and A500 rev A (1:1 replica of the original routing, 2-layer flex,
all copper 0/45/90°).

## Scans
- `a600-top-left/right.tiff` = carbon side, `a600-bottom-left/right.tiff` = silver side.
- `a600-top-tail` / `a600-bottom-tail` show only the tail end. Their labels are swapped compared with the body:
  "bottom-tail" is the printed (contact) side.
- `a600-top-right.tiff` was rescanned on 2026-11-22. The first one was 15402 × 16659 px.
- Registration by holes (`tools/a600/register.py`):
  - halves 10 holes, 0.035 mm rms; back halves 12 holes, 0.04 mm rms
  - front↔back 12–14 holes, 0.12–0.13 mm rms
  - The right-hand scans are turned 180°.
- Stitched: `a600/docs/scan-front-stitched.png`, `a600/docs/scan-back-mirrored-into-front-frame.png` (seam at y = 195).

## Measured
- Body: about 142 × 318 mm, with a notch at the bottom. 16 holes: 13 × Ø6.5, 1 × Ø6.0 (6.1 measured), 2 slots of 6 × 8 mm.
- Keys: 78 + the Caps Lock LED.
  - 158 pads, 4.11 × 3.25 mm, 7.16 mm apart at 43.5°.
  - Two pads were left over by the mutual-nearest pairing and were added as a pair: (122.3, 75.6) and (127.5, 80.5).
- Tail (on the long edge, at y ≈ 146–185 in the front frame):
  - 30 traces at 1.2518 mm pitch, 39.0 mm wide.
  - 30 contacts on the printed side, ~0.85 mm wide carbon, 1.25 mm pitch; 1.35 / 1.16 mm from the tail edges.
- Stiffener (user, 2026-11-22): "0.30 mm, total 100 mm" → 100 mm long from the tail end, behind the contacts.
  It shows as the darker green section in the tail scans.
- Tail length (user, 2026-11-22): **180 mm** from the body edge to the end. The tail scans can't be lined up with the
  body along the tail, so this is the user's measurement.
- **0.30 mm is the stiffener alone** (user). The original total at the contacts is therefore ≈ 0.40–0.43 mm.
- Body (green-film mask): x 61.2–179.5, y 29.2–346.6, i.e. 118.3 × 317.5 mm. The tail root is at x ≈ 179.5.
  A full 180 mm tail gives ≈ 298 × 318 mm, over JLC's flex limit on both sides.
  **The user chose to shorten the tail to 132 mm.** It will be ≈ 131.5 mm, so the board is ≤ 250 mm wide.

## Netlist (2026-11-22): traced from the original, all checks pass
Pipeline:
1. `tools/a600/lands.py`: 64 landing spots. Pad centres are excluded, because on the A600 a pad's silver centre is as big as a spot.
2. `tools/a600/bridges.py`: 25 straight + 3 bent bridges, plus 7 read by hand (`scan-data/manual_jumpers.json`).
   - 5 of the hand-read ones have a trace joined to one spot, so that spot fails the roundness test.
   - 2 replace wrong automatic pairings in the cluster at (150–165, 140–167).
3. `tools/a600/netlist.py`: 30/30 tail traces, 158/158 pads on exactly one pin, 0 bad keys, 0 shorts.

Matrix (pin 1 = the tail trace at the smallest y, y = 147.5):
- Rows: pins **1, 2, 3, 5, 7** (12 / 15 / 15 / 15 / 14 keys).
- Columns: pins **15–29**.
- Modifiers: 7 keys, one each on pins **6, 8, 10, 11, 12, 13, 14**, with **pin 30** as their common.
- Caps Lock LED: pins **4 and 9**.
- 71 matrix keys + 7 modifiers = 78 keys.
