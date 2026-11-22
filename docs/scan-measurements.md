# Scan measurements — Mitsumi 56C774A membrane (2026-11-14)

Source scans (project root): `top-left/right.tiff` (carbon-pad side), `back-left/right.tiff`
(silver side), `back-tail.tiff` (carbon side, despite the name), `top-tail.tiff` (silver side).
All 600 dpi, Canon i-SENSYS MF744Cdw, printed rulers from `docs/scan-ruler.pdf` in every scan.
Scripts: `tools/scan/*.py`. Extracted data: `docs/scan-data/`.

## Accuracy
- Ruler ticks: X 600.0 dpi, Y 599.4–599.8 dpi (≤0.1 % error, ~0.4 mm over 440 mm). Tick fit residual ~0.03 mm.
  Printed-ruler accuracy itself not yet verified (100 mm test square not measured).
- Stitching via through-holes: front L↔R 0.05 mm rms; back→front (mirrored) 0.13 mm rms; tail scan→front 0.07 mm rms.

## Stitched images (front frame = carbon side up, mm, origin top-left of image)
- `docs/scan-front-stitched.png` — carbon side, 600 dpi.
- `docs/scan-back-mirrored-into-front-frame.png` — silver side, mirrored so it overlays the front exactly.

## Body
- Bounding box **137.7 × 440.1 mm** (x 26.9–164.5, y 20.2–460.2), stepped outline, 106-vertex polygon in `features.json`.
- CAVEAT: rulers were butted against both short ends; confirm overall length (~440 mm) with a tape measure.
- Holes: mostly **Ø6.45 mm** round (likely 6.5 nominal), one Ø6.0 mm, one 6.0 × 8.0 mm slot, one edge notch. Positions in `front-holes.json`.

## Keys / contacts
- Single printed sheet: silver traces, carbon over the contact pads, printed green insulation with a window
  (~0.3 mm halo) around each pad, printed dielectric patches + jumpers for crossovers.
- **Each key = two separate octagonal pads**, ~4.1 × 3.3 mm (~9.5 mm²), centres **7.16 mm apart on a 45° diagonal**
  (vector +5.14, +5.01 mm), closest edge-to-edge gap **4.55 mm** (4.52–4.64 over 91 keys).
- 193 pads found → 91 pairs confirmed automatically + a few to resolve by hand (≈96 keys expected).
- Contact mechanism (user photos 2026-11-14): no rubber-dome sheet. Each key has its own plunger with a
  **black conductive-rubber bar** on the bottom, about **8.2 × 2.5 mm** (estimated from a photo), notched at the ends and
  saddle-shaped (ends stand proud). The bar lies along the pads' 45° axis: its ends land on the two pads
  (pad centres ±3.58 mm, inner edges ±2.3 mm, bar ends ±4.1 mm → roughly 1.8 mm overlap per pad).

## Tail (connector to CN13)
- Exits the long edge at y 147.6–188.6 mm (front frame), runs perpendicular, free length **~112 mm**.
- Width **40.15–40.25 mm**.
- **31 contacts at 1.249 mm pitch** (≈1.25), exposed carbon fingers 0.72 mm wide, **6.7 mm long**,
  on the carbon-pad side; outer finger centres 1.3 / 1.2 mm from the tail edges.
- Darker (likely stiffened) zone from the tail end to ~35 mm; faint line at ~61 mm from the end.
- OPEN: thickness at the contacts and of the stiffener (calipers).

## Overall size vs JLCPCB flex
- Body + tail = **~248 × 440 mm**. JLC flex standard max 234 × 490 mm, absolute limit ~250 × 500 mm.
