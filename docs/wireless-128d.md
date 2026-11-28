# Wireless 128D / DCR: dongle and battery board (idea, not designed)

A way to use the rev 3 keyboard with a 128D or 128DCR without the cable.  Nothing here is
drawn yet.  The rule that shapes it: **the keyboard board stays the same**.  Every build, flat
or 128D, wired or wireless, uses the one PCB; the wireless parts live in a dongle and in a
battery board that is part of the case.

## The three parts

| Part | What it is | Power |
|---|---|---|
| Keyboard | the rev 3 board, unchanged; new firmware only | 5 V into its USB-C (J1) from the battery board |
| Dongle | plugs into the 128D's front DB25 keyboard port: an ESP32 (a C3 is enough) and a copy of the rev 3 crosspoint sheet (CH446Q, the RESTORE and lock-line FETs, 3.3 V regulator) | the computer's +5 V on the DB25 |
| Battery board | in the case: a LiPo, a power-path charger, a 5 V boost, two USB-C ports | its cell, or USB when plugged in |

## Why a dongle works

The 128D scans its keyboard by driving the matrix lines and reading them back.  The CH446Q
answers that scan by closing analog switches between lines, and holds that state on its own,
so the keyboard only has to send "these keys are down" when something changes.  The dongle
copies that into its own CH446Q.  A few milliseconds of radio delay is far shorter than the
time between the computer's scans.

**Link: ESP-NOW,** not Bluetooth.  No pairing stack, about 1-2 ms delivery, simple retries.

- Each change of key state carries a sequence number.
- A full-state resend goes out every few hundred milliseconds, so a lost packet cannot leave a
  key stuck down.
- If the link goes quiet, the dongle releases every key.
- RESTORE, CAPS LOCK and 40/80 are sent as state like any other key; the dongle drives those
  lines with its FETs, as the keyboard does today.

What a wireless build gives up: the dongle powers up on its own, after the computer, and
there is no hard guarantee of zero latency.  Typing will not notice; joystick-style games on
the keyboard are worth a test.

## Battery board

Feeding the keyboard through its own USB-C keeps the keyboard unchanged and keeps USB data
for flashing.  The board has two USB-C ports.

### Port 1: on the outside of the case (charge and data in)

- **CC:** 5.1 k pull-downs (Rd), like the keyboard's R3 and R4, so a charger or PC supplies power.
- **VBUS:** into a **power-path charger**, not a plain charger.  With USB plugged in it runs
  the keyboard straight from USB and charges the cell with what is left; unplugged, the boost
  converter takes over with no gap.  Without power path the keyboard either shuts off or fights
  the charger while charging.  TI's BQ24074 and Microchip's MCP73871 are chips of this kind;
  check the chosen part's current limits against the LED load.
- **D+/D-:** straight through to port 2.  Full-speed USB (12 Mbps) is fine through two
  connectors and a short cable, so the one outside port does everything: charging, flashing
  the ESP32, USB keyboard mode and the console.

### Port 2: inside the case (power out to the keyboard's J1)

- **CC:** pull-ups (Rp), so this port is a source; the keyboard's 5.1 k pull-downs already make
  it a proper sink.
- **VBUS:** the power-path output, boosted to 5 V on battery, about 2 A for the LED peaks.  It
  enters the keyboard through D2, as USB power does today.
- **Cable:** a short USB-C to USB-C cable, or a right-angle plug if the two boards sit close.

### Other connections and settings

- **J4 link (optional):** J4 (UART TX, RX, GND) can carry two messages.  The battery board
  reports its charge level, so the firmware can show it and warn when low.  The keyboard asks
  to be turned off after a long idle, and a power button on the case turns it back on.  J4 is
  the development console otherwise; the finished keyboard does not need it.
- **LED current on battery:** the firmware's LED current cap should come down on battery,
  whatever the boost is rated for.  The firmware cannot see the source by itself; the J4 link
  or a lower LED setting in wireless mode covers it.
- **Idle drain:** the LED power switch (`docs/led-power-switch.md`) cuts the ~90 mA the dark
  LEDs draw, which leaves the ESP32 and its radio.  Roughly, with the LEDs off a 5000 mAh cell
  lasts several days of normal use; with the LEDs lit at a modest level, 6-10 hours.
- **Space:** the printed 128D case has about 31 mm of height at the rear, which fits a flat
  5000 mAh or larger pack.

## Dongle hardware

The user's direction (2026-11-27): a straight solder-cup DB25 straddles fingers on each end
of the board, so the dongle passes the keyboard through; USB-C on one side, status LEDs on the
other, and a 3D-printed clamshell snapped over the whole board.

```
            north: USB-C
        +-------------------+
 west   |                   |   east
 DB25 ==|  ESP32   CH446Q   |== DB25
 to the |                   |   for the
 128D   |                   |   keyboard
        +-------------------+
            south: status LEDs, antenna corner
```

### The board

- **Size:** at least about 41 mm north to south, so each DB25 body fits along its edge (the
  flanges, about 53 mm, overhang outside the board).  East to west is free; about 50-60 mm
  leaves room for the ESP32, the CH446Q and the routing.
