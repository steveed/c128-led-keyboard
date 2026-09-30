# Reading the firmware, for someone coming from Python, PHP and JavaScript

This walks through the bench firmware in the order it runs, and stops to explain the C and
ESP-IDF idioms the first time each one appears.  Read it with the files open; every heading
names one.

## The mental model, before any syntax

Three things about C that the languages you know hide from you:

1. **Nothing is checked at runtime.**  There are no exceptions, no bounds checks, no garbage
   collector.  An array index past the end reads whatever memory is there.  Functions
   report failure through return values, and it is on the caller to look.
2. **Every variable has a fixed size in bytes, chosen by you.**  `uint16_t` is exactly
   16 bits, unsigned, so it holds 0..65535 and wraps silently.  The firmware uses these
   fixed widths on purpose: a row of twelve key bits fits in a `uint16_t`.
3. **The program is compiled per file, then linked.**  Each `.c` file is compiled on its own
   with no knowledge of the others.  A `.h` header is how one file tells another "these
   functions and types exist"; the actual code lives in the `.c`.  That is why every module
   here comes as a pair.

And two about the environment:

4. **There is no operating system in the desktop sense.**  ESP-IDF is a library that includes
   FreeRTOS, a small scheduler that runs several *tasks* (think threads) on the two CPU cores.
   There is no process, no file system unless you add one, and `printf` goes to the USB port
   because we configured it so.
5. **`app_main` is the entry point,** not `main`.  ESP-IDF's own startup code runs first,
   brings up the CPU, flash and the console, then calls `app_main`.  When `app_main`
   returns, the tasks it created keep running; that is normal, not a crash.

## The build: `CMakeLists.txt`, `main/CMakeLists.txt`, `sdkconfig.defaults`

ESP-IDF projects are CMake projects.  The top-level `CMakeLists.txt` is three lines of
boilerplate that pull in ESP-IDF's build system and name the project (`c128kb`, which is
also the name of the output binary).

`main/CMakeLists.txt` registers our code as a *component*: the list of `.c` files to
compile, where our headers are, and which ESP-IDF components we depend on (`driver` for GPIO,
`nvs_flash` for saved settings, and so on).  If you add a `.c` file, add it to `SRCS`.  If
you include a header from a new ESP-IDF component and get an error like "file not found",
add that component to `REQUIRES`.

`sdkconfig.defaults` is the equivalent of a settings file: chip type, flash size, which port
the console uses.  `idf.py menuconfig` edits the full `sdkconfig`; the defaults file is the
subset we care about, kept in git.

## `main/pins.h`: the preprocessor

```c
#pragma once
#define PIN_ROW0        4
```

Lines starting with `#` are handled by the *preprocessor*, a text substitution pass that runs
before the compiler.  `#define PIN_ROW0 4` means "wherever `PIN_ROW0` appears from here on,
paste `4`."  It is not a variable; it has no type and takes no memory.  Constants in C are
very often done this way.

`#pragma once` at the top of a header means "if this file gets included twice in one
compilation, ignore the second time," which prevents duplicate-definition errors.  Every
header has it.

`#include "pins.h"` pastes the whole file in at that point.  Quotes mean "look in our
directory first"; angle brackets like `<stdio.h>` mean "look in the system and library
directories."

```c
#define PIN_DIRECT_COLS { 14, 21, 47, 48, 45, 46, 3, 35, 36, 37, 19, 20 }
```

A macro can expand to anything textual, here an array initializer.  `matrix.c` uses it as
`static const int COL_PINS[MATRIX_COLS] = PIN_DIRECT_COLS;`, which after substitution is an
ordinary array definition.

## `main/keymap.h`: arrays and strings

```c
static const char *const KEY_NAMES[MATRIX_ROWS][MATRIX_COLS] = {
    {"Inst/Del", "3", "5", ...},
    ...
};
```

Read declarations from the name outwards.  `KEY_NAMES` is a two-dimensional array, 8 by 12.
Each element is a `const char *const`: a pointer to characters (that is what a string is in
C, a pointer to the first character of a run of characters ending in a zero byte) that may
not be changed, and the pointer itself may not be changed either.  `static` on a file-level
variable means "visible only inside this file"; on a header that gets included into several
files it gives each file its own private copy, which is fine for a lookup table.

`NULL` is the null pointer, used here for the one matrix slot with no key.  Python's `None`,
JavaScript's `null`, except that dereferencing it crashes the chip rather than raising.

This file is generated; do not hand-edit it.  `tools/gen_keymap.py` rebuilds it from the
KiCad board file.

## `main/matrix.h`: a struct and a typedef

```c
typedef struct {
    uint16_t rows[MATRIX_ROWS];
} matrix_state_t;
```

