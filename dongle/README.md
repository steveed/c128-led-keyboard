# C128D wireless dongle

A small board that plugs into the 128D's keyboard socket (on the computer's right side) and
passes the keyboard straight through.  An ESP32-S3 on it drives a CH446Q crosspoint on the
host lines, so keys can come from the rev 3 keyboard over the radio, from an app on a Mac
(USB-C), or from a USB keyboard (USB-A).  The plan and every decision behind it are in
[docs/wireless-128d.md](../docs/wireless-128d.md).

Status (2026-11-27): **schematic generated and ERC-clean; footprints drawn; board and firmware
not started.**

## Files

| File | What |
|---|---|
| `pcb/tools/gen_sch.py` | writes the schematic: `c128-dongle.kicad_sch`, `mcu.kicad_sch`, `host.kicad_sch`, the project symbol library and both library tables |
| `pcb/c128-dongle.kicad_sch` | root sheet |
| `pcb/mcu.kicad_sch` | ESP32-S3-MINI-1, USB-C and USB-A behind the CH442E switch, the SY6280AAC USB-A power switch, the 5 V entry and the 3.3 V LDO, status LED, buttons, UART pads |
| `pcb/host.kicad_sch` | the keyboard's crosspoint circuit (CH446Q, lock-line and RESTORE FETs, sense diode, LED buffer) and the two DB25s |
| `pcb/c128rev3.kicad_sym`, `pcb/sym-lib-table` | project symbols: CH446Q, CH442E, SY6280AAC |
| `pcb/fp-lib-table` | the keyboard's footprint library (for the USB-C) and `dongle.pretty` |
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
- **Board:** the outline (at least 41 mm across the DB25 edges) and
  placement.
- **Firmware:** the dongle app, sharing the keyboard firmware's crosspoint driver.
