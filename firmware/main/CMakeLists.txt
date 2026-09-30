idf_component_register(
    SRCS "main.c" "matrix.c" "ch446q.c" "locks.c"
    INCLUDE_DIRS "."
    REQUIRES driver esp_driver_usb_serial_jtag esp_driver_uart nvs_flash esp_timer vfs
)

# `idf.py -DMATRIX_DIRECT_COLUMNS=1 build`: one GPIO per column, no decoder (Wokwi simulator only)
if(MATRIX_DIRECT_COLUMNS)
    target_compile_definitions(${COMPONENT_LIB} PRIVATE MATRIX_DIRECT_COLUMNS=1)
endif()
