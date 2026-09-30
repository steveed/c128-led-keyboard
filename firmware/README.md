# Rev 3 keyboard firmware

ESP-IDF project for the ESP32-S3.  What is here today is the bench firmware for milestones
1 and 2 of the plan: scan the physical matrix, mirror it into the CH446Q crosspoint so the
C128 sees the keys, the three lock keys as saved toggles, RESTORE sense and press, and a
console that prints key names and takes a few commands.  Everything else in the feature list
(LEDs, command layer, macros, WiFi, USB keyboard mode, network keyboard) builds on this.

## Development setup (macOS)

Nothing installs on the host except Docker Desktop and, for flashing, a Python venv with
`esptool` that the Makefile creates itself.

1. Install Docker Desktop and start it.
2. From this directory: `make build`.  The first run pulls Espressif's `espressif/idf`
   image (about 2 GB) and compiles; later builds take under a minute thanks to the ccache
   volume.  The build writes `build/c128kb.bin`.
3. Plug the DevKitC-1 in by its **USB** port (the one labeled USB, not UART).  It shows up
   as `/dev/cu.usbmodem*`.  `make flash` writes the bootloader, partition table and app.
   If the board does not enter download mode by itself, hold BOOT, tap RESET, release BOOT,
   then flash.
4. `make monitor` opens the console (screen, 115200; quit with ctrl-a then k).  Press `?`.

`make menuconfig` opens ESP-IDF's configuration UI in the container; the settings that
matter are pinned in `sdkconfig.defaults` so a fresh checkout builds identically.

Why the split: builds, package management and the toolchain live in the container so the
host never drifts from what CI would run.  Docker Desktop on macOS cannot pass a USB device
into a container, so the two steps that touch the port (flash, monitor) run on the host with
the smallest possible tool.

## Simulator (no hardware needed)

`make build-wokwi` builds a variant for the [Wokwi](https://wokwi.com) simulator: UART0
console instead of USB, and the twelve columns driven straight from GPIO instead of through
the decoder.  `wokwi/` holds the diagram (virtual keys, lock buttons, RESTORE, indicator LEDs
on the gate pins, a logic analyzer on the CH446Q lines) and its README explains how to run it.
It uses its own `build-wokwi/` directory and `sdkconfig`, so it never disturbs the hardware
build.  `make sim` runs it headless with the console on your terminal, and `make sim-test`
runs a scripted press of every button and fails if the console does not report each one.

## Layout

| File | What |
|---|---|
| `main/pins.h` | the GPIO plan, identical for the rev 3 board and the devkit rig |
| `main/matrix.c` | 1 kHz scan through the column decoder, 5 ms debounce; `MATRIX_DIRECT_COLUMNS` drives the columns straight from GPIO for the simulator |
| `main/ch446q.c` | CH446Q serial-mode driver: 7 address bits on CS/CK, DAT, STB pulse; RST |
| `main/locks.c` | SHIFT LOCK (left-shift crosspoint held), CAPS LOCK and 40/80 (open-drain gates), state in NVS; RESTORE sense/drive |
| `main/keymap.h` | physical (row, col) to key legend, generated from the rev 2.3 board by `tools/gen_keymap.py` |
| `main/main.c` | tasks: scan/mirror, console |
| `sdkconfig.defaults`, `partitions.csv` | ESP32-S3, 8 MB flash, USB Serial/JTAG console, NVS + app + storage partitions |

## Console

Single characters over the USB console:

| Key | Does |
|---|---|
| `?` | list commands |
| `d` | dump scan-pass time, lock state, RESTORE state and the keys currently down |
| `S` `C` `8` | toggle SHIFT LOCK, CAPS LOCK, 40/80 (saved to NVS; 40/80 applies at the next C128 reset) |
| `R` | press RESTORE for 100 ms through Q3 |
| `r` | RUN/STOP + RESTORE |
| `x` | open every crosspoint, then re-apply SHIFT LOCK |

Every debounced key change is printed as `down Return (1,0)`.

## Matrix conventions

Physical (row, column) equals the C128 matrix position, so the mirror is
`ch446q_set(row, col, down)` with no table.  Columns 8..10 are the K0..K2 lines.  Column 11
exists only on the rev 3 board and carries the three lock keys (rows 0, 1, 2 = SHIFT LOCK,
CAPS LOCK, 40/80); on the rev 2.3 bench board they are not scannable, so use the console
commands instead.  RESTORE is not in the matrix.

## The bench rig needs the decoder

`MATRIX_DIRECT_COLUMNS` (one GPIO per column, no decoder) is for the Wokwi build only.  Its
pin list uses the devkit's USB pins (19, 20), strapping pins (3, 45, 46) and, on R8 kits, the
PSRAM bus (35-37): fine in the simulator, but on a real devkit it kills the console or stops
the chip booting, so `matrix.c` refuses to build it with the USB console.  The devkit has no
twelve spare safe pins once the crosspoint, lock and LED lines are taken, so wire the column
decoder (two 74HC138s, or 74LS138s at 5 V; see the bench README).
