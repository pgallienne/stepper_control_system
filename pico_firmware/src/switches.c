#include "switches.h"
#include "pico/stdlib.h"
#include "hardware/gpio.h"

// --- Debouncing Parameters ---
#define DEBOUNCE_DELAY_US 5000 // 5ms debounce time (adjust as needed)

// --- Internal State for Debouncing ---
typedef struct {
    uint pin;
    bool raw_state;         // Current unfiltered reading
    bool debounced_state;   // Stable state after debouncing
    bool changed;           // Flag if debounced_state changed
    uint32_t last_change_time; // Time of last potential change
} switch_debounce_t;

static switch_debounce_t switch_state[2];

// --- Initialization ---
void init_switches(uint sw1_pin, uint sw2_pin) {
    // Switch 1
    gpio_init(sw1_pin);
    gpio_set_dir(sw1_pin, GPIO_IN);
    gpio_pull_up(sw1_pin); // Enable internal pull-up (assumes switches connect pin to GND)
    switch_state[0].pin = sw1_pin;
    switch_state[0].raw_state = gpio_get(sw1_pin);
    switch_state[0].debounced_state = switch_state[0].raw_state;
    switch_state[0].changed = false;
    switch_state[0].last_change_time = time_us_32();

    // Switch 2
    gpio_init(sw2_pin);
    gpio_set_dir(sw2_pin, GPIO_IN);
    gpio_pull_up(sw2_pin);
    switch_state[1].pin = sw2_pin;
    switch_state[1].raw_state = gpio_get(sw2_pin);
    switch_state[1].debounced_state = switch_state[1].raw_state;
    switch_state[1].changed = false;
    switch_state[1].last_change_time = time_us_32();
}

// --- Update and Debounce Switches ---
void update_switch_status_registers(volatile uint8_t *registers, uint sw1_pin, uint sw2_pin) {
    uint32_t now = time_us_32();
    bool needs_register_update = false;

    for (int i = 0; i < 2; i++) {
        bool current_reading = gpio_get(switch_state[i].pin);

        if (current_reading != switch_state[i].raw_state) {
            // State differs from last reading, reset debounce timer
            switch_state[i].raw_state = current_reading;
            switch_state[i].last_change_time = now;
            switch_state[i].changed = false; // Not stable yet
        } else {
            // State is the same as last reading
            if (!switch_state[i].changed && (now - switch_state[i].last_change_time > DEBOUNCE_DELAY_US)) {
                // State has been stable for longer than debounce delay
                if (current_reading != switch_state[i].debounced_state) {
                    // Stable state is different from the last known stable state
                    switch_state[i].debounced_state = current_reading;
                    switch_state[i].changed = true; // Mark that a stable change occurred
                    needs_register_update = true; // Signal that the register needs updating
                }
            }
        }
         // After debounce time passes, changed remains true until next change starts
         if (now - switch_state[i].last_change_time <= DEBOUNCE_DELAY_US) {
              switch_state[i].changed = false; // Clear changed flag during debounce period
         }
    }

    // --- Update Register if any debounced state changed ---
    if (needs_register_update) {
        uint8_t status_byte = 0;
        // Remember: gpio_get reads 1 if high (not pressed with pull-up), 0 if low (pressed)
        if (!switch_state[0].debounced_state) { // Bit 0 for Switch 1 pressed (LOW)
            status_byte |= (1 << 0);
        }
        if (!switch_state[1].debounced_state) { // Bit 1 for Switch 2 pressed (LOW)
            status_byte |= (1 << 1);
        }
        registers[REG_SWITCH_STATUS] = status_byte;
    }
}
