# LED power switch (rev 3, before the first order)

A high-side switch on the LEDs' 5 V, so the firmware can turn the lighting fully off.  Dark
SK6812 MINIs still draw roughly 1 mA each, about 90 mA for the chain of 92, and the board has
no way to stop that today.  The switch is what makes "LEDs off" in the UI really off, and it
is what would let a battery case (see the wireless 128D idea) last days instead of about one.

## Why the plane is the part that moves

Every LED and its 100n take 5 V only through their own via into the In2 plane (laid by
`route_keys.py`, 184 pads).  So the plane becomes the switched rail, **+5V_LED**, and the
per-key copper does not change at all.  What has to move is everything else that sits on
+5V_SYS today and reaches it through the plane:

| Part | Where (mm) | After |
|---|---|---|
| D2, USB diode (VBUS in) | 104, 88 | stays on +5V_SYS |
| U2 AP7361C LDO, C6 10u at its input | 93-104, 114 | stays on +5V_SYS |
| U4 74AHCT1G125 LED buffer, C9 its 100n | 101-107, 100 | stays on +5V_SYS |
| **D1, Commodore diode (+5V_KB_F in)** | **212, 115** | stays on +5V_SYS: needs a link to the MCU corner |
| C5 220u | 316, 90 | moves to +5V_LED (it is the LEDs' burst reservoir) |
| J3 external LED header, pin 1 | 239, 115 | moves to +5V_LED (switched with the chain) |

D1 is 108 mm from the rest, in the crosspoint pocket.  Today the plane joins them; after the
change a **+5V_SYS track** does.  The clean place for it is In2 itself: a 1.0 mm track on
In2.Cu from D1 to the MCU corner, which the +5V_LED fill flows around.  It carries the
Commodore-powered LED current, held under F1's 1.1 A by the firmware's current cap, so keep it
1.0 mm wide.  The slot it cuts in the 5 V plane is harmless for slow signals on B.Cu.

## Circuit

```
 +5V_SYS ──┬──────────────── S  Q4 AO3401A (P-FET)  D ──┬── +5V_LED (In2 plane, LEDs, J3, C5)
           │                         G                   │
       R13 100k                      │               C13 220n  (gate-drain: soft start)
           │                         │                   │
           └─────────────────────────┴───────────────────┘   (LED_PWR_GATE)
                                     │
                                 R14 10k
                                     │
                                     D  Q5 2N7002
 MCU_LED_EN (IO38) ──┬────────────── G
                 R15 100k            S
                     │               │
                    GND             GND
```

- **Q4** AO3401A, SOT-23, LCSC C15127 (JLCPCB basic).  About 50-60 mOhm at -4.5 V gate: at 1 A
  it drops ~60 mV and dissipates ~60 mW.
- **R13** 100k gate to source: Q4 is **off** whenever nothing pulls its gate down, so the LEDs
  stay dark through power-up and boot.  That also spares the Commodore's rail the LEDs'
  power-on surge, and stops SK6812s flashing random colours at power-up.
- **Q5** 2N7002 (as Q1-Q3, LCSC C8545).  A 3.3 V GPIO cannot turn off a P-FET whose source is at
  5 V, so Q5 does the level shift.
- **R15** 100k holds Q5's gate low while the ESP32's pins float at reset.
- **R14** 10k and **C13** 220n slow Q4's turn-on so charging the LED rail does not surge through
  F1.  The LED rail carries C5 220u plus 92 x 100n plus C12, about 250 uF.  With these values the
  rail should ramp in about 4 ms, an inrush of about 0.3 A.  Check the ramp on the bench and
  adjust C13 (larger is slower).  The gate settles at -4.5 V (R13/R14).
- **C12** 10u on +5V_LED next to Q4's drain, and **C14** 10u on +5V_SYS by U2: C5 moves to the
  LED side, so the ESP32's 5 V input keeps a reservoir of its own.
- **GPIO: IO38** (U1 pad 34, west edge of the module, next to U4).  It is free and is not a
  strapping pin.  Avoid IO3, IO45 and IO46, which are.
- **Net names:** `MCU_LED_EN` (IO38 to Q5's gate), `LED_PWR_GATE` (Q4's gate), `+5V_LED`.  Add
  `+5V_LED` to the Power net class.

### Parts

| Ref | Value | Footprint | LCSC | Note |
|---|---|---|---|---|
| Q4 | AO3401A | SOT-23 | C15127 | new line |
| Q5 | 2N7002 | SOT-23 | C8545 | as Q1-Q3 |
| R13, R15 | 100k | 0603 | C25803 | as R5, R7, R12 |
| R14 | 10k | 0603 | C25804 | as R1, R2 |
| C13 | 220n | 0603 | C21120 | new line |
| C12, C14 | 10u | 1206 | C13585 | as C6, C7; 10u on +5V_SYS is enough beside C6 |

Check the two new numbers (C15127, C21120) on lcsc.com before ordering, as for every other part.

## Firmware rules

- **Off:** finish the frame, hold the data line **low** (MCU_LED_DATA, so U4's output and J3's
  data are low), then drive IO38 low.  U4 stays on +5V_SYS, and a high data line into an
  unpowered LED feeds that LED backwards through its data input.
- **On:** drive IO38 high, wait for the rail (10 ms covers the ~4 ms soft start), then send a full
  frame; LEDs come up dark and need one.
- **Boot:** IO38 starts low, so the chain is off until the LED engine starts.

## Doing it

1. **Schematic: done in `pcb/tools/gen_sch.py`.**
   - The switch is drawn at the top right of the MCU sheet.
   - The LEDs, their 100n, C5 and J3 pin 1 are on +5V_LED, and IO38 is `MCU_LED_EN`.
   - `pinmaps.json` and `firmware/main/pins.h` (`PIN_LED_EN`) follow.
   - Regenerate with `docker compose run --rm -e KICAD_SYMBOLS=/usr/share/kicad/symbols kicad python3 pcb/tools/gen_sch.py`.
2. **Board: done 2026-11-27.**
   - In2 is the +5V_LED plane.  Q4, Q5, R13-R15 and C12-C14 sit on the back in the channel
     under the top row, x 111-140, y 107-114.
   - The rest of the board is the hand placement from before the switch.  An automatic
     placement (KiCadRoutingTools, the `krt` service) was tried and set aside: it routed no
     better and left the groups untidy.
   - KiCadRoutingTools' router laid everything except the locked copper (`route_keys`, the
     host lines, `plane_taps`), held to the project's own rules (`--escalation board
     --no-fix-drc-settings`).  +5V_SYS runs as 0.5 mm tracks on the outer layers, so there is
     no In2 link.
   - The USB crossing at J1 was routed by hand, then `tidy.py`, `silk.py` and `plane_taps.py`
     were run.
3. **Checks:**
   - DRC with schematic parity.
   - Nothing on +5V_SYS left as an island.
   - `fab.py` writes the order files.
   - The new parts' rotations look right in JLCPCB's placement preview.
