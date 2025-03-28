#ifndef REGISTERS_H
#define REGISTERS_H

#include <stdint.h>

// --- Register Map Definition ---
// Define ALL registers used by the system here.
// Ensure addresses are contiguous or manage gaps carefully.

// Status Registers (Read-Only by RPi Zero)
#define REG_STATUS              0x00 // R (1 byte): Bitmask: 0=Ready, 1=M1 Moving, 2=M2 Moving, 3=M1 Homing, 4=M2 Homing
#define REG_SWITCH_STATUS       0x01 // R (1 byte): Bitmask: 0=SW1 Pressed(Active LOW), 1=SW2 Pressed(Active LOW)
#define REG_ERROR_FLAGS         0x02 // R (1 byte): Bitmask for errors (e.g., TMC fault, limit hit unexpectedly)

// Motor 1 Registers
#define REG_MOTOR1_CONTROL      0x10 // W (1 byte): Bitmask: 0=Start Move, 1=Stop Move, 2=Start Homing
#define REG_MOTOR1_TARGET_POS_L 0x11 // R/W (4 bytes total): Target position (steps), Little Endian LSB
#define REG_MOTOR1_TARGET_POS_M 0x12 // R/W
#define REG_MOTOR1_TARGET_POS_H 0x13 // R/W
#define REG_MOTOR1_TARGET_POS_U 0x14 // R/W                              USB
#define REG_MOTOR1_CURRENT_POS_L 0x15 // R (4 bytes total): Current position (steps), Little Endian LSB
#define REG_MOTOR1_CURRENT_POS_M 0x16 // R
#define REG_MOTOR1_CURRENT_POS_H 0x17 // R
#define REG_MOTOR1_CURRENT_POS_U 0x18 // R
#define REG_MOTOR1_MAX_SPEED_L  0x19 // R/W (2 bytes total): Max speed (e.g., steps/sec)
#define REG_MOTOR1_MAX_SPEED_H  0x1A // R/W
#define REG_MOTOR1_ACCEL_L      0x1B // R/W (2 bytes total): Acceleration (e.g., steps/sec^2)
#define REG_MOTOR1_ACCEL_H      0x1C // R/W
#define REG_MOTOR1_CONFIG       0x1D // R/W (2 bytes?): Microstepping, StallGuard threshold etc. (Map to TMC registers)
// ... Add more config as needed

// Motor 2 Registers (Similar structure, adjust addresses)
#define REG_MOTOR2_CONTROL      0x20 // W (1 byte)
#define REG_MOTOR2_TARGET_POS_L 0x21 // R/W (4 bytes)
#define REG_MOTOR2_TARGET_POS_M 0x22 // R/W
#define REG_MOTOR2_TARGET_POS_H 0x23 // R/W
#define REG_MOTOR2_TARGET_POS_U 0x24 // R/W
#define REG_MOTOR2_CURRENT_POS_L 0x25 // R (4 bytes)
#define REG_MOTOR2_CURRENT_POS_M 0x26 // R
#define REG_MOTOR2_CURRENT_POS_H 0x27 // R
#define REG_MOTOR2_CURRENT_POS_U 0x28 // R
#define REG_MOTOR2_MAX_SPEED_L  0x29 // R/W (2 bytes)
#define REG_MOTOR2_MAX_SPEED_H  0x2A // R/W
#define REG_MOTOR2_ACCEL_L      0x2B // R/W (2 bytes)
#define REG_MOTOR2_ACCEL_H      0x2C // R/W
#define REG_MOTOR2_CONFIG       0x2D // R/W (2 bytes?)
// ...

// --- Register Map Size ---
// Calculate the total size needed for the register array.
// Should be 1 + the address of the last byte used.
// Example: If last byte is at 0x2D, size is 0x2E = 46
#define REGISTER_MAP_SIZE       (REG_MOTOR2_CONFIG + 1) // Adjust based on the last register define

// --- Helper Macros/Functions (Optional but Recommended) ---
// Macros to read/write multi-byte values from the register array easily
// Assumes Little Endian byte order

#define READ_U16_REGISTER(regs, addr) \
    ((uint16_t)((regs)[addr]) | ((uint16_t)(regs)[(addr)+1] << 8))

#define WRITE_U16_REGISTER(regs, addr, value) \
    do { \
        (regs)[addr] = (uint8_t)((value) & 0xFF); \
        (regs)[(addr)+1] = (uint8_t)(((value) >> 8) & 0xFF); \
    } while (0)

#define READ_U32_REGISTER(regs, addr) \
    ((uint32_t)((regs)[addr]) | \
     ((uint32_t)(regs)[(addr)+1] << 8) | \
     ((uint32_t)(regs)[(addr)+2] << 16) | \
     ((uint32_t)(regs)[(addr)+3] << 24))

#define WRITE_U32_REGISTER(regs, addr, value) \
    do { \
        (regs)[addr] = (uint8_t)((value) & 0xFF); \
        (regs)[(addr)+1] = (uint8_t)(((value) >> 8) & 0xFF); \
        (regs)[(addr)+2] = (uint8_t)(((value) >> 16) & 0xFF); \
        (regs)[(addr)+3] = (uint8_t)(((value) >> 24) & 0xFF); \
    } while (0)

#endif // REGISTERS_H
