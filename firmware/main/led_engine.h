// The LED engine's frame maths: patterns, key actions, lock indicators, brightness, gamma and
// the current cap.  No ESP-IDF calls, so it builds and runs on the host for tests; leds.c
// drives it from a task and sends the frames out.
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define LED_MAX       128      // chain length limit (the board has 92, the bench strip 60)
#define LED_PATTERNS  12       // 0 .. 11
#define LED_ACTIONS   7        // 0 .. 6
#define LED_LEVELS    16       // brightness 1 .. 16
#define LED_SPEEDS    10       // speed 1 .. 10

typedef struct {
    uint8_t  pattern;          // 0 .. LED_PATTERNS - 1
    uint8_t  pattern_bri;      // 1 .. 16
    uint8_t  speed;            // 1 .. 10
    uint8_t  action;           // 0 .. LED_ACTIONS - 1
    uint8_t  action_bri;       // 1 .. 16
    uint16_t cap_ma;           // current cap for the whole chain
    uint8_t  count;            // LEDs in the chain
} led_settings_t;

typedef struct {
    bool shift, caps, col80;   // lock states (col80: the 40/80 key is down = 80 columns)
} led_locks_t;

extern const char *const LED_PATTERN_NAMES[LED_PATTERNS];
extern const char *const LED_ACTION_NAMES[LED_ACTIONS];

void led_defaults(led_settings_t *s);
void led_clamp(led_settings_t *s);           // pull every field into range

void engine_reset(uint32_t seed);
// A key went down or up; `led` is its LED (LED_OF_KEY), `now_ms` a free-running clock.
void engine_key(const led_settings_t *s, int led, bool down, uint32_t now_ms);
// One frame: `grb` gets s->count pixels, 3 bytes each.  Returns the estimated chain current
// in mA after the cap.
uint32_t engine_frame(const led_settings_t *s, led_locks_t locks, uint32_t now_ms, uint8_t *grb);

// exposed for tests
uint8_t led_level_scale(int level);          // brightness 1 .. 16 -> 0 .. 255
uint32_t led_estimate_ua(const uint8_t *grb, int n);
