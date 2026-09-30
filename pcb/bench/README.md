# Rev 3 bench rig: rev 2.3 board + breadboard + a C128

Goal: prove the rev 3 architecture on a breadboard before laying out a board.  A populated
rev 2.3 keyboard is the physical switch matrix, an ESP32-S3 devkit scans it, a CH446Q on an
LQFP-44 adapter mirrors it onto a real C128, and the lock lines, LEDs and power get measured.  This
covers bench proofs 1 to 6 in [docs/rev3-plan.md](../../docs/rev3-plan.md).

Everything below uses the same nets and GPIOs as the rev 3 schematic in the folder above,
so firmware written on the bench moves to the real board unchanged.  The firmware itself is in
[`firmware/`](../../firmware/README.md).  While waiting for parts, the measurements in
[before-parts-arrive.md](before-parts-arrive.md) need only the 128 and the rev 2.3 keyboard.

## Shopping list

Semiconductors (buy a spare of each; they are cheap and one will get plugged in backwards):

| Qty | Part | Notes |
|---|---|---|
| 2 | ESP32-S3-DevKitC-1 | any flash/PSRAM variant; the design does not use GPIO35-37.  A `-1U` kit (e.g. DevKitC-1U-N8R8) carries the WROOM-1U module with no on-board antenna: add a U.FL 2.4 GHz antenna for the WiFi tests |
| 3 | CH446Q (LQFP-44) | WCH 8x16 crosspoint; LCSC / AliExpress.  Three because 0.8 mm pitch by hand deserves a spare |
| 3 | LQFP-44 0.8 mm to DIP adapter board | Adafruit 1162 ("SMT Breakout PCB for 44-QFN or 44-TQFP", 3-pack, 1:1 pins, 0.7" row spacing) plus break-away 0.1" male header.  Avoid the "QFP44 to DIP40" ATmega programming sockets: their 44 pins are remapped to the ATmega DIP-40 pinout |
| 4 | 74HC138 (DIP-16) | two of them replace the 74HC154 4-to-16 decoder exactly (see the wiring table); the DIP-24 74HC154 is hard to find, though TI's CD74HC154E is sometimes stocked and works if you have one |
| 20 | 1N4148 (through-hole) | one is the RESTORE sense diode; the rev 2.3 board has no per-key diodes, so chord tests on the bench will ghost like the original, and a few diodes let you prove the rev 3 scan on a handful of keys if you want |
| 2 | 74AHCT125N (DIP-14) | 3.3 -> 5 V buffer for the LED data line (one gate used; the board uses a single-gate 74AHCT1G125) |
| 5 | 2N7000 (TO-92) | breadboard stand-in for the 2N7002 lock-line and RESTORE FETs (three used) |
| 5 | 1N5819 or SS34 | Schottky for the 5 V OR-ing test |
| 20 | SK6812 MINI (3.5 x 3.5 mm, top emitting) | Adafruit 2659 "NeoPixel Mini 3535" 10-packs, or the LCSC-stocked SK6812MINI.  For the fit test under a real switch; sits on the board surface in the switch's LED pocket.  Not the 4020 side-emitting SK6812B (Adafruit 4691), which fires sideways |
| 1 | WS2812B / SK6812 RGB strip, 60 LEDs, 5 V | Adafruit 2541 (1 m, 60/m, SK6812-class, RGB).  For LED engine development without soldering MINIs.  Power it from its own 5 V, 2 A supply; a 1 m cut may come without a JST SM plug |

Passives (a kit covers it, otherwise): 1k x15, 5k1 x2, 10k x15, 100k x5; 100 nF x20,
10 uF x5, 220 uF electrolytic x2; one 1.1 A polyfuse.

Wiring and cable proofs:

| Qty | Part |
|---|---|
| 2 | 830-point breadboards plus one 400-point |
| 1 | jumper wire kit, male-male and female-male |
| 1 m | 26-way 0.05" ribbon cable (gray floppy-style) |
| 2 | 2 x 13 IDC socket (ribbon crimp) and 2 x 13 shrouded box header |
| 1 each | IDC DB25 male and IDC DB25 female (ribbon crimp) |
| 1 | USB-C breakout board (for the VBUS OR-ing and CC test) |

Already on hand: one populated rev 2.3 board, four bare rev 2.3 boards, the FFC-to-DB25
crossover adapter, the printed 1 x 25 keyboard plug and wires for a flat 128.

## How the rig fits together

```
 rev 2.3 board ──FFC──► crossover adapter ──DB25-pattern pins──► jumpers ──┐
 (physical switches, +5 V for its MAX16054s)                               │
                                                                           ▼
   ┌──────────── breadboard ────────────────────────────────────────────────────────────┐
   │  column decoder (3.3 V) ──1k──► COL0..10 of the rev 2.3 board                      │
   │  ROW0..7 of the rev 2.3 board ──► ESP32-S3 devkit inputs (internal pull-ups)       │
   │  ESP32 ──► CH446Q DAT / CS-CK / STB / RST directly (serial mode, 3.3 V is enough)  │
   │  CH446Q X0..10 / Y0..7 ──► C128 COL0..10 / ROW0..7                                 │
   │  2N7000 x2 ──► C128 40/80, CAPS LOCK          rev 2.3 RESTORE ──straight──► C128   │
   └────────────────────────────────────────────────────────────────────────────────────┘
                                                                           │
                          printed 1 x 25 plug (flat) or DB25 cable (128D) ◄┘
```

Power: the C128's keyboard +5 V (connector pin 4) feeds the CH446Q, the 74AHCT125 and the
rev 2.3 board's latch ICs, exactly as on the real rev 3 board.  The devkit is powered from
its own USB cable and its 3V3 pin feeds the column decoder and the pull-ups.  **Join all grounds**
(C128 pin 1, devkit GND, breadboard rails).  Do **not** tie the devkit's 5 V pin to the C128
rail.  Power the LED strip from a separate 5 V supply with common ground until the current
measurements are done.

## Stock C128 keyboard connector (D-sub numbering)

Both the crossover adapter's output and the C128 itself use this order.

| Pin | Signal | Pin | Signal | Pin | Signal |
|---|---|---|---|---|---|
| 1 | GND | 10 | ROW2 | 19 | COL1 |
| 2 | key, no pin | 11 | ROW1 | 20 | COL7 |
| 3 | RESTORE | 12 | ROW0 | 21 | K0 = COL8 |
| 4 | +5 V | 13 | COL0 | 22 | K1 = COL9 |
| 5 | ROW3 | 14 | COL6 | 23 | K2 = COL10 |
| 6 | ROW6 | 15 | COL5 | 24 | 40/80 |
| 7 | ROW5 | 16 | COL4 | 25 | CAPS LOCK |
| 8 | ROW4 | 17 | COL3 | | |
| 9 | ROW7 | 18 | COL2 | | |

## ESP32-S3 devkit pins

| GPIO | Net | Goes to |
|---|---|---|
| IO4, 5, 6, 7, 15, 16, 17, 18 | P_ROW0..7 | rev 2.3 ROW0..7 (adapter pins 12, 11, 10, 5, 8, 7, 6, 9).  Inputs, internal pull-up |
| IO8, 9, 10, 11 | MCU_COLSEL0..3 | column decoder address (two 74HC138s, or a 74HC154 if you have one); see below |
| IO12 | MCU_XP_CK | CH446Q CS/CK (pin 34), serial clock |
| IO38 | MCU_XP_DAT | CH446Q DAT (pin 36) |
| IO39 | MCU_XP_STB | CH446Q STB (pin 14); 10k to GND |
| IO40 | MCU_XP_RST | CH446Q RST (pin 41); 10k to 3V3 |
| IO41 | MCU_LED_DATA | 74AHCT125 gate 1 input (pin 2) |
| IO14, 21, 35, 36, 37 | spare | unused |
| IO42 | MCU_4080_GATE | 2N7000 Q1 gate; 100k to GND; 10k to 3V3 through a jumper for the "80 col default" test |
| IO2 | MCU_CAPLK_GATE | 2N7000 Q2 gate; 100k to GND |
| IO1 | MCU_RESTORE_SENSE | 1N4148 anode to IO1 (internal pull-up on), cathode to the C128 RESTORE line |
| IO13 | MCU_RESTORE_GATE | 2N7000 Q3 gate; 100k to GND; drain to the C128 RESTORE line |
| 3V3 | +3V3 | decoder VCC, pull-ups |
| GND | GND | everything |

Leave IO0, IO3, IO45, IO46 alone unless noted (strapping pins); IO19/IO20 are the devkit's
native USB.  The R8-devkit caveat no longer bites: IO35-37 are not used.

## Column decoder: two 74HC138N (DIP-16), 3.3 V

Two 3-to-8 decoders wired as one 4-to-16.  The low three address bits go to both chips; the
fourth bit enables one chip or the other.  Electrically identical to the 74HC154 the board
uses, so the firmware is the same.

| Pin (both chips) | 74HC138 function | Wire to |
|---|---|---|
| 1, 2, 3 | A, B, C | IO8, IO9, IO10 (COLSEL0..2) |
| 5 | G2B (enable, active low) | GND |
| 16 / 8 | VCC / GND | 3V3 / GND, 100 nF across each chip |

| Pin | Chip 1 (columns 0..7) | Chip 2 (columns 8..11) |
|---|---|---|
| 6 | G1 (enable, active high) | 3V3 | IO11 (COLSEL3) |
| 4 | G2A (enable, active low) | IO11 (COLSEL3) | GND |
| 15, 14, 13, 12, 11, 10, 9, 7 | Y0..Y7 | 1k each, then rev 2.3 COL0..COL7 (adapter pins 13, 19, 18, 17, 16, 15, 14, 20) | Y0..Y2: 1k each, then K0, K1, K2 (adapter pins 21, 22, 23); Y3: 1k, then P_COL11 (unused on the bench); Y4..Y7 open |

With COLSEL3 low chip 1 is enabled and chip 2 is not; with it high the reverse.  Each chip
drives exactly one output low for the selected code, so at any moment one of the twelve
columns is low and the rest are high, which is what the scan needs.

If you do have a 74HC154 in DIP-24 (TI CD74HC154E): A0..A3 = pins 23, 22, 21, 20 to IO8..IO11;
E0, E1 (pins 18, 19) to GND; Y0..Y10 = pins 1..11 and Y11 = pin 13 through 1k to the
columns; Y12..Y15 (pins 14..17) open; VCC pin 24 to 3V3, GND pin 12.

**74LS138 instead of 74HC138.**  Same pinout and wiring as the tables above, with two
changes.  VCC (pin 16) goes to **5 V**, not 3V3: LS is TTL and needs 4.75 to 5.25 V (the
devkit's 5V pin is fine for scan-only tests; the C128 +5 V once it is connected).  The
3.3 V address lines are enough, since TTL reads anything above 2.0 V as high.  An LS output
high is about 3.4 V, up to about 4 V unloaded, and it reaches a 3.3 V row input through a
closed key; the 1k column resistors keep that current to a few hundred microamps, so they
are not optional.  Before connecting the rev 2.3 board, load one deselected output with 1k to
3V3 and meter it: 3.3 to 3.6 V is fine, well over 4 V is not.

Do not skip the decoder by driving the columns straight from GPIO: the firmware's
`MATRIX_DIRECT_COLUMNS` pin list is for the simulator and uses the devkit's USB, strapping
and PSRAM pins (see the firmware README).

## 74AHCT125N (DIP-14), 5 V

Gate 1 only: OE pin 1 to GND, input pin 2 from IO41, output pin 3 to the LED strip DIN.  Tie
the other three gates' OE and inputs to GND.  VCC pin 14 to C128 +5 V, GND pin 7, 100 nF
across.

## CH446Q (LQFP-44 on an adapter), 5 V, serial mode

| LQFP pin | Name | Wire to | LQFP pin | Name | Wire to |
|---|---|---|---|---|---|
| 31, 30, 29, 28, 27, 26 | X0..X5 | C128 COL0..5 (pins 13, 19, 18, 17, 16, 15) | 33 | Y0 | C128 ROW0 (pin 12) |
| 3, 4, 5, 6, 7 | X6..X10 | C128 COL6, COL7, K0, K1, K2 (pins 14, 20, 21, 22, 23) | 35 | Y1 | C128 ROW1 (pin 11) |
| 8, 25, 24, 1, 2 | X11..X15 | open | 37 | Y2 | C128 ROW2 (pin 10) |
| 36 | DAT | IO38 | 39 | Y3 | C128 ROW3 (pin 5) |
| 34 | CS/CK | IO12 | 17 | Y4 | C128 ROW4 (pin 8) |
| 14 | STB | IO39, 10k to GND | 15 | Y5 | C128 ROW5 (pin 7) |
| 41 | RST | IO40, 10k to 3V3 | 13 | Y6 | C128 ROW6 (pin 6) |
| 10 | P/S | GND (serial mode) | 11 | Y7 | C128 ROW7 (pin 9) |
| 43, 18, 19, 42, 20, 21, 40 | AX0..3, AY0..2 | GND (required in serial mode) | 38 | VDD | C128 +5 V, 100 nF to GND |
| 12 | GND | GND | 16 | VEE | GND |
| 9, 22, 23, 32, 44 | NC | open | | | |

Writing one switch (datasheet section 5): with STB low, clock seven address bits on CS/CK
rising edges, MSB first, from DAT: AY2 AY1 AY0 AX3 AX2 AX1 AX0, where AY = host row and
AX = host column (the address is simply AY*16 + AX).  Then put the switch state on DAT
(1 = closed), pulse STB high for at least 10 ns, and drop it with DAT still stable.  RST high
opens every switch.  The ESP32 inputs read as high above 2.0 V, so no level shifting.
Firmware maps physical (ROW r, COL c) to AY = r, AX = c, which is why the physical and host
matrices use the same numbering.

## Lock lines and RESTORE

- Q1 (2N7000, flat face toward you: S, G, D): source GND, gate IO42 with 100k to GND, drain
  to C128 pin 24 (40/80).  For the power-on default test add 10k from 3V3 to the gate through
  a removable jumper and hold the devkit in reset while powering the C128.
- Q2: source GND, gate IO2 with 100k to GND, drain to C128 pin 25 (CAPS LOCK).
- RESTORE: adapter pin 3 straight to C128 pin 3.  A 1N4148 from IO1 (anode) to that line
  (cathode), with IO1's internal pull-up enabled, lets the firmware see the key.  Q3
  (2N7000): source GND, gate IO13 with 100k to GND, drain to the same line, lets the firmware
  press it.
- The rev 2.3 board's own 40/80 and CAPS LOCK outputs (adapter pins 24, 25) stay
  **unconnected** on the bench; its SHIFT LOCK still works because the 74AUC1G66 closes
  ROW7/COL1, which the scan sees as left shift held.

## Test sequence

1. **Reset window** (plan proof 1).  No breadboard needed.  Scope the C128 +5 V rail and the
   40/80 line at the keyboard connector with a stock or rev 2.3 keyboard, power on, and find
   when the KERNAL samples 40/80.  Repeat on a 128D if one is available.  Write the numbers
   into the plan.
2. **Scan only.**  Devkit + column decoder + rev 2.3 board, C128 not connected.  Firmware scans and
   prints key names over USB serial.  Check every key, then chords (SHIFT+letter, CTRL+digit,
   C=+digit, SHIFT LOCK).
3. **Crosspoint** (proof 3).  Add the CH446Q, connect to the C128, mirror pressed keys.  Type
   at the READY prompt.  Test all 88 matrix keys, the three-key chords the KERNAL uses,
   RUN/STOP+RESTORE, and key repeat.  Measure the on-resistance with a key held (voltage
   across X-Y at the CIA's scan current; the datasheet says 120 to 185 ohm at 5 V).
4. **Locks.**  Toggle 40/80 and CAPS LOCK from firmware; reset the C128 and confirm the screen
   mode follows.  Then the power-on default: jumper in, devkit held in reset, power the C128
   and confirm 80 columns.
5. **Light path** (proof 2).  Light through the mid-height switch is already proven by the
   rev 2.3 lock-key LEDs, which are through-hole parts that needed the housing trimmed.  The
   rev 3 question is only fit: glue an SK6812 MINI to a bare rev 2.3 board at the north LED
   position under one switch, wire it with magnet wire, fit an untrimmed Outemu mid-height
   switch and a Mitsumi cap on its adapter, drive it from the strip output.  Confirm the
   switch seats fully with the LED in its pocket, then photograph the glow and decide on
   brightness defaults.
6. **Power** (proof 4).  Ammeter in the C128 +5 V feed: idle, scanning, WiFi AP on, then the
   strip at increasing brightness until 500 mA.
7. **Boot time** (proof 5).  Scope 3V3 rising to the first column-decoder address change.
8. **Cables** (proof 6).  Crimp the ribbon proofs and meter them against the connector table
   above before either touches a mainboard.

## Firmware starting point

A minimal sketch (ESP-IDF or Arduino-ESP32, either works on the devkit):

- scan: for c in 0..11 set COLSEL = c, wait ~20 us, read the 8 row inputs (active low);
  debounce 5 ms;
- mirror: on any change, for each changed key clock the 7-bit address (AY = row, AX = col)
  into the CH446Q, set DAT = pressed, pulse STB;
- on boot: RST high 1 us then low, then restore saved 40/80 and CAPS LOCK state to IO42 and
  IO2, and if SHIFT LOCK was saved on, close (ROW7, COL1);
- SHIFT LOCK, CAPS LOCK and 40/80 keys (P_COL11 rows 0..2 on rev 3; not scannable on the
  rev 2.3 bench board, so use serial commands or two spare buttons) toggle their state and save
  it to NVS.

Once that types reliably on the C128, the rest of the feature list in the plan is software.
