# A1200 Flex Membrane — Design Spec (for approval)

Status: approved 2026-11-14; built as rev A 2026-11-15 (see "As built" at the end).
Measurements behind every number: `docs/scan-measurements.md`.

## 1. Goal
A drop-in replacement for the Mitsumi 56C774A Amiga 1200 keyboard membrane, made as a 2-layer flex PCB.
It must fit with no changes to the keyboard and plug straight into CN13. The end result is a package that
can be uploaded and ordered from JLCPCB flex as it is.

## 2. Board / JLC order settings
| Item | Value |
|---|---|
| Type | Flex (FPC), 2 layers |
| Thickness | 0.11 mm (25 µm PI dielectric) |
| Copper | 18 µm (0.5 oz) both sides |
| Coverlay | standard PI coverlay both sides (colour doesn't matter) |
| Finish | ENIG, 2 µ" gold |
| Stiffener | PI 0.1 mm at the tail end, on the side opposite the contacts → 0.21 ± 0.03 mm at the contacts |
| Outline | laser cut, ±0.1 mm |
| Size | ~248 × 440.3 mm. Over JLC's 234 mm standard and under its 250 mm limit, so JLC may review it or quote it higher. Fallback: shorten the tail by up to 14 mm. |

## 3. Outline and holes (copied from the scan)
- Stepped outline traced from the stitched scan, cleaned up to straight lines and arcs, with the
  Y-scale correction applied (599.6 dpi measured along the length, 600.0 dpi across it).
- Holes: Ø6.5 mm round (measured 6.45), one Ø6.0 mm, one 6.0 × 8.0 mm slot, edge notch — at the scanned positions.
- Check before ordering: a 1:1 PDF of outline, holes and pads, printed and laid under the original membrane.

## 4. Key contacts
- Each key keeps the original layout: **two pads, centres 7.16 mm apart on a 45° diagonal**, which the plunger's
  ~8.2 × 2.5 mm conductive-rubber bar bridges.
- Pad shape: the original octagon (~4.1 × 3.3 mm), **extended 0.75 mm towards the partner pad** (agreed range
  0.5–1 mm). Gap between the two pads becomes ~3.05 mm (was 4.55 mm).
- The pads are on the top layer (the original carbon side). Each has a coverlay opening ~0.3 mm larger than the pad, like the original.
- No vias, crossovers or bends inside a key's bar footprint.

## 5. Matrix / netlist
- Key-to-matrix connections: from skielek/A1200KB (MIT) and the Mitsumi key-to-pin map. Each key is assigned
  to its scanned pad pair by position.
- Verification: follow the original traces in the scans (both sides) to confirm each pad reaches the expected
  tail contact. Anything unclear: a multimeter continuity check on the original, done by the user.
- Caps Lock LED: keep the two LED pads (near the diode symbol on the original) at the same position.
- Expected ≈96 keys. 91 pad pairs found automatically so far. The rest will be resolved by hand.

## 6. Routing
- Top layer: pads + most traces. Bottom layer: crossovers only (replaces the original printed jumpers).
- Traces ≥ 0.3 mm, rounded/45° corners, teardrops on pads and vias. Vias kept away from pads, bars and holes.
- No copper pour needed (no electronics, low-speed matrix).

## 7. Tail
- Same exit position and width (40.2 mm) as the original, full length (~110 mm free).
- **31 contacts, 1.25 mm pitch**, 0.72 mm wide, 6.7 mm long, on the top layer, exposed at the tail end.
  Outer contact centres 1.3 / 1.2 mm from the tail edges (as measured).
- PI stiffener 0.1 mm, ~35 mm from the tail end, bottom side.
- Pin order taken from the original tail (traced in the scan) and checked against the A1200 schematic.

## 8. Deliverables
1. KiCad project (schematic + PCB), with the stitched scans as a reference layer.
2. JLC package: Gerber + drill zip, stiffener drawn on a mechanical layer as JLC requires, and a list of
   the order-form settings in §2.
3. 1:1 check PDF (§3).

## 9. Risks / assumptions
- Size over JLC's 234 mm standard: may need review or cost more; fallback is a shorter tail.
- Contacts were checked against the plunger by photo only; the multimeter gold-pad test is recommended before ordering.
- ENIG nickel is stiff: the membrane must not be creased across keys. Bends happen only in the tail.

---

## As built — rev A (2026-11-15)
Status: **approved by the user and built.** KiCad DRC clean (0 violations, 0 unconnected). Order package: `fab/`.

Changes from the draft above, all agreed during the build:
- **Routing is a 1:1 replica of the original** (user's call; replaces autorouting). Top copper = the original
  silver traces (0.30 mm). Bottom copper = the original printed crossover bridges (0.40 mm), with 72 vias
  (0.70/0.35 mm, tented) where the original bridges land. Two tarnished trace segments near TAB/the LED were restored
  by hand (`docs/scan-data/manual_traces.json`).
- **No keep-out between the pads:** the original routes traces between the two pads of 77 keys, under its
  insulating coat. The coverlay does the same job here.
- **Pad extension is adaptive:** 165 pads +0.75 mm, 23 pads +0.5 mm, 4 pads +0.25 mm, so that it keeps ≥0.25 mm from
  traces of other nets. Coverlay window 0.30 mm around pads (reduced to ≥0.20 mm on 18 pads next to traces).
- **Tail 10 mm shorter** than the original (user: the original has spare length that bows), so the overall size is **237.0 × 440.0 mm**.
- Tail contacts: 31 × 0.75 × 6.35 mm at 1.25 mm pitch, starting 0.35 mm from the end. One coverlay opening, 7.5 mm.
- Connectivity checked three ways: skielek matrix ↔ original silver traces + bridges (0 conflicts), the replica's
  net groups (0 conflicts), and KiCad DRC (0 unconnected).
- Rebuild everything from the scans: `tools/build/make.sh` (see the header for the Python packages it needs).
- **Fit check passed (2026-11-15):** the user printed the 1:1 PDF (100 mm bar measured correct) and laid the original on top. The outline, holes and pads match exactly, with the tail 10 mm shorter as intended.
- **Tidied (2026-11-15):** from x = 155 mm, where the original's 31 tail traces already run parallel at 1.25 mm, the tail traces are clean straight lines with a 25 mm taper (under 2°) onto the contacts. 388 traces and 27 bridges were snapped exactly to 0°/45°/90°, each only where that moved it ≤ 0.12 mm and kept ≥ 0.25 mm from other nets (`tools/build/tidy.py`). DRC is still clean.
- **Tail centred on its traces (2026-11-15):** at the tail start the original's 31 traces run parallel at 1.2544 mm, within ±0.08 mm. The idealised perpendicular tail had drifted 0.76 mm off them, because the tail lay about 0.2° skewed in its scan. The tail outline and contacts were moved +0.758 mm so the traces run straight into their contacts with no jog or taper, as on the original. The fit-check PDF is regenerated to match.
- **Tail entry, the user's hand-routing method (2026-11-15):** the user hand-routed the tail start in KiCad, saved in `kicad/handrouted/`. Method: each trace's 45° diagonal is extended or shortened along its own direction until it reaches its contact's y. From there **one straight level line** runs to the contact. A trace that already arrives level gets one straight line into its contact. No jogs, no tapers. This is now `tidy.py` step 4. It matches the hand routing within 0.1 mm on 25 nets and within 0.16 mm on all 31.
- **All copper 0°/45°/90° (2026-11-15, user's rule: "always do 45 deg, no small bends along the way"):** new stage `tools/build/octi.py` (between heal and tidy). Each trace is fitted with straight runs on the 8 directions, with bends at line intersections, so it does not follow the scan's small kinks. Runs move ≤ 0.45 mm and keep ≥ 0.25 mm from other nets (or the original clearance if less, never < 0.20). Before fitting, end-to-end joins are merged and overlapping ends are snapped onto their trace. A check confirms every net's connectivity is unchanged. Small sideways jogs are removed where there is room. 17 remain, where removing one would crowd another net. Bottom bridges are also built from 0/45/90 pieces (tidy.py step 3). Result: 2696 segments, 0 off-angle, DRC 0 violations / 0 unconnected. The tail matches the hand routing within 0.37 mm.
- **Bridges simplified (2026-11-15):** each bottom bridge now takes the fewest-bend 0/45/90 path between its two vias: 1 straight and 32 with a single bend, replacing the staircases that copied the printed bar's wobble. Bridges keep ≥ 0.25 mm from other bridges and other-net vias, and 0.3 mm from the edge and holes. Shared helpers are in `tools/build/octilib.py`. DRC: 0 violations, 0 unconnected.
- **Tail root corners rounded (2026-11-15, user):** the two inner corners where the tail meets the body now have 2 mm radius fillets (first 5 mm, tightened to 2 mm at the user's request) (`TAIL_FILLET` in geometry.py) instead of 1 mm. This adds a little material outside the old outline. Traces are untouched. Confirmed by the user against the original membrane: spot on.
