// GPIO plan for the rev 3 board and the DevKitC-1 bench rig.  Identical on both, see
// pcb/tools/pinmaps.json and pcb/bench/README.md.
#pragma once

// physical matrix.  The bench rig scans the rev 2.3 board, 8 x 12 in the C128's order; the
// rev 3 board (BOARD_REV3) scans 6 x 20: decoder columns 0-14, then 15-19 straight from GPIO,
// on the pins the bench's rows 6 and 7 use plus three spares.
#define PIN_ROW0        4
#define PIN_ROW1        5
#define PIN_ROW2        6
#define PIN_ROW3        7
#define PIN_ROW4        15
#define PIN_ROW5        16
#if BOARD_REV3
#define DECODER_COLS    15     // 74HC154 outputs 0-14 are columns 0-14; output 15 is the park
#define PIN_GPIO_COLS   { 17, 18, 14, 21, 35 }    // columns 15-19
#else
#define PIN_ROW6        17
#define PIN_ROW7        18
#endif
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