A `struct` is a record: named fields laid out in memory in order.  This one holds eight
16-bit numbers.  `typedef` gives the anonymous struct the name `matrix_state_t` so we can
write `matrix_state_t s;` instead of `struct matrix_state s;`.  The `_t` suffix is a C
convention for type names.

Bit c of `rows[r]` is 1 while key (r, c) is down.  Packing booleans into bits is normal in
firmware: the whole keyboard state is 16 bytes, and comparing two states is eight integer
compares.

```c
static inline bool matrix_key(const matrix_state_t *s, int row, int col) {
    return (s->rows[row] >> col) & 1;
}
```

Small functions in headers are marked `static inline` so the compiler pastes them in place
rather than calling them.  `s` is a *pointer* to a state (the `*`), so its fields are reached
with `->` instead of `.`.  Passing pointers is how C avoids copying a struct on every call,
and `const` promises the function will not modify it.

`(x >> col) & 1` shifts the bits right by `col` places, then keeps only the lowest bit: "is
bit `col` set?"  You will see three bit idioms throughout:

| Idiom | Meaning |
|---|---|
| `x \|= 1u << c` | set bit c |
| `x &= ~(1u << c)` | clear bit c (`~` flips every bit, `&` keeps only where both are 1) |
| `(x >> c) & 1` | test bit c |

The `u` in `1u` makes the constant unsigned, which avoids a class of sign-extension surprises
when shifting.  For the GPIO masks the SDK wants 64-bit values, hence `1ULL << pin`.

The header also declares the functions `matrix.c` provides.  A declaration ends in `;` and
has no body; it lets other files call the function before the linker joins everything.

## `main/matrix.c`: scanning

```c
#ifndef MATRIX_DIRECT_COLUMNS
#define MATRIX_DIRECT_COLUMNS 0
#endif
```

A compile-time switch.  `#ifndef` means "if not defined": the default is 0 unless something
defined it earlier.  Below, `#if MATRIX_DIRECT_COLUMNS ... #else ... #endif` includes one
of two code paths in the compiled output and drops the other entirely.  This is how the same
source serves the real decoder and the simulator, which has none.

```c
static const int ROW_PINS[MATRIX_ROWS] = {PIN_ROW0, PIN_ROW1, ...};
static matrix_state_t debounced;
static uint8_t stable_ms[MATRIX_ROWS][MATRIX_COLS];
```

Module state lives in file-level `static` variables: private to this file, created once,
zero-initialized.  C has no classes; a `.c` file with static state and a set of functions is
the equivalent of a singleton object.

### `matrix_init`

```c
gpio_config_t in = {
    .pin_bit_mask = 0, .mode = GPIO_MODE_INPUT, .pull_up_en = GPIO_PULLUP_ENABLE, ...
};
```

A *designated initializer*: fill in named fields of a struct, leaving unnamed ones zero.  It
is the closest C gets to keyword arguments, and ESP-IDF's drivers are configured this way:
build a config struct, pass its address to a function.

```c
for (int r = 0; r < MATRIX_ROWS; r++) in.pin_bit_mask |= 1ULL << ROW_PINS[r];
gpio_config(&in);
```

The GPIO driver configures many pins at once from a 64-bit mask, one bit per pin number,
so the loop sets bit 4, 5, 6, 7, 15, 16, 17, 18.  `&in` is "the address of `in`": the
function receives a pointer, C's way of passing a struct without copying it.  The rows are
inputs with the chip's internal pull-up resistors on, so an unconnected row reads 1 and a
key connecting it to a low column reads 0.

`memset(&debounced, 0, sizeof debounced)` zeroes a block of memory: address, byte value,
number of bytes.  `sizeof` is evaluated by the compiler.

### `select_column` and `matrix_scan`

```c
for (int b = 0; b < 4; b++) gpio_set_level(SEL_PINS[b], (c >> b) & 1);
```

Puts the column number on the four decoder address pins, one bit each.  The decoder pulls
that one column low.

```c
for (int c = 0; c < MATRIX_COLS; c++) {
    select_column(c);
    esp_rom_delay_us(SETTLE_US);
    for (int r = 0; r < MATRIX_ROWS; r++)
        if (!gpio_get_level(ROW_PINS[r])) out->rows[r] |= 1u << c;
}
```

For each column: select it, wait 20 microseconds for the signal to settle through the
decoder, the 1 k resistor and the wiring, then read all eight rows.  A row reading 0 means
a key in this column is down, so set that bit.  `esp_rom_delay_us` is a busy-wait; fine for
microseconds, never use it for milliseconds inside a task (that is what `vTaskDelay` is for).