- **Straddle mounts:** at each end the board's edge slides between the connector's two rows of
  solder cups: 13 pads on one side (pins 1-13) and 12 on the other (pins 14-25), at the
  DB25's 2.77 mm pitch, the rows offset by half a pitch, each cup soldered flat to its pad.
  The gap between the cup rows sets the board thickness; 1.6 mm is common, but check the
  chosen connector's drawing.
- **West DB25:** to the computer, the opposite gender to the 128D's own keyboard socket.
- **East DB25:** for the keyboard cable, the same gender as the 128D's socket, so a keyboard
  plugs into the dongle exactly as it would into the computer.  Check both genders on the
  machine before ordering.
- **Pass-through:** all 25 pins straight through between the two connectors, +5 V and GND
  included, so a wired keyboard is powered as normal.  The CH446Q taps the same matrix lines
  in parallel, the way the rev 3 board's crosspoint sits on the host lines.
- **Pin numbering:** a plug and a socket number their pins as mirror images.  Work out which
  side of the board carries each connector's 1-13 row before routing, so the 25 through-lines
  need no via each.

### North and south

- **USB-C on the north edge,** for the app and for flashing.  Its 5 V joins the DB25's +5 V
  through diodes, as the keyboard's D1 and D2 do.
- **Status LEDs on the south edge:** side-firing (right-angle) LEDs at the board edge, seen
  through the shell; or one SK6812 (the keyboard's part) behind a small light pipe, showing
  power, link and key activity in colour.
- **Antenna:** with metal D-sub shells at both ends and the USB-C north, the clearest spot is
  the south edge.  Use a module with a PCB antenna (for example the ESP32-C3-MINI-1), its
  antenna end at a south corner away from the LEDs, copper kept clear under it.

### Clamshell

- **Fit:** two printed halves snap together over the whole board, with slots that capture
  the DB25 flanges, so the flanges take the plugging force, not the solder joints.
- **Retention:** the flanges' 4-40 holes take jackscrews or hex standoffs, so the dongle can
  screw to the computer and the keyboard cable can screw to the dongle.
- **Openings:** a cut-out for the USB-C on the north side, and windows or light pipes for the
  LEDs on the south side.  Plastic is fine for the radio.

## The dongle on its own

The dongle does not care where key states come from: the C128 only sees switches closing
between its matrix lines.  So anything that can tell the dongle's ESP32 "these keys are down"
can type on the computer: the keyboard over ESP-NOW, or an app on a Mac or PC.

### How an app talks to it

- **USB serial:** the simplest.  The ESP32 shows up as a serial port, and the app sends
  commands such as `type 10 PRINT "HI"`, `press RETURN` or `hold SHIFT`.  The ESP32-C3 has USB
  built in, so no extra chip is needed.
- **Wi-Fi:** a small TCP or WebSocket server on the ESP32, so the app works across the room
  with only the C128 powering the dongle.
- **A USB keyboard plugged straight in:** with an ESP32-S3 instead of a C3, its USB can act as
  a host and read a USB keyboard directly, with no computer involved.  This is the main reason
  to pick the S3 over the C3.

### What it is good for

- Pasting text: BASIC listings, or long commands typed from a file.
- A Mac's or PC's keyboard as the C128's keyboard: the app forwards key presses.
- Scripting: automated tests of software, reproducible key sequences, demos.
- Controls the C128's own keyboard lacks: RESTORE, CAPS LOCK and 40/80 are lines the dongle
  drives, so the app can set them too.

### Limits

- **Typing speed:** the KERNAL reads the keyboard once per 60 Hz tick and buffers only 10
  characters.  A paste has to hold each key for about two ticks and release between repeated
  letters, so it types at about 15-25 characters a second at most.  Programs that read the
  matrix themselves (most games) see key presses directly.
- **Character mapping:** PETSCII becomes matrix keys plus SHIFT or C= combinations, including
  the graphics characters.  The rev 3 firmware's key map (`firmware/tools/gen_keymap.py`)
  already has the C128's matrix.
- **Power:** a dongle on USB and on the DB25 at once joins the two 5 V supplies through
  diodes, as the keyboard's D1 and D2 do.

### With a real keyboard as well

The C128's matrix is wired together, so the dongle's switches and a real keyboard's switches
can sit on the same lines at once.

- **On a 128D:** the dongle's east DB25 passes the keyboard through, so the normal keyboard
  plugs in behind it.
- **On a flat C128:** the same circuit can sit on a small board at the internal keyboard
  header, alongside the stock keyboard.

Two keys pressed at once from the two sources can ghost, just as three keys on one keyboard
can.

### Firmware

Mostly the rev 3 firmware's CH446Q driver and crosspoint map, plus a command parser for the
app and the ESP-NOW receiver for the keyboard.

## On the Commodore

None of this is used on a wired build.  The keyboard runs from J2's +5V_KB as now, and its
USB-C still works for flashing.

## Open questions

- Which charger and boost: a power-path charger with a separate boost, or an all-in-one
  power-bank chip.  Compare their current limits, quiescent draw and JLCPCB stock.
- Whether to use the J4 link at all, or start with a fixed wireless-mode LED limit.
- The dongle's housing on the DB25, and whether it needs a pairing button.
- ESP32-C3 or S3 for the dongle: the S3 can host a USB keyboard directly.
- The solder-cup connectors: their cup gap (board thickness) and the two genders.
- Status LEDs: side-firing LEDs or one SK6812 behind a light pipe.
