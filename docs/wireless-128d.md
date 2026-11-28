# Wireless 128D / DCR: dongle and battery board (idea, not designed)

A way to use the rev 3 keyboard with a 128D or 128DCR without the cable.  Nothing here is
drawn yet.  The rule that shapes it: **the keyboard board stays the same**.  Every build, flat
or 128D, wired or wireless, uses the one PCB; the wireless parts live in a dongle and in a
battery board that is part of the case.

## The three parts

| Part | What it is | Power |
|---|---|---|
| Keyboard | the rev 3 board, unchanged; new firmware only | 5 V into its USB-C (J1) from the battery board |
| Dongle | plugs into the 128D's front DB25 keyboard port: an ESP32-S3 and a copy of the rev 3 crosspoint sheet (CH446Q, the RESTORE and lock-line FETs, 3.3 V regulator) | the computer's +5 V on the DB25 |
| Battery board | in the keyboard's case: a LiPo, a power-path charger, a 5 V boost, two USB-C ports | its cell, or USB when plugged in |

The dongle and the battery board are separate boards that know nothing of each other.  The
dongle is powered by the 128D (or its own USB-C); the battery board only ever feeds the
keyboard.  The radio link between the keyboard and the dongle is all they share, and either
can be built without the other: a dongle with a wired keyboard, or a battery keyboard with a
dongle on a second 128D.

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

### Basics: one cell and a boost

- **Boost, not buck.**  One lithium cell (a LiPo pouch or an 18650) sits between 4.2 V full and
  about 3.0 V empty, always below the keyboard's 5 V, so the board needs a boost converter
  (steps up), not a buck (steps down).  Two cells in series (7.4 V) would take a buck, but
  charging them from USB needs a balancing charger and a boost of its own.  One cell and a
  boost is the standard way.
- **Rough currents:** a boost is about 90 % efficient, so 1 A out at 5 V draws about 1.5 A from
  a 3.7 V cell.

### Safety rules for one lithium cell

- **Charge with a proper charger chip:** constant current, then constant voltage, stopping at
  exactly 4.2 V.  Never connect 5 V straight to a cell.
- **Charge current at or below the cell's rating,** usually 0.5-1 times its capacity (0.5-1 C):
  1 A is gentle for a 5000 mAh pack.
- **Cells with a built-in protection board.**  Most pouch cells sold with wires have one: it
  cuts the cell off on overcharge, over-discharge, overcurrent and short circuit.
- **Temperature:** no charging below about 0 C or above about 45 C.  Better chargers read a
  thermistor on the pack.
- **Mechanics:** a pouch cell must not be punctured, crushed or squeezed, and needs a little
  room to swell with age.  A printed tray with soft padding is the usual fix.
- **Connector polarity:** JST-PH battery plugs are wired with opposite polarity by different
  sellers.  Check every pack with a meter before plugging it in.

### Step 1: measure

Before choosing the cell or the boost, run the keyboard from USB through an in-line USB power
meter (a USB-A to USB-C type with a current display, about 15 USD) and note its draw with the
LEDs off and idle, while typing, and with the LEDs at a usual brightness.  Those numbers set the
battery size and the boost rating, and show whether a low-load auto-off (below) would bite.

### Step 2: test with an off-the-shelf module

**Adafruit PowerBoost 1000C** (Adafruit product 2465, about 20 USD; stocked by Jameco and The
Pi Hut, among others, when checked on 2026-11-27).  It is built the way the final board is: a
Microchip MCP73871 power-path charger feeding a TI TPS61090 5 V boost.  It switches to USB power
whenever USB is plugged in, so the keyboard runs from a charging pack.

- **Output:** a USB-A socket at 5 V, about 1 A continuous, into the keyboard's J1 with an
  ordinary USB-A to USB-C cable.  Charging is from its micro-USB input, up to 1.8 A.
- **Limits:** 1 A rather than 2 A, so set the firmware's LED current cap to about 600-700 mA
  while testing on it.  No USB data pass-through: flash the keyboard by plugging it into the Mac
  directly.  Keep the cell connected: it absorbs the load spikes.
- **Cell:** a protected LiPo with a JST-PH plug of Adafruit's polarity (Adafruit's own packs are
  the safe choice; check any other with a meter), about 2500 mAh for tests.
- **Other candidates found:** Pimoroni's MP2636 module (2.5 A charge and boost, but whether it
  powers the load while charging needs checking in its datasheet); Adafruit's bq25185 board
  (power path, but 1 A out and a 6-hour charge timer); SparkFun's boards (600 mA, or no power
  path).
