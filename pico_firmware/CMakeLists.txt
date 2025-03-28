cmake_minimum_required(VERSION 3.13)

# Pull in Raspberry Pi Pico SDK (must be defined, e.g., export PICO_SDK_PATH=...)
include(pico_sdk_import.cmake)

project(pico_stepper_firmware C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# Initialize the SDK
pico_sdk_init()

# Add executable target
add_executable(stepper_firmware
        src/main.c
        src/uart_protocol.c
        src/tmc2130.c
        src/motor_control.c
        src/switches.c
        )

# Pull in hardware libraries from SDK
target_link_libraries(stepper_firmware pico_stdlib hardware_uart hardware_spi hardware_gpio)

# Enable USB UART output
pico_enable_stdio_usb(stepper_firmware 1)
pico_enable_stdio_uart(stepper_firmware 0)

# Add generated ELF/UF2 files targets
pico_add_extra_outputs(stepper_firmware)

# Example: Add include directory if needed
# target_include_directories(stepper_firmware PRIVATE src)

install(TARGETS stepper_firmware
        DESTINATION .)
