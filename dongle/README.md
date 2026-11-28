# C128D wireless dongle

A small board that plugs into the 128D's keyboard socket (on the computer's right side) and
passes the keyboard straight through.  An ESP32-S3 on it drives a CH446Q crosspoint on the
host lines, so keys can come from the rev 3 keyboard over the radio, from an app on a Mac
(USB-C), or from a USB keyboard (USB-A).  The plan and every decision behind it are in
[docs/wireless-128d.md](../docs/wireless-128d.md).

Status (2026-11-27): **schematic generated and ERC-clean; footprints drawn; board placed and
routed (autorouted, the USB nets at J1 and U5 finished by hand); DRC clean and matching the
schematic; firmware not started.**

## Files

| File | What |
|---|---|
| `pcb/tools/gen_sch.py` | writes the schematic: `c128-dongle.kicad_sch`, `mcu.kicad_sch`, `host.kicad_sch`, the project symbol library and both library tables |
| `pcb/c128-dongle.kicad_sch` | root sheet |
| `pcb/mcu.kicad_sch` | ESP32-S3-MINI-1, USB-C and USB-A behind the CH442E switch, the SY6280AAC USB-A power switch, the 5 V entry and the 3.3 V LDO, status LED, buttons, UART pads |
| `pcb/host.kicad_sch` | the keyboard's crosspoint circuit (CH446Q, lock-line and RESTORE FETs, sense diode, LED buffer) and the two DB25s |
| `pcb/c128rev3.kicad_sym`, `pcb/sym-lib-table` | project symbols: CH446Q, CH442E, SY6280AAC |
| `pcb/fp-lib-table` | the keyboard's footprint library (for the USB-C) and `dongle.pretty` |
| `pcb/tools/gen_board.py` | writes `c128-dongle.kicad_pro` and `.kicad_dru` from the keyboard's (same rules, the dongle's sheets and power nets), and once the 65 x 45 mm 4-layer board with its outline; it will not overwrite the board |
| `pcb/c128-dongle.kicad_pro`, `.kicad_dru`, `.kicad_pcb` | the project, its J1 USB-C rule, and the board (hand-edited from here: F8 brings the parts in) |
| `pcb/tools/gen_fp.py` | writes the two edge-straddle DB25 footprints into `dongle.pretty` |
| `pcb/dongle.pretty/` | the USB-A (JLCPCB's own C8328 footprint, via easyeda2kicad 1.0.1, checked against the datasheet; peg holes made non-plated, shell pads named SH) and the two DB25s (from `gen_fp.py`) |

## The schematic is generated

```
docker compose run --rm -e KICAD_SYMBOLS=/usr/share/kicad/symbols kicad python3 dongle/pcb/tools/gen_sch.py
```

Change the script, not the sheets: every run rewrites them.  The host side is not copied from
the keyboard but called: the script imports `pcb/tools/gen_sch.py` and runs its
`crosspoint_core()`, so the CH446Q, the FETs, the sense diode and the LED buffer are the same
parts, references and nets on both boards, on the same ESP32 pins.  The two DB25s take their
pin assignment from the keyboard's `HOST_PINS` table, converted to D-sub numbering.

## The DB25 footprints

`docker compose run --rm kicad python3 dongle/pcb/tools/gen_fp.py` writes both, from FCI drawing
C-DSUB-0064 (`pcb/datasheets/FCI-C-DSUB-0064.pdf`), size 25: 2.76 mm pitch, 2.84 mm between the
cup rows (a 1.6 mm board fits between them), cups about 7.4 mm behind the insulator.

- Pins 1-13 on F.Cu, pins 14-25 on B.Cu, offset half a pitch; pads 1.5 x 4.5 mm from 0.4 mm
  inside the board edge (y = 0 in the footprint; the connector hangs off at y < 0).
- Seen from the solder side with the 13-pin row on top, a plug has pin 1 on the right and a
  socket on the left, so `DB25_Pins_*` (J2) has pin 1 at +x and `DB25_Socket_*` (J3) at -x.
- The D shell goes in one way only, so the 128D's socket decides which way up the dongle
  sits: with its 13-pin row at the top, the dongle's F.Cu face is up.
- Fab: insulator, flange with its jackscrew holes (47.04 mm apart) and the D shell; a dashed
  line on Dwgs.User marks the board edge.

## The board

- **Outline:** 65 x 45 mm (widened from 60 on 2026-11-27 for room round U5 and the USB-C pair), 1 mm corners; DB25s on the west and east edges, USB on the north,
  the ESP32's antenna over the south edge (`gen_board.py`).
- **Stackup:** F.Cu signals and ICs; In1.Cu a solid GND plane; In2.Cu a third signal layer;
  B.Cu signals and the discretes.  +3V3 runs as 0.5 mm tracks.  With In2 as a +3V3 plane
  instead, the 25 straight-through DB25 lines and the CH446Q's 19 left 21-28 nets that would
  not route on two signal layers; with three, only the USB nets at J1 and the CH442E were left
  (the USB-C's A/B crossing is hand-routed, as on the keyboard).
- **Placement:** the connectors, the ESP32, the buttons and the status LED placed by hand and
  locked; the rest by KiCadRoutingTools' placer (`krt` container) with ICs on top and the
  resistors, capacitors, transistors and diodes underneath at 0 or 90 degrees, each IC's
  decaps under it.  Seed 0 of 12 (second round, `build/placement-dongle/round2/`, not
  committed), judged by a quick route; Q2 then moved clear of J3's courtyard, which the
  placer's legality check missed.
- **Silkscreen:** `docker compose run --rm kicad python3 pcb/tools/silk.py
  dongle/pcb/c128-dongle.kicad_pcb` (the keyboard's tool) moved the references DRC flagged,
  put TP2's, R1's and LED1's pin-1 mark on the fab layer (no clear spot near them), and trimmed
  J4's flange and U1's antenna outline where they run past the board edge, and J4's lines over
  its shield pads.  So J4 no longer matches its library copy (a DRC warning): don't update it
  from the library, or rerun `silk.py` after.
- **In1 is the plane only:** after hand routing, check nothing landed on In1 and no via is
  blind (both happened once).  GND is in the Power class, 0.5 mm: pick 0.25 mm before routing
  from U5's 0.35 mm GND pads, or the router won't start.
- **Connector clearances:** J4 (USB-A) at x 123 and J1 (USB-C) at x 146 leave 8.3 and 3.3 mm
  to the DB25 pad strips; the buttons are turned 90 degrees for 3.6 mm.  J4's EasyEDA courtyard
  did not cover its shell tabs and was widened.

## Ordering

```
docker compose run --rm -e KICAD_CLI=kicad-cli kicad python3 pcb/tools/fab.py dongle/pcb/c128-dongle.kicad_pcb
```

writes `dongle/pcb/fab/` (untracked): the gerbers zip, BOM and CPL, as for the keyboard (see
`pcb/README.md`).  J2 and J3, the DB25s, are left to the builder.  Order a 4-layer board with
assembly on both sides.  Rotations were checked in JLCPCB's placement preview on 2026-11-27: the
bottom side as written, the top with the corrections in `fab.py`'s `ROT_ADD_TOP` (U2-U8).
U3's and U5's turn ("right 90" in the preview, taken as clockwise) is still to be confirmed on
the next upload.  Quoted that day for five: about 175 USD for boards and assembly, plus 127 USD
shipping and tariffs; to be ordered with the keyboard's next order to share the shipping.

## Parts this board adds

LCSC numbers are in the script; check each on lcsc.com before ordering.

| Part | LCSC | Datasheet checked |
|---|---|---|
| ESP32-S3-MINI-1-N8 (PCB antenna) | C2913206 | |
| WCH CH442E, USB 2.0 2:1 switch | C150097 | `pcb/datasheets/C150097.pdf` (WCH CH440/CH442 v3B): pins, select polarity, runs at 3.3 V |
| Silergy SY6280AAC, USB-A power switch | C55136 | `pcb/datasheets/C55136.pdf` (preliminary rev 0.3): pins, Ilim = 6800 / Rset, EN active high |
| USB-A receptacle, right angle (Jing Extension 904-131A2032S10100) | C8328 | `pcb/datasheets/C8328.pdf`: pins, outline, PCB layout (signal-pad width not dimensioned) |
| UNI-ROYAL 12 k, 0603, 1 % (the SY6280's Rset, about 0.57 A) | C22790 | `pcb/datasheets/C22790.pdf` (series sheet); value from the LCSC page |
| DB25 male and female, solder cup | none | hand-soldered; straddle 1.6 mm board edges |

## Still open

- **Power:** the 128D's +5 V on the keyboard socket feeds the dongle, with the ESP32's radio
  peaks and a USB keyboard on top of the keyboard's own draw.  Measure what the 128D's
  keyboard 5 V delivers before relying on it without the USB-C.
- **Routing:** KiCadRoutingTools' router (`krt`): `route_diff.py` for the three USB pairs, then
  `route.py` on F.Cu, In2 and B.Cu at the board's rules (`--escalation board
  --no-fix-drc-settings`).  It cannot do the USB-C pair at J1 legally: J1's D+/D- pads are 0.3 mm
  wide, and the pair pass drops a 0.3/0.15 mm via into the pad to change layers (its own log calls
  it an advanced-tier fab floor), so that pair is hand-routed, with the A6/B6 and A7/B7 crossing.
  U5 sits between the USB-A and the USB-C, just in from the north edge (139, 83), where its
  lines to both ports are shortest.  The USB-C pair's layer change beside J1, its A7/B7 crossing
  and the last stubs into U5 were routed by hand.
- **Firmware:** the dongle app, sharing the keyboard firmware's crosspoint driver.