- **The catch with cheap modules and power banks:** many switch themselves off when the load
  falls below roughly 50-100 mA, which a keyboard with its LEDs off can.  The PowerBoost 1000C
  does not do this.

### Step 3: the final board

A power-path charger and a separate 5 V boost, as on the PowerBoost 1000C, with the two USB-C
ports below.  Candidates: TI's BQ24074 or Microchip's MCP73871 for the charger, and a boost
such as TI's TPS61023 or TPS61088, sized from the step 1 numbers.  An all-in-one power-bank
chip (Injoinic's IP5306, as in M5Stack devices) is cheaper and smaller, but has the low-load
auto-off to work around.

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

- **J4 stays available (decided 2026-11-27).**  The keyboard's 3-pin UART header (TX, RX,
  GND) is already on the board and is left as it is.  A battery board can use it later for two
  messages: the battery board reports its charge level, so the firmware can show it and warn
  when low; and the keyboard asks to be turned off after a long idle, with a power button on
  the case to turn it back on.  Until then J4 is the development console.  No keyboard change
  is needed either way.
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
            north: USB-C, USB-A
        +-------------------+
 west   |                   |   east
 DB25 ==|  ESP32   CH446Q   |== DB25
 to the |                   |   for the
 128D   |                   |   keyboard
        +-------------------+
            south: status light pipe, antenna corner
