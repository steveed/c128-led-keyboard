// SK6812 / WS2812 chain on one GPIO, driven by the RMT peripheral.
#pragma once
#include <stdint.h>
#include "esp_err.h"

esp_err_t ws2812_init(int gpio, int max_leds);
// Send `n` pixels, 3 bytes each in G, R, B order, and wait until the frame is out (about
// 30 us per LED: under 3 ms for 92), so the buffer is free again when this returns.
esp_err_t ws2812_show(const uint8_t *grb, int n);
