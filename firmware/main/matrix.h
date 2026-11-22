// Physical switch matrix scanner: rows read with pull-ups, columns selected one at a time
// through the 74HC154 (or two 74HC138s on the bench), plus GPIO columns on the rev 3 board,
// or every column straight from GPIO in the simulator.  Sizes come from keymap.h.
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "keymap.h"

// One scan's worth of key state: bit c of state[r] is set while key (r, c) is down.
typedef struct {
    uint32_t rows[MATRIX_ROWS];
} matrix_state_t;

void matrix_init(void);

// Scan once (about MATRIX_COLS x 30 us) and return the raw, undebounced state.
void matrix_scan(matrix_state_t *out);

// Debounced state, updated by matrix_tick(); call matrix_tick() every millisecond.
// Returns true when the debounced state changed since the previous tick.
bool matrix_tick(void);
const matrix_state_t *matrix_debounced(void);

static inline bool matrix_key(const matrix_state_t *s, int row, int col) {
    return (s->rows[row] >> col) & 1;
}
