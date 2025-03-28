# This is a standard file from the Pico SDK examples.
# Ensure PICO_SDK_PATH is set in your environment, or change the path below.

# This can be uncommented if you are putting the SDK into your project directory
# set(PICO_SDK_PATH ${CMAKE_CURRENT_LIST_DIR}/pico-sdk)

if (NOT PICO_SDK_PATH)
    message(FATAL_ERROR "PICO_SDK_PATH not set")
endif ()

set(PICO_SDK_PATH ${PICO_SDK_PATH} CACHE PATH "Path to the Raspberry Pi Pico SDK")
get_filename_component(PICO_SDK_PATH ${PICO_SDK_PATH} REALPATH BASE_DIR "${CMAKE_BINARY_DIR}")
if (NOT EXISTS ${PICO_SDK_PATH})
    message(FATAL_ERROR "PICO_SDK_PATH does not exist")
endif ()

# Include the SDK
include(${PICO_SDK_PATH}/pico_sdk_init.cmake)