Note the braces rule: `if` and `for` govern exactly one statement unless you add `{}`.  The
inner `for` here has a single `if` as its body, so no braces.  When in doubt, add them.

### `matrix_tick`: debouncing

A mechanical switch bounces for a few milliseconds when it changes, producing a burst of
0-1-0-1.  The debouncer only believes a change once the raw reading has stayed the same for
`DEBOUNCE_MS` consecutive ticks:

```c
if (now != was) stable_ms[r][c] = 0;
else if (stable_ms[r][c] < 255) stable_ms[r][c]++;
if (now != deb && stable_ms[r][c] >= DEBOUNCE_MS) { ... accept ... }
```

`stable_ms` counts how many ticks each key's raw reading has been unchanged; any flip resets
it.  The `< 255` guard stops a `uint8_t` from wrapping back to zero after 255 quiet
milliseconds, which would otherwise make a held key look like it just changed.  The function
returns `true` when any debounced key changed, so the caller only does work on change.

`const matrix_state_t *matrix_debounced(void)` returns a pointer to the module's private
state, read-only.  `(void)` in a parameter list means "takes no arguments"; in old C an empty
list meant "unknown arguments."

## `main/ch446q.c`: bit-banging the crosspoint

"Bit-banging" means driving a serial protocol by setting pins high and low in software.
The CH446Q wants, per switch: seven address bits clocked in one at a time, then the on/off
value, then a strobe pulse.

```c
int addr = ((y & 7) << 4) | (x & 15);
for (int bit = 6; bit >= 0; bit--) {
    gpio_set_level(PIN_XP_DAT, (addr >> bit) & 1);
    esp_rom_delay_us(T_US);
    pulse_high(PIN_XP_CK);
}
```

`(y & 7) << 4 | (x & 15)` builds the address the datasheet specifies, row in the top three
bits and column in the low four: `y * 16 + x`, written with shifts and masks as C programmers
do.  The loop walks bits 6 down to 0, most significant first, putting each on the data pin
and clocking it in.  `pulse_high` is a `static inline` helper that raises a pin, waits a
microsecond, and lowers it.

The `T_US = 1` delays are a thousand times longer than the chip needs.  They cost nothing
noticeable (a full switch write is about 20 microseconds) and make the timing immune to
wiring on a breadboard.

## `main/locks.c`: saved settings

```c
typedef enum { LOCK_SHIFT = 0, LOCK_CAPS = 1, LOCK_4080 = 2, LOCK_COUNT } lock_t;
```

An `enum` is a set of named integer constants.  `LOCK_COUNT` at the end is a common trick:
it equals 3, the number of real entries, so arrays can be sized `[LOCK_COUNT]` and loops can
run `for (i = 0; i < LOCK_COUNT; i++)` without repeating the number.

`static bool state[LOCK_COUNT];` holds the three toggles.  `apply()` pushes one of them to
hardware: SHIFT LOCK closes the left-shift crosspoint (row 7, column 1), the other two set a
GPIO that drives a transistor.

### NVS

NVS ("non-volatile storage") is a key-value store in flash: string keys, small values, and it
survives power cycles.  Think of it as a tiny persistent dictionary.

```c
esp_err_t err = nvs_flash_init();
if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    ESP_ERROR_CHECK(nvs_flash_erase());
    err = nvs_flash_init();
}
ESP_ERROR_CHECK(err);
```

This is the error-handling style you will see across ESP-IDF.  Functions return an
`esp_err_t` status code; `ESP_OK` is zero.  `ESP_ERROR_CHECK(x)` is a macro that calls `x`
and, if the result is not `ESP_OK`, prints the file and line and halts the chip.  Use it for
things that cannot sensibly fail at runtime (initialization); check the return value yourself
for things that can (a missing key).  The dance above handles a flash partition from an
older layout by erasing it, which is the standard recipe from Espressif's examples.

```c
uint8_t v = (i == LOCK_4080) ? 1 : 0;
nvs_get_u8(nvs, KEYS[i], &v);
```

`nvs_get_u8` writes into `v` through the pointer `&v` and returns a status.  If the key does
not exist yet it returns an error and leaves `v` alone, so `v` keeps the default: 80 columns
on, the others off.  Ignoring that return on purpose is the idiom for "use the default if
unset."  The `? :` is the ternary operator, same as JavaScript.

`locks_set` writes the new value with `nvs_set_u8` and then `nvs_commit`, which actually
flushes to flash.  Flash wears out after roughly a hundred thousand writes per sector, which
is why it writes only on change.

## `main/main.c`: tasks and the console

### Setting up the console

```c
usb_serial_jtag_driver_config_t cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
usb_serial_jtag_driver_install(&cfg);
usb_serial_jtag_vfs_use_driver();
```

