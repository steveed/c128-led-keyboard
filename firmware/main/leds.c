// The LED engine's task: per-key lighting on the SK6812 chain, settings saved to NVS.
//
// The scan task hands key changes over through a queue (it never waits on the LEDs); this
// task draws a frame every 20 ms with led_engine.c and sends it out over RMT.  Settings
// changes are saved 2 s after the last one, so stepping through the patterns doesn't wear
// the flash.
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "nvs.h"
#include "pins.h"
#include "keymap.h"
#include "led_map.h"
#include "led_engine.h"
#include "locks.h"
#include "ws2812.h"
#include "leds.h"

static const char *TAG = "leds";

#define FRAME_MS     20
#define SAVE_AFTER_MS 2000
#define CFG_VERSION  1

typedef struct { uint8_t version; led_settings_t s; } saved_t;

static led_settings_t cfg;
static QueueHandle_t events;            // uint16_t: led | down << 15
static nvs_handle_t nvs;
static volatile bool dirty;
static volatile uint32_t dirty_ms, last_ma;
static uint8_t frame[3 * LED_MAX];
static volatile bool blank_tail = true;  // send black past the chain's end (boot, count lowered)

static uint32_t now_ms(void) { return (uint32_t)(esp_timer_get_time() / 1000); }

static void load(void)
{
    led_defaults(&cfg);
    if (nvs_open("leds", NVS_READWRITE, &nvs) != ESP_OK) { nvs = 0; return; }
    saved_t sv;
    size_t len = sizeof sv;
    if (nvs_get_blob(nvs, "cfg", &sv, &len) == ESP_OK && len == sizeof sv && sv.version == CFG_VERSION)
        cfg = sv.s;
    led_clamp(&cfg);
}

static void save(void)
{
    if (!nvs) return;
    saved_t sv = {.version = CFG_VERSION, .s = cfg};
    nvs_set_blob(nvs, "cfg", &sv, sizeof sv);
    nvs_commit(nvs);
}

static void changed(void)
{
    led_clamp(&cfg);
    dirty = true;
    dirty_ms = now_ms();
}

static void led_task(void *arg)
{
    TickType_t last = xTaskGetTickCount();
    for (;;) {
        uint32_t t = now_ms();
        uint16_t ev;
        while (xQueueReceive(events, &ev, 0) == pdTRUE)
            engine_key(&cfg, ev & 0x7FFF, ev >> 15, t);
        led_locks_t lk = {locks_get(LOCK_SHIFT), locks_get(LOCK_CAPS), locks_get(LOCK_4080)};
        last_ma = engine_frame(&cfg, lk, t, frame);
        int n = cfg.count;
        if (blank_tail) {                 // LEDs past the end keep their last color otherwise
            blank_tail = false;
            memset(frame + 3 * n, 0, 3 * (LED_MAX - n));
            n = LED_MAX;
        }
        ws2812_show(frame, n);
        if (dirty && t - dirty_ms > SAVE_AFTER_MS) { dirty = false; save(); }
        vTaskDelayUntil(&last, pdMS_TO_TICKS(FRAME_MS));
    }
}

void leds_init(void)
{
    load();
    engine_reset((uint32_t)esp_timer_get_time() | 1);
    events = xQueueCreate(64, sizeof(uint16_t));
    ESP_ERROR_CHECK(ws2812_init(PIN_LED_DATA, LED_MAX));
    xTaskCreate(led_task, "leds", 4096, NULL, 4, NULL);
    ESP_LOGI(TAG, "%d LEDs, pattern %d (%s), cap %d mA", cfg.count, cfg.pattern,
             LED_PATTERN_NAMES[cfg.pattern], cfg.cap_ma);
}

static void post(int led, bool down)
{
    if (led == LED_NONE || !events) return;
    uint16_t ev = (uint16_t)(led | (down ? 0x8000 : 0));
    xQueueSend(events, &ev, 0);           // never block the scan; a full queue drops a flash
}

void leds_key(int row, int col, bool down) { post(LED_OF_KEY[row][col], down); }
void leds_restore(bool down) { post(LED_RESTORE, down); }

void leds_dump(void)
{
    printf("leds: pattern %d %s, brightness %d, speed %d; key action %d %s, brightness %d; "
           "cap %d mA (now ~%lu mA), %d LEDs\n",
           cfg.pattern, LED_PATTERN_NAMES[cfg.pattern], cfg.pattern_bri, cfg.speed,
           cfg.action, LED_ACTION_NAMES[cfg.action], cfg.action_bri, cfg.cap_ma,
           (unsigned long)last_ma, cfg.count);
}

bool leds_console(int ch)
{
    switch (ch) {
    case 'p': cfg.pattern = (cfg.pattern + 1) % LED_PATTERNS; break;
    case 'o': cfg.pattern = (cfg.pattern + LED_PATTERNS - 1) % LED_PATTERNS; break;
    case 'a': cfg.action = (cfg.action + 1) % LED_ACTIONS; break;
    case '+': cfg.pattern_bri++; break;
    case '-': if (cfg.pattern_bri > 1) cfg.pattern_bri--; break;
    case ']': cfg.action_bri++; break;
    case '[': if (cfg.action_bri > 1) cfg.action_bri--; break;
    case '>': cfg.speed++; break;
    case '<': if (cfg.speed > 1) cfg.speed--; break;
    case 'M': cfg.cap_ma += 50; break;
    case 'm': if (cfg.cap_ma > 50) cfg.cap_ma -= 50; break;
    case 'N': cfg.count++; break;
    case 'n': if (cfg.count > 1) { cfg.count--; blank_tail = true; } break;
    case 'z': led_defaults(&cfg); blank_tail = true; break;
    case 'l': leds_dump(); return true;
    default: return false;
    }
    changed();
    leds_dump();
    return true;
}
