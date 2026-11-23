// Host tests for main/led_engine.c (no ESP-IDF).  `make test` builds and runs them for both
// boards (the rev 3 chain and the bench strip) with the container's gcc.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "led_engine.h"
#include "led_map.h"

static int failures;
#define CHECK(cond, ...) do { if (!(cond)) { failures++; printf("FAIL %s:%d: ", __FILE__, __LINE__); \
    printf(__VA_ARGS__); printf("\n"); } } while (0)

static uint8_t f[3 * LED_MAX];
static const led_locks_t NO_LOCKS = {false, false, false};

static led_settings_t quiet(void)           // pattern off, no action
{
    led_settings_t s;
    led_defaults(&s);
    s.pattern = 0;
    s.action = 0;
    return s;
}

static int lit(int i) { return f[3 * i] + f[3 * i + 1] + f[3 * i + 2]; }

static uint32_t run(const led_settings_t *s, led_locks_t lk, uint32_t from, uint32_t to)
{
    uint32_t ma = 0;
    for (uint32_t t = from; t <= to; t += 20) ma = engine_frame(s, lk, t, f);
    return ma;
}

static void test_levels(void)
{
    CHECK(led_level_scale(1) == 8, "level 1 -> %d", led_level_scale(1));
    CHECK(led_level_scale(16) == 255, "level 16 -> %d", led_level_scale(16));
    for (int l = 2; l <= 16; l++)
        CHECK(led_level_scale(l) > led_level_scale(l - 1), "level %d not brighter", l);
}

static void test_off_is_dark(void)
{
    engine_reset(1);
    led_settings_t s = quiet();
    uint32_t ma = run(&s, NO_LOCKS, 20, 1000);
    for (int i = 0; i < s.count; i++) CHECK(lit(i) == 0, "LED %d lit with pattern off", i);
    CHECK(ma == s.count * 600 / 1000, "idle current %u mA", (unsigned)ma);
}

static void test_cap(void)
{
    engine_reset(1);
    led_settings_t s;
    led_defaults(&s);
    s.pattern = 1;                          // white, full brightness: ~3 A uncapped on 92 LEDs
    s.pattern_bri = 16;
    s.cap_ma = 200;
    uint32_t ma = run(&s, NO_LOCKS, 20, 200);
    CHECK(ma <= 200, "capped frame draws %u mA", (unsigned)ma);
    CHECK(ma >= 150, "cap scaled too far: %u mA", (unsigned)ma);
    CHECK(led_estimate_ua(f, s.count) <= 200000u, "estimate over the cap");
    s.cap_ma = 3000;
    ma = run(&s, NO_LOCKS, 220, 400);
    CHECK(ma > 200, "uncapped white only %u mA", (unsigned)ma);
}

static void test_flash_fades(void)
{
    engine_reset(1);
    led_settings_t s = quiet();
    s.action = 1;
    int k = 10;
    run(&s, NO_LOCKS, 20, 100);
    engine_key(&s, k, true, 120);
    engine_key(&s, k, false, 140);
    engine_frame(&s, NO_LOCKS, 140, f);
    // action brightness 12 is 140 / 255 linear, about 70 per color after gamma
    CHECK(lit(k) > 100, "flashed LED only %d", lit(k));
    CHECK(lit(k + 1) == 0, "neighbor lit by a flash");
    run(&s, NO_LOCKS, 160, 800);
    CHECK(lit(k) == 0, "flash still lit after 650 ms: %d", lit(k));
}

static void test_hold(void)
{
    engine_reset(1);
    led_settings_t s = quiet();
    s.action = 5;
    run(&s, NO_LOCKS, 20, 100);
    engine_key(&s, 4, true, 100);
    run(&s, NO_LOCKS, 120, 1500);
    CHECK(lit(4) > 100, "held key dimmed to %d", lit(4));
    engine_key(&s, 4, false, 1500);
    run(&s, NO_LOCKS, 1520, 2200);
    CHECK(lit(4) == 0, "released key still lit: %d", lit(4));
}

