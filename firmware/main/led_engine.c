// The LED engine's frame maths.  See led_engine.h.
//
// A frame is built in four layers, in linear 0-255 color:
//   1. the pattern, at pattern brightness;
//   2. key actions on top (a flash, a ripple, ...), at key-action brightness;
//   3. the lock keys' own LEDs, lit while their lock is on, and the 40/80 strobe (the whole
//      board flashes green for 40 columns, gray for 80, when the key is toggled);
//   4. gamma, then the current cap: if the estimated chain current is over s->cap_ma the
//      whole frame is scaled down, so the cap holds whatever the pattern does.
#include <math.h>
#include <string.h>
#include "led_engine.h"
#include "led_map.h"

const char *const LED_PATTERN_NAMES[LED_PATTERNS] = {
    "off", "white", "commodore blue", "rainbow", "rainbow wave", "color cycle",
    "breathe", "scanner", "twinkle", "rain", "plasma", "vic-ii rows",
};
const char *const LED_ACTION_NAMES[LED_ACTIONS] = {
    "none", "flash white", "flash color", "ripple", "cross", "hold", "heat",
};

// SK6812 MINI-012: about 12 mA per color at full PWM, about 0.6 mA idle (datasheet)
#define UA_PER_STEP   47       // 12000 uA / 255
#define IDLE_UA       600

// the 16 VIC-II colors (Pepto's palette), for the vic-ii pattern and the 40/80 strobe
static const uint8_t VIC[16][3] = {
    {0, 0, 0}, {255, 255, 255}, {104, 55, 43}, {112, 164, 178}, {111, 61, 134}, {88, 141, 67},
    {53, 40, 121}, {184, 199, 111}, {111, 79, 37}, {67, 57, 0}, {154, 103, 89}, {68, 68, 68},
    {108, 108, 108}, {154, 210, 132}, {108, 94, 181}, {149, 149, 149},
};
#define VIC_GREEN 5
#define VIC_GRAY  12

static uint8_t gamma8[256];
static uint32_t rng;

typedef struct {
    uint8_t level;             // action intensity, 0 .. 255
    uint8_t hue;
    uint8_t heat;
    uint8_t twinkle;           // twinkle pattern: this LED's sparkle, 0 .. 255
    uint8_t twinkle_hue;
    bool    held;
} led_state_t;
static led_state_t st[LED_MAX];

#define RIPPLES 8
typedef struct { float x, y; uint32_t t0; uint8_t hue; bool on; } ripple_t;
static ripple_t ripples[RIPPLES];

static uint32_t last_ms;
static float anim_t;           // animation clock: ms scaled by speed, wrapped (see engine_frame)
#define ANIM_WRAP 4194304.0f   // 2^22: about 70 minutes at speed 6, still 0.5 ms resolution
static bool have_locks;
static led_locks_t prev_locks;
static uint32_t strobe_t0;
static bool strobe_on, strobe_80;

static uint32_t rnd(void)
{
    rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5;
    return rng;
}

// LED position: the board's map for the chain, a straight line for anything past it
static void pos(int i, int n, float *x, float *y)
{
    if (i < LED_CHAIN_LEN) { *x = LED_X[i]; *y = LED_Y[i]; return; }
    *x = n > 1 ? i * 255.0f / (n - 1) : 128;
    *y = 128;
}

// distance between two LEDs in board millimetres (the switch field is about 395 x 100 mm)
static float dist_mm(float x0, float y0, float x1, float y1)
{
    float dx = (x1 - x0) * (395.0f / 255), dy = (y1 - y0) * (100.0f / 255);
    return sqrtf(dx * dx + dy * dy);
}

static uint8_t hue(float v)   // any float -> 0 .. 255, wrapping (a plain cast is undefined past 255)
{
    float m = fmodf(v, 256.0f);
    return (uint8_t)(int)(m < 0 ? m + 256.0f : m);
}

