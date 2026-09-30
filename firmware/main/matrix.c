#include "matrix.h"
#include "pins.h"
#include "driver/gpio.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include <string.h>

#ifndef MATRIX_DIRECT_COLUMNS
#define MATRIX_DIRECT_COLUMNS 0      // 1 = simulator: one GPIO per column, no decoder
#endif

// PIN_DIRECT_COLS includes the native USB pins (19, 20), strapping pins (3, 45, 46) and, on
// octal-PSRAM devkits, the PSRAM bus (35-37).  Harmless in Wokwi, which is the only place
// this mode runs; on a real devkit it would kill the USB console or stop the chip booting.
#if MATRIX_DIRECT_COLUMNS && CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG
#error "MATRIX_DIRECT_COLUMNS is for the Wokwi build only; real hardware needs the column decoder"
#endif
#define DEBOUNCE_MS 5
#define SETTLE_US   20               // decoder + 1 k + row capacitance settle time

// Short busy-wait on the microsecond timer.  esp_rom_delay_us counts CPU cycles instead,
// which is fine on silicon but runs many times slower than the timer in the Wokwi
// simulator, where it stretched a 240 us pass past the 1 ms period and starved every
// other task.  The timer-based wait behaves the same in both places.
static inline void settle(uint32_t us)
{
    int64_t t0 = esp_timer_get_time();
    while (esp_timer_get_time() - t0 < us) { }
}

static const int ROW_PINS[MATRIX_ROWS] = {PIN_ROW0, PIN_ROW1, PIN_ROW2, PIN_ROW3,
                                          PIN_ROW4, PIN_ROW5, PIN_ROW6, PIN_ROW7};
#if MATRIX_DIRECT_COLUMNS
static const int COL_PINS[MATRIX_COLS] = PIN_DIRECT_COLS;
#else
static const int SEL_PINS[4] = {PIN_COLSEL0, PIN_COLSEL1, PIN_COLSEL2, PIN_COLSEL3};
#endif

static matrix_state_t debounced;
static matrix_state_t last_raw;
static uint8_t stable_ms[MATRIX_ROWS][MATRIX_COLS];

static void select_column(int c)
{
#if MATRIX_DIRECT_COLUMNS
    // release the previously selected column, pull the new one low: two pin writes, not twelve
    static int current = -1;
    if (current >= 0) gpio_set_level(COL_PINS[current], 1);
    if (c >= 0) gpio_set_level(COL_PINS[c], 0);
    current = c;
#else
    for (int b = 0; b < 4; b++) gpio_set_level(SEL_PINS[b], (c >> b) & 1);
#endif
}

void matrix_init(void)
{
    gpio_config_t in = {
        .pin_bit_mask = 0, .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_ENABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE, .intr_type = GPIO_INTR_DISABLE,
    };
    for (int r = 0; r < MATRIX_ROWS; r++) in.pin_bit_mask |= 1ULL << ROW_PINS[r];
    gpio_config(&in);

    gpio_config_t out = {.pin_bit_mask = 0, .mode = GPIO_MODE_OUTPUT};
#if MATRIX_DIRECT_COLUMNS
    // every column high before the pins become outputs; they would otherwise start low, and
    // select_column() only raises a column it has selected before
    for (int c = 0; c < MATRIX_COLS; c++) {
        gpio_set_level(COL_PINS[c], 1);
        out.pin_bit_mask |= 1ULL << COL_PINS[c];
    }
#else
    for (int b = 0; b < 4; b++) out.pin_bit_mask |= 1ULL << SEL_PINS[b];
#endif
    gpio_config(&out);
    // park on an unused decoder output so no column sits low between scans
#if !MATRIX_DIRECT_COLUMNS
    select_column(15);
#endif
    memset(&debounced, 0, sizeof debounced);
    memset(&last_raw, 0, sizeof last_raw);
    memset(stable_ms, 0, sizeof stable_ms);
}

void matrix_scan(matrix_state_t *out)
{
    memset(out, 0, sizeof *out);
    for (int c = 0; c < MATRIX_COLS; c++) {
        select_column(c);
        settle(SETTLE_US);
        for (int r = 0; r < MATRIX_ROWS; r++)
            if (!gpio_get_level(ROW_PINS[r])) out->rows[r] |= 1u << c;     // active low
    }
#if !MATRIX_DIRECT_COLUMNS
    select_column(15);
#else
    select_column(-1);
#endif
}

bool matrix_tick(void)
{
    matrix_state_t raw;
    matrix_scan(&raw);
    bool changed = false;
    for (int r = 0; r < MATRIX_ROWS; r++) {
        for (int c = 0; c < MATRIX_COLS; c++) {
            bool now = (raw.rows[r] >> c) & 1;
            bool was = (last_raw.rows[r] >> c) & 1;
            bool deb = (debounced.rows[r] >> c) & 1;
            if (now != was) stable_ms[r][c] = 0;                 // input moved: restart the clock
            else if (stable_ms[r][c] < 255) stable_ms[r][c]++;
            if (now != deb && stable_ms[r][c] >= DEBOUNCE_MS) {  // stable long enough: accept
                if (now) debounced.rows[r] |= 1u << c; else debounced.rows[r] &= ~(1u << c);
                changed = true;
            }
        }
    }
    last_raw = raw;
    return changed;
}

const matrix_state_t *matrix_debounced(void) { return &debounced; }
