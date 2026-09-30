// Physical switch matrix scanner: 8 rows read with pull-ups, 12 columns selected one at a
// time through the 74HC154 (or two 74HC138s, or directly from GPIO on the bench).
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "keymap.h"

// One scan's worth of key state: bit c of state[r] is set while key (r, c) is down.
typedef struct {
    uint16_t rows[MATRIX_ROWS];
} matrix_state_t;

void matrix_init(void);

// Scan once (about 12 x 30 us) and return the raw, undebounced state.
void matrix_scan(matrix_state_t *out);

// Debounced state, updated by matrix_tick(); call matrix_tick() every millisecond.
// Returns true when the debounced state changed since the previous tick.
bool matrix_tick(void);
const matrix_state_t *matrix_debounced(void);

static inline bool matrix_key(const matrix_state_t *s, int row, int col) {
    return (s->rows[row] >> col) & 1;
}