static void hsv(uint8_t h, uint8_t s, uint8_t v, uint8_t rgb[3])
{
    if (!s) { rgb[0] = rgb[1] = rgb[2] = v; return; }
    unsigned region = h / 43, rem = (h - region * 43) * 6;
    uint8_t p = (v * (255 - s)) >> 8, q = (v * (255 - ((s * rem) >> 8))) >> 8,
            t = (v * (255 - ((s * (255 - rem)) >> 8))) >> 8;
    switch (region) {
    case 0:  rgb[0] = v; rgb[1] = t; rgb[2] = p; break;
    case 1:  rgb[0] = q; rgb[1] = v; rgb[2] = p; break;
    case 2:  rgb[0] = p; rgb[1] = v; rgb[2] = t; break;
    case 3:  rgb[0] = p; rgb[1] = q; rgb[2] = v; break;
    case 4:  rgb[0] = t; rgb[1] = p; rgb[2] = v; break;
    default: rgb[0] = v; rgb[1] = p; rgb[2] = q; break;
    }
}

void led_defaults(led_settings_t *s)
{
    s->pattern = 4;            // rainbow wave
    s->pattern_bri = 6;
    s->speed = 5;
    s->action = 1;             // flash white
    s->action_bri = 12;
    s->cap_ma = 500;
    s->count = LED_CHAIN_LEN;
}

void led_clamp(led_settings_t *s)
{
#define CLAMP(v, lo, hi) ((v) < (lo) ? (lo) : (v) > (hi) ? (hi) : (v))
    s->pattern = CLAMP(s->pattern, 0, LED_PATTERNS - 1);
    s->pattern_bri = CLAMP(s->pattern_bri, 1, LED_LEVELS);
    s->speed = CLAMP(s->speed, 1, LED_SPEEDS);
    s->action = CLAMP(s->action, 0, LED_ACTIONS - 1);
    s->action_bri = CLAMP(s->action_bri, 1, LED_LEVELS);
    s->cap_ma = CLAMP(s->cap_ma, 50, 3000);
    s->count = CLAMP(s->count, 1, LED_MAX);
#undef CLAMP
}

// brightness level 1 .. 16 -> scale 8 .. 255, square law so the low steps stay fine
uint8_t led_level_scale(int level)
{
    if (level < 1) level = 1;
    if (level > LED_LEVELS) level = LED_LEVELS;
    return (uint8_t)(8 + 247 * (level - 1) * (level - 1) / ((LED_LEVELS - 1) * (LED_LEVELS - 1)));
}

void engine_reset(uint32_t seed)
{
    for (int i = 0; i < 256; i++) gamma8[i] = (uint8_t)lroundf(255.0f * powf(i / 255.0f, 2.2f));
    rng = seed ? seed : 0x12345678;
    memset(st, 0, sizeof st);
    memset(ripples, 0, sizeof ripples);
    have_locks = false;
    anim_t = 0;
    strobe_on = false;
    last_ms = 0;
}

// speed 1 .. 10 -> time multiplier 0.1 .. 3.5
static float speed_mul(int speed)
{
    static const uint8_t m[LED_SPEEDS] = {1, 2, 3, 5, 7, 10, 14, 19, 26, 35};
    return m[(speed < 1 ? 1 : speed > LED_SPEEDS ? LED_SPEEDS : speed) - 1] / 10.0f;
}

void engine_key(const led_settings_t *s, int led, bool down, uint32_t now_ms)
{
    if (led < 0 || led >= s->count || led >= LED_MAX) return;
    led_state_t *e = &st[led];
    e->held = down;
    if (!down) return;
    float x, y;
    pos(led, s->count, &x, &y);
    switch (s->action) {
    case 1: e->level = 255; e->hue = 0; break;
    case 2: e->level = 255; e->hue = (uint8_t)rnd(); break;
    case 3:
        for (int k = 0; k < RIPPLES; k++)
            if (!ripples[k].on || k == RIPPLES - 1) {
                ripples[k] = (ripple_t){x, y, now_ms, (uint8_t)rnd(), true};
                break;
            }
        break;
    case 4:                                    // light the key's row and column
        for (int i = 0; i < s->count; i++) {
            float xi, yi;
            pos(i, s->count, &xi, &yi);
            if (fabsf(xi - x) < 6 || fabsf(yi - y) < 12) { st[i].level = 255; st[i].hue = 0; }
        }
        break;
    case 5: e->level = 255; e->hue = 0; break;
    case 6: e->heat = e->heat > 255 - 64 ? 255 : e->heat + 64; break;
    default: break;
    }
}

