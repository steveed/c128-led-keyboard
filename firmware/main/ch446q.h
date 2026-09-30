// WCH CH446Q 8x16 analog crosspoint, serial address mode (P/S tied low).
// Y0..Y7 are the C128 rows, X0..X10 the C128 columns.  Datasheet: https://www.wch-ic.com/downloads/CH446DS1_PDF.html
#pragma once
#include <stdbool.h>

void ch446q_init(void);              // drives RST high then low: every switch open
void ch446q_reset(void);             // open every switch
void ch446q_set(int y, int x, bool on);   // y = host row 0..7, x = host column 0..15
