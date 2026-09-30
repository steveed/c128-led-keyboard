// GPIO plan for the rev 3 board and the DevKitC-1 bench rig.  Identical on both, see
// pcb/tools/pinmaps.json and pcb/bench/README.md.
#pragma once

// physical matrix
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

// Simulator only (make build-wokwi): the 12 columns straight from GPIO, because Wokwi has no
// decoder model.  Not for a real devkit: 19/20 are its USB port, 3/45/46 are strapping pins
// and 35-37 are the PSRAM bus on R8 kits; matrix.c refuses to build this for the USB console.
#define PIN_DIRECT_COLS { 14, 21, 47, 48, 45, 46, 3, 35, 36, 37, 19, 20 }
