#ifndef SWITCHES_H
#define SWITCHES_H

#include "registers.h" // Includes stdint.h via pico/stdlib.h -> pico/types.h likely
#include "pico/stdlib.h" // Ensure stdint types are available

// --- Function Prototypes ---

// Initialize GPIO pins for switches with pull-ups
// Use uint32_t for pin numbers, consistent with Pico SDK GPIO functions
void init_switches(uint32_t sw1_pin, uint32_t sw2_pin);

// Read switch states (with debouncing) and update the switch status register
// Use uint32_t for pin numbers
void update_switch_status_registers(volatile uint8_t *registers, uint32_t sw1_pin, uint32_t sw2_pin);

#endif // SWITCHES_H
