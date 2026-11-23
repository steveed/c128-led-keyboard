#include "ch446q.h"
#include "crosspoint_map.h"
#include "pins.h"
#include "driver/gpio.h"
#include "esp_rom_sys.h"

// Datasheet minimums are 10 ns edges and 7 ns setup; we use 1 us everywhere, which is still
// far faster than the KERNAL can notice and keeps the bit-bang immune to bus noise.
#define T_US 1

static inline void pulse_high(int pin)
{
    gpio_set_level(pin, 1);
    esp_rom_delay_us(T_US);
    gpio_set_level(pin, 0);
    esp_rom_delay_us(T_US);
}

void ch446q_init(void)
{
    gpio_config_t out = {
        .pin_bit_mask = (1ULL << PIN_XP_CK) | (1ULL << PIN_XP_DAT) | (1ULL << PIN_XP_STB) | (1ULL << PIN_XP_RST),
        .mode = GPIO_MODE_OUTPUT,
    };
    gpio_config(&out);
    gpio_set_level(PIN_XP_CK, 0);
    gpio_set_level(PIN_XP_DAT, 0);
    gpio_set_level(PIN_XP_STB, 0);
    // R10 held RST high through boot; take over, then release with everything open
    gpio_set_level(PIN_XP_RST, 1);
    esp_rom_delay_us(5);
    gpio_set_level(PIN_XP_RST, 0);
}

void ch446q_reset(void)
{
    gpio_set_level(PIN_XP_RST, 1);
    esp_rom_delay_us(5);
    gpio_set_level(PIN_XP_RST, 0);
}

void ch446q_set(int row, int col, bool on)
{
    if (row < 0 || row > 7 || col < 0 || col > 10)
        return;
    // host line to the chip pin that carries it, then the 7-bit address, MSB first:
    // AY2 AY1 AY0 AX3 AX2 AX1 AX0 = y * 16 + x
    int addr = (XP_Y_OF_ROW[row] << 4) | XP_X_OF_COL[col];
    for (int bit = 6; bit >= 0; bit--) {
        gpio_set_level(PIN_XP_DAT, (addr >> bit) & 1);
        esp_rom_delay_us(T_US);
        pulse_high(PIN_XP_CK);                    // latched on the rising edge
    }
    gpio_set_level(PIN_XP_DAT, on);               // switch data ...
    esp_rom_delay_us(T_US);
    pulse_high(PIN_XP_STB);                       // ... written on STB's falling edge
}