static void test_ripple_spreads(void)
{
    engine_reset(1);
    led_settings_t s = quiet();
    s.action = 3;
    run(&s, NO_LOCKS, 20, 100);
    int k = LED_CHAIN_LEN / 2;
    engine_key(&s, k, true, 100);
    int seen = 0;
    uint8_t ever[LED_MAX] = {0};
    for (uint32_t t = 120; t < 1400; t += 20) {
        engine_frame(&s, NO_LOCKS, t, f);
        for (int i = 0; i < s.count; i++) if (lit(i)) ever[i] = 1;
    }
    for (int i = 0; i < s.count; i++) seen += ever[i];
    CHECK(seen > s.count / 4, "ripple reached only %d LEDs", seen);
    CHECK(lit(k) == 0, "ripple still lit at 1.3 s");
}

static void test_locks_and_strobe(void)
{
    engine_reset(1);
    led_settings_t s = quiet();
    led_locks_t lk = {true, false, false};
    run(&s, lk, 20, 100);
    CHECK(lit(LED_LOCK_SHIFT) > 0, "shift lock LED dark while locked");
    CHECK(lit(LED_LOCK_CAPS) == 0, "caps lock LED lit while unlocked");
    lk.col80 = true;                        // toggle 40/80: the board strobes gray
    engine_frame(&s, lk, 120, f);
    int far = LED_CHAIN_LEN - 1;
    CHECK(lit(far) > 0, "no 40/80 strobe");
    CHECK(f[3 * far] == f[3 * far + 1] && f[3 * far + 1] == f[3 * far + 2], "80-column strobe not gray");
    run(&s, lk, 140, 1800);
    CHECK(lit(far) == 0, "strobe still lit after 1.7 s");
    CHECK(lit(LED_LOCK_4080) > 0, "40/80 LED dark in 80 columns");
    lk.col80 = false;                       // back to 40: green
    engine_frame(&s, lk, 1820, f);
    CHECK(f[3 * far] > f[3 * far + 1], "40-column strobe not green (G %d R %d)", f[3 * far], f[3 * far + 1]);
}

static void test_patterns_move(void)
{
    for (int p = 3; p < LED_PATTERNS; p++) {
        if (p == 3) continue;                // the static rainbow doesn't move
        engine_reset(7);
        led_settings_t s = quiet();
        s.pattern = p;
        s.pattern_bri = 16;
        uint8_t a[3 * LED_MAX];
        run(&s, NO_LOCKS, 20, 1000);
        memcpy(a, f, sizeof a);
        run(&s, NO_LOCKS, 1020, 3600);        // the vic-ii rows step every 2 s
        CHECK(memcmp(a, f, 3 * s.count) != 0, "pattern %d (%s) did not change in 2.6 s", p, LED_PATTERN_NAMES[p]);
        int any = 0;
        for (int i = 0; i < s.count; i++) any |= lit(i);
        CHECK(any, "pattern %d (%s) dark", p, LED_PATTERN_NAMES[p]);
    }
}

static void test_long_uptime(void)
{
    // 49 days of free-running clock: the animation clock must keep moving smoothly
    engine_reset(3);
    led_settings_t s = quiet();
    s.pattern = 4;
    s.pattern_bri = 16;
    uint32_t t0 = 4000000000u;
    run(&s, NO_LOCKS, t0, t0 + 200);
    uint8_t a[3 * LED_MAX];
    memcpy(a, f, sizeof a);
    run(&s, NO_LOCKS, t0 + 220, t0 + 600);
    CHECK(memcmp(a, f, 3 * s.count) != 0, "rainbow wave frozen at 46 days uptime");
}

int main(void)
{
    test_levels();
    test_off_is_dark();
    test_cap();
    test_flash_fades();
    test_hold();
    test_ripple_spreads();
    test_locks_and_strobe();
    test_patterns_move();
    test_long_uptime();
    printf("%s: %s (%d LEDs)\n", BOARD_NAME, failures ? "FAILED" : "ok", LED_CHAIN_LEN);
    return failures ? 1 : 0;
}
