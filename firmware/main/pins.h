// GPIO plan.  The rev 3 board (BOARD_REV3) takes its pins from pcb/tools/gen_sch.py GPIO
// (also in pcb/tools/pinmaps.json), chosen so each line leaves the module on the side that
// faces where it goes.  The DevKitC-1 bench rig keeps the plan it is wired to, in
// pcb/bench/README.md.
#pragma once

#if BOARD_REV3
// physical matrix: 6 x 20, decoder columns 0-14, then 15-19 straight from GPIO
#define PIN_ROW0        36
#define PIN_ROW1        26
#define PIN_ROW2        47
#define PIN_ROW3        33
#define PIN_ROW4        34
#define PIN_ROW5        48
#define DECODER_COLS    15     // 74HC154 outputs 0-14 are columns 0-14; output 15 is the park
#define PIN_GPIO_COLS   { 1, 2, 4, 5, 6 }         // columns 15-19
#define PIN_COLSEL0     18     // 74HC154 A0 ...
#define PIN_COLSEL1     17
#define PIN_COLSEL2     16
#define PIN_COLSEL3     15     // ... A3

// CH446Q crosspoint, serial address mode
#define PIN_XP_CK       11     // CS/CK
#define PIN_XP_DAT      12
#define PIN_XP_STB      10
#define PIN_XP_RST      13

// LEDs
#define PIN_LED_DATA    35
#define PIN_LED_EN      38     // high = LED power on (Q5 -> Q4, docs/led-power-switch.md); hold PIN_LED_DATA low before turning it off

// lock lines and RESTORE
#define PIN_4080_GATE   7      // high = pull 40/80 low = 80 columns
#define PIN_CAPLK_GATE  8      // high = CAPS LOCK down
#define PIN_RESTORE_SENSE 14   // input, internal pull-up; low = RESTORE pressed (diode D3)
#define PIN_RESTORE_GATE 9     // high = press RESTORE (Q3)

#else
// bench rig: scans the rev 2.3 board, 8 x 12 in the C128's order
#define PIN_ROW0        4
#define PIN_ROW1        5
#define PIN_ROW2        6
#define PIN_ROW3        7
#define PIN_ROW4        15
#define PIN_ROW5        16
#define PIN_ROW6        17
#define PIN_ROW7        18
#define PIN_COLSEL0     8      // 74HC154 A0 (or the two 74HC138s' A) ...
#define PIN_COLSEL1     9
#define PIN_COLSEL2     10
#define PIN_COLSEL3     11     // ... 74HC154 A3 / 74HC138 enable swap

// CH446Q crosspoint, serial address mode
#define PIN_XP_CK       12     // CS/CK
#define PIN_XP_DAT      38
#define PIN_XP_STB      39
#define PIN_XP_RST      40

// LEDs
#define PIN_LED_DATA    41

// lock lines and RESTORE
#define PIN_4080_GATE   42     // high = pull 40/80 low = 80 columns
#define PIN_CAPLK_GATE  2      // high = CAPS LOCK down
#define PIN_RESTORE_SENSE 1    // input, internal pull-up; low = RESTORE pressed (diode D3)
#define PIN_RESTORE_GATE 13    // high = press RESTORE (Q3)
#endif

// Simulator only (make build-wokwi): the 12 columns straight from GPIO, because Wokwi has no
// decoder model.  Not for a real devkit: 19/20 are its USB port, 3/45/46 are strapping pins
// and 35-37 are the PSRAM bus on R8 kits; matrix.c refuses to build this for the USB console.
#define PIN_DIRECT_COLS { 14, 21, 47, 48, 45, 46, 3, 35, 36, 37, 19, 20 }
