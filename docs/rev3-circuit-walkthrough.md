# Rev 3 circuit walkthrough

A tour of the rev 3 schematic for someone who knows Ohm's law and what a capacitor does but
has not designed a board with a microcontroller on it before.  It follows the four schematic
sheets in `pcb/` and, for every part, answers two questions: what is it for, and why
that part and that value.  Reference designators (U1, R6, C8) match the schematic and the
BOM.

## The one-paragraph version

The Commodore 128 finds out which key you pressed by scanning a grid of switches: it pulls
one column line low at a time and looks at which row lines went low with it.  The original
keyboard is nothing but switches wired into that grid.  Rev 3 puts a small computer between
the switches and the Commodore.  An ESP32 microcontroller scans the real switches itself,
then closes tiny electronic switches inside a *crosspoint* chip so that the Commodore sees
exactly the grid it expects.  Because firmware now sits in the middle, the board can remember
the lock keys across power cycles, drive a light under every key, type macros, and be
configured over WiFi.  Plugged into a PC instead of a Commodore, it can also behave as an
ordinary USB keyboard, which is what makes a C128 emulator finally feel like a C128.  Everything else on the board exists to power those two chips safely,
to translate between the ESP32's 3.3 V world and the Commodore's 5 V world, and to keep the
keyboard working in the corner cases: power-on, a dead firmware, a shorted cable.

## Power: three rails and why there are three

| Rail | Comes from | Feeds | Why it exists |
|---|---|---|---|
| `+5V_KB` | pin 4 of the keyboard connector: the Commodore's own 5 V | the crosspoint (U3) and the lock-line pull-downs | the crosspoint's analog switches must span the same 0..5 V the Commodore's lines use, so it must run from the Commodore's rail, not a diode-dropped copy |
| `+5V_SYS` | the higher of the fused keyboard rail and USB-C, through two diodes | the 3.3 V regulator, the LEDs, the LED level shifter | lets the board run from USB alone on the bench, and lets a USB supply carry the LED current so the Commodore does not have to |
| `+3V3` | regulator U2 | the ESP32, the 74HC154, the physical switch matrix, pull-ups | the ESP32 is a 3.3 V part; nothing on this rail ever touches a Commodore signal |

There is one ground.  Everything, including the Commodore, the USB host and the LED strip,
shares it.

### F1, a 1.1 A polyfuse

A polyfuse is a resettable fuse: a polymer whose resistance shoots up when it heats past a
threshold, then recovers when it cools.  It sits in series with the Commodore's 5 V feed.  Its
job is to protect the *Commodore*, whose keyboard connector and PCB trace were never meant to
supply more than a few tens of milliamps, from a fault on this board.  1.1 A is its hold
current (it stays low-resistance below that); it trips around twice that.  The firmware's LED
current limiter keeps normal draw well under the hold current.

### D1 and D2, SS34 Schottky diodes

Two supplies feed `+5V_SYS`: the Commodore and USB.  If they were joined with wire, whichever
sat at a slightly higher voltage would push current back into the other, into the Commodore's
5 V rail or into your PC's USB port.  A diode in each path stops that: current only flows out
of each source, and the higher one wins.  This is called diode OR-ing.

Why Schottky: an ordinary silicon diode drops about 0.7 V; a Schottky drops 0.3 to 0.4 V, so
`+5V_SYS` lands around 4.6 V instead of 4.3 V.  Why the SS34 specifically: it is rated 3 A,
far above anything here, in a package (SMA) that handles the heat, and it is a cheap fab-stock
part.

### C5, 220 uF electrolytic

A bulk reservoir on `+5V_SYS`.  Two things on this board draw current in sharp bursts: the
ESP32 when its WiFi radio transmits (hundreds of milliamps for microseconds) and 92 LEDs when
they all change brightness on the same frame.  The diodes and the long cable back to the
Commodore cannot deliver those bursts instantly; the capacitor does, then refills.  220 uF is
a comfortable value; anything from 100 to 470 uF would do.

### U2, AP7361C-33E regulator, with C6 and C7

A linear regulator turns the roughly 4.55 V on `+5V_SYS` into a clean 3.3 V by burning the
difference as heat.  For a few hundred milliamps that is simpler and electrically quieter than
a switching regulator: the ESP32 averages 100 to 200 mA, so the regulator wastes about a
quarter of a watt, which a SOT-223 on a copper pour sheds without noticing.  A switching
regulator would save that quarter watt at the cost of an inductor, more parts, stricter
layout and switching noise next to the WiFi antenna.  C6 (10 uF on the input) and C7 (10 uF
on the output) are what the regulator's datasheet asks for: the output capacitor in
particular keeps the regulator's feedback loop stable, and without it the output can
oscillate.

