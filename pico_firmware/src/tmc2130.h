#ifndef TMC2130_H
#define TMC2130_H

#include "hardware/spi.h"
#include "pico/stdlib.h"

// --- TMC2130 Register Addresses (Add more as needed) ---
// See TMC2130 Datasheet
#define TMC_REG_GCONF       0x00 // Global configuration
#define TMC_REG_GSTAT       0x01 // Global status
#define TMC_REG_DRVSTATUS   0x6F // Driver status flags
#define TMC_REG_CHOPCONF    0x6C // Chopper configuration
#define TMC_REG_IHOLD_IRUN  0x10 // Current settings
#define TMC_REG_TPOWERDOWN  0x11 // Standstill delay
#define TMC_REG_XDIRECT     0x2D // Direct motor coil current (for diagnostics)
// Add registers for COOLSTEP, STALLGUARD, microstepping (MSLUT, MSCNT), etc.

// --- Function Prototypes ---

// Initialize SPI and basic TMC configuration
void init_tmc_drivers(spi_inst_t *spi, uint cs1_pin, uint cs2_pin);

// Write to a TMC register
// driver_id: 0 for motor 1 (CS1), 1 for motor 2 (CS2)
void tmc_write_register(uint driver_id, uint8_t reg_addr, uint32_t value);

// Read from a TMC register
uint32_t tmc_read_register(uint driver_id, uint8_t reg_addr);

// --- Helper Functions/Macros (Specific to your hardware/needs) ---
// e.g., Functions to set specific modes like StealthChop, SpreadCycle
// Functions to set current, microstepping, StallGuard thresholds

// You might want functions like:
// void tmc_set_current(uint driver_id, uint8_t run_current, uint8_t hold_current);
// void tmc_set_microsteps(uint driver_id, uint16_t microsteps); // e.g., 1, 2, 4,.., 256
// uint8_t tmc_get_status_flags(uint driver_id); // Read DRVSTATUS or GSTAT

#endif // TMC2130_H
