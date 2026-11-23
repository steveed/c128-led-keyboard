# Measurements to make on the 128 before the bench parts arrive

Everything here needs only what is already on hand: a flat 128, the populated rev 2.3 keyboard
with its adapter and printed plug, a multimeter, an oscilloscope, a few resistors, calipers,
and a lump of modeling clay.  Each result closes an open item in
[docs/rev3-plan.md](../../docs/rev3-plan.md); write the numbers back there where indicated.

**Safety.**  Everything measured is 5 V logic and the keyboard connector.  Keep probes away
from the power supply side of the mainboard and the RF modulator.  Power the 128 down between
re-wirings; the keyboard connector is not hot-pluggable in either direction.

## 1. Reset window (plan proof 1)

*Question:* how long after power-on does the KERNAL read the 40/80 line?  This decides how
much the hardware default-assert on Q1/JP1 matters versus the ESP32 simply booting fast.

*Why the user port is the place to look:* the KERNAL reads 40/80 inside its reset routine,
a few milliseconds after /RESET is released.  So the window is, to a good approximation, the
power-on reset pulse width, and /RESET is available on **user port pin 3** (the edge connector
at the rear; pin 3 is on the top row, counting from the left with the machine facing you;
pins 1 and 12 are GND, A and N on the bottom row are GND too).

Procedure:

1. Stock or rev 2.3 keyboard plugged in, machine off.
2. Scope channel 1 on keyboard connector pin 4 (+5 V), channel 2 on user port pin 3
   (/RESET), grounds to pin 1 of the keyboard connector.  Single-shot trigger on channel 1
   rising through 2.5 V, 200 ms/div, 2 V/div.
3. Power on.  Read off: the time from +5 V reaching 4.5 V to /RESET going high (t_reset),
   and the shape of the +5 V ramp itself (how long it takes to reach 4.5 V).
4. Repeat three times; power-on reset circuits are not precise.
5. Optional confirmation with the rev 2.3 board: hold the 40/80 key so its latch is set
   *before* power-on (press it after power-off; the MAX16054 forgets, so instead: power on
   and press 40/80 as fast as you can; if you consistently get 80 columns, t_reset is long,
   if never, it is short).  Crude, but a cross-check.

Record in the plan under bench proof 1: t_reset (min/max of three), the 5 V rise time, and
whether a 128D is available to repeat it on.  Expect t_reset in the hundreds of milliseconds.
If it is under about 300 ms the JP1 default-assert circuit is essential; if it is over a
second the ESP32 could boot and assert it in time on its own, and JP1 becomes belt and braces.

## 2. Keyboard rail: voltage and how much current it will give (proofs 4 and the regulator question)

*Questions:* what does keyboard connector pin 4 actually sit at, how far does it sag under
load, and therefore what is `+5V_SYS` after the OR-ing diode and how much LED current is
reasonable to draw through the keyboard cable.

Procedure, machine on and idle at the READY prompt, rev 2.3 keyboard connected through the
adapter so the pins are reachable:

1. Meter across pin 4 (+5 V) and pin 1 (GND) at the adapter: V_open.
2. Meter the same rail at the mainboard (any 5 V point near the CIA is fine, or the +5 V pin
   of the user port, pin 2): V_board.  The difference is the harness and connector drop with
   the keyboard's own few milliamps.
3. Load the rail: clip a 22 Ω 2 W resistor between pin 4 and pin 1 (about 0.23 A) and read
   V_load1; then 10 Ω 5 W (about 0.5 A) for V_load2.  Keep each load on for only a few
   seconds; the resistors get hot.  If the machine resets or the screen blinks under the
   10 Ω load, stop and note it.
4. Compute the effective source resistance: (V_open − V_load2) / 0.5 A.

Record in the plan under proof 4: V_open, V_board, V_load1, V_load2, and source resistance.
Interpretation: `+5V_SYS` will be about V_load minus 0.35 V.  It tells you where the
firmware current cap must sit when running from the keyboard connector alone.

