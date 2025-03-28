#include <stdio.h>
#include "pico/stdlib.h"
#include "hardware/uart.h"
#include "hardware/spi.h"
#include "hardware/gpio.h"
#include "registers.h"      // Define register addresses and the register array
#include "uart_protocol.h"  // Handle UART communication and register access logic
#include "tmc2130.h"        // Handle SPI communication with TMC drivers
#include "motor_control.h"  // Handle motor movement logic
#include "switches.h"       // Handle switch reading

// --- Hardware Pins (Example - Adjust as per your wiring) ---
#define UART_ID uart0
#define UART_TX_PIN 0
#define UART_RX_PIN 1
#define BAUD_RATE 115200

#define SPI_PORT spi0
#define SPI_MISO_PIN 16
#define SPI_CSN1_PIN 17 // Chip select for TMC Driver 1
#define SPI_CSN2_PIN 2 // Chip select for TMC Driver 2
#define SPI_SCK_PIN 18
#define SPI_MOSI_PIN 19

#define SWITCH1_PIN 20
#define SWITCH2_PIN 21

// --- Global Register Storage ---
// Define this array based on your register map in registers.h
volatile uint8_t virtual_registers[REGISTER_MAP_SIZE]; // Use volatile if accessed by ISRs

int main() {
    stdio_init_all(); // Initialize stdio for printf over USB UART
    printf("Pico Stepper Controller Booting...\n");

    // --- Initialize UART ---
    uart_init(UART_ID, BAUD_RATE);
    gpio_set_function(UART_TX_PIN, GPIO_FUNC_UART);
    gpio_set_function(UART_RX_PIN, GPIO_FUNC_UART);
    // Optionally enable UART interrupts here if needed for uart_protocol.c
    printf("UART Initialized (Pins %d TX, %d RX, Baud %d)\n", UART_TX_PIN, UART_RX_PIN, BAUD_RATE);

    // --- Initialize SPI ---
    spi_init(SPI_PORT, 500 * 1000); // 500kHz clock speed - Adjust as needed
    gpio_set_function(SPI_MISO_PIN, GPIO_FUNC_SPI);
    gpio_set_function(SPI_SCK_PIN, GPIO_FUNC_SPI);
    gpio_set_function(SPI_MOSI_PIN, GPIO_FUNC_SPI);
    printf("SPI Initialized (Port %d, MISO %d, SCK %d, MOSI %d)\n", spi_get_index(SPI_PORT), SPI_MISO_PIN, SPI_SCK_PIN, SPI_MOSI_PIN);

    // Initialize Chip Select pins for TMC drivers
    gpio_init(SPI_CSN1_PIN);
    gpio_set_dir(SPI_CSN1_PIN, GPIO_OUT);
    gpio_put(SPI_CSN1_PIN, 1); // Deselect initially
    gpio_init(SPI_CSN2_PIN);
    gpio_set_dir(SPI_CSN2_PIN, GPIO_OUT);
    gpio_put(SPI_CSN2_PIN, 1); // Deselect initially
    printf("SPI CS Initialized (CS1 %d, CS2 %d)\n", SPI_CSN1_PIN, SPI_CSN2_PIN);

    // --- Initialize Switches ---
    init_switches(SWITCH1_PIN, SWITCH2_PIN);
    printf("Switches Initialized (SW1 %d, SW2 %d)\n", SWITCH1_PIN, SWITCH2_PIN);

    // --- Initialize TMC Drivers ---
    // Add specific TMC2130 initialization code here via tmc2130.c functions
    // e.g., configure microstepping, currents, modes via SPI
    init_tmc_drivers(SPI_PORT, SPI_CSN1_PIN, SPI_CSN2_PIN);
    printf("TMC Drivers Initialized\n");

    // --- Initialize Motor Control ---
    init_motor_control();
    printf("Motor Control Initialized\n");

    // --- Main Loop ---
    printf("Starting main loop...\n");
    while (1) {
        // 1. Handle incoming UART commands & update registers
        handle_uart_rx(UART_ID, virtual_registers);

        // 2. Update hardware/motor state based on register changes
        // This logic might be complex, potentially involving state machines
        update_motor_control_from_registers(virtual_registers);

        // 3. Perform real-time tasks
        // Example: If using polling for steps instead of timers/interrupts
        // run_motor_step_sequence(); // Placeholder for step generation logic

        // 4. Read hardware status and update relevant registers
        // Debouncing for switches should be handled within update_switch_status
        update_switch_status_registers(virtual_registers, SWITCH1_PIN, SWITCH2_PIN);
        update_motor_status_registers(virtual_registers); // Update current position, status flags etc.

        // Consider using sleep_ms(1) or WFI (Wait For Interrupt) if using interrupts
        // to reduce CPU load, especially if tasks are not needed every cycle.
        // tight_loop_contents(); // Use if no sleep/interrupts are used
    }

    return 0; // Should not reach here
}
