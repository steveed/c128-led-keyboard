# PCB rev 3: the smart board

Status: schematic drafted 2026-09-17 in `pcb/`, revised 2026-09-18 (CH446Q in serial
mode, per-key diodes, top-mount LEDs, RESTORE sense diode, fab assembly, aluminum plate
boards generated); board file created and placed 2026-11-21, routed and DRC clean
2026-11-23, with the JLCPCB order files checked in the fab's preview and the dual-spacebar
plate ready (see `pcb/README.md`); nothing ordered yet; bench proofs not started.  Decisions taken 2026-09-17/18.  Background and the reasoning
behind each change is in [pcb-issues-and-plans.md](pcb-issues-and-plans.md), and a part-by-part
explanation of the schematic is in [rev3-circuit-walkthrough.md](rev3-circuit-walkthrough.md);
this document is
the thing to pick up when the work starts.  It lists what changes from rev 2.3, in what order,
and what has to be proven on the bench before copper is ordered.

## Decisions

- Rev 2.3 stays the "dumb" board.  There is no rev 2.4; the next spin is rev 3.
- Rev 3 adds a microcontroller and an analog crosspoint between the switches and the C128.
  The C128 still sees a plain switch matrix.  The crosspoint is the WCH **CH446Q** (8x16,
  LQFP-44, about a tenth of the MT8816's price, fab-stocked), driven in its serial address
  mode straight from the ESP32: its digital inputs accept 3.3 V at a 5 V supply, so no level
  shifters.  The MT8816 is functionally the same part and remains a drop-in fallback in
  parallel mode if the CH446Q ever disappears.
- Lock keys (CAPS LOCK, 40/80, SHIFT LOCK) become virtual toggles in firmware with the state
  saved to flash.
- Per-key RGB (SK6812 MINI, 3.5 x 3.5 mm top mount in the switch's SMD LED pocket) on every
  switch, DNP-able, lock keys first in the chain.  No PCB cutouts.
- Keyboard connector moves to the back of the board in the **stock C128 pin order**, and the
  FFC goes away.  The original 128 cable is plain wires soldered to the keyboard PCB, and the
  printed 1 x 25 housing exists to mimic the original plug, so the board gets one 2 x 13
  0.1" footprint laid out in D-sub IDC order.  The cable is 26-way 0.05" ribbon, the same
  family as a floppy cable, crimped to an IDC DB25 for a 128D or split into crimped pins for
  the printed housing on a flat.  At the keyboard end the ribbon either mates to an IDC
  header (if the flat's underside clearance allows about 9 mm) or is soldered straight into
  the same pads (zero height).  The crossover adapter project is only needed for rev 2.x
  boards.
- Spacebar: the plate gets a **6.25u** variant next to the stock 9u.  The PCB footprint already
  has both stabilizer hole sets.  No extra keys beside the spacebar; SHIFT LOCK is the
  command modifier on every build, as on the BlingBox.  The Signature Plastics keycap set
  includes a 9u spacebar, so the stock 9u plate is the primary one for MX-cap builds too;
  6.25u stays as an option for other keycap sets.
- Stabilizers: **PCB-mount screw-in** on every stabilized key (spacebar, Return, keypad 0,
  keypad Enter).  The plate carries clearance slots for the stabilizer housings and wires,
  not stabilizer mounting cutouts.
- MCU: ESP32-S3-MINI-1U-N8 module (no PSRAM, so GPIO 35..37 stay free).  Changed from the
  WROOM-1 on 2026-11-21: the whole PCB sits under the plate (PCB rear edge y 80.1, plate to
  y 70), so an on-board antenna would be under metal, and the MINI is 2.4 mm tall against the
  WROOM's 3.2 mm, which matters on the flat 128's underside.  The antenna is external on the
  U.FL; with no WiFi wanted, nothing is fitted.  Same GPIO map.  RP2040 is the fallback only
  if the ESP32 fails bring-up on power or timing.
- Board outline, plate-ground pad and switch positions do **not** move, so the existing
  plate, printed case and printables keep fitting.  A thin insulating liner taped to the
  underside protects flat builds, as on the Amiga 1000 keyboard; the PCB needs no holes.
- One 1N4148W diode per scanned key, on the back with the other SMD parts, so the board also
  works as a ghost-free USB keyboard.
- Every SMD part is placed by the fab; builders solder through-hole only (see Assembly).
- Four copper layers (decided 2026-11-21): signals on F.Cu and B.Cu, a GND plane on In1.Cu
  and a 5V_SYS plane on In2.Cu.  On two layers the matrix rows and LED chain (horizontal, F.Cu)
  and columns (vertical, B.Cu) cut any 5 V or GND pour into strips, and 92 LEDs at full white
  draw several amps; the planes give every LED's power vias a solid return and supply.
- The firmware also gives the board a USB keyboard mode for emulators and a network keyboard
  (see Firmware).

## Architecture

```
                 ┌──────────── physical side (3.3 V) ────────────┐   ┌──── host side (5 V) ────┐
 92 switches ──► 6 rows x 20 cols ──► ESP32-S3 ──► CH446Q 8x16 crosspoint ──► ROW0-7, COL0-10
                                          │        (serial: DAT, CK, STB, RST, 3.3 V direct)
   (1 diode per key) (74HC154 selects      │   └─► 2N7002 open-drain ──────────► 40/80 (default-assert)
                    the column)           │   └─► 2N7002 open-drain ──────────► CAPS LOCK
                                          ├──► 74AHCT1G125 ──► 92 x SK6812 MINI ──► ext. LED header
                                          ├──► USB-C: 5 V in (OR'd with keyboard +5 V), native USB
                                          └──► WiFi AP for the web UI
 RESTORE switch ───────────────────────────────────────────────────────────────► RESTORE (hard-wired)
                                          └─► 2N7002 open-drain (Q3) ─────────► RESTORE (firmware press)
```

- The MCU scans the physical matrix continuously, debounces, and mirrors each pressed key
  into the CH446Q so the C128 sees a closed switch at the same ROW/COL it always did.  One
  switch write is seven address bits clocked on CS/CK, DAT set, and a STB pulse: under a
  microsecond at any sane clock.
- Lock keys are ordinary physical keys.  SHIFT LOCK "on" means the left-shift crosspoint
  (COL1/ROW7) stays closed; CAPS LOCK and 40/80 pull their dedicated host lines low through
  a FET, as the mechanical switches did.
- RESTORE stays a plain switch to the RESTORE line, so it works with the firmware dead.  A
  diode lets the MCU sense it (lighting, USB mode) and an open-drain FET lets the MCU press it
  (network keyboard, macros).
- Nothing 5 V ever reaches an ESP32 pin.  The CH446Q runs at 5 V and is bidirectional
  analog, and it takes 3.3 V on its control inputs; the FETs are open-drain; the LED data
  line is the one remaining 5 V logic input and gets a single-gate buffer.

## Schematic changes

### Remove

| Ref | Part | Why |
|---|---|---|
| U1, U2, U3 | MAX16054 | replaced by firmware toggles |
| U4 | 74AUC1G66 | left-shift is now a crosspoint |
| R1, R2, R3 | 330 ohm LED resistors | single-color lock LEDs replaced by RGB |
| C1, C2, C3 | 220 pF on K0..K2 | dropped; the crosspoint isolates the host lines and the C128 side has its own filtering |
| SW89/91/92 LED pads | MX-1U footprint with LED | all keys use the same footprint with SK6812 MINI pads |

### Add

| Block | Parts | Notes |
|---|---|---|
| MCU | ESP32-S3-MINI-1U-N8 (U.FL antenna), BOOT and RESET tact switches, 10 k pull-ups, 100 nF | strapping pins (GPIO0, 3, 45, 46) left free or used only for outputs that are safe at boot |
| 3.3 V supply | AP7361C-33E low-dropout LDO (SOT-223, 1 A, 0.36 V dropout, LCSC C500795), 10 uF in/out | fed from the OR'd 5 V rail, about 4.55 V; the AMS1117 originally planned had no headroom there |
| 5 V OR-ing | 2 x SS34 Schottky (keyboard +5 V, USB VBUS) into 5V_SYS, PTC fuse 1.1 A on the keyboard side, 220 uF bulk | the CH446Q and lock FETs are referenced to the keyboard rail; everything else runs from 5V_SYS |
| USB-C | 16-pin receptacle, 5.1 k CC pull-downs, ESD array | native USB on GPIO19/20 for flashing, serial config and the web flasher |
| Crosspoint | CH446Q LQFP-44 at 5 V (VDD = +5V_KB, VEE = GND), 100 nF | Y pins carry host ROW0..7 and eleven of the X pins host COL0..10, in the order that routes cleanly from J2 (`XP_X_OF_COL` / `XP_Y_OF_ROW` in `gen_sch.py`; the firmware addresses through the same table); five X pins unused.  Serial mode: P/S and AX0-3/AY0-2 to GND; DAT, CS/CK, STB, RST direct from the ESP32.  10k pull-up on RST (crosspoint stays cleared until the MCU boots), 10k pull-down on STB |
| Column select | 74HC154 4-to-16 decoder for columns 0-14, five GPIO for columns 15-19, driven directly | the scanned matrix follows the board (6 key rows x 20 columns, decided 2026-11-21), not the C128's assignment, which keeps the matrix copper short; the firmware maps each position to its host position.  Columns go low one at a time; no series resistors, since the per-key diodes already stop two pressed keys in one row from joining a high column to a low one |
| Rows | 8 GPIO inputs with internal pull-ups | ROW0..7 physical |
| Matrix diodes | 91 x 1N4148W SOD-123 (D101..D192, one per scanned key; RESTORE has none) | row -> switch -> diode -> column; any chord reads without ghosting, which USB keyboard mode needs |
| RESTORE sense | D3 1N4148W, cathode to H_RESTORE, anode to IO14 with the internal pull-up on | reads the key with or without a Commodore attached; replaces the 10k/20k divider |
| RESTORE driver | Q3 2N7002 open-drain on H_RESTORE, 100 k gate pull-down (R12), gate on IO9 | lets the firmware press RESTORE (RUN/STOP + RESTORE from the network keyboard, macros); the physical switch stays hard-wired in parallel |
| Lock drivers | 2 x 2N7002 | 40/80 gate has a 10 k pull-up to 3.3 V behind a solder jumper (closed = asserts 80 columns from the instant power arrives, before the MCU boots); the MCU drives the gate low to release.  CAPS LOCK is plain open-drain |
| LEDs | 92 x SK6812 MINI (top mount), 92 x 100 nF, 74AHCT1G125 single-gate level shifter, 3-pin external LED header | chain order: SHIFT LOCK, CAPS LOCK, 40/80, then row by row.  Data out of the last LED to the header for a "Razzle"-style power LED or an underglow strip |
| Connector | 2 x 13 0.1" footprint on B.Cu in D-sub IDC pin order.  Populate a shrouded IDC box header (vertical or right-angle, both ~9 mm mated) where height allows, otherwise leave it empty and solder the ribbon into the pads | pinout below.  Replaces the FFC |
| Test | 0.1" test points on 5V_SYS, 3V3, LED data, one row, one column | layout item; not in the schematic yet |

### GPIO budget (ESP32-S3-MINI-1U-N8)

| Function | Pins |
|---|---|
| Physical rows in | 6 |
| Column select (74HC154 A..D) | 4 |
| GPIO columns 15-19 (IO1, 2, 4, 5, 6) | 5 |
| CH446Q DAT, CS/CK, STB, RST (serial mode) | 4 |
| LED data | 1 |
| 40/80, CAPS LOCK gates | 2 |
| RESTORE sense | 1 |
| RESTORE drive | 1 |
| USB D+/D- | dedicated (19/20) |
| **Total** | **24** of ~31 usable (spare: IO36, 37, and IO26, 33, 34 on the MINI) |

### Connector pinout (stock C128 order)

The 2 x 13 footprint is laid out so a standard 0.05" ribbon crimped to an IDC DB25 needs no
re-ordering (ribbon conductor n is header pin n; the IDC D-sub puts odd conductors on pins
1..13 and even conductors on pins 14..25; conductor 26 is trimmed).  The same property makes
the ribbon solderable straight into the pads with no fanning: 1.27 mm conductors alternate
between the two 2.54 mm rows, so conductor 1 goes to pin 1, conductor 2 to pin 2, and so on
down the footprint.  For a flat, the far end is split and each conductor crimped into a
kk-style pin in the printed 1 x 25 housing, following the D-sub column of the table:

| Header | D-sub | Signal | Header | D-sub | Signal |
|---|---|---|---|---|---|
| 1 | 1 | GND | 2 | 14 | COL6 |
| 3 | 2 | key (NC) | 4 | 15 | COL5 |
| 5 | 3 | RESTORE | 6 | 16 | COL4 |
| 7 | 4 | +5 V | 8 | 17 | COL3 |
| 9 | 5 | ROW3 | 10 | 18 | COL2 |
| 11 | 6 | ROW6 | 12 | 19 | COL1 |
| 13 | 7 | ROW5 | 14 | 20 | COL7 |
| 15 | 8 | ROW4 | 16 | 21 | K0 (COL8) |
| 17 | 9 | ROW7 | 18 | 22 | K1 (COL9) |
| 19 | 10 | ROW2 | 20 | 23 | K2 (COL10) |
| 21 | 11 | ROW1 | 22 | 24 | 40/80 |
| 23 | 12 | ROW0 | 24 | 25 | CAPS LOCK |
| 25 | 13 | COL0 | 26 | - | not used |

Verify the odd/even convention with a meter on a real IDC DB25 before ordering boards.
Silkscreen the D-sub pin number next to every header pin so hand-wiring a flat cable needs
no table.

## Layout changes

- Keep the rev 2.3 outline, mounting holes, plate-ground pad and every switch center.
- Screw-in stabilizer holes (3.05 mm screw and 4.0 mm peg) on every stabilized key.  The 2u
  footprints (Return, keypad 0, the flipped keypad Enter) had both sizes on rev 2.3 and keep
  them.  The rev 2.3 spacebar as fabricated has two sets, 99.77 mm and 125.35 mm (not the
  three spacings its library file suggests); the rev 3 footprint drills the standard MX 100 mm and
  133.35 mm that the plates and keycap drawing use (decided 2026-11-21: standard MX spacebar;
  the original spacebar's narrower 125.35 mm is not drilled).  See pcb/README.md.  The
  original bar fits through a printed offset adapter (`printables/spacebar_offset_adapter`,
  decided 2026-11-23 over drilling 125.35 again); test-fitted on a 9u MX board the same day,
  and it works.
- Every switch footprint gains SK6812 MINI pads on the front at the north LED position, where
  the Outemu bottom housing has its SMD LED pocket.  No cutouts, so the rev 2.3 routing
  survives; the LED chain and 5 V feed are new front-side traces.  Front-side SMD means the
  board is assembled on both sides (LEDs front, everything else back); hand builds solder the
  LEDs before the switches go on.
- **Underside height budget.**  On a flat 128 the space between the keyboard PCB and the RF
  shield is the tight dimension, and rev 3 puts taller parts on the back than rev 2.3 ever
  had: the ESP32 module (~3.2 mm), the USB-C receptacle (~3.3 mm), the cable header and the
  CH446Q (LQFP-44, ~1.6 mm, no longer a concern).  A 26-way IDC header is about 9 mm mated
  whether vertical or right-angle.  The 1 mm the plate change in issue 4 gives back below
  the plate counts toward this budget.

  Measured 2026-11-21 on a flat 128, case top to RF shield: about 25 mm at the rear edge and
  about 10 mm at the front edge.  Less the 8 mm keyboard stack (plate top to PCB bottom),
  that leaves **about 17 mm under the PCB at the rear and about 2 mm at the front**, tapering
  in between (the case angles up toward the rear).  On a straight taper over the 126 mm
  depth, the rear band (y < 113) has 13 to 17 mm, so the IDC header, the electrolytic and the
  tact switches all fit there, header included.  The front rows have about 2 mm against
  1.7 mm of switch pins: rev 3 adds nothing taller than the pins there (only the SOD-123
  diodes and 0603 capacitors), and nothing tall may move forward of the rear band.
- Cluster every tall back-side part (module, CH446Q, USB-C, connectors) in a band along the
  rear edge.  The flat 128's wedge is deepest at the rear, and it keeps the bottom cover flat
  over the rest of the board.
- No mounting holes for a bottom cover: it is a taped liner (decided 2026-11-23, see
  *Bottom cover*).
- Connector footprints on B.Cu near the rear edge, at roughly the same X as today's CN2 so the
  printed case's DB25 cutout still lines up.  Confirm clearance to the flat C128's RF shield
  before fixing Y.
- ESP32-S3-MINI-1U on B.Cu in the rear band.  The rear edge is *not* outside the plate (the
  plate overhangs it by 10 mm), which is why the module is the U.FL variant: route the
  antenna lead out of the case rather than keeping copper clear for a trace antenna.  Keep
  the U.FL reachable and its mated height (about 2 mm above the module) inside the budget.
- CH446Q on B.Cu next to the connector, so the 19 host lines are short.  Keep its pads clear
  of switch pins.
- USB-C on the rear edge, accessible with the plate on; on the flat it will be reachable only
  with the case open, which is acceptable.
- LED chain routed as a single snake; power for the LEDs from the 5V_SYS plane on In2.Cu,
  one via per LED pad.  The chain starts at the three lock keys.
- The three lock keys keep their positions; only their footprint changes.

## Bottom cover

A thin insulating liner under the PCB so the switch pins, solder joints and back-side parts
can never touch the flat 128's RF shield, a bench, or a hand.  In the printed 128D case the
tray already does this job, so the liner is for flat builds and bare keyboards.

Decided 2026-11-23: do what Commodore did on the Amiga 1000 keyboard, a thin plastic liner
(the kind under an old computer case) held on with double-sided tape.  No screws, no printed
part and no mounting holes in the PCB, which rev 3 does not have.

Drawn 2026-11-23 as a die-cut Formex part: `pcb/liner/` (DXF, dimensioned PDF, and how it
fits), generated from the board by `pcb/tools/gen_liner.py`.

- Coverage: the 128's main board does not reach under the last two key rows (the Z row and
  the spacebar), which is also where there is only about 2 mm below the PCB.  The liner stops
  at the Z row; at its front edge there is still about 6 mm.
- Material: Formex GK-17 (0.43 mm polypropylene) or 0.4 mm fish paper, die cut or cut by
  hand from the 1:1 drawing.
- Fixing: 35 pads of 2.3 mm double-sided foam tape on bare board, in the lanes between the
  switch rows, between the function keys and in the rear band.  The foam holds the sheet
  clear of the 1.7 mm switch pins, so only the tape touches the PCB; 2.7 mm in all.
- Windows for every back-side part taller than 1.9 mm (the ESP32, USB-C, cable header, C5,
  J3/J4, the tact switches, U6, D1/D2).  Those at the rear edge open into notches for the
  USB-C plug, the ribbon and the antenna lead.  Plastic over the antenna lead is fine; metal
  is not.

## Layout tooling: KiCadRoutingTools

**Superseded 2026-11-21:** the regular per-key copper is laid by `pcb/tools/route_keys.py`
and the rest goes to Freerouting in a Docker container (push-and-shove, and it keeps to the
containers-only rule; KiCadRoutingTools needs host numpy/scipy/shapely and ships a
macOS-only router binary).  The review below is kept for reference.

`../KiCadRoutingTools` (v0.22.0, also installed as the KiCad 10 plugin) is the autorouter and
checker set to use for rev 3.  Reviewed 2026-09-18; the fit for this board:

- **Placement:** mostly fixed by mechanics (92 switches, 92 LEDs, 91 diodes near their keys,
  connectors on the rear band).  Write a `design-brief.json` beside the board naming the
  rear-edge connectors and the antenna keep-out, then `check_floorplan.py --emit-intent` and
  grade; `place_optimize.py` is only for the small free-floating parts.
- **Routing:** `route.py` over all nets with `--power-nets "+5V*" GND --power-nets-widths`
  wider for the LED 5 V feed, the CH446Q analog lines routed first (MPS ordering), keepouts on
  User.2 for the antenna and the plate-screw pockets, guide corridors on User.1 for the LED
  chain snake.  No push-and-shove, so the switch/diode/LED pattern must leave channels first.
- **Planes:** `route_planes.py` for a GND pour on B.Cu with pad welding by the route step.
- **Checks:** `check_drc.py`, `check_connected.py`, `check_orphan_stubs.py`, `check_pads.py`,
  and `kicad_unconnected.py` as the KiCad-DRC oracle; `/review-routed-board` for sign-off;
  `/diagnose-routing-failures` when nets fail.
- **Host state:** the Rust router binary loads on this machine, but the CLI needs numpy, scipy
  and shapely, which are not installed for the host Python; use a venv or the plugin GUI.

## Plate

**Make the plate as a PCB.**  Board fabs sell single-layer aluminum-core PCBs in 1.5 mm and
1.6 mm, and a keyboard plate is just an outline plus cutouts, so the plate can be ordered from
the same fab as the PCB for a fraction of laser-cut steel plus powder coat.  Cutouts are routed
to PCB tolerances (about +/-0.1 mm), the silkscreen side can carry key legends or assembly
marks, and every variant (9u or 6.25u spacebar, the enlarged screw-in stabilizer clearance,
mid-height vs full-height builds) is a parameter in the generator instead of a new CAD
export and a new quote.  The switch cutouts come from the same rev 2.3 positions the rev 3
schematic already uses, so plate and PCB cannot drift apart.  Points to settle:

- Thickness 1.5 mm so MX clips engage; confirm the fab offers 1.5 (most list 1.0, 1.2, 1.5,
  1.6, 2.0) and the size, about 395 x 126 mm, is within their aluminum panel limit.
- Aluminum is about a third as stiff as steel at the same thickness.  Fine in a flat 128,
  where the case supports the plate; in the printed 128D case the plate is the structural
  member, so add a stiffening rib or a second support ledge to the tray rather than going to a
  thicker plate that the switch clips cannot grip.
- The copper/solder-mask face goes up (legends, black or white mask); the bare aluminum face
  goes down.  Mounting holes are plain drills; the plate-ground strap becomes a pad.
- A plain FR4 two-layer board also works as a plate and is cheaper still, but flexes more; try
  aluminum first.
- The rev 2.3 steel plate stays available as the drawing of record until an aluminum plate
  has been built and fitted.

**Done (2026-09-18):** `pcb/tools/gen_plate.py` reads the outline and every cutout of the
original [`plate/plate.step`](https://codeberg.org/jflitton/the-c128-keyboard-project/src/branch/main/plate/plate.step) (extracted to `layout/plate.json`), places them in PCB coordinates (the 88 switch openings
land on the rev 2.3 switch centers with 0.06 mm RMS) and writes `pcb/plate/plate-9u.kicad_pcb`
and `plate-6.25u.kicad_pcb`, both DRC clean, Gerbers exportable.  The mounting features are
in `plate_features.json` for the layout and the bottom cover.  The Fusion model is no longer
needed for plate variants.

Still to do on the plate boards:

- Enlarge the stabilizer clearance cutouts enough to clear the screw-in housing shoulders,
  once a housing has been measured, so that on the Mitsumi-cap, mid-height-switch build the
  plate can sit 4 mm above the PCB and the per-switch shims go away (issue 4 in the background
  document).  The same geometry serves the 5 mm builds: full-height switches, or mid-height
  switches with MX caps, which still need the shim or shim sheet because molded caps cannot
  absorb the 1 mm the way the printed stabilizer adapters can.  Pair with 1 mm shorter 2u and
  spacebar stabilizer adapters (the originals are in
  [`printable_parts/`](https://codeberg.org/jflitton/the-c128-keyboard-project/src/branch/main/printable_parts) of the-c128-keyboard-project).
- Check the existing spacebar and 2u openings against a real screw-in stabilizer and widen
  where they were cut for plate-mount clips.
- Silkscreen legends, if wanted, on F.SilkS.

## Firmware

Lives in `firmware/`: an ESP-IDF project built in the `espressif/idf` container
(`docker-compose.yml` at the repo root, `make -C firmware build`), flashed with esptool from
the host.  Releases as a single merged binary plus an ESP Web Tools manifest so users flash
from a browser over the USB-C port.  `make -C firmware build-wokwi` produces a variant for
the Wokwi simulator (`firmware/wokwi/`): keys, lock buttons, RESTORE and the gate LEDs can be
exercised with no hardware, and the CH446Q control lines are captured on a logic analyzer.

**Feature order.**

1. Scan, debounce, mirror into the CH446Q.  Diodes on every key, so the scan is fully
   n-key: any chord reads correctly.  On the host side the firmware may choose not to close a
   fourth crosspoint that would complete a ghost rectangle in the C128's own matrix.
2. Virtual locks with NVS-backed state; restore on boot; 40/80 change strobes the keyboard
   green (40) or gray (80) and applies at the next reset, as on the BlingBox.
3. LED engine: pattern (0..11), pattern brightness (1..16), animation speed (1..10), key
   action (0..6), key-action brightness (1..16), global current cap, LED count.
4. Command layer on SHIFT LOCK held un-latched, BlingBox-compatible where the key exists:
   `S-LOCK+1..5` then `+`/`-` for the five LED selectors, `S-LOCK+I+1` types the settings
   dump, `S-LOCK+W` (3 s) starts the WiFi AP.  The C128D extended-key combos are dropped
   because this keyboard has the real keys.  Power-on `SHIFT LOCK+F1` factory reset,
   `SHIFT LOCK+D` diagnostic mode.
5. Macros: ten user slots (record with `S-LOCK+C=+digit`, play with `S-LOCK+L-SHIFT+digit`),
   system slots on `S-LOCK+CTRL+digit` starting with UNNEW.
6. WiFi AP + web page: everything above, per-key colors, key remap, backup/restore of
   settings as JSON.
7. **USB keyboard mode** for emulators and any other host that takes a USB keyboard; see the
   section below.  Detect the mode by whether `+5V_KB` is present.
8. **Network keyboard.**  Anything the ESP32 receives over WiFi can be typed into the 128
   through the crosspoint: paste a BASIC listing from a phone or PC, a remote keyboard page in
   the browser (a sysop console for a BBS machine), scripted key sequences from a PC.  Same
   PETSCII-to-matrix table and key pacing as macros: the KERNAL scans at 60 Hz with a
   ten-character buffer, so about 20 characters a second, held two scans and released one.
   Off by default; enabled by a physical action (the SHIFT LOCK + W combo), token-protected,
   local network or the board's own access point only.  RUN/STOP + RESTORE works remotely
   through Q3, so a hung machine can be recovered from the console.

### USB keyboard mode, for emulators

The board's second life: unplugged from a Commodore and plugged into a PC, it enumerates as a
USB HID keyboard.  The point is not typing e-mail on it; it is making C128 emulation feel
right.  Emulators map a PC keyboard onto the C128 matrix either symbolically (the PC's `:`
becomes the C128's `:`, and the shifted symbols end up wrong) or positionally (each PC key
stands in for the C128 key in roughly the same place, with the keys the PC lacks hanging off
F-keys and the keypad).  Neither is good, because the PC keyboard is the wrong shape.  A real
C128 keyboard that reports every key unambiguously fixes it at the source.

- **Positional mode (default when no `+5V_KB` is present).**  Every physical key sends its own
  USB usage code: standard usages where a PC has the same key (letters, digits, Return,
  Space, Tab, Esc, cursor keys, F1..F8, the keypad), and otherwise-unused usages (F13..F24,
  the International and Language keys) for the keys a PC does not have: C=, RUN/STOP,
  RESTORE, CLR/HOME, INST/DEL, 40/80, NO SCROLL, LINE FEED, HELP, the pound key, left arrow,
  up arrow, SHIFT LOCK, CAPS LOCK.  Left and right SHIFT are reported separately, as the C128
  needs.  Lock keys report press and release like any key; the emulator keeps the state.
- **A VICE keymap ships with the firmware** (`firmware/host/vice/`): a positional `.vkm` for
  x128 and one for x64 that map each of those usages to its exact matrix row and column,
  plus the entries VICE has for the C128's 40/80, CAPS LOCK and RESTORE keys.  Load it once in
  VICE and every key does what its legend says, shifted symbols included.  Other emulators
  that accept custom scan-code maps get the same table in their format as people ask.
- **PC mode (SHIFT LOCK + P, saved).**  Symbolic mapping for using the keyboard as an ordinary
  PC keyboard: C= as a GUI/Alt key, RUN/STOP as Escape, and so on.  Convenience only.
- **Circuit consequences,** both on the schematic: the per-key diodes so any chord reads (a
  PC expects that; the C128 never did), and D3, a diode from the ESP32's RESTORE sense pin to
  the RESTORE line, replacing the earlier resistor divider.  With no Commodore attached the
  RESTORE line has no pull-up and a divider would float; the diode with the pin's internal
  pull-up reads the key either way and never puts 5 V on the pin.

**Settings stored in NVS.**  Lock states, the five LED selectors, current cap, LED count,
per-key colors, keymap, macros, WiFi credentials.  Written on change with a short debounce.

## Assembly

Decision: **every SMD part is placed by the board fab** (JLCPCB or equivalent); the builder
solders only through-hole parts: switches, connectors and headers.  Consequences for the design:

- **Two assembly sides.**  LEDs are on the front (they must sit in the switch pockets), the
  MCU module, crosspoint, buffers, power and USB-C are on the back.  Order double-sided SMT.
  Keep every other SMD part off the front so the front side is LEDs only.
- **Fab-stocked parts first.**  0603 passives, SS34, 2N7002, USBLC6-2SC6 and the
  AP7361C-33E are basic or common stock items and carry their LCSC numbers in the schematic's
  `LCSC` field (verify each on the LCSC site before ordering).  The ESP32-S3-MINI-1U-N8,
  SK6812 MINI, CH446Q, 74HC154 and 74AHCT1G125 are stocked in some package; pick the
  stocked package at layout time and fill the field in.  The 220 uF electrolytic, the polyfuse
  and the USB-C receptacle likewise.  **Done 2026-11-22**: every SMD part has an in-stock
  number (the list and two substitutions are in `pcb/README.md`, *Part numbers for fab
  assembly*).
- **CH446Q.**  A WCH part, so LCSC stocks it; confirm the part number and that it is not a
  minimum-order extended part.  LQFP-44 at 0.8 mm pitch is fine for the fab and workable by
  hand with flux if a board ever needs a replacement.
- **Board size.**  About 395 x 126 mm.  Check the fab's assembly panel limit (JLCPCB quotes a
  maximum around 400 x 500 mm for assembly) before layout, and keep 5 mm of clear rail along
  the long edges for their fixtures if they ask for it.
- **Fiducials and tooling holes** on both sides, three per side, outside the plate footprint.
  Not added: JLCPCB quoted the board without them; confirm at their order review.
- **Panelisation is not worth it** at this size; order as single boards.
- The plate is a separate, unassembled aluminum order from the same fab.

## BOM delta (rough)

| Item | Qty | Approx. cost |
|---|---|---|
| ESP32-S3-MINI-1U-N8, U.FL antenna | 1 | 4 |
| CH446Q LQFP-44 | 1 | 1-2 |
| SK6812 MINI | 92 | 11 |
| 74HC154, 74AHCT1G125, AP7361C-33E | 3 | 2 |
| USB-C receptacle, ESD, Schottky x2, PTC, 2N7002 x3, tacts x2, 2 x 13 IDC header (optional) | ~12 | 3 |
| 1N4148W SOD-123 | 91 | 1 |
| Passives | ~120 | 3 |
| **Total added** | | **~22 USD** |

The rev 2.3 parts that go away (three MAX16054, the 1G66, six passives) are about 10 USD.
All SMD goes on at the fab (see Assembly); the hand-build path is through-hole only.

## Bench proofs before layout

1. **Reset window.**  Scope +5 V and the 40/80 line on a flat 128 and a 128D: when does the
   KERNAL sample it?  Confirms the default-assert FET is needed (assumed yes).
2. **Light path.**  Mostly answered already: on the rev 2.3 board the three lock-key LEDs are
   through-hole parts and they do shine through the Outemu mid-height switches, though the
   housings had to be trimmed for the 5 mm leads and dome.  The housings are made for a
   3528-size SMD LED in the bottom-housing pocket, so a top-mount SK6812 MINI (3.5 x 3.5 mm)
   on the front of the board sits where the switch expects it, no trimming and no cutout.
   Remaining check: one MINI glued to a bare rev 2.3 board under one switch position, an
   untrimmed mid-height switch over it, to confirm the pocket clears the part and how much
   light reaches a Mitsumi cap on its adapter.
3. **CH446Q on a live C128.**  A CH446Q on an LQFP-44 adapter between a rev 2.3 board and a
   128: on-resistance and levels against the CIA scan (datasheet says 120 to 185 ohm at 5 V),
   no ghosting regressions versus stock, SHIFT/CTRL/C= chords, and clean serial-mode control
   at 3.3 V (datasheet VIH 2.0 V at a 5 V supply).
4. **Power.**  Current on the keyboard header at each brightness step with the limiter on;
   ESP32 WiFi bursts on the keyboard rail alone; does the flat's PSU care?
5. **ESP32 boot time** to first matrix scan, so a key held at power-on (diagnostic mode,
   factory reset) behaves predictably.
6. **Cable.**  Build one flat cable (0.05" ribbon soldered into a rev 2.3-sized scrap
   footprint at one end, split into kk pins in the printed 1 x 25 housing at the other) and
   one 128D cable (IDC header to IDC DB25) from the pinout table, and meter every pin against
   the stock order before either meets a mainboard.  Check that the IDC DB25's mounting
   flange fits the printed case's rear cutout so it can double as the panel connector.

## Work breakdown

1. Bench proofs 1 to 6 above.  Any failure changes the plan, so they go first.  Proofs 1
   and 4 and several fit measurements need no new parts: see
   [pcb/bench/before-parts-arrive.md](../pcb/bench/before-parts-arrive.md).
2. Schematic in KiCad 10: new sheets for MCU/power, crosspoint, LEDs, connector; matrix sheet
   reworked to physical + host nets.  **Drafted**: see [pcb/](../pcb/README.md),
   ERC clean; the bench rig and shopping list are in
   [pcb/bench/README.md](../pcb/bench/README.md).
3. Layout: footprint changes, re-route, DRC clean; kibot outputs.  **Done 2026-11-23**:
   routed and DRC clean; the fab outputs come from `pcb/tools/fab.py` instead of kibot.
4. Plate as an aluminum PCB: **done** (both spacebar variants generated, DRC clean, and a
   dual plate with slots for both spacebars' stabilizers, the one to order); the
   stabilizer-clearance change remains.  The bottom cover is a taped liner (`pcb/liner/`), die cut or cut by hand.
5. Firmware milestones 1 and 2 on a devkit wired to a rev 2.3 board through the breadboarded
   crosspoint, so bring-up of the first rev 3 board is just hardware.  **Started**: the
   ESP-IDF project in [firmware/](../firmware/README.md) has the scan, crosspoint mirror,
   saved lock keys, RESTORE sense/press, the LED engine (milestone 3: twelve patterns, seven
   key actions, lock indicators, the 40/80 strobe and a current cap, host-tested) and a
   console; it builds in the `idf` container
   (`make -C firmware build`) and flashes from the host.
6. Order boards: two unlit hand builds, one assembled lit board.  **Ready** (2026-11-23):
   five assembled boards quoted at about 500 USD shipped, plus about 50 USD for the plate;
   not ordered yet.
7. Bring-up, then firmware milestones 3 to 8.
8. VICE positional keymaps for x128 and x64, tested against the shifted-symbol keys.
9. README: rev 3 configuration table, flashing instructions, command reference page modeled
   on the BlingBox card, mark the adapter project as rev 2.x only.

## Open questions

- ~~Regulator headroom.~~  Decided 2026-09-21: the 128's keyboard connector measured 4.9 V,
  so `+5V_SYS` is about 4.55 V after the OR-ing diode.  The AMS1117-3.3 would have had
  roughly 0.1 V of margin during a WiFi burst; U2 is now the AP7361C-33E (1 A, 0.36 V
  dropout at 1 A, stable on ceramic capacitors, LCSC C500795, same SOT-223 footprint), which
  leaves over 1 V.  A switching regulator was considered and rejected: the ESP32's average
  draw wastes only about a quarter of a watt in a linear part, and a buck adds parts, layout
  rules and switching noise next to the antenna.  If a machine ever measures under 4.7 V, the
  next lever is a P-FET ideal diode in place of D1.
- ~~Underside height budget.~~  Measured 2026-11-21: about 17 mm under the PCB at the rear,
  about 2 mm at the front; see *Layout changes*.  The layout keeps every part taller than the
  switch pins in the rear band (y < 113); the cover stops before the last two rows.
- Which system macros beyond UNNEW the community wants.
- ~~A RESTORE driver?~~  Decided 2026-09-19: added as Q3/R12 on IO13.
