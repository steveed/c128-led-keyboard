// WCH CH446Q 8x16 analog crosspoint, serial address mode (P/S tied low).
// Y pins carry the C128 rows, X pins the C128 columns, in the order crosspoint_map.h gives
// (in order on the bench rig, routing order on the rev 3 board).  Datasheet: https://www.wch-ic.com/downloads/CH446DS1_PDF.html
#pragma once
#include <stdbool.h>

void ch446q_init(void);              // drives RST high then low: every switch open
void ch446q_reset(void);             // open every switch
void ch446q_set(int row, int col, bool on);   // host row 0..7, host column 0..10
