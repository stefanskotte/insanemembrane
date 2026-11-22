# A1200 Flex Keyboard Membrane — Design Notes (work in progress)

Status: brainstorming. **Not an approved design yet.**
2026-11-14: membrane scanned and measured — see `docs/scan-measurements.md`. Key finding: each key
is TWO separate pads 4.55 mm apart (not a comb), so the rubber-dome contact geometry must be confirmed.
User wants the end result as a package orderable directly from JLCPCB (flex, max 234×490 mm std).
Tail measured: 0.2 mm at contact end, 0.1 mm mid → 0.11 mm 2-layer FPC + 0.1 mm PI stiffener.
**Design spec drafted: `docs/design-spec.md` — awaiting user approval.**

## What we're making

A drop-in replacement for the **Mitsumi 56C774A** Amiga 1200 keyboard membrane,
built as a **2-layer polyimide flex PCB** (not rigid FR-4).

## Why

- Rigid FR-4 replacements (e.g. C64iSTANBUL's on PCBWay) don't work well in practice.
- The original flex membranes were the right choice, but on the user's keyboards the
  pads/traces have cracked and broken with age.
- Copper-on-polyimide should be far more durable than the original printed traces
  while staying flexible.

## Agreed so far

- **Tool:** KiCad.
- **Keyboard type:** Mitsumi 56C774A.
- **Contact mechanism (corrected 2026-11-14):** each key has its own plunger with a ~8.2 × 2.5 mm
  conductive-rubber bar on the bottom. The bar's two ends land on two separate octagonal pads 7.16 mm
  apart on a 45° diagonal. No dome sheet, spacer or second sheet.

- **Pads (agreed 2026-11-14):** keep the original two-pad layout, but extend each pad 0.5–1 mm
  toward its partner along the 45° axis, giving the rubber bar more contact area.

- **Size (agreed 2026-11-14):** keep the full-length tail, overall ~248 × 440 mm (over JLC's
  234 mm standard, under the 250 mm limit). Shortening the tail is the fallback if JLC won't accept it.
- **Length:** use the scan value, ~440.3 mm after the Y-scale correction (the tape read 439 mm; the
  ruler test square measured 100 mm both ways, so the scan scale is trusted).

## Working assumptions (Claude's proposals, not yet confirmed)

- 2-layer flex: pads + most traces on top; matrix crossovers on bottom via vias placed
  away from contact pads.
- ENIG (gold) finish on contact pads.
- Stiffener on the tail so it seats in the A1200's 31-pin connector like the original.
- Success = fits the original keyboard with no changes to case, backplate or keycaps;
  tail plugs directly into CN13; every key registers reliably; orderable as a fab
  package from a standard flex service (JLCPCB / PCBWay flex).

## Known data sources

- **Matrix + key centres:** skielek/A1200KB (MIT licence, KiCad, reverse-engineered
  from a real A1200 keyboard): https://github.com/skielek/A1200KB
- **Pin verification:** A1200 schematics https://www.amigawiki.org/dnl/schematics/A1200_R1.pdf
  and Mitsumi key-to-pin map https://wiki.preterhuman.net/A1200_Keyboard_Matrix
- **Connector:** CN13 on motherboard, 31 conductors, ~1.25 mm pitch (not 1.27),
  Commodore part 390492-04. No electronics on the keyboard; one line per
  row/column, dedicated lines for the 7 modifiers, plus the Caps Lock LED.
  https://eab.abime.net/showthread.php?p=597612
  https://amigastore.eu/778-amiga-1200-600-keyboard-connector.html

## Unknowns (need the physical membrane)

- Membrane outline, mounting/locating holes, tail exit position and bend.
- Tail length, thickness at contact area (must suit the ZIF/latch socket).
- Contact pad size/pattern — depends on carbon pill diameter.
- Whether Mitsumi key positions match skielek's (they should; verify against scan).

## Next session

1. User scans the original membrane on a flatbed **next to a ruler** (both sides if
   possible; high DPI, e.g. 600).
2. Measure: carbon pill diameter, tail width/length/thickness, hole diameters.
3. Continue brainstorming: remaining open questions (quantity / who it's for,
   whether to also support the 32-pin FFC fallback, LED handling), then write the
   full design doc and get approval before drawing in KiCad.

## Not doing

- Not downloading the C64iSTANBUL Gerbers (PCBWay gates them behind an order;
  the S3 URL returns 403 without a signed link).
