#ifndef MOTOR_CONTROL_H
#define MOTOR_CONTROL_H

#include "registers.h"

// Define GPIO pins used for STEP/DIR/ENABLE if not directly controlled by TMC SPI only modes
// Example:
// #define MOTOR1_STEP_PIN   3
// #define MOTOR1_DIR_PIN    4
// #define MOTOR1_ENABLE_PIN 5 // Active LOW
// #define MOTOR2_STEP_PIN   6
// #define MOTOR2_DIR_PIN    7
// #define MOTOR2_ENABLE_PIN 8 // Active LOW

// --- Function Prototypes ---

// Initialize GPIOs, timers, or other resources for motor control
void init_motor_control(void);

// Read relevant registers and update motor controller state (targets, speeds, start/stop commands)
// This is the main interface between the register map and the motion control logic
void update_motor_control_from_registers(volatile uint8_t *registers);

// Update status registers (e.g., current position, moving flags) based on internal state
void update_motor_status_registers(volatile uint8_t *registers);

// If using a polling-based step generation, this function would be called in the main loop
// void run_motor_step_sequence(void); // Uncomment if needed

// --- Add internal state variables or structures if needed ---
// typedef struct { ... } motor_state_t;
// extern motor_state_t motor1_state;
// extern motor_state_t motor2_state;


#endif // MOTOR_CONTROL_H