```

### How it sits on the 128D

The 128D's keyboard socket is on the computer's right side, about halfway back (the user,
2026-11-27).  The dongle plugs in sideways, like an extension of the socket: the west DB25 in
the computer's side, the east DB25 facing out to the right for the keyboard cable, and the
north edge toward the computer's rear.  So the USB cables run straight back alongside the case,
clear of everything, and the status light on the south edge faces the front, where it can be
seen.

### The board

- **Size:** at least about 41 mm north to south, so each DB25 body fits along its edge (the
  flanges, about 53 mm, overhang outside the board).  East to west is free; about 50-60 mm
  leaves room for the ESP32, the CH446Q and the routing.
- **Straddle mounts:** at each end the board's edge slides between the connector's two rows of
  solder cups: 13 pads on one side (pins 1-13) and 12 on the other (pins 14-25), at the
  DB25's 2.77 mm pitch, the rows offset by half a pitch, each cup soldered flat to its pad.
- **Board thickness: 1.6 mm,** which fits between the cup rows (confirmed by the user,
  2026-11-27).
- **West DB25: male,** to the computer.  The 128D's keyboard socket is female.
- **East DB25: female,** like the 128D's socket, for the keyboard cable's male plug, so a
  keyboard plugs into the dongle exactly as it would into the computer.
- **Pass-through:** all 25 pins straight through between the two connectors, +5 V and GND
  included, so a wired keyboard is powered as normal.  The CH446Q taps the same matrix lines
  in parallel, the way the rev 3 board's crosspoint sits on the host lines.
- **Pin numbering:** a plug and a socket number their pins as mirror images.  Work out which
  side of the board carries each connector's 1-13 row before routing, so the 25 through-lines
  need no via each.

### North and south

- **Two USB ports on the north edge** (decided 2026-11-27): a USB-C for the Mac and for
  flashing, and a USB-A for a USB keyboard.  Both can stay plugged in; a mode button picks
  which one the S3 talks to (see *USB: two ports, one switch* below).  The USB-C's 5 V joins
  the DB25's +5 V through diodes, as the keyboard's D1 and D2 do.
- **Status light on the south edge: one SK6812 MINI behind a light pipe** (the user's choice,
  2026-11-27: simplest to make and cheapest).  It is the keyboard's own LED (LCSC C2886570,
  already in the BOM and stocked by JLCPCB), placed by the fab like any other part, and its
  colour shows power, link and key activity.  The light pipe is part of the clamshell: a short
  clear-printed rod, or a standard press-fit pipe in a hole above the LED.
  - **Data level: a 74AHCT1G125 buffer** (decided 2026-11-27), as on the keyboard (U4 there,
    LCSC C7484).  At 5 V the SK6812 wants its data above about 3.5 V and the ESP32 drives
    3.3 V; the AHCT input reads 3.3 V as high and drives the LED at a full 5 V.
- **Module: ESP32-S3-MINI-1** (decided 2026-11-27), the PCB-antenna version of the
  keyboard's S3-MINI-1U, chosen over a C3 because its USB can also host a USB keyboard.
- **Antenna:** with metal D-sub shells at both ends and the USB-C north, the clearest spot is
  the south edge: the module's antenna end at a south corner away from the status light,
  copper kept clear under it.
- **Pairing button:** reachable through the clamshell (a printed cap over a tact switch).  It
  can be the S3's BOOT button on IO0: held at reset it enters download mode, pressed while
  running it starts pairing, so one switch does both.

### Clamshell

- **Fit:** two printed halves snap together over the whole board, with slots that capture
  the DB25 flanges, so the flanges take the plugging force, not the solder joints.
- **Retention:** the flanges' 4-40 holes take jackscrews or hex standoffs, so the dongle can
  screw to the computer and the keyboard cable can screw to the dongle.
- **Openings:** a cut-out for the USB-C on the north side, and the light pipe over the status
  LED on the south side.  Plastic is fine for the radio.

## USB: two ports, one switch

The S3 has one USB transceiver: its USB is a device or a host, never both at once.  So the
dongle has two ports and routes the S3 to one of them.

- **USB-C, device mode (the default):** the Mac app (USB serial) and flashing.  The port is
  only ever a device, so its CC pins carry plain 5.1 k pull-downs, as on the keyboard.
- **USB-A, host mode:** a USB keyboard.  Its 5 V comes through a current-limited power switch
  (about 500 mA), turned on in host mode only.
- **Both lie flat** (decided 2026-11-27): a right-angle USB-A beside the right-angle USB-C on
  the north edge, both opening the same way, toward the rear of the C128.  That keeps the
  clamshell low, and both cables leave together.
- **The switch:** a USB 2.0 analog switch chip routes the S3's D+/D- to one port or the
  other, so both can stay connected and the mode button toggles between them.
- **Mode button:** a second tact switch through the clamshell.  The status light shows the
  mode: for example cyan for the Mac and flashing, amber for the USB keyboard.  The mode is
  saved, and the simplest firmware saves it and restarts in the new mode, which takes under a
  second.
- **Flashing always wins:** holding BOOT (the pairing button) at reset puts the S3 into
  download mode on the USB-C, whatever mode is saved, so a bad setting can never stop a
  reflash.
- Considered and set aside: one USB-C that swaps roles (needs an adapter for a USB-A keyboard
  and a switched CC pull-up), and a separate USB-host chip (keyboard and Mac at once, but more
  parts and cost than the use needs).

## Pairing

The user's flow (2026-11-27): press the dongle's pairing button, its light blinks, then press
RETURN on the keyboard.

1. **The button opens pairing** for about 30 seconds.  The status light blinks, and the
   dongle broadcasts a "pairing open" beacon over ESP-NOW.
2. **The keyboard answers at the next RETURN** (or keypad ENTER).  A keyboard that hears the
   beacon sends a pairing request instead of the key.  The first request wins.
3. **Both sides store each other** (the other's MAC address and a shared ESP-NOW encryption
   key, in NVS), so they find each other after a power cycle.  The dongle's light goes solid,
   and the keyboard can flash its own LEDs to confirm.
4. **The RETURN is not typed:** it is swallowed by the pairing, so the C128 never sees it.

Pairing again replaces the stored partner.  A timeout with no RETURN closes pairing and
leaves the old pairing in place.

## The dongle on its own

The dongle does not care where key states come from: the C128 only sees switches closing
between its matrix lines.  So anything that can tell the dongle's ESP32 "these keys are down"
can type on the computer: the keyboard over ESP-NOW, or an app on a Mac or PC.

### How an app talks to it

- **USB serial:** the simplest.  The ESP32 shows up as a serial port, and the app sends
  commands such as `type 10 PRINT "HI"`, `press RETURN` or `hold SHIFT`.  The S3 has USB
  built in, so no extra chip is needed.
- **Wi-Fi:** a small TCP or WebSocket server on the ESP32, so the app works across the room
  with only the C128 powering the dongle.
- **A USB keyboard plugged straight in:** the S3's USB can act as a host and read a USB
  keyboard on the dongle's USB-A, with no computer involved.  This is why the dongle uses the
  S3 rather than a C3.

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

- The battery board's charger and boost parts, chosen from the step 1 measurements: compare
  current limits, quiescent draw and JLCPCB stock.
- The USB parts: which analog switch, and which current-limited power switch for the USB-A.
