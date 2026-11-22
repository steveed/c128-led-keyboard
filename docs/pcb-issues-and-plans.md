# PCB rev 2.3: known issues and plans

Status: decided 2026-09-17, see [rev3-plan.md](rev3-plan.md) for the plan to execute.  Nothing here is built yet.  The point of this document is to
pin down what is wrong with the current board, why, and what the next revision should do about
it, so the work can be split up and argued about before anyone orders copper.

The feature bar is set by CBMstuff's Blingboard64 / BlingBox for the C64
(see its [command reference](http://cbmstuff.com/blingboard64/blingbox_shortcuts.html)):
per-key RGB, settings that survive power cycles, a modifier-key command layer, macros, a
diagnostic mode and a WiFi web UI.  The 128 deserves the same, and four of the five issues
below turn out to be the same project once you decide to put a microcontroller on the board.

## Where rev 2.3 stands

Facts pulled from [`pcb/C128-keyboard.kicad_pcb`](https://codeberg.org/jflitton/the-c128-keyboard-project/src/branch/main/pcb/C128-keyboard.kicad_pcb) (rev 2.3, KiCad 10) in the-c128-keyboard-project and the parts in that repo:

- 92 switch positions in a passive 8-row x 11-column matrix (COL8..COL10 are the C128's extra
  K0..K2 lines), plus RESTORE, 40/80 and CAPS LOCK as dedicated lines.  Two-layer, 1.6 mm,
  roughly 395 x 111 mm plus the spacebar tab, which brings the depth to 126 mm.
- Switches are on the front (F.Cu); all ICs and passives are on the back (B.Cu).
- **Lock keys.**  Three MAX16054 push-button on/off controllers (U1..U3) turn the momentary
  CAPS LOCK (SW91), 40/80 (SW92) and SHIFT LOCK (SW89) switches into toggles.
  U1 and U2 drive the CAPS LOCK and 40/80 host lines directly from their push-pull /OUT pin.
  U3 drives a 74AUC1G66 analog switch (U4) that shorts COL1 to ROW7, the left-shift matrix
  position.  Each lock key footprint has a single-color LED position fed from VCC through a
  330 ohm resistor (R1..R3), lit while locked.  C1..C3 (220 pF) sit on K0..K2.
- **Connector.**  CN2 is a Molex 200528-0260, a 26-way 1.0 mm horizontal FFC, on the
  *switch side* at about 207 mm from the left board edge and 13 mm from the rear edge, i.e.
  between the ESC/function row and the number row, under the plate.  Its pin order is the
  original mechboard order, not the C128's, so the flat cable ends in a pinout no Commodore
  understands.  The `c128-mech-keyboard-adapter` project next door exists purely to remap those
  26 pins onto the stock DB25 order.  +5 V and GND each get one or two pins.
- **Spacebar.**  SW52 uses a custom footprint, `MX-6.25_7_9U-ReversedStabilizers-NoLED`, centerd
  under N.  Its library file has stabilizer holes at +/-49.9 mm (6.25u, 100 mm), +/-57.15 mm
  (7u, 114.3 mm) and +/-66.7 mm (9u, 133.35 mm), but the copy on the board, and the NPTH
  drill file it was fabricated from, has only +/-49.886 and +/-62.675 mm (125.35 mm), with
  both the 3.05 mm and 4.0 mm holes for screw-in stabs.  The
  stock C128 spacebar is 9u (the keycap legend map lists it as width 9), and the plate STEP is
  cut for that.
- **Per-key printed parts** when reusing Mitsumi keycaps: one stem adapter per key
  (`adapter_mitsumi_regular_keycap_...` / `..._function_keycap_...`, about 7 x 7 x 6 mm, two
  variants) and one `shim_keyswitch` per switch (a 14 x 14 x 1 mm frame between the switch
  bottom and the PCB that makes up for the mid-height switch's 1 mm shorter lower housing, so
  switch stems and the PCB-mounted stabilizer stems sit at the same height).  The README covers the adapters and recommends batches
  of 10 to 12 for consistency.  That is roughly 184 small parts to print, sort and press for
  a full board, before the 2u and spacebar stabilizer adapters.

## Issue 1: lock state does not survive a power cycle

**Symptom.**  Every power-up comes up with CAPS LOCK, SHIFT LOCK and 40/80 all off.
The MAX16054 powers up with OUT low and has no non-volatile state.

**Why it matters more on a 128 than it sounds.**  The KERNAL samples the 40/80 line once at
reset to decide whether to boot into the VIC 40-column or VDC 80-column screen.  On a stock
keyboard the mechanical latch simply stays down for years.  On this board an 80-column user
has to press 40/80 during the first fraction of a second after power-on, or press it and then
reset the machine, every single time.  CAPS LOCK and SHIFT LOCK are read continuously so they
are merely annoying.

**Options.**

1. *MX-style mechanical lock switches.*  Cherry MX Lock is long discontinued and the clones
   are scarce, none exist in the Outemu mid-low form factor the README recommends, and the
   key would sit at a different height.  No LED, no indicator.  Not recommended.
2. *Power-on default jumpers (no firmware).*  Put an XOR gate (74LVC1G86) between each
   MAX16054 output and its host line, with the other XOR input on a solder jumper.  The
   jumper picks the state at power-on and the key still toggles relative to it.  Three tiny
   parts, keeps the board dumb.  It is a default, not persistence: the state after toggling is
   lost at the next power cycle, which is fine for the common case (always 80 columns).
   Worth doing only if a rev 2.x respin ships before the microcontroller board.
3. *Supercap-backed MAX16054s.*  Possible in principle (the ICs draw microamps) but the LED
   supply has to be split off, and the push-pull outputs would back-feed the host lines while
   the C128 is off unless they are buffered open-drain.  Fiddly for a partial result.  Skip.
4. *Microcontroller.*  Read the three lock keys, hold the state in flash, drive CAPS LOCK and
   40/80 through open-drain transistors to ground exactly as the mechanical switches did, and
   drive the shift-lock analog switch (or, on the crosspoint design below, just close the
   left-shift crosspoint).  Write flash only on change, so wear is a non-issue.

**Recommendation.**  Option 4, as part of the rev 3 board ([rev3-plan.md](rev3-plan.md)).  Two details
matter:

- **40/80 must be asserted before the KERNAL samples it**, which is early in the reset
  sequence.  MCU boot times range from tens of milliseconds (RP2040) to a few hundred
  (ESP32 with the default bootloader), so this needs measuring on the bench: scope the +5 V
  rail and the 40/80 line and find the sampling window.  The robust circuit does not depend on
  boot time at all: an N-channel MOSFET pulls 40/80 low, its gate is pulled up (asserted, 80
  columns) by default through a solder-jumper-selectable resistor, and the MCU drives the gate
  low once it has booted and read the stored state.  The user's saved preference and the
  jumper default should normally agree.
- **Indicators** move to the per-key RGB LEDs of issue 2; if a build has no LEDs populated,
  the three lock keys keep dedicated LED positions at the head of the LED chain (see below).

## Issue 2: no lighting

Every keyboard should have it, yes.  What it can realistically do on this board:

- The keycaps are opaque, whether original Mitsumi caps or the planned double-shot set, so
  per-key RGB reads as glow around and under the caps and as bright status indicators on the
  three lock keys, not as lit legends.  That is still the whole Blingboard64 effect.
- **LED type:** SK6812 MINI, the 3.5 x 3.5 mm top-mount part.  It sits on the front of the
  board in the SMD LED pocket the switch's bottom housing already has, so no PCB cutout and no
  switch trimming.  (The reverse-mount MINI-E in a board cutout was considered; it solves a
  problem this switch does not have and complicates the board.)  The LEDs are a DNP option: a
  board with no LEDs is electrically the same keyboard.
- **Light path is proven.**  The rev 2.3 board's three lock-key LEDs shine through the Outemu
  mid-height switches.  Those are through-hole LEDs and the housings needed trimming to take
  them; the switch pocket is sized for a 3528-style SMD LED, which the SK6812 MINI is, so rev 3
  needs no trimming.  A single MINI under one switch on a bare rev 2.3 board confirms the fit
  before 92 are laid out.
- **Chain order:** WS2812-class LEDs are a series chain, so a missing LED breaks everything
  after it.  Route the chain SHIFT LOCK -> CAPS LOCK -> 40/80 first, then snake through the
  rest of the board.  A minimal build then populates three LEDs and gets lock indicators for
  free, and the firmware's "LED count" setting handles the rest.
- **Data line:** 3.3 V MCU data into a 5 V LED chain wants a level shifter
  (74AHCT1G125) on the first LED's data input.
- **Power is the real constraint.**  Rough figures:

  | Load | Current |
  |---|---|
  | 92 SK6812 idle | ~90 mA |
  | 92 SK6812 at ~25 % white | ~0.9 A |
  | 92 SK6812 full white | ~3.5 A |
  | MCU (ESP32-S3, WiFi off / AP on) | ~50 mA / ~300 mA peaks |

  The keyboard +5 V arrives on a single connector pin with a single GND return, through a
  printed kk-style connector on the flat or one DB25 pin on the 128D, from a 5 V rail that the
  mainboard already leans on.  Treat about 0.5 A as the ceiling for keyboard-header power:
  enforce a global current cap in firmware (brightness limiter, as Blingbox's 1..16 scale
  implies), fit a PTC fuse and bulk capacitance, and add a **USB-C 5 V input** (power only,
  with an ideal-diode or Schottky OR so both can be connected).  This is exactly the
  workaround CBMstuff tells Ultimate64 owners to use.  The USB-C port doubles as the firmware
  and configuration port.
- **Optional extras that cost almost nothing:** a 3-pin header on the end of the chain for an
  external RGB LED that replaces the C128's front power LED (the "Razzle LED" idea), and a
  second header for an underglow strip inside the printed 128D case.

Per-key LEDs are 92 more SMD parts on the switch side.  Decision (see the rev 3 plan): every
SMD part on rev 3 is placed by the fab, LEDs on the front and everything else on the back, so
the builder only solders through-hole parts.  A board ordered without LEDs is electrically the
same keyboard.

## Issue 3: the FFC connector is under the plate and speaks the wrong pinout

**Symptoms.**  The flat cable has to be threaded out from under the plate, the connector is
inaccessible once the keyboard is assembled, and a flat-flex cable cannot be crimped into
anything a Commodore accepts, so every build needs the separate crossover adapter board to
reach a stock C128 or Open128 connector.  The original 128 simply soldered plain wires to the
keyboard PCB; the printed 1 x 25 housing in this repo mimics the original plug on the
mainboard end.

**Plan.**

1. **Move the connector to the back of the board**, near the rear edge.  The ICs already
   live on the back, the stock keyboard ribbon on a flat C128 runs under the keyboard anyway,
   and the printed 128D case has 31 mm of height at the rear.  Check the clearance to the
   flat's RF shield and mainboard before fixing the exact spot.  A right-angle DB25 on the
   rear edge is not an option: the top row of switches is only 10 mm from the edge.
2. **Adopt the stock C128 pin order on the board** so the cable is straight-through and the
   crossover adapter becomes unnecessary.  The order is documented in the adapter's README;
   note that with the stock pinout there is exactly one +5 V pin (4) and one GND pin (1),
   which is another reason for the USB-C input in issue 2.
3. **Drop the FFC for floppy-style ribbon**: one 2 x 13 0.1" footprint on the back, laid
   out in D-sub IDC order, and 26-way 0.05" ribbon cable.  A 128D cable is the ribbon crimped
   to an IDC DB25.  A flat cable is the same ribbon split at the far end into kk-style crimp
   pins in the printed 1 x 25 housing.  At the keyboard end the ribbon mates to an IDC box
   header where there is 9 mm of room (128D case, bench) and is soldered straight into the
   pads where there is not (the flat), which works without fanning because the ribbon's
   1.27 mm conductors alternate between the footprint's two rows.  No adapter board in any
   case.
4. Mark the adapter project as needed only for rev 2.x boards.

## Issue 4: assembly is tedious with a shim and an adapter under every key

The count is the problem: ~92 stem adapters plus ~92 shims, printed in small batches, each
pressed individually.  The uncommitted `tighter_standard_keycap_adapters.3mf` shows the adapter
fit is still being tuned as well.

**The shim.**  The Outemu mid-height switch's lower housing is about 1 mm shorter than a
standard MX switch's.  The screw-in stabilizers sit directly on the PCB and their housings
hold the plate at the standard 5 mm above the PCB, so a mid-height switch clipped into the
plate would float 1 mm above the board.  The 1 mm shim under each switch fills that gap, which
puts the switch stems and the stabilizer stems at the same height.  Ways to get rid of 92 of
them:

- *Let the plate sit 1 mm lower and move the 1 mm to the stabilizer adapters.*  Enlarge the
  plate's stabilizer clearance cutouts so they clear the screw-in housings' shoulders; the
  plate then drops to 4 mm above the PCB, the mid-height switches sit directly on the board,
  and the shims go away.  The stabilizer stems now stand 1 mm proud of the switch stems, so
  the existing printed 2u and spacebar stabilizer adapters (only a handful per board) get
  1 mm shorter, i.e. the Cherry insert seats 1 mm deeper in them.  The keycap-to-switch
  adapter is untouched, so no extra wiggle on the keycaps.  Keycap height above the plate,
  and therefore above the case, does not change; what changes is the plate-to-PCB gap, so
  **the whole keyboard stack is 1 mm thinner below the plate**.  That matters in the flat
  128's wedge case, where the space between the keyboard PCB and the RF shield is the tight
  dimension.  A larger stabilizer clearance costs nothing on the full-height/MX-cap build,
  so one cutout geometry can serve both plate variants.  Recommended, pending the checks
  below.
- *One shim sheet instead of 92 shims.*  A 1 mm sheet laid on the PCB under all the switches,
  with holes for pins and pegs and windows for the top-side LEDs.  Works; it is the second
  choice for the Mitsumi-cap build and the only shim option for MX caps on mid-height switches.
  **Built 2026-09-23** as an OpenSCAD generator driven by the board and plate data, two
  panels for a 256 mm bed; not part of this repository.
- *A longer keycap adapter.*  Rejected: more stem engagement lost, more keycap wiggle.
- *Mid-height stabilizers.*  Nobody makes a stabilizer that is exactly "MX minus 1 mm".
  The low-profile stabilizers that exist (Gateron low-profile sets sold by Keychron, Kailh
  Choc, the Outemu low-profile plate stabilizers Redragon ships as spares) are matched to
  their own, much shorter, switch families and would sit far too low.  Not a path.

Checks before cutting a plate: that the mid-height switch's clips still engage a 1.5 mm
plate normally with the plate 1 mm lower (they should, the difference is in the lower
housing); that the stabilizer housing tops, now 1 mm further through the plate, clear the
underside of the Mitsumi 2u and spacebar caps at full travel (this is the one place the
1 mm is taken from above the plate rather than below it); and that the stabilizer adapters
(spacebar 8.9 mm, 2u 7.2 mm tall today) still hold the Cherry insert securely when 1 mm
shorter.

**The three builds and what each needs.**  The mid-height switch has a standard MX cross
stem, so MX keycaps fit it directly; the only question is height.

| Build | Plate-to-PCB | Shims | Printed adapters | Notes |
|---|---|---|---|---|
| Mitsumi caps on mid-height switches | 4 mm (plate rests 1 mm lower, enlarged stab clearance) | none | keycap stem adapters; 2u and spacebar stab adapters 1 mm shorter | the printed stab adapters absorb the 1 mm |
| SP MX caps on mid-height switches | 5 mm (standard) | yes, or the one-piece shim sheet | none | molded caps have fixed stabilizer inserts, so the switch stem must be at standard height: the shim (or sheet) is mandatory here.  Same keycap height as full-height switches; you get the shorter travel, nothing else |
| SP MX caps on full-height switches | 5 mm (standard) | none | none | the plain build: clips engage the plate, any MX switch works |

One plate file serves all three: the enlarged stabilizer clearance is harmless at 5 mm, and
the 4 mm position simply happens when there is no shim.  For MX caps the case-clearance
question (is a standard-height MX cap too tall for the flat 128's bezel?) is the same for
mid-height and full-height switches, since the shim puts the mid-height stem at full height.

**Adapters.**

- *Short term:* print them as row-length combs on a thin sprue at 19.05 mm pitch.  A comb
  presses onto a whole row's stems in one go and snaps apart afterwards.  Fewer, more
  consistent print batches and far less handling, same parts count in the end.
- *Real fix:* the MX-compatible keycap set that the [keycaps](../keycaps/) work is preparing.
  Signature Plastics has quoted it (2026-09-18): $67 a set plain, $95 with front legends, at
  a 50-set minimum; see [keycaps/front_legend_vendors.md](../keycaps/front_legend_vendors.md).
  With MX caps and full-height switches there are no adapters and no shims at all.  That
  configuration is still untested for keycap height and case clearance on the flat, which is
  the next thing to measure once a sample set exists.


## Issue 5: allow a standard 6.25u spacebar

Decision: support the standard 6.25u bar next to the stock 9u.  (A 6.5u option was
considered and dropped; 6.25u is what every MX keycap set ships.)  Since then Signature
Plastics has confirmed the project's own set will include a 9u spacebar, so the stock plate
serves both the Mitsumi-cap and the SP-cap builds; 6.25u remains for anyone using a generic
set.

**Where it stands.**  The PCB is already done: the spacebar footprint has the 6.25u
(100 mm) stabilizer hole set, in both the 3.05 mm and 4.0 mm sizes for screw-in stabs, and
the switch stays centerd under N.  The board outline's spacebar tab is wider than needed and
can stay.

**Work items.**

1. Plate: **done** as KiCad boards for aluminum-PCB fabrication, `pcb/plate/plate-9u.kicad_pcb`
   and `plate-6.25u.kicad_pcb`, generated from the STEP model (see the rev 3 plan).  Stabilizers
   are PCB-mount screw-in (decided), so the plate only needs clearance slots for the housings and
   wires and the PCB carries the 3.05 mm and 4.0 mm holes, which the spacebar footprint already has.
2. Cosmetics: a 6.25u bar leaves about 1.4u of empty plate on each side of the spacebar
   row.  In the printed 128D case the bezel can close in; on a flat C128 the case opening is
   fixed and the gap will show.  No extra keys go there; SHIFT LOCK is the command modifier
   on every build.


## Decisions and where the plan lives

- No rev 2.4.  Rev 2.3 remains the dumb board; the next spin is rev 3.
- Rev 3 is the microcontroller-plus-crosspoint board.  Architecture, schematic and layout
  changes, firmware feature order, BOM delta, bench proofs and work breakdown are in
  [rev3-plan.md](rev3-plan.md).
- Spacebar: 6.25u plate variant, no FN or macro keys beside the bar.
- Stabilizers: PCB-mount screw-in everywhere; the plate carries clearance only.
- Plate: order it as a 1.5 mm aluminum-core PCB from the board fab instead of laser-cut
  steel, generated from the same switch positions as the PCB.  Details in the rev 3 plan.
- A thin insulating bottom cover for flat builds, with mounting holes added to the PCB for it
  (rev 2.3 has none).  Specified in the rev 3 plan.
- Shim: drop it by enlarging the plate's stabilizer clearance so the plate sits 1 mm lower
  on mid-height builds, and deepen the stabilizer adapters 1 mm.  Tracked here and in the
  rev 3 plate section, since it is a plate/printables change.
