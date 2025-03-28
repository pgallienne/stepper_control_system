#ifndef SWITCHES_H
#define SWITCHES_H

#include "registers.h"

// --- Function Prototypes ---

// Initialize GPIO pins for switches with pull-ups
void init_switches(uint sw1_pin, uint sw2_pin);

// Read switch states (with debouncing) and update the switch status register
void update_switch_status_registers(volatile uint8_t *registers, uint sw1_pin, uint sw2_pin);

#endif // SWITCHES_H
