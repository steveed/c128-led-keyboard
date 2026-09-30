#include "locks.h"
#include "pins.h"
#include "ch446q.h"
#include "driver/gpio.h"
#include "nvs_flash.h"
#include "nvs.h"
#include "esp_log.h"

static const char *TAG = "locks";
static const char *KEYS[LOCK_COUNT] = {"shift", "caps", "c4080"};
static bool state[LOCK_COUNT];
static nvs_handle_t nvs;

// SHIFT LOCK is the left-shift crosspoint held closed: host row 7, column 1
#define SHIFT_ROW 7
#define SHIFT_COL 1

static void apply(lock_t which)
{
    switch (which) {
    case LOCK_SHIFT: ch446q_set(SHIFT_ROW, SHIFT_COL, state[which]); break;
    case LOCK_CAPS:  gpio_set_level(PIN_CAPLK_GATE, state[which]); break;
    case LOCK_4080:  gpio_set_level(PIN_4080_GATE, state[which]); break;   // on = 80 columns
    default: break;
    }
}

void locks_init(void)
{
    gpio_config_t out = {.pin_bit_mask = (1ULL << PIN_CAPLK_GATE) | (1ULL << PIN_4080_GATE) | (1ULL << PIN_RESTORE_GATE),
                         .mode = GPIO_MODE_OUTPUT};
    gpio_config(&out);
    gpio_set_level(PIN_RESTORE_GATE, 0);
    gpio_config_t in = {.pin_bit_mask = 1ULL << PIN_RESTORE_SENSE, .mode = GPIO_MODE_INPUT,
                        .pull_up_en = GPIO_PULLUP_ENABLE};
    gpio_config(&in);

    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);
    ESP_ERROR_CHECK(nvs_open("locks", NVS_READWRITE, &nvs));
    for (int i = 0; i < LOCK_COUNT; i++) {
        uint8_t v = (i == LOCK_4080) ? 1 : 0;          // default: 80 columns, locks off
        nvs_get_u8(nvs, KEYS[i], &v);
        state[i] = v;
        apply(i);
    }
    ESP_LOGI(TAG, "restored: shift=%d caps=%d 80col=%d", state[0], state[1], state[2]);
}

bool locks_get(lock_t which) { return state[which]; }

void locks_set(lock_t which, bool on)
{
    if (state[which] == on) return;
    state[which] = on;
    apply(which);
    nvs_set_u8(nvs, KEYS[which], on);
    nvs_commit(nvs);
    ESP_LOGI(TAG, "%s -> %d", KEYS[which], on);
}

void locks_toggle(lock_t which) { locks_set(which, !state[which]); }

bool restore_pressed(void) { return gpio_get_level(PIN_RESTORE_SENSE) == 0; }
void restore_drive(bool press) { gpio_set_level(PIN_RESTORE_GATE, press); }
