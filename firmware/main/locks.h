// The three lock keys as firmware toggles with state saved to NVS, plus RESTORE.
#pragma once
#include <stdbool.h>

typedef enum { LOCK_SHIFT = 0, LOCK_CAPS = 1, LOCK_4080 = 2, LOCK_COUNT } lock_t;

void locks_init(void);                 // loads saved state and applies it to the hardware
bool locks_get(lock_t which);
void locks_set(lock_t which, bool on); // applies and saves
void locks_toggle(lock_t which);

// RESTORE: hard-wired switch, sensed through D3, pressable through Q3
bool restore_pressed(void);
void restore_drive(bool press);