*Result so far (2026-09-21):* 4.9 V at the keyboard connector.  That alone decided the
regulator question: U2 became the AP7361C-33E low-dropout part (see the plan).  The loaded
readings are still worth taking for the current cap.

## 3. Underside clearance in the flat (layout height budget)

*Question:* how much room is there between the keyboard PCB's underside and the RF shield or
mainboard, along the rear band where the rev 3 parts go.

Procedure with the rev 2.3 keyboard installed as normal:

1. Press five blobs of modeling clay (about 10 mm) onto the shield under the keyboard:
   rear-left, rear-center, rear-right, and two mid-board.  Note where each sits relative to
   the keyboard outline; the rear band is what matters most.
2. Fit the keyboard and close the case completely, latching or screwing it as for use.
3. Open, lift the keyboard, and measure each squashed blob's height with calipers.
4. Subtract nothing: the blob height is the clearance from the PCB underside (or from the
   tallest thing on it, so avoid the existing ICs on the back).

Record in the plan under the underside height budget.  Compare against the parts: ESP32
module about 3.2 mm, USB-C receptacle 3.3 mm, CH446Q 1.6 mm, bottom liner about 0.5 mm, IDC
header 9 mm if fitted.  This decides whether the header is populated on flat builds and
whether the liner can be a single flat sheet.

## 4. Cable and connector facts (proof 6, partly)

1. With the rev 2.3 board, its FFC and the adapter, meter each adapter pin to the stock
   connector order in the bench README's table.  This confirms the table the rev 3 header
   is laid out from, independent of the adapter's own documentation.
2. On the flat's mainboard keyboard header, confirm which pin is +5 V and which is GND with
   the meter, and photograph the header with pin 1 marked.  The printed plug's orientation
   depends on it.
3. Measure the printed 1 x 25 plug's overall length and the header's pin pitch (expected
   about 2.77 mm), for the record.

## 5. Parts you already have: measure for the plate and the footprints

1. **Screw-in stabilizer housing:** width, length and the height of the shoulder above the
   PCB surface, plus the wire clearance it needs.  This sizes the enlarged plate clearance
   (issue 4) and the plate-1-mm-lower build.
2. **Outemu mid-height switch LED pocket:** width, depth (front-to-back) and height of the
   recess in the bottom housing, and its center distance from the stem.  The SK6812 MINI is
   3.5 x 3.5 x about 1.9 mm; a 3528-size pocket should take it.  This is the whole of bench
   proof 2's fit question and can be answered with calipers today.
3. **Mid-height switch total height and lower-housing height** versus a full-height MX
   switch, to confirm the 1 mm figure the shim compensates.
4. **Rev 2.3 lock-key LED holes:** their position relative to the switch center, as a check
   on where the LED pads go in the rev 3 switch footprint (the north position, nominally
   5.08 mm from center).

Record these in `docs/pcb-issues-and-plans.md` issue 4 and in the rev 3 README's footprint
placeholders.

## 6. Keycap heights above the plate (case bezel clearance)

The case README already has numbers for Mitsumi caps on mid-height switches.  If any MX-style
keycap is to hand, even a single one, put it on a full-height switch in a spare plate opening
and measure its skirt height above the plate at rest and pressed.  This is the number the
Signature Plastics set will need, and it decides `bezel_gap` for MX-cap builds.

## What each result unlocks

| Measurement | Decides |
|---|---|
| 1 reset window | whether JP1 default-assert is essential or belt and braces |
| 2 rail voltage under load | the regulator swap; the firmware current cap on keyboard power |
| 3 underside clearance | IDC header or soldered ribbon on flats; one-piece cover or pocketed |
| 4 cable facts | the J2 pinout is confirmed before boards are ordered |
| 5 stabilizer and pocket sizes | plate clearance cutouts; LED footprint position |
| 6 MX cap height | bezel gap for the SP keycap build |
