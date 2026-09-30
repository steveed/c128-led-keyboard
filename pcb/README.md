# PCB rev 3 (draft)

KiCad 10 project for the smart board described in [docs/rev3-plan.md](../docs/rev3-plan.md):
ESP32-S3 module scanning the switches, a CH446Q crosspoint presenting them to the C128,
per-key SK6812 MINI lighting, saved lock state, and a rear-exit host connector in stock C128
pin order.

Status: **schematic drafted and revised through 2026-09-18, passes ERC with zero violations; no layout yet.**
A part-by-part explanation of the circuit is in
[docs/rev3-circuit-walkthrough.md](../docs/rev3-circuit-walkthrough.md).

## Files

| File | What |
|---|---|
| `C128-keyboard-rev3.kicad_pro` / `.kicad_sch` | project and root sheet (four sub-sheets) |
| `mcu.kicad_sch` | ESP32-S3-WROOM-1-N8, USB-C, 5 V OR-ing, AP7361C-33E LDO, buttons |
| `crosspoint.kicad_sch` | CH446Q in serial mode, 74AHCT1G125 LED-data buffer, lock-line and RESTORE FETs, RESTORE sense diode D3, host connector J2, external LED header J3 |
| `matrix.kicad_sch` | 92 switches with the rev 2.3 ROW/COL assignments, one 1N4148W per scanned key, 74HC154 column select |
| `leds.kicad_sch` | 92 SK6812 MINI (top mount) in chain order (lock keys first) |
| `c128rev3.kicad_sym`, `sym-lib-table` | project library with the CH446Q symbol (LQFP-44 numbering) |
| `bom.csv` | grouped BOM exported from the schematic |
| `tools/gen_sch.py`, `tools/kisym.py` | the generator that produced all of the above |
| `tools/pinmaps.json` | CH446Q LQFP-44 pin map, GPIO plan, host connector pinout |
| `bench/README.md` | shopping list and breadboard wiring to prove the design on a rev 2.3 board |
| `plate/plate-9u.kicad_pcb`, `plate/plate-6.25u.kicad_pcb` | the plate as a KiCad board (outline polygons plus a full copper pour) for aluminum-core PCB fabrication, in PCB coordinates; DRC clean |
| `plate/plate_features.json` | mounting holes, locating holes, tab slots and stabilizer cutouts in PCB coordinates, for the layout and the bottom cover |
| `tools/plate_step.py`, `tools/gen_plate.py` | STEP reader and plate-board generator |
| `tools/plate_header.kicad_pcb` | the plate boards' layer stack and setup block, copied into every generated board |
| `tools/extract_layout.py`, `tools/layout.py` | write and read `../layout/`, the measurements every generator works from |

## Layout data

Every generator here, and `firmware/tools/gen_keymap.py`, reads its key positions from the
repository's `layout/` folder rather than from another board file:

- `layout/switches.json`: the 92 switches (reference, key legend, center in KiCad board
  coordinates, row and column nets).  Extracted from the rev 2.3 board,
  [`pcb/C128-keyboard.kicad_pcb`](https://codeberg.org/jflitton/the-c128-keyboard-project/src/branch/main/pcb/C128-keyboard.kicad_pcb) in the-c128-keyboard-project.
- `layout/plate.json`: the plate's outline and every cutout as line/arc loops, in the STEP
  model's own frame.  Extracted from that project's
  [`plate/plate.step`](https://codeberg.org/jflitton/the-c128-keyboard-project/src/branch/main/plate/plate.step); `gen_plate.py` fits it onto the switches.

They are the original measurements, used until the new board exists.  Once it is laid out,
point the extractor at it and regenerate:

```
python3 pcb/tools/extract_layout.py switches pcb/<new board>.kicad_pcb
python3 pcb/tools/gen_plate.py            # plate refits onto the new switch centers
python3 firmware/tools/gen_keymap.py
```

`extract_layout.py plate <file>.step` does the same for a new plate model.  Both files keep
one switch or loop per line, so a moved key is a one-line diff.

## How it was made, and how to change it

The schematic is generated: `python3 pcb/tools/gen_sch.py` rewrites every `.kicad_sch`
here.  Symbols come straight from the KiCad 10 standard libraries (derived symbols are
flattened the way eeschema does it), switch positions and matrix nets come from
`layout/switches.json` (see *Layout data* below), and all connectivity is global labels on short pin stubs.
The output is meant to be opened in eeschema and tidied by hand.  **Once hand edits start,
stop running the generator**, or fold the change into `gen_sch.py` first.

The generator writes the file-format versions KiCad 10.0 uses (`VERSION`, `LIB_VERSION` at
the top of `gen_sch.py`), so eeschema opens the sheets without asking to resave them.  When
a newer KiCad moves the format, `kicad-cli sch upgrade --force` on a copy shows the new
version number to paste in; the check that nothing else changed is to export the netlist
from both and compare.

Every UUID in the output is deterministic: symbols and pins are keyed on sheet file plus
reference designator, wires, labels and text on type and position.  Running the generator
twice gives byte-identical files, a one-part change shows up as a one-part diff, and once a
board exists its footprints stay linked to their symbols across regenerations.  Renaming a
reference designator does change that symbol's UUID, so treat refs as stable once layout
has started.

One quirk worth knowing: `kicad-cli sch erc` reports a wire that runs directly from one pin
to another as "not connected to anything", even though both pins show as connected.  The
generator therefore puts a net label on every such wire (the LED chain segments, the 74HC154
fan-out, the jumper link).  Wires that end on a label, junction or another wire are fine.

Placeholders to resolve during layout:

- Switch footprints are KiCad's `SW_Cherry_MX_1.00u_PCB`.  Rev 3 needs footprints with the
  SK6812 MINI pads at the north LED position and the screw-in stabilizer holes; make them in a project footprint
  library and reassign (the 2u keys, keypad Enter and the 9u/6.25u spacebar included).
- The USB-C footprint is the GCT USB4105; swap for whatever is actually ordered.
- The CH446Q footprint is KiCad's generic LQFP-44 10 x 10 mm; check it against the WCH drawing.

## Plate

`tools/gen_plate.py` reads the plate's loops from `layout/plate.json` (see *Layout data*
below), fits the 88 switch openings onto the switch centers in `layout/switches.json` to get the plate-to-PCB transform (RMS 0.06 mm, so plate and PCB agree
exactly), and writes the loops to Edge.Cuts.  The 6.25u variant is the same plate with the
spacebar's stabilizer boxes slid in from 133.35 mm to 100 mm spacing.  Silkscreen text is on
F.SilkS; add legends there if wanted.  Order as 1.5 mm single-layer aluminum PCB.

Every loop is written as one closed polygon with arcs flattened to chords (error under
5 um), so each contour closes exactly (a closed polyline repeats its first vertex verbatim;
separate line and arc primitives can land a nanometer apart after KiCad recomputes arc
endpoints on export).  The top copper layer carries a zone covering the whole plate, filled
by KiCad's python module when the generator runs (kicad-cli cannot fill zones), keeping the
board's copper-to-edge clearance from every cutout.  Aluminum-core PCBs are ordered as one
copper layer under soldermask, so this copper is what carries the plate's color.  DRC
reports one warning, an isolated copper fill with no net, which is the point.

**JLCPCB's online gerber viewer shows this plate with the switch cutouts filled in.  That
is a limit of the viewer, not of the files.**  Established on 2026-09-22 by uploading some
forty variants to the quote page:

* The outline layer is valid: 110 closed contours, every endpoint shared exactly, parsed
  cleanly by KiCad, by an independent gerber library, and by the viewer itself.
* The viewer renders every one of our cutouts when the outer contour is a plain rectangle,
  or a rectangle with a single edge notch or the single tab slot.  It stops resolving inner
  cutouts as soon as the outer contour carries two or more edge features, however they are
  drawn (fine arcs, coarse chords, chamfers, plain rectangles all fail together; notch plus
  tab slot fails).  This plate's rear edge has five features, so no version of the true
  outline previews correctly.  The A500 plate that does preview has a seven-segment outline
  with one step.
* Header attributes, file names and extensions, line endings, coordinate ranges, winding
  direction, chained versus separate segments, copper clearance and the silkscreen were each
  varied and ruled out.

Two things the exercise did find and fix: header-only drill files (this plate has no drilled
holes, every opening is routed) make the viewer drop the outline entirely, so `export drill`
is not run and the zip carries gerbers only; and silkscreen outside the outline inflates the
board size the quote is based on, so the legend sits inside the plate.

To check the cutouts yourself, open the gerbers in KiCad's gerber viewer (Tools > Gerber
Viewer, or `gerbview`), or upload `plate-9u-Edge_Cuts.gm1` on its own: alone, the viewer
draws the plate correctly, cutouts and all.  The fab's CAM works from the outline data, not
the preview; the routed result is what the outline says.

To order: export with the commands below, then zip the `gerbers/` files **without** the
Finder (`zip -X plate-9u-gerbers.zip plate-9u-*.g?? plate-9u-job.gbrjob`).  A Finder-made zip carries `__MACOSX`
resource-fork twins with the same extensions, which some uploaders mistake for layers.

## Part numbers for fab assembly

Every symbol carries an `LCSC` field.  The generator fills it for the parts we are sure are
stock items at JLCPCB (0603 R/C, SS34, 2N7002, USBLC6-2SC6, AP7361C-33E); the rest are blank
and get filled in at layout time once the stocked package is chosen.  `bom.csv` includes the
column.  Verify every number on lcsc.com before ordering; part numbers rotate.

## Verifying

```
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$KC sch erc --severity-all C128-keyboard-rev3.kicad_sch
$KC sch export pdf -o rev3.pdf C128-keyboard-rev3.kicad_sch
$KC sch export bom -o bom.csv --fields 'Reference,Value,Footprint,LCSC,${QUANTITY}' --group-by Value,Footprint C128-keyboard-rev3.kicad_sch
$KC pcb drc --severity-all plate/plate-9u.kicad_pcb
$KC pcb export gerbers --layers "Edge.Cuts,F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS" -o plate/gerbers/ plate/plate-9u.kicad_pcb
# no drill export: the plate has no drilled holes, and header-only drill files confuse JLCPCB's viewer
```