static void pattern_color(const led_settings_t *s, int i, float x, float y, float t, uint8_t c[3])
{
    switch (s->pattern) {
    case 0: c[0] = c[1] = c[2] = 0; break;
    case 1: c[0] = 255; c[1] = 220; c[2] = 180; break;
    case 2: c[0] = VIC[14][0]; c[1] = VIC[14][1]; c[2] = VIC[14][2]; break;
    case 3: hsv(hue(x), 255, 255, c); break;
    case 4: hsv(hue(x + t / 16), 255, 255, c); break;
    case 5: hsv(hue(t / 16), 255, 255, c); break;
    case 6: {
        float v = 0.55f + 0.45f * sinf(t / 1000.0f * 1.6f);
        hsv(hue(t / 64), 255, (uint8_t)(255 * v), c);
        break;
    }
    case 7: {                                  // a red bar sweeping across and back
        float p = fmodf(t / 8, 510);
        if (p > 255) p = 510 - p;
        float v = 255 - fabsf(x - p) * 6;
        c[0] = v > 0 ? (uint8_t)v : 0; c[1] = c[2] = 0;
        break;
    }
    case 8:                                    // twinkle: state kept per LED
        hsv(st[i].twinkle_hue, 160, st[i].twinkle, c);
        break;
    case 9: {                                  // rain: drops run down each column
        uint32_t h = ((uint32_t)(x / 13) * 2654435761u) >> 24;
        float ph = fmodf(t / 6 + h * 4, 400) - 60;
        float d = ph - y;
        float v = (d >= 0 && d < 60) ? 255 * (1 - d / 60) : 0;
        c[0] = 0; c[1] = (uint8_t)v; c[2] = (uint8_t)(v / 3);
        break;
    }
    case 10: {
        float v = sinf(x / 40 + t / 1000) + sinf(y / 30 - t / 1300) + sinf((x + y) / 50 + t / 1700);
        hsv(hue(v * 42 + 128), 255, 255, c);
        break;
    }
    case 11: {                                 // each key row its own VIC-II color, rotating
        int row = (int)(y / 43);
        const uint8_t *v = VIC[1 + (row + (int)(t / 2000)) % 15];
        c[0] = v[0]; c[1] = v[1]; c[2] = v[2];
        break;
    }
    default: c[0] = c[1] = c[2] = 0; break;
    }
}

static uint8_t mix(uint8_t a, uint8_t b, uint8_t k)  // a -> b by k / 255
{
    return (uint8_t)((a * (255 - k) + b * k) / 255);
}

uint32_t led_estimate_ua(const uint8_t *grb, int n)
{
    uint32_t ua = 0;
    for (int i = 0; i < 3 * n; i++) ua += grb[i] * UA_PER_STEP;
    return ua + (uint32_t)n * IDLE_UA;
}

