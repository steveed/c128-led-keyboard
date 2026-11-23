// The LED engine's task: per-key lighting on the SK6812 chain, settings saved to NVS.
#pragma once
#include <stdbool.h>

void leds_init(void);                    // after locks_init (it opens NVS)
void leds_key(int row, int col, bool down);   // from the scan task: a scanned key changed
void leds_restore(bool down);            // RESTORE (its own line, but it has an LED)
// Console: handles the LED commands, returns false for any other character.
bool leds_console(int ch);
void leds_dump(void);
