#include "motor_control.h"
#include "pico/stdlib.h"
#include "hardware/gpio.h"
#include <stdio.h> // For debug printf
#include <string.h> // For memcpy

// --- Placeholder Implementation ---
// This needs to be replaced with actual stepper motor control logic.
// Consider using:
// 1. Timer Interrupts: Generate STEP pulses at precise intervals based on speed/acceleration.
// 2. PIO (Programmable I/O): Offload step generation to the PIO state machines for high speeds.
// 3. Simple blocking loops (for low speeds, less precise): Generate steps directly.

// --- Internal State (Example) ---
typedef struct {
    bool moving;
    int32_t current_pos;
    int32_t target_pos;
    uint16_t max_speed;
    uint16_t accel;
    // Add state for current speed, acceleration phase, direction etc.
} motor_state_t;

static motor_state_t motor_state[2]; // State for motor 1 and motor 2
static uint32_t last_reg_check_time = 0;

// --- Initialization ---
void init_motor_control(void) {
    printf("Motor Control Init (Placeholder)\n");
    // Initialize GPIOs if STEP/DIR pins are used
    // Setup timers or PIO if used for step generation
    memset(motor_state, 0, sizeof(motor_state));
    last_reg_check_time = time_us_32();

    // Example: If using dedicated enable pins
    // gpio_init(MOTOR1_ENABLE_PIN); gpio_set_dir(MOTOR1_ENABLE_PIN, GPIO_OUT); gpio_put(MOTOR1_ENABLE_PIN, 1); // Disabled
    // gpio_init(MOTOR2_ENABLE_PIN); gpio_set_dir(MOTOR2_ENABLE_PIN, GPIO_OUT); gpio_put(MOTOR2_ENABLE_PIN, 1); // Disabled
}

// --- Update state from registers ---
void update_motor_control_from_registers(volatile uint8_t *registers) {
    // Check registers periodically, not necessarily every loop iteration
    uint32_t now = time_us_32();
    if (now - last_reg_check_time < 10000) { // Check every 10ms (adjust interval)
        return;
    }
    last_reg_check_time = now;

    // --- Motor 1 ---
    uint8_t m1_control = registers[REG_MOTOR1_CONTROL];
    if (m1_control & 0x01) { // Check Start Move bit
        motor_state[0].target_pos = READ_U32_REGISTER(registers, REG_MOTOR1_TARGET_POS_L);
        motor_state[0].max_speed = READ_U16_REGISTER(registers, REG_MOTOR1_MAX_SPEED_L);
        motor_state[0].accel = READ_U16_REGISTER(registers, REG_MOTOR1_ACCEL_L);
        // TODO: Add actual logic to start movement (e.g., enable timer, set PIO)
        motor_state[0].moving = true;
        printf("M1 Start Cmd: Target=%ld, Speed=%d, Accel=%d\n", motor_state[0].target_pos, motor_state[0].max_speed, motor_state[0].accel);
        // Clear the start bit in the register after processing
        registers[REG_MOTOR1_CONTROL] &= ~0x01;
    }
    if (m1_control & 0x02) { // Check Stop Move bit
         // TODO: Add actual logic to stop movement (disable timer, PIO, ramp down)
         motor_state[0].moving = false;
         printf("M1 Stop Cmd\n");
         // Clear the stop bit
         registers[REG_MOTOR1_CONTROL] &= ~0x02;
    }
    // Add homing command handling (bit 2)

    // --- Motor 2 ---
    // Similar logic for Motor 2 using REG_MOTOR2_* registers
     uint8_t m2_control = registers[REG_MOTOR2_CONTROL];
     if (m2_control & 0x01) { // Start
         motor_state[1].target_pos = READ_U32_REGISTER(registers, REG_MOTOR2_TARGET_POS_L);
         motor_state[1].max_speed = READ_U16_REGISTER(registers, REG_MOTOR2_MAX_SPEED_L);
         motor_state[1].accel = READ_U16_REGISTER(registers, REG_MOTOR2_ACCEL_L);
         motor_state[1].moving = true;
         printf("M2 Start Cmd: Target=%ld, Speed=%d, Accel=%d\n", motor_state[1].target_pos, motor_state[1].max_speed, motor_state[1].accel);
         registers[REG_MOTOR2_CONTROL] &= ~0x01;
     }
     if (m2_control & 0x02) { // Stop
          motor_state[1].moving = false;
          printf("M2 Stop Cmd\n");
          registers[REG_MOTOR2_CONTROL] &= ~0x02;
     }

    // TODO: Apply other configurations read from registers (e.g., microstepping from REG_MOTORx_CONFIG)
    // This might involve writing to TMC registers via tmc2130.c functions
}


// --- Update status registers ---
void update_motor_status_registers(volatile uint8_t *registers) {
    // --- Update Status Byte ---
    uint8_t status = registers[REG_STATUS]; // Read current status
    // Set/clear moving bits based on internal state
    if (motor_state[0].moving) status |= (1 << 1); else status &= ~(1 << 1);
    if (motor_state[1].moving) status |= (1 << 2); else status &= ~(1 << 2);
    // Add homing status bits (3, 4) if implementing homing
    // Update ready bit (0) - maybe based on initialization complete or error status?
    status |= (1 << 0); // Assume ready for now
    registers[REG_STATUS] = status;

    // --- Update Current Positions ---
    // TODO: Update motor_state[0].current_pos and motor_state[1].current_pos based on
    // actual steps generated (e.g., count steps in ISR or read from PIO)
    // This is just a placeholder:
    if (motor_state[0].moving && motor_state[0].current_pos < motor_state[0].target_pos) motor_state[0].current_pos++;
    if (motor_state[0].moving && motor_state[0].current_pos > motor_state[0].target_pos) motor_state[0].current_pos--;
    if (motor_state[1].moving && motor_state[1].current_pos < motor_state[1].target_pos) motor_state[1].current_pos++;
    if (motor_state[1].moving && motor_state[1].current_pos > motor_state[1].target_pos) motor_state[1].current_pos--;

    // Check if target reached (simplified)
    if (motor_state[0].moving && motor_state[0].current_pos == motor_state[0].target_pos) {
        motor_state[0].moving = false;
        printf("M1 Target Reached\n");
    }
     if (motor_state[1].moving && motor_state[1].current_pos == motor_state[1].target_pos) {
        motor_state[1].moving = false;
        printf("M2 Target Reached\n");
    }


    // Write updated positions back to registers
    WRITE_U32_REGISTER(registers, REG_MOTOR1_CURRENT_POS_L, motor_state[0].current_pos);
    WRITE_U32_REGISTER(registers, REG_MOTOR2_CURRENT_POS_L, motor_state[1].current_pos);

    // TODO: Update error flags register (REG_ERROR_FLAGS) based on TMC status reads or limit switches
}

// --- Step Generation (Placeholder - Not functional without timer/PIO) ---
// void run_motor_step_sequence(void) {
//     // This function would contain the logic to generate STEP pulses
//     // based on the current speed and acceleration profile derived from
//     // motor_state. This is highly timing-dependent and best done
//     // with hardware timers or PIO.
// }