uint32_t engine_frame(const led_settings_t *s, led_locks_t locks, uint32_t now_ms, uint8_t *grb)
{
    int n = s->count > LED_MAX ? LED_MAX : s->count;
    uint32_t dt = last_ms ? now_ms - last_ms : 0;
    if (dt > 200) dt = 200;
    last_ms = now_ms;
    anim_t = fmodf(anim_t + dt * speed_mul(s->speed), ANIM_WRAP);
    float t = anim_t;
    uint8_t pb = led_level_scale(s->pattern_bri), ab = led_level_scale(s->action_bri);

    // 40/80 strobe on a change of the 40/80 lock
    if (have_locks && locks.col80 != prev_locks.col80) {
        strobe_on = true; strobe_t0 = now_ms; strobe_80 = locks.col80;
    }
    prev_locks = locks; have_locks = true;
    uint8_t strobe_k = 0;
    if (strobe_on) {
        uint32_t age = now_ms - strobe_t0;
        if (age >= 1500) strobe_on = false;
        else strobe_k = (uint8_t)(255 - age * 255 / 1500);
    }

    // decay: action flashes fade over about 400 ms (hold keeps a held key lit), heat over 6 s
    uint32_t fade = dt * 255 / 400, cool = dt * 255 / 6000 + (dt ? 1 : 0);
    for (int i = 0; i < n; i++) {
        led_state_t *e = &st[i];
        if (!(s->action == 5 && e->held)) e->level = e->level > fade ? e->level - fade : 0;
        e->heat = e->heat > cool ? e->heat - cool : 0;
        // twinkle: decay and respawn
        uint32_t tf = dt * 255 / 700;
        e->twinkle = e->twinkle > tf ? e->twinkle - tf : 0;
        if (s->pattern == 8 && (rnd() % 1000) < dt * speed_mul(s->speed) * 2) {
            e->twinkle = 255; e->twinkle_hue = (uint8_t)rnd();
        }
    }
    for (int k = 0; k < RIPPLES; k++)
        if (ripples[k].on && now_ms - ripples[k].t0 > 1200) ripples[k].on = false;

    for (int i = 0; i < n; i++) {
        float x, y;
        pos(i, n, &x, &y);
        uint8_t c[3], a[3];
        pattern_color(s, i, x, y, t, c);
        for (int k = 0; k < 3; k++) c[k] = (uint8_t)(c[k] * pb / 255);

        // key actions
        led_state_t *e = &st[i];
        uint8_t ak = 0;
        if (s->action == 2) { hsv(e->hue, 255, 255, a); ak = e->level; }
        else if (s->action == 6) {
            hsv((uint8_t)(170 - e->heat * 170 / 255), 255, 255, a);   // blue -> red
            ak = e->heat ? (e->heat < 64 ? e->heat * 4 : 255) : 0;
        } else if (s->action == 3) {
            a[0] = a[1] = a[2] = 0;
            for (int k = 0; k < RIPPLES; k++) {
                if (!ripples[k].on) continue;
                float r = (now_ms - ripples[k].t0) * 0.25f;   // 250 mm/s
                float d = fabsf(dist_mm(ripples[k].x, ripples[k].y, x, y) - r);
                if (d < 12) {
                    uint8_t kk = (uint8_t)(255 * (1 - d / 12) * (1 - (now_ms - ripples[k].t0) / 1200.0f));
                    if (kk > ak) { ak = kk; hsv(ripples[k].hue, 255, 255, a); }
                }
            }
        } else { a[0] = a[1] = a[2] = 255; ak = e->level; }
        if (ak) for (int k = 0; k < 3; k++) c[k] = mix(c[k], (uint8_t)(a[k] * ab / 255), ak);

        // lock keys' own LEDs, lit while locked
        if ((i == LED_LOCK_SHIFT && locks.shift) || (i == LED_LOCK_CAPS && locks.caps) ||
            (i == LED_LOCK_4080 && locks.col80))
            for (int k = 0; k < 3; k++) c[k] = ab;

        if (strobe_k) {
            const uint8_t *v = VIC[strobe_80 ? VIC_GRAY : VIC_GREEN];
            for (int k = 0; k < 3; k++) c[k] = mix(c[k], (uint8_t)(v[k] * ab / 255), strobe_k);
        }

        grb[3 * i + 0] = gamma8[c[1]];
        grb[3 * i + 1] = gamma8[c[0]];
        grb[3 * i + 2] = gamma8[c[2]];
    }

    // current cap: scale the whole frame so the estimate fits
    uint32_t ua = led_estimate_ua(grb, n), cap = (uint32_t)s->cap_ma * 1000, idle = (uint32_t)n * IDLE_UA;
    if (ua > cap) {
        uint32_t lit = ua - idle, room = cap > idle ? cap - idle : 0;
        for (int i = 0; i < 3 * n; i++) grb[i] = (uint8_t)((uint64_t)grb[i] * room / lit);
        ua = led_estimate_ua(grb, n);
    }
    return ua / 1000;
}
