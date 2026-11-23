# PCB rev 3

KiCad 10 project for the smart board described in [docs/rev3-plan.md](../docs/rev3-plan.md):
ESP32-S3 module scanning the switches, a CH446Q crosspoint presenting them to the C128,
per-key SK6812 MINI lighting, saved lock state, and a rear-exit host connector in stock C128
pin order.

Status (2026-11-23): **schematic passes ERC with zero violations; the board is placed, fully
routed and tidied, with nothing unconnected, no schematic parity differences and no DRC
errors or silkscreen warnings.  The JLCPCB order files come out of `tools/fab.py`, every
SMD part has an in-stock LCSC number, and the placement rotations have been checked part by
part in JLCPCB's preview.  The dual-spacebar plate is ready to order.**  Nothing has been
ordered or built yet.
A part-by-part explanation of the circuit is in
[docs/rev3-circuit-walkthrough.md](../docs/rev3-circuit-walkthrough.md).

## Files

| File | What |
|---|---|
| `C128-keyboard-rev3.kicad_pro` / `.kicad_sch` | project and root sheet (four sub-sheets) |
| `mcu.kicad_sch` | ESP32-S3-MINI-1U-N8 (U.FL antenna), USB-C, 5 V OR-ing, AP7361C-33E LDO, buttons |
| `crosspoint.kicad_sch` | CH446Q in serial mode, 74AHCT1G125 LED-data buffer, lock-line and RESTORE FETs, RESTORE sense diode D3, host connector J2, external LED header J3 |
| `matrix.kicad_sch` | 92 switches in a 6 x 20 scanned matrix that follows the board (`tools/layout.py` `physical_matrix`), one 1N4148W per scanned key, 74HC154 plus five GPIO for the columns |
| `leds.kicad_sch` | 92 SK6812 MINI (top mount) in chain order (lock keys first) |
| `c128rev3.kicad_sym`, `sym-lib-table` | project library with the CH446Q symbol (LQFP-44 numbering) |
| `c128rev3.pretty/`, `fp-lib-table` | project footprints: MX switches (1u, 1.5u, 2u, spacebar), the SK6812 MINI for the switch LED pocket, and the USB-C receptacle |
| `datasheets/README.md` | links to the datasheets the footprints, pinouts and placement rotations were checked against; the PDFs are downloaded there by LCSC number and not tracked |
| `tools/gen_fp.py` | the generator that writes `c128rev3.pretty/` and `fp-lib-table` |
| `C128-keyboard-rev3.kicad_pcb` | the board: rev 2.3 outline, four layers, every footprint linked to the schematic, placed and routed; DRC clean |
| `tools/gen_pcb.py` | made the board's first version; the board is the source now (see *The board* below) |
| `tools/route_keys.py` | lays the regular per-key copper on the board; rerunnable (see *Routing*) |
| `tools/freeroute.py`, `tools/plane_taps.py`, `tools/clean_dangling.py` | autoroute the rest in a container; tap the inner planes from SMD pads; delete dead-end stubs (see *Routing*) |
| `tools/move.py`, `tools/swap_footprint.py`, `tools/sync_nets.py`, `tools/rip_up.py`, `tools/tidy.py`, `tools/silk.py`, `tools/to_sheet.py` | rework a routed board: move or turn parts, swap a footprint, take the schematic's nets after a change, rip up an area, tidy the router's copper, clear the silkscreen, center the board on its sheet |
| `tools/route_host.py` | lays the host lines between J2 and the CH446Q (see *Routing*) |
| `bom.csv` | grouped BOM exported from the schematic |
| `tools/fab.py`, `fab/` | the JLCPCB order files (gerber zip, BOM, placement list) and the script that writes them; `fab/` is not tracked (see *Ordering from JLCPCB*) |
| `tools/gen_sch.py`, `tools/kisym.py` | the generator that produced all of the above |
| `tools/pinmaps.json` | CH446Q LQFP-44 pin map, GPIO plan, host connector pinout |
| `bench/README.md` | shopping list and breadboard wiring to prove the design on a rev 2.3 board |
| `plate/plate-dual.kicad_pcb` | the plate to order: a KiCad board (outline polygons plus a full copper pour) for aluminum-core PCB fabrication, with stabilizer slots for both a 9u and a 6.25u spacebar; DRC clean |
| `plate/plate-9u.kicad_pcb`, `plate/plate-6.25u.kicad_pcb` | the same plate for one spacebar only |
| `plate/plate_features.json` | mounting holes, locating holes, tab slots and stabilizer cutouts in PCB coordinates, for the layout |
| `tools/plate_step.py`, `tools/gen_plate.py` | STEP reader and plate-board generator |
| `liner/` | the bottom liner: die-cut DXF, 1:1 drawing and how it fits ([liner/README.md](liner/README.md)) |
| `tools/gen_liner.py` | writes the liner from the board: outline, windows over the tall back-side parts, tape pads on bare board |
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