**Why this part and not the usual AMS1117.**  Every linear regulator needs its input to sit
some minimum above its output, the *dropout voltage*, or it stops regulating and the output
just follows the input down.  The AMS1117 needs 1.1 to 1.3 V.  The 128's keyboard connector
measured 4.9 V, D1 takes about 0.35 V, so the regulator sees about 4.55 V and the AMS1117
would have had 0.1 V of margin at the worst moment, a WiFi transmit burst, when the diode
drop and the dropout are both at their highest.  The AP7361C needs about 0.36 V at a full
1 A and far less at our current, leaving more than a volt of margin.  It also stays stable
on ceramic capacitors, where the AMS1117 really wants a tantalum.  Same SOT-223 footprint,
about 65 cents, stocked at JLCPCB (LCSC C500795).

### PWR_FLAG symbols

Not parts.  KiCad's electrical rules checker wants to know where each power net's energy
comes from, and a net that is only fed through a connector or a diode has no "power output"
pin to satisfy it.  The flags tell the checker "this net is powered, trust me."  They produce
nothing on the board.

## Sheet: MCU and power

### U1, ESP32-S3-MINI-1U-N8

The microcontroller, bought as a module rather than a bare chip.  The module includes the
ESP32-S3 die, 8 MB of flash for the firmware and settings, the crystal, the RF matching
network and a U.FL socket for an external antenna, all under a metal can, and it comes with
regulatory certification for the radio.  The U variant (no PCB-trace antenna) is used because
the whole keyboard PCB sits under the metal plate, where an on-board antenna would barely
radiate; it is also only 2.4 mm tall, which helps under a flat 128.  Designing that from parts is a project in itself; the module
costs about three dollars.  Why this MCU: it has WiFi (for the configuration web page),
native USB (for flashing and a serial console), enough GPIO, and a peripheral (RMT) that
generates the LED data stream in hardware.

The `-N8` suffix means 8 MB flash, no PSRAM.  That matters because the PSRAM versions steal
GPIO 35, 36 and 37 for the memory chip; the N8 leaves them free.

The GPIO assignments are printed on the sheet.  Four pins are avoided on purpose: IO0, IO3,
IO45 and IO46 are *strapping pins*, which the chip reads at the instant of reset to decide how
to boot, and driving them from external circuitry can put it into the wrong mode.

### R1, C1 and SW93: the reset circuit

EN is the chip-enable pin.  R1 (10 k) pulls it to 3.3 V so the chip runs; SW93 shorts it to
ground to force a reset.  C1 (100 nF) with R1 forms an RC delay of about a millisecond, so
that when power first appears EN rises a little after the 3.3 V rail has settled, giving the
chip a clean start instead of a start on a wobbling supply.  Espressif's own guidance
suggests up to 1 uF here for slow supplies; 100 nF is fine with a regulator this close.

### R2 and SW94: the boot button

IO0 is the strapping pin that selects normal boot (high) or firmware-download mode (low).
R2 (10 k) holds it high so the board boots normally.  Holding SW94 while pressing reset pulls
it low and the chip waits for new firmware over USB.  The firmware can also enter download
mode by itself over USB, so on a finished board this button is a fallback, but it costs
almost nothing.

### C2 and C3: 100 nF and 10 uF on the 3.3 V pin

Decoupling capacitors.  Every digital chip draws current in fast spikes as its transistors
switch; a capacitor right next to the power pin supplies those spikes locally so the supply
rail does not dip.  The two values cover two speed ranges: the small ceramic 100 nF responds
to nanosecond spikes, the 10 uF handles the slower, larger demands of the radio.  You will
see 100 nF next to every chip on this board for the same reason.

### J4: UART header

Three pins: the ESP32's serial transmit, receive and ground.  During development it is the
console for log messages, and it is the second way to flash the chip if USB ever misbehaves.
Not needed by the finished keyboard.

### J1: USB-C receptacle

A 16-pin USB-C connector carries only the USB 2.0 signals, which is all the ESP32 has.  A
few details that are not obvious:

- **CC1 and CC2 with R3 and R4 (5.1 k to ground).**  USB-C decides who is the power source
  by looking at these pins.  A 5.1 k pull-down on each says "I am a device, please give me
  5 V."  Without them a USB-C charger or a modern laptop supplies nothing at all.
- **D+ and D- appear twice (A6/B6, A7/B7).**  A USB-C plug can go in either way up; the two
  copies of each data pin are the two orientations.  Wiring both to the same net is what the
  USB-C specification says to do for a USB 2.0 device.
