// SK6812 / WS2812 chain on one GPIO, driven by the RMT peripheral.
//
// The encoder follows ESP-IDF's led_strip example (Apache-2.0): a bytes encoder turns each
// bit into a high/low pulse pair, then a copy encoder appends the reset gap.  Timing is the
// SK6812's at a 10 MHz RMT clock: 0 = 0.3 us high, 0.9 us low; 1 = 0.6 us high, 0.6 us low;
// reset = 80 us low (the SK6812 wants over 80; WS2812B parts are happy with it too).
#include <stdlib.h>
#include <string.h>
#include "driver/rmt_tx.h"
#include "esp_check.h"
#include "ws2812.h"

#define RES_HZ   10000000                // 0.1 us per tick
#define T0H 3
#define T0L 9
#define T1H 6
#define T1L 6
#define RESET_TICKS 800

static const char *TAG = "ws2812";

typedef struct {
    rmt_encoder_t base;
    rmt_encoder_t *bytes;
    rmt_encoder_t *copy;
    int state;                           // 0 = sending pixels, 1 = sending reset
    rmt_symbol_word_t reset;
} strip_encoder_t;

static size_t encode(rmt_encoder_t *enc, rmt_channel_handle_t ch, const void *data, size_t size,
                     rmt_encode_state_t *ret_state)
{
    strip_encoder_t *s = __containerof(enc, strip_encoder_t, base);
    rmt_encode_state_t st = RMT_ENCODING_RESET, out = RMT_ENCODING_RESET;
    size_t n = 0;
    if (s->state == 0) {
        n += s->bytes->encode(s->bytes, ch, data, size, &st);
        if (st & RMT_ENCODING_COMPLETE) s->state = 1;
        if (st & RMT_ENCODING_MEM_FULL) { out |= RMT_ENCODING_MEM_FULL; goto done; }
    }
    if (s->state == 1) {
        n += s->copy->encode(s->copy, ch, &s->reset, sizeof s->reset, &st);
        if (st & RMT_ENCODING_COMPLETE) { s->state = RMT_ENCODING_RESET; out |= RMT_ENCODING_COMPLETE; }
        if (st & RMT_ENCODING_MEM_FULL) out |= RMT_ENCODING_MEM_FULL;
    }
done:
    *ret_state = out;
    return n;
}

static esp_err_t del(rmt_encoder_t *enc)
{
    strip_encoder_t *s = __containerof(enc, strip_encoder_t, base);
    rmt_del_encoder(s->bytes);
    rmt_del_encoder(s->copy);
    free(s);
    return ESP_OK;
}

static esp_err_t reset(rmt_encoder_t *enc)
{
    strip_encoder_t *s = __containerof(enc, strip_encoder_t, base);
    rmt_encoder_reset(s->bytes);
    rmt_encoder_reset(s->copy);
    s->state = RMT_ENCODING_RESET;
    return ESP_OK;
}

static rmt_channel_handle_t chan;
static rmt_encoder_t *encoder;

esp_err_t ws2812_init(int gpio, int max_leds)
{
    rmt_tx_channel_config_t cfg = {
        .gpio_num = gpio,
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = RES_HZ,
        .mem_block_symbols = 64,
        .trans_queue_depth = 2,
    };
    ESP_RETURN_ON_ERROR(rmt_new_tx_channel(&cfg, &chan), TAG, "channel");

    strip_encoder_t *s = calloc(1, sizeof *s);
    ESP_RETURN_ON_FALSE(s, ESP_ERR_NO_MEM, TAG, "encoder");
    s->base.encode = encode;
    s->base.del = del;
    s->base.reset = reset;
    rmt_bytes_encoder_config_t bc = {
        .bit0 = {.level0 = 1, .duration0 = T0H, .level1 = 0, .duration1 = T0L},
        .bit1 = {.level0 = 1, .duration0 = T1H, .level1 = 0, .duration1 = T1L},
        .flags.msb_first = 1,
    };
    ESP_RETURN_ON_ERROR(rmt_new_bytes_encoder(&bc, &s->bytes), TAG, "bytes encoder");
    rmt_copy_encoder_config_t cc = {};
    ESP_RETURN_ON_ERROR(rmt_new_copy_encoder(&cc, &s->copy), TAG, "copy encoder");
    s->reset = (rmt_symbol_word_t){.level0 = 0, .duration0 = RESET_TICKS / 2,
                                   .level1 = 0, .duration1 = RESET_TICKS / 2};
    encoder = &s->base;
    (void)max_leds;
    return rmt_enable(chan);
}

esp_err_t ws2812_show(const uint8_t *grb, int n)
{
    rmt_transmit_config_t tc = {.loop_count = 0};
    ESP_RETURN_ON_ERROR(rmt_transmit(chan, encoder, grb, (size_t)n * 3, &tc), TAG, "transmit");
    return rmt_tx_wait_all_done(chan, 50);
}
