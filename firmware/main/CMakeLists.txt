idf_component_register(
    SRCS "main.c" "matrix.c" "ch446q.c" "locks.c" "leds.c" "led_engine.c" "ws2812.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_driver_rmt esp_driver_usb_serial_jtag esp_driver_uart nvs_flash esp_timer vfs
)

# `idf.py -DMATRIX_DIRECT_COLUMNS=1 build`: one GPIO per column, no decoder (Wokwi simulator only)
# `idf.py -DBOARD_REV3=1 build`: the rev 3 board's 6 x 20 matrix instead of the bench rig's
if(BOARD_REV3)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE BOARD_REV3=1)
endif()

if(MATRIX_DIRECT_COLUMNS)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE MATRIX_DIRECT_COLUMNS=1)
endif()