- **SBU1/SBU2** are for alternate modes (video, audio) and are left unconnected.
- **SHIELD** ties the connector's metal shell to ground.

### U7, USBLC6-2SC6: ESD protection

The USB connector is the one place a person's fingers, and any static charge on them, reach
the circuit directly.  The USBLC6 is a package of fast clamping diodes: any voltage spike on
D+ or D- above 5 V or below ground is shunted to the rails before it reaches the ESP32.  It is
placed between the connector and the chip.  Cheap insurance.

## Sheet: crosspoint and host

### U3, CH446Q: the crosspoint

An 8 x 16 array of analog switches with a memory cell for each one.  The Commodore's eight
row lines connect to the Y side and its eleven column lines (COL0 to COL7 plus the three
extra "K" lines the 128 added) to eleven of the sixteen X lines.  Closing the switch at
(Y = row 3, X = column 5) is electrically the same as pressing the key that sits at row 3,
column 5 on a stock keyboard.  The Commodore cannot tell the difference: the switches are
bidirectional and passive, they simply connect two wires.

Why not just wire the switches through as before?  Because then nothing could sit between
switch and host.  With the crosspoint, firmware decides what the Commodore sees: it can hold
SHIFT LOCK closed forever without a mechanical latch, type a macro, or swallow the digit in a
SHIFT LOCK + digit command.

Why this chip: it does exactly this one job, costs a dollar or two, runs from a single 5 V
supply, and its control inputs accept 3.3 V logic (it reads anything above 2.0 V as high),
so the ESP32 drives it with no translation.  The classic part for this job, the MT8816, is
functionally identical and costs five times as much.

Things on the sheet that need explaining:

- **VDD on `+5V_KB`, VEE on ground.**  The switches can pass any voltage between VEE and
  VDD.  The Commodore's lines swing 0 to 5 V, so VDD must be the Commodore's own 5 V, not the
  diode-dropped `+5V_SYS`.  VEE exists for audio applications that switch negative voltages;
  we have none, so it is grounded.
- **Serial mode.**  The chip can take its 7-bit switch address on seven parallel pins or
  clocked in one bit at a time.  Serial mode needs only DAT, CS/CK (the clock), STB (strobe)
  and RST, which saves six GPIO.  P/S tied to ground selects serial mode, and the datasheet
  requires the unused address pins AX0..AX3 and AY0..AY2 to be grounded too, hence the row
  of ground labels.
- **On-resistance.**  A closed switch is about 120 to 185 ohm at 5 V.  The Commodore's row
  inputs are pulled up through a few kilohms, so a few hundred ohms in the path is nothing.
- **X11..X15 unused.**  The Commodore has eleven columns; the chip has sixteen X lines.  The
  extras are marked no-connect.
- **C8, 100 nF.**  Decoupling, as always.

### R10 and R11: what the crosspoint does while the ESP32 is still asleep

The ESP32 takes a few hundred milliseconds to boot, and until its firmware runs its pins are
undriven, floating.  Two resistors give the crosspoint safe defaults during that window:

- **R10 (10 k) pulls RST high.**  RST high opens every switch and ignores everything else.
  So from the moment power arrives until the firmware deliberately drives RST low, the
  Commodore sees an empty keyboard, never garbage.
- **R11 (10 k) pulls STB low.**  STB is the "latch it now" pulse.  A floating STB could
  register random switch writes; held low, nothing is written.

### Q1, Q2 and their resistors: CAPS LOCK and 40/80

These two Commodore lines are not part of the row/column grid.  On a stock keyboard each is
a latching mechanical switch to ground; the Commodore holds the line high through a pull-up
and reads it low when the switch is down.  To imitate a switch to ground with a logic signal
you use an open-drain transistor: an N-channel MOSFET with source to ground and drain on the
line.  Gate high, the line is pulled to ground ("key down"); gate low, the transistor is off
and the line floats up to the Commodore's own pull-up ("key up").  The transistor never
*drives* the line high, which is why 3.3 V logic can safely control a 5 V line this way.

- **2N7002** is the standard small logic-level MOSFET: it turns on well with 3.3 V on the
  gate, and the current here is under a milliamp.
- **R5 and R7 (100 k) from each gate to ground** keep the transistors off while the ESP32 is
  booting and its pins are floating.  100 k is large enough not to load the GPIO and small
  enough to drain any stray charge.
