// Rev 3 keyboard firmware, bench milestone 1+2: scan the physical matrix, mirror it into
// the CH446Q so the C128 sees the keys, virtual lock keys with saved state, key names and
// a few commands over the USB console.
//
// Console (115200 on the native USB port), single-character commands:
//   ?  help        d  dump state       x  open every crosspoint (then re-apply shift lock)
//   S  toggle SHIFT LOCK   C  toggle CAPS LOCK   8  toggle 40/80   R  press RESTORE 100 ms
//   r  RUN/STOP + RESTORE
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#if CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG
#include "driver/usb_serial_jtag.h"
#include "driver/usb_serial_jtag_vfs.h"
#else
#include "driver/uart.h"
#include "driver/uart_vfs.h"
#endif
#include "esp_log.h"
#include "esp_timer.h"
#include "pins.h"
#include "keymap.h"
#include "matrix.h"
#include "ch446q.h"
#include "locks.h"

static const char *TAG = "c128kb";

static const char *key_name(int r, int c)
{
    const char *n = KEY_NAMES[r][c];
    return n ? n : "?";
}

// mirror one physical key change into the host matrix, or handle a lock key
static void on_key(int r, int c, bool down)
{
    uint8_t h = KEY_HOST[r][c];
    if (h == HOST_NONE) return;
    if (h < HOST_LOCK_SHIFT) {               // a crosspoint: host row in the high nibble
        ch446q_set(h >> 4, h & 0x0F, down);
        return;
    }
    if (!down) return;                       // lock keys act on press
    switch (h) {
    case HOST_LOCK_SHIFT: locks_toggle(LOCK_SHIFT); break;
    case HOST_LOCK_CAPS:  locks_toggle(LOCK_CAPS); break;
    case HOST_LOCK_4080:  locks_toggle(LOCK_4080); break;
    default: break;
    }
}

static void press_for(int r, int c, int ms)
{
    ch446q_set(r, c, true);
    vTaskDelay(pdMS_TO_TICKS(ms));
    ch446q_set(r, c, false);
}

// scan-pass timing, for checking the 1 ms budget on real hardware and in the simulator
static volatile uint32_t scan_last_us, scan_max_us;

static void dump(void)
{
    const matrix_state_t *s = matrix_debounced();
    printf("scan pass %lu us (max %lu us)\n", (unsigned long)scan_last_us, (unsigned long)scan_max_us);
    printf("shift=%d caps=%d 80col=%d restore=%d  down:", locks_get(LOCK_SHIFT), locks_get(LOCK_CAPS),
           locks_get(LOCK_4080), restore_pressed());
    for (int r = 0; r < MATRIX_ROWS; r++)
        for (int c = 0; c < MATRIX_COLS; c++)
            if (matrix_key(s, r, c)) printf(" %s(%d,%d)", key_name(r, c), r, c);
    printf("\n");
}

static void console_task(void *arg)
{
    for (;;) {
        int ch = getchar();
        if (ch < 0) { vTaskDelay(pdMS_TO_TICKS(10)); continue; }
        switch (ch) {
        case '?': printf("? d x S C 8 R r\n"); break;
        case 'd': dump(); break;
        case 'x': ch446q_reset(); locks_set(LOCK_SHIFT, locks_get(LOCK_SHIFT)); printf("crosspoint cleared\n"); break;
        case 'S': locks_toggle(LOCK_SHIFT); break;
        case 'C': locks_toggle(LOCK_CAPS); break;
        case '8': locks_toggle(LOCK_4080); break;
        case 'R': restore_drive(true); vTaskDelay(pdMS_TO_TICKS(100)); restore_drive(false); printf("RESTORE\n"); break;
        case 'r':                                      // RUN/STOP is host (7, 7)
            ch446q_set(7, 7, true); vTaskDelay(pdMS_TO_TICKS(30));
            restore_drive(true); vTaskDelay(pdMS_TO_TICKS(100)); restore_drive(false);
            vTaskDelay(pdMS_TO_TICKS(30)); ch446q_set(7, 7, false);
            printf("RUN/STOP+RESTORE\n"); break;
        default: break;
        }
    }
}

// One matrix pass per millisecond.  The debounce counter in matrix.c counts passes, so it
// only means milliseconds if this really is 1 ms; the tick rate is set to 1 kHz in
// sdkconfig.defaults, and this check refuses to build a period that rounds to zero ticks.
#define SCAN_PERIOD_TICKS pdMS_TO_TICKS(1)
_Static_assert(pdMS_TO_TICKS(1) >= 1, "CONFIG_FREERTOS_HZ must be 1000 for the 1 ms scan period");

static void scan_task(void *arg)
{
    matrix_state_t prev;
    memset(&prev, 0, sizeof prev);
    bool restore_was = false;
    TickType_t last = xTaskGetTickCount();
    for (;;) {
        bool restore_now = restore_pressed();          // not in the matrix: own sense line
        if (restore_now != restore_was) {
            restore_was = restore_now;
            printf("%s RESTORE\n", restore_now ? "down" : "up  ");
        }
        int64_t t0 = esp_timer_get_time();
        bool changed = matrix_tick();
        scan_last_us = (uint32_t)(esp_timer_get_time() - t0);
        if (scan_last_us > scan_max_us) scan_max_us = scan_last_us;
        if (changed) {
            const matrix_state_t *cur = matrix_debounced();
            for (int r = 0; r < MATRIX_ROWS; r++) {
                uint32_t diff = cur->rows[r] ^ prev.rows[r];
                for (int c = 0; diff; c++, diff >>= 1) {
                    if (!(diff & 1)) continue;
                    bool down = (cur->rows[r] >> c) & 1;
                    on_key(r, c, down);
                    printf("%s %s (%d,%d)\n", down ? "down" : "up  ", key_name(r, c), r, c);
                }
            }
            prev = *cur;
        }
        // 1 kHz scan.  If a pass ever overruns the period, xTaskDelayUntil returns pdFALSE
        // without blocking; re-anchor and yield one tick so lower-priority tasks and the
        // idle task (which feeds the task watchdog) still get the CPU.
        if (xTaskDelayUntil(&last, SCAN_PERIOD_TICKS) == pdFALSE) {
            last = xTaskGetTickCount();
            vTaskDelay(1);
        }
    }
}

void app_main(void)
{
    // blocking stdin: USB Serial/JTAG on the board, UART0 in the Wokwi simulator build
#if CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG
    usb_serial_jtag_driver_config_t cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    usb_serial_jtag_driver_install(&cfg);
    usb_serial_jtag_vfs_use_driver();
#else
    uart_driver_install(UART_NUM_0, 256, 0, 0, NULL, 0);
    uart_vfs_dev_use_driver(UART_NUM_0);
#endif

    ESP_LOGI(TAG, "rev 3 bench firmware");
    ch446q_init();          // everything open first
    locks_init();           // then restore saved lock state (may close the shift crosspoint)
    matrix_init();

    xTaskCreate(scan_task, "scan", 4096, NULL, 10, NULL);
    xTaskCreate(console_task, "console", 4096, NULL, 5, NULL);
    (void)press_for;
}