Three lines that make `printf` and `getchar` talk to the native USB port with buffering, so
`getchar()` can block waiting for a key without spinning.  This is one of the places where
the API names changed between ESP-IDF versions; the container pins the version, so it stays
put.

### Tasks

```c
xTaskCreate(scan_task, "scan", 4096, NULL, 10, NULL);
xTaskCreate(console_task, "console", 4096, NULL, 5, NULL);
```

Create two FreeRTOS tasks: the function to run, a name for debugging, a stack size in bytes
(4096 is generous for these; run out and the chip reboots with a stack-overflow message), an
argument pointer (unused, `NULL`), a priority (higher number runs first; the scan matters
more than the console), and an optional handle we do not keep.  Each task is a function that
never returns, hence `for (;;)`, C's idiom for an infinite loop.

```c
#define SCAN_PERIOD_TICKS pdMS_TO_TICKS(1)
_Static_assert(pdMS_TO_TICKS(1) >= 1, "CONFIG_FREERTOS_HZ must be 1000 for the 1 ms scan period");
...
vTaskDelayUntil(&last, SCAN_PERIOD_TICKS);
```

Sleep until one tick after the previous wake-up, giving a steady 1 kHz scan regardless of how
long the work took.  `vTaskDelay` (used in the console task) sleeps for a duration from now
instead.  Both yield the CPU to other tasks; `esp_rom_delay_us` does not.  `pdMS_TO_TICKS`
converts milliseconds to the scheduler's tick units, and rounds *down*: at FreeRTOS's default
100 Hz tick, 1 ms becomes 0 ticks and `vTaskDelayUntil` asserts, rebooting the chip in a loop.
The first simulator run found exactly that.  `sdkconfig.defaults` now sets the tick to
1 kHz, and the `_Static_assert` turns the same mistake into a compile error: a check the
compiler evaluates at build time, with a message it prints if the condition is false.

### Detecting changes

```c
uint16_t diff = cur->rows[r] ^ prev.rows[r];
for (int c = 0; diff; c++, diff >>= 1) {
    if (!(diff & 1)) continue;
    bool down = (cur->rows[r] >> c) & 1;
    on_key(r, c, down);
}
```

`^` is exclusive-or: a 1 bit wherever the new and old row differ, so `diff` is "which keys in
this row changed."  The loop shifts `diff` right one bit per iteration and stops when it is
zero, so it only iterates as far as the highest changed bit.  For each set bit, read the
new state of that key and act on it.  `cur` is a pointer (`->`), `prev` a local struct (`.`).

### `on_key`

Columns 0..10 are the C128 matrix, so a change there is one crosspoint write with the same
row and column.  Column 11 holds the lock keys, which toggle on press and are ignored on
release.  This function is where most future features plug in: the command layer will look
at combinations here before deciding whether to pass a key through.

### The console

`getchar()` blocks until a character arrives over USB, then a `switch` dispatches on it.
`switch`/`case` works as in JavaScript, including the need for `break` to stop falling into
the next case.  `case 'r'` shows a small choreography: close RUN/STOP's crosspoint, wait,
press RESTORE through the transistor, release both.  The C128 sees exactly what it would see
from fingers.

`(void)press_for;` at the end of `app_main` silences an "unused function" warning for a
helper kept for the next milestone.  Casting an expression to `void` is the standard way to
say "yes, I know."

## Things that will bite a Python/JS programmer

- `=` assigns and `==` compares, and `if (x = 5)` compiles.  The compiler warns; read the
  warnings.
- Integer division truncates, and mixing signed and unsigned in comparisons produces
  surprises.  Keep counters `int` unless they are bit masks.
- A string literal is `"abc"` with double quotes; `'a'` with single quotes is a single
  character, which is a small integer.  That is why the console compares `ch` to `'d'`.
- There is no `len()` for arrays; the size is whatever you declared, hence the `MATRIX_ROWS`
  constants everywhere.
- Every statement ends in `;`, including after a `}` that closes a struct definition.
- Forgetting a header gives "implicit declaration of function" (the error you saw fixed during
  the first build); it means the compiler has not been told the function exists yet.

## Where to go next

The next milestones in `docs/rev3-plan.md` map onto the code like this: the LED engine is a
new module driving `PIN_LED_DATA` with ESP-IDF's RMT peripheral (`led_strip` component); the
command layer is logic in `on_key` plus a small state machine; macros are a table of
`(row, col, hold_ms)` steps replayed through `ch446q_set`; USB keyboard mode uses the
`tinyusb` component and a table from physical position to HID usage; WiFi and the web page
use `esp_wifi` and `esp_http_server`.  Each is a new `.c`/`.h` pair added to `SRCS`.