- **R6 (10 k) and JP1, the "80 column default" jumper.**  This one is about timing.  The
  128's KERNAL reads the 40/80 line once, early in reset, and never again.  If the board
  waited for the ESP32 to boot and then asserted 40/80, the KERNAL would already have chosen
  40 columns.  So with JP1 closed, R6 pulls Q1's gate up to 3.3 V the instant power appears,
  asserting 80 columns before the Commodore's CPU has even started.  Once the firmware is
  running it drives the gate directly, low if the saved preference is 40 columns, and the
  10 k is easily overridden by the GPIO.  With JP1 open, R5 wins and the default is 40
  columns.  The solder jumper is on the board so the choice is a blob of solder, not a
  firmware build.

### Q3 and R12: pressing RESTORE from firmware

The same open-drain arrangement once more, on the RESTORE line.  Q3's drain sits on RESTORE,
its source on ground, and R12 (100 k) keeps the gate low until the ESP32 drives it.  With it
the firmware can press RESTORE, which matters for the network keyboard: RUN/STOP + RESTORE is
how you recover a hung Commodore, and a remote console without it would be half a console.
The physical RESTORE key is still wired straight through beside it, so a dead firmware never
takes the escape hatch away.

### D3: sensing RESTORE

RESTORE is wired straight through from the switch to the Commodore (see the matrix sheet).
The ESP32 only wants to *see* it: for lighting effects, and to report it as a key when the
board is acting as a USB keyboard.  The line swings 0 to 5 V and an ESP32 pin must not see
more than 3.3 V, and there is a second catch: with no Commodore attached, nothing pulls the
line up at all, so a simple resistor divider would read noise.

A diode solves both.  Its cathode is on the RESTORE line and its anode on an ESP32 pin with
the chip's internal pull-up switched on.  Key pressed: the line is grounded, current flows
through the diode, the pin reads low.  Key released: the line is at the Commodore's 5 V, or
floating with no Commodore, and in both cases the diode blocks, so the pin's pull-up holds it
at 3.3 V and it reads high.  The pin never sees 5 V, and the board never puts a voltage onto
the Commodore's line.  A single 1N4148W, the same diode used under every key.

### U4, 74AHCT1G125: the LED level shifter, with C9

The SK6812 LEDs run on 5 V and, like most logic, recognize "high" only above about 70 % of
their supply, so 3.5 V.  The ESP32 outputs 3.3 V, which is marginal at best.  The 74AHCT1G125
is a single logic buffer built to fix exactly this: the "T" in AHCT means its input treats
anything above 2 V as high, and it is powered from 5 V so its output swings to 5 V.  Pin 1 is
its output enable, active low, tied to ground so the gate is always on.  C9 is its decoupling
capacitor.  This is the only 5 V logic input left on the board; the crosspoint takes 3.3 V
natively.

### J2: the keyboard cable header

A 2 x 13 header laid out in *D-sub IDC order*.  A flat 26-way ribbon cable crimped onto this
header and onto an insulation-displacement DB25 at the other end connects pin for pin to the
Commodore's connector with no crossing wires.  The trick is that the IDC DB25 puts odd ribbon
conductors on D-sub pins 1..13 and even ones on 14..25, and the header is wired to match.  On
a flat 128 the ribbon is soldered straight into these pads instead (no header, no height) and
split into crimped pins at the far end for the printed 1 x 25 plug.  Pins 3 and 26 are
unused: pin 3 is the D-sub's keying position, and a 25-wire connector only needs 25 of the
26 conductors.

### J3: external LED header

Three pins, 5 V, data out of the last LED in the chain, ground.  Lets one more addressable
LED sit somewhere off the board, for instance replacing the 128's power LED, or an underglow
strip inside the printed case.

## Sheet: physical matrix

### The switches and the diode on every key

92 switches, wired into eight physical rows and twelve physical columns using the *same*
row/column assignment the Commodore uses, plus a twelfth column that only the ESP32 sees for
the three lock keys.  Keeping the assignment identical means the firmware's job is trivial:
physical (row, column) maps to crosspoint (row, column) with no table.

Each key has a small diode (D101..D192, 1N4148W) in series: row, then switch, then diode
anode to cathode, then column.  Here is why.  When the scan pulls one column low, current
should flow only from the pulled-up rows through keys *in that column*.  Without diodes, three
pressed keys that form three corners of a rectangle create a sneak path: current runs from a
row through one key to another column, along that column through a second key to another row,
and through a third key back, and the scan reads a phantom fourth key at the missing corner.
That is "ghosting".  A diode in each key only lets current flow from row to column, which
kills every sneak path, so any combination of keys reads correctly.

