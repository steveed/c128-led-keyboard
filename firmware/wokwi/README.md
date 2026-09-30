# Simulating the firmware in Wokwi

[Wokwi](https://wokwi.com) simulates the ESP32-S3 well enough to run this firmware unmodified:
the real ESP-IDF binary boots, the scan task runs, GPIOs toggle, and the console works.  It
gives you a "test bench" with clickable keys, buttons for the lock keys and RESTORE, LEDs on
the gate pins, and a logic analyzer on the CH446Q control lines, with no hardware at all.

What it cannot do: there is no CH446Q model and no 74HC154 model, so the crosspoint writes
are only *observed* (logic analyzer), not acted on, and the columns are driven straight from
GPIO.  That is exactly what the `MATRIX_DIRECT_COLUMNS` build does.  That build is simulator
only: its column pins include the devkit's USB, strapping and PSRAM pins, which Wokwi does
not care about and a real devkit does (see the firmware README).

It has already paid for itself: the first run found two bugs that would have hit the real
devkit too (a 1 ms task delay that rounded to zero ticks and rebooted the chip in a loop, and
a scan pass that could starve every other task).  Both are fixed in `main.c` / `matrix.c`.

## Two ways to run it

### Headless, from the terminal (what `make sim` does)

1. Download the `wokwi-cli-macos-arm64` binary from the
   [wokwi-cli releases](https://github.com/wokwi/wokwi-cli/releases), put it at
   `~/.wokwi/bin/wokwi-cli` (or anywhere on `PATH`; override with `make WOKWI=/path sim`).
2. Create a CI token at https://wokwi.com/dashboard/ci and export it as `WOKWI_CLI_TOKEN`
   (for example in `~/.zshrc`).  The license file the VS Code extension stores is a
   different token and does not work here.
3. `make sim` builds the simulator variant and runs it with the console on your terminal.
   Type `?`, `d`, `R` and so on; ctrl-c ends it.
4. `make sim-test` runs `smoke.scenario.yaml`: it presses CAPS LOCK, SHIFT LOCK, 40/80 and
   RESTORE through the simulator's automation API and fails unless the console reports each
   one.  Exit code 0 is a pass.  Extend the scenario as features land; it is the start of a
   test suite that needs no hardware.

### Interactive, in VS Code

1. Install the **Wokwi Simulator** extension.  F1, **Wokwi: Request a new License**, sign in
   (a free account is enough) and let it send the license back to VS Code.
2. Open the `firmware/wokwi/` folder as the workspace (the extension wants `wokwi.toml` and
   `diagram.json` at the workspace root).
3. `make -C .. build-wokwi`, then F1, **Wokwi: Start Simulator**.

The console is **not** in the Output or Debug Console panels.  It is the **Terminal** tab,
in a terminal named *Wokwi Terminal*.  Click into it before typing commands.  Keep the
simulator tab visible; the extension pauses the simulation when it is hidden.

Rebuild after every code change and start the simulator again.  The hardware build in
`build/` is untouched; `make build` and `make flash` still do what they did.

## What is wired

The virtual devkit uses the same pins as `main/pins.h`, so nothing in the firmware knows it is
being simulated.

| Part | Connects | Firmware sees |
|---|---|---|
| 4x4 keypad | rows R1..R4 to GPIO 4, 5, 6, 7 (matrix rows 0..3); columns C1..C4 to GPIO 14, 21, 47, 48 (`PIN_DIRECT_COLS` 0..3) | the top-left 4x4 block of the C128 matrix |
| SHIFT LOCK, CAPS LOCK, 40/80 buttons | rows 0, 1, 2 to GPIO 20 (direct column 11) | the three lock keys as on the rev 3 board |
| RESTORE button | GPIO 1 to GND | RESTORE pressed (active low, like the D3 sense diode) |
| green LED "80 col" | GPIO 42 | Q1 gate: lit = 80 columns asserted |
| yellow LED "CAPS" | GPIO 2 | Q2 gate: lit = CAPS LOCK held down |
| red LED "RESTORE drive" | GPIO 13 | Q3 gate: lit while the firmware presses RESTORE |
| logic analyzer D0..D3 | GPIO 12, 38, 39, 40 | XP_CK, XP_DAT, XP_STB, XP_RST |
| `$serialMonitor` | the board's TX/RX (UART0, GPIO 43/44) | the console |

The two `$serialMonitor` lines in `connections` are required.  Without them the board boots
and runs but the serial monitor stays empty, which is confusing because the "80 col" LED
lights anyway (GPIO 42 is a JTAG pin with a pull-up at reset).

Keypad legends and the matrix positions behind them:

| | C1 (col 0) | C2 (col 1) | C3 (col 2) | C4 (col 3) |
|---|---|---|---|---|
| R1 (row 0) | ⌫ Inst/Del | 3 | 5 | 7 |
| R2 (row 1) | ↵ Return | W | R | Y |
| R3 (row 2) | ↔ Crsr Horiz | A | D | G |
| R4 (row 3) | F7 | 4 | 6 | 8 |

Keyboard shortcuts while the diagram has focus: `s` SHIFT LOCK, `c` CAPS LOCK, `v` 40/80,
`r` RESTORE.  Ctrl-click (Cmd-click) a button to make it stay down.  Click the keypad once and
the digit keys press the matching keypad key.

## What you should see

On boot the log shows `rev 3 bench firmware` and `restored: shift=0 caps=0 80col=1` (the
simulator's flash is blank on first run, so the defaults apply).  The "80 col" LED lights
immediately because the saved default asserts 80 columns.

- Press `W` on the keypad: `down W (1,1)`, then `up   W (1,1)` on release.  The logic
  analyzer records one seven-bit address write plus a strobe for each edge.
- Hold `W` and `R` together: both report down.  Add `A` and the fourth corner `D` is *not*
  reported, because the scan drives one column at a time.
- Click SHIFT LOCK: the lock log `shift -> 1`, then `down ShiftLock (0,11)`, plus a
  crosspoint write for (7,1).  Click again: `shift -> 0`.  Stop and restart the simulator: the
  state comes back from NVS.
- Click CAPS LOCK: `caps -> 1` and the yellow LED comes on.
- Click 40/80: `c4080 -> 0` and the green LED goes off (40 columns).  On the real machine
  this only takes effect at the next reset; the LED shows what the gate is doing now.
- Click RESTORE: `down RESTORE` / `up   RESTORE`.
- Type in the console: `?` lists commands; `R` flashes the red LED for 100 ms; `r` writes
  (7,7) to the crosspoint, flashes the LED, then releases (7,7); `d` dumps the scan-pass
  time, lock state, RESTORE and the keys currently down.

### Reading the crosspoint writes

`make sim`/`make sim-test` write the capture where `--vcd-file` points (add it to the make
line, or run `wokwi-cli` yourself); in VS Code it lands in this folder as `wokwi.vcd`
(ignored by git).  Open it with PulseView (sigrok) or a VCD viewer extension in VS Code.
Channels D0..D3 are CK, DAT, STB, RST.  A correct write looks like: CK toggles seven times
with DAT holding each address bit (MSB first: AY2 AY1 AY0 AX3 AX2 AX1 AX0), then DAT goes to
the switch state and STB pulses high.  RST pulses once at boot and whenever you send `x`.

## Limits and notes

- **Timing is approximate.**  Wokwi emulates GPIO register access slowly, so a scan pass
  that costs about 250 us on silicon takes about 1 ms in the simulator (`d` shows it).  The
  scan loop tolerates that, but the 5 ms debounce is really "five passes" and stretches
  accordingly.  Do not use the simulator to judge timing margins; use it for logic.
- The simulated console is UART0 (`sdkconfig.wokwi`).  Wokwi also supports the S3's USB
  Serial/JTAG console: add `"serialInterface": "USB_SERIAL_JTAG"` to the board's `attrs`,
  drop the `$serialMonitor` connections, and the hardware sdkconfig would work too.  UART0
  is kept because it is the documented default and it is what has been tested.
- GPIO 38 (XP_DAT) also feeds the devkit's on-board RGB LED in Wokwi's board model.  The LED
  may flicker during crosspoint writes; that is cosmetic.
- Only 16 of the 92 keys are on the keypad.  Add more `wokwi-membrane-keypad` parts on the
  remaining `PIN_DIRECT_COLS` pins if a test needs them; rows are shared.
- `wokwi-cli lint wokwi/` checks the diagram.  It reports the devkit as an "undocumented"
  part type; that is Wokwi's wording for every ESP32 board and is harmless.
- Next step, if the sim keeps earning its keep: Wokwi custom chips (C, compiled to
  WebAssembly) for the 74HC154 and the CH446Q, so the crosspoint state can be shown as an
  8x16 grid instead of decoded from a VCD.  A third chip could play the C128, scanning the
  crosspoint the way the CIA does and printing what the host would read.
