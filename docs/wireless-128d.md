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

## On the Commodore

None of this is used on a wired build.  The keyboard runs from J2's +5V_KB as now, and its
USB-C still works for flashing.

## Open questions

- Which charger and boost: a power-path charger with a separate boost, or an all-in-one
  power-bank chip.  Compare their current limits, quiescent draw and JLCPCB stock.
- Whether to use the J4 link at all, or start with a fixed wireless-mode LED limit.
- The dongle's housing on the DB25, and whether it needs a pairing button.