- `layout/outline.json`: the board outline (Edge.Cuts lines and circles) from the same
  rev 2.3 board; `gen_pcb.py` drew the rev 3 outline from it.

`switches.json` also records each switch's rotation.  They are the original measurements,
used until the new board exists.  Once it is laid out,
point the extractor at it and regenerate:

```
python3 pcb/tools/extract_layout.py switches pcb/<new board>.kicad_pcb
python3 pcb/tools/gen_plate.py            # plate refits onto the new switch centers
python3 pcb/tools/gen_liner.py            # liner windows and tape follow the parts (then make liner)
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

- Switch and LED footprints are the project's own (`tools/gen_fp.py`, run it with
  `python3 pcb/tools/gen_fp.py`).  The switches keep rev 2.3's MX pin pattern without the
  Alps pads; the LED is a separate footprint that the placement script puts at `LED_OFFSET`
  in each switch's frame, opposite the pins where rev 2.3 had its lock-key LED holes.
  `LED_OFFSET` (0, 5.08) is **provisional** until the Outemu LED pocket is measured
  (bench/before-parts-arrive.md section 5).  The LED footprint has no courtyard on purpose:
  it sits inside the switch's.
- Spacebar stabilizer spacing (`SPACEBAR_STABS` in `gen_fp.py`): standard MX, 100 mm (6.25u)
  and 133.35 mm (9u), matching both plates and the 9u keycap drawing.  Decided 2026-11-21.
  The original C128 spacebar on its adapters wants the narrower 125.35 mm the rev 2.3 board
  drilled (and 99.77 mm for its 6.25u set); 125.35 and 133.35 are 4 mm apart, so one
  footprint cannot carry both, and rev 3 drills for standard MX spacebars.  The original bar
  goes on the 133.35 mm stabilizers through
  [`printables/spacebar_offset_adapter`](../printables/spacebar_offset_adapter/README.md),
  which moves each stabilizer stem 4 mm outward (tested 2026-11-23).
- USB-C is the SHOU HAN TYPE-C 16P 3MD 040 (LCSC C41417453; datasheet linked in `datasheets/README.md`), a
  16-pin USB 2.0 receptacle that sits on the board surface (3.26 mm tall) with its shell legs
  in four plated slots.  It is on the back at the rear edge, where the case leaves about
  17 mm under the board, so a mid-mount part is not needed.  The footprint is drawn from the
  datasheet's recommended layout (`usb_c()` in `gen_fp.py`), front flush with the board edge.
  KiCad has no 3D model for it; the footprint shows GCT's USB4105 instead, which has the
  same land pattern 3.65 mm nearer the edge, so the renders look right.
- The CH446Q footprint is KiCad's generic LQFP-44 10 x 10 mm; check it against the WCH drawing.

## The board

`tools/gen_pcb.py` made the first `C128-keyboard-rev3.kicad_pcb` straight from the schematic
netlist, the way Update PCB from Schematic would (every footprint carries its symbol's sheet
path and UUID), and `kicad-cli pcb drc --schematic-parity` reports no parity issues.  It runs
under KiCad's own python, because it needs the pcbnew module:

```
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 pcb/tools/gen_pcb.py
```

It refuses to overwrite an existing board (`--force` to start over): from here the board is
hand-edited, and schematic changes come in through Update PCB from Schematic (F8).

What it set up:

- **Outline** from `layout/outline.json`, the rev 2.3 Edge.Cuts unchanged (including the
  6.25 mm hole in the spacebar tab).  1.6 mm, four layers: signals on F.Cu and B.Cu, a
  GND plane on In1.Cu and a 5V_SYS plane on In2.Cu, each a zone over the whole board.  The
  script leaves them unfilled (pcbnew's filler crashes on a board built in memory);
  `route_keys.py` fills them.
- **Switches** on the rev 2.3 centers.  Rev 2.3 turned 14 top-row switches by 180 degrees;
  with an LED in every pocket that would light those keys from the top and the rest from the
  bottom, so rev 3 lines them all up (pins north, LED south, like the rev 2.3 lock keys).
  Keypad Enter keeps -90.  `UNIFORM_180` in the script.
- **Per key:** LED on the front in the pocket; diode (anode toward switch pin 2) and the
  LED's 100n on the back, behind the pocket.  Their references are on B.Fab: under the plate
  nobody reads them.  The LED chain snakes through the rows (`layout.led_chain`: lock keys
  first, then row 0 left to right, row 1 right to left, ...), and each LED is turned so data
  comes in on its upstream side; the 100n is turned to match its power pads.
- **Electronics** on the back in the three switch-free pockets of the top row, which have no
  holes on the back: x 183-225 (MCU, USB-C, LDO, buttons), x 297-340 at rev 2.3's FFC
  (host connector, CH446Q, FETs, LED buffer, keyboard-side fuse and diode), x 411-430
  (the five GPIO-column resistors, next to the keypad columns they drive).  The 74HC154
  and its 15 resistors sit mid-board at x 227-274 in the channel under the top row, which
  is clear of holes on the back the whole width (y 97.5-113).  First pass, packed by
  courtyard; no overlaps.  (These x values are in the generator's frame, before the move
  onto the sheet; see *Routing*.)
- **Rules** in the project file: net class Power (0.5 mm) for GND, +5V_KB, +5V_KB_F,
  +5V_SYS, +3V3 and VBUS; Default 0.25 mm, 0.6/0.3 mm vias; JLCPCB minimums.

Changed since that first pass, by hand and with `move.py`: the ESP32 was turned 180 degrees
so its GND row faces the rear edge and its GPIOs face the parts they drive (the GPIO plan in
`gen_sch.py` was re-picked to suit), and the LED buffer moved next to it; the 20 column
resistors are gone, since the key diodes already keep the columns apart (see the circuit
walkthrough); the silkscreen was cleared with `silk.py`; and the board was moved onto an A3
sheet with `to_sheet.py`.

## Routing

Status: routed completely (2026-11-23) by the steps below, several router passes and the
last few connections by hand, then `tidy.py` and `silk.py`.

`tools/route_keys.py` (KiCad's python, like `gen_pcb.py`) lays the copper every key shares,
in the switch's frame, and keeps it in one group, `route_keys`, that the next run replaces:

- switch pin 2 to the diode anode on B.Cu, past the east side of the center hole
- each LED power pad to a via (below the bottom-left pad, east of the top-right one), and
  both vias to the 100n on B.Cu
- the data hop to the next LED on F.Cu along the LED center line, where the two keys are
  neighbours in a row; hops around the lock keys, between rows and at the row ends are
  left for the router

It lays 91 switch-to-diode links, 92 LED power pairs and 75 data hops, with no DRC
copper errors.  It refills the planes after laying its vias, so every LED pad reaches GND or
5V_SYS through them.  Its copper is locked, so the autorouter treats it as fixed wiring.

`tools/freeroute.py` routes the rest with Freerouting 2.5.0 in a container (the
`freerouting` service in `docker-compose.yml`, built from `freerouting/Dockerfile`, jar pinned
by checksum): it exports the board to Specctra DSN in `freerouting/out/` (not committed),
runs the router headless, imports the session and refills the planes.  It changes the board
in place, so commit first; `git checkout` is the undo.

The planes are In1.Cu (GND) and In2.Cu (+5V_SYS).  An SMD pad reaches its plane only
through a via, and the router leaves many of those taps out, so `tools/plane_taps.py` adds
them: for each GND or +5V_SYS SMD pad whose copper holds no via or through-hole pad, a via
beside it on a short track (or inside it, for a big pad), at the first spot that clears
everything on all four copper layers.  Its copper is the group `plane_taps`, replaced on each
run.  Pads in tight spots (fine-pitch IC pins) are listed as having no room, for the next
router pass.

`tools/route_host.py` lays the host lines between J2 and the CH446Q by hand, locked, in the
group `route_host`.  The crosspoint's pin order (`XP_X_OF_COL` / `XP_Y_OF_ROW` in
`gen_sch.py`) is chosen so they need no crossings: columns on B.Cu into the package's sides
in nested lanes, rows on F.Cu down to vias inside the ring of pins.  It also ties the
CH446Q's corner GND pins and gives STB a way out from between two rows.  `route_keys.py`
leaves out any LED data hop that would cross the pockets' electronics.

Other tools for reworking a routed board: `tools/rip_up.py` deletes unlocked copper in a
rectangle or around named pads; `tools/sync_nets.py` gives the pads the schematic's nets
after a schematic change (and deletes copper on the nets that changed);
`tools/swap_footprint.py` replaces a footprint in place; `tools/move.py REF=X,Y,ROT ...` moves
or turns parts (by courtyard center), with `--check` to list clashes with other courtyards,
switch holes and the edge before anything is saved.  sync_nets.py drops all unlocked copper
on a changed net, board-wide: a remap of a matrix row loses that row's routing too.

After a router pass, `tools/tidy.py` cleans up its copper: it deletes stubs to nowhere and
copper wholly inside pads, then string-pulls every chain of segments into the fewest
0/45/90-degree runs that still clear the other nets, the holes and the edge.  Locked copper
and the USB pair are left alone.  `--report` lists the chains it couldn't clean (most bends,
longest detour) without changing anything, and `--mark` circles them on Eco1.User.

`tools/silk.py` hides the LCSC and Key fields the schematic gives every footprint and moves
any reference that overlaps other silk, a mask opening, a hole or the edge to a clear spot
beside its part.  `tools/to_sheet.py` puts the board in the middle of an A3 sheet.  It moved
the board by (-96.475, +5.475) mm, so its coordinates no longer match rev 2.3's, `layout.py`
or the `gen_pcb.py` PLACE table; add that offset to any coordinate taken from those.

```
PY=/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3
$PY pcb/tools/route_keys.py
$PY pcb/tools/rip_up.py --rect 200.525 85.575 243.525 117.875   # the CH446Q pocket
$PY pcb/tools/route_host.py
$PY pcb/tools/plane_taps.py
$PY pcb/tools/freeroute.py 25 00:45:00
$PY pcb/tools/tidy.py
$PY pcb/tools/silk.py
```

## Plate

`tools/gen_plate.py` reads the plate's loops from `layout/plate.json` (see *Layout data*
below), fits the 88 switch openings onto the switch centers in `layout/switches.json` to get the plate-to-PCB transform (RMS 0.06 mm, so plate and PCB agree
exactly), and writes the loops to Edge.Cuts.  The original plate's spacebar stabilizer boxes
sit 125.35 mm apart, rev 2.3's spacing; rev 3 drills 133.35 and 100 mm (`SPACEBAR_STABS` in
`gen_fp.py`), so the generator moves the boxes onto the PCB's holes: 133.35 mm in `plate-9u`,
100 mm in `plate-6.25u`, and both pairs in `plate-dual` (the union of the two cutouts), which
takes either spacebar's stabilizers as the PCB's spacebar footprint does.  It checks every
plate has a box centered on each hole pair before writing.  Order the dual plate.  Silkscreen text is on
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
Viewer, or `gerbview`), or upload `plate-dual-Edge_Cuts.gm1` on its own: alone, the viewer
draws the plate correctly, cutouts and all.  The fab's CAM works from the outline data, not
the preview; the routed result is what the outline says.

To order: export with the commands below, then zip the `gerbers/` files **without** the
Finder (`zip -X plate-dual-gerbers.zip plate-dual-*.g?? plate-dual-job.gbrjob`).  A Finder-made zip carries `__MACOSX`
resource-fork twins with the same extensions, which some uploaders mistake for layers.

## Part numbers for fab assembly

Every symbol carries an `LCSC` field, set in `gen_sch.py` (the `LCSC` table and a few
explicit fields).  Every SMD part has one; the through-hole parts the builder solders (key
switches, J2-J4) and JP1 (copper only) are blank, which keeps them out of the fab's BOM.
`bom.csv` includes the column.  Verify every number on lcsc.com before ordering; part
numbers rotate.  Two were swapped after a first JLCPCB upload (2026-11-22): U6 is TI's
CD74HC154M96 (C2832236), because JLCPCB was out of the Nexperia 74HC154D; and the LEDs are
the SK6812MINI-012 (C2886570), because JLCPCB rates the SK6812MINI-B-012 (C5183448) MSL 5 and
"difficult to process".  Both are drop-in: same package, pins and lands.

## Ordering from JLCPCB

```
$PY pcb/tools/fab.py
```

writes `pcb/fab/` (untracked): `C128-keyboard-rev3-gerbers.zip`, `-bom.csv` and `-cpl.csv`.
It refuses to write if DRC finds an error, anything unconnected or a parity difference, or if
an SMD part has no LCSC number.  Order a 4-layer board, upload the zip, then turn on
assembly for **both sides** and upload the BOM and CPL.  In the placement preview check
every part's rotation and pin 1, the LEDs and the ESP32 module especially: JLCPCB's part
models don't all share KiCad's zero orientation.  The LED's pin 1 is DIN (its chamfered
corner), which is pad 3 of our footprint, not pad 1; the silkscreen dot beside each LED marks
that corner, so the part's pin-1 mark belongs on the dot.  Fix a turned part there, or put its
footprint in `ROT_ADD` in `fab.py` (the degrees the preview needed on top of KiCad's rotation) and rerun.

Status: checked in the preview on 2026-11-23, every part placed correctly with the CPL as
written (J1, U1, U3, U6, U7, C5 and the diodes carry corrections in `ROT_ADD`); five
assembled boards quoted at about 500 USD shipped.  J1's CPL position is the middle of its
pads, not its footprint origin (which sits at the board edge), so the fab turns it in place.
The plate is a separate order: upload `plate/gerbers/plate-dual-gerbers.zip` (made with the
commands under *Verifying*) as a 1.5 mm single-layer aluminum board; about 50 USD.
The bottom liner, for flat builds, goes to a die-cut converter as `liner/liner.dxf` with
`liner/liner.pdf`, or is cut by hand from the PDF.

## Verifying

```
KC=/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli
$KC sch erc --severity-all C128-keyboard-rev3.kicad_sch
$KC sch export pdf -o rev3.pdf C128-keyboard-rev3.kicad_sch
$KC sch export bom -o bom.csv --fields 'Reference,Value,Footprint,LCSC,${QUANTITY}' --group-by Value,Footprint C128-keyboard-rev3.kicad_sch
$KC pcb drc --severity-all plate/plate-dual.kicad_pcb
$KC pcb export gerbers --layers "Edge.Cuts,F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS" -o plate/gerbers/ plate/plate-dual.kicad_pcb
# no drill export: the plate has no drilled holes, and header-only drill files confuse JLCPCB's viewer
```