The original 128 keyboard has no diodes and the Commodore itself cannot resolve those
combinations, so for the Commodore alone the diodes would not be needed.  They are here
because this board can also act as a plain USB keyboard for a PC or an emulator, and a USB
keyboard is expected to handle any chord.  With the fab placing them, 92 diodes cost about a
dollar.  The 1N4148W is the surface-mount version of the most common small signal diode
there is.

### U6, 74HC154: column select

To scan, the ESP32 has to pull one of twenty columns low at a time.  The scanned matrix
follows the board, six key rows by twenty columns (one per key of the number row), rather
than the C128's own assignment; the firmware knows which C128 position each key stands for.
Twenty GPIO would do it, but a 4-to-16 decoder covers fifteen of them with four: give it a
4-bit number and exactly one of its sixteen outputs goes low.  Outputs 0-14 are columns 0-14;
output 15 has nothing on it, and the firmware selects it between scans so no column sits
low.  Columns 15-19 come straight from five GPIO.  The two enable
inputs are grounded so it is always active.  It runs from 3.3 V (the HC family works from 2
to 6 V) because everything on this sheet is on the ESP32's side of the fence.  C11 is its
decoupling capacitor.

### R20 to R39, 1 k in each column

Imagine two keys pressed in the same row but different columns.  The scan pulls one column
low while the decoder holds the other high, and the two pressed switches connect those two
columns together through the row wire.  Without resistors the decoder's two outputs would
fight each other directly.  1 k in each column limits that to about 3 mA, harmless, while
still letting a pressed key pull its row input firmly low (the ESP32's internal pull-ups on
the row pins are about 45 k, so 1 k in series barely dents the low level).

### The rows

The six row lines go straight to ESP32 inputs with the chip's internal pull-ups enabled.
A pressed key connects a row to the selected (low) column and the input reads low.

### RESTORE

The RESTORE key is not scanned.  Its switch connects the Commodore's RESTORE line directly to
ground, exactly as on the stock keyboard.  RESTORE triggers the CPU's non-maskable interrupt
and is the user's escape hatch when a program hangs; it should keep working even if the
firmware on this board has crashed or was never flashed.

## Sheet: LEDs

### LED1..LED92, SK6812 MINI

Addressable RGB LEDs: each package holds red, green and blue emitters and a tiny controller.
They chain on a single data line: the first LED takes the first 24 bits of color from the
stream, strips them off, and forwards the rest to the next.  One ESP32 pin drives all 92, with
no shift registers or multiplexing.  The MINI (3.5 x 3.5 mm) sits on the switch side of the
board in the pocket the Outemu switch housing already has for an SMD LED, which is why light
gets through without modifying the switch.

The chain order is deliberate: SHIFT LOCK, CAPS LOCK and 40/80 come first.  A chain breaks at
any missing LED, so a board with only three LEDs fitted still gets its lock indicators.

### C101..C192, 100 nF at every LED

Each LED's controller switches its emitters on and off thousands of times a second, and 92 of
them doing that along one long 5 V trace makes the rail ripple.  A 100 nF capacitor next to
each LED is the manufacturer's standard requirement; skipping them is the classic cause of
flicker and color glitches on long chains.

### Current

Every LED at full white is about 40 mA; 92 of them would be 3.7 A, far more than the
Commodore's keyboard connector can supply.  The firmware caps total brightness so the draw
stays around half an amp from the Commodore, and the USB-C input exists so a lit keyboard can
be powered externally instead.

## Reading the netlist between sheets

Signals cross between sheets as global labels with a prefix telling you which world they
belong to:

- `P_ROW0..7`, `P_COL0..11`: the physical matrix, 3.3 V, ESP32 side.
- `MCU_...`: an ESP32 pin.
- `H_ROW0..7`, `H_COL0..10`, `H_RESTORE`, `H_4080`, `H_CAPLK`: the Commodore's lines, 5 V.
- `LED_DATA_5V`, `LED_D1..91`, `LED_OUT`: the LED chain.

Nothing with a `P_` or `MCU_` prefix ever connects to anything with an `H_` prefix except
through the crosspoint, the three FETs, or the RESTORE sense diode.  That separation is the whole
safety story of the board.

## Assembly, in one paragraph

Every surface-mount part is placed by the board fab.  The LEDs are on the front (switch
side); the ESP32 module, crosspoint, regulator, USB-C, the 91 matrix diodes, the two buttons
and all the small parts are on the back.  The builder solders the through-hole parts: 92 key
switches, the cable header or the ribbon itself, and the three-pin headers.  Each
surface-mount symbol carries an `LCSC` field with the fab's part number where it is known;
the BOM in `pcb/bom.csv` lists them.
