#include "tmc2130.h"
#include <stdio.h> // For debug printf

// Store SPI instance and CS pins globally or pass them around
static spi_inst_t* spi_instance;
static uint cs_pins[2]; // cs_pins[0] for driver 1, cs_pins[1] for driver 2

// --- Helper for SPI transaction ---
static void tmc_spi_transfer(uint driver_id, uint8_t* data_tx, uint8_t* data_rx, size_t len) {
    if (driver_id >= 2) return; // Invalid driver ID

    // Assert CS
    gpio_put(cs_pins[driver_id], 0);
    sleep_us(2); // Small delay after CS assert might be needed

    // Perform SPI transfer
    spi_write_read_blocking(spi_instance, data_tx, data_rx, len);

    sleep_us(2); // Small delay before CS deassert might be needed
    // Deassert CS
    gpio_put(cs_pins[driver_id], 1);
}

// --- Initialization ---
void init_tmc_drivers(spi_inst_t *spi, uint cs1_pin, uint cs2_pin) {
    spi_instance = spi;
    cs_pins[0] = cs1_pin;
    cs_pins[1] = cs2_pin;

    // Ensure CS pins are high (deselected)
    gpio_put(cs_pins[0], 1);
    gpio_put(cs_pins[1], 1);

    printf("Initializing TMC2130 Drivers...\n");

    // --- Configure BOTH Drivers ---
    for (uint driver_id = 0; driver_id < 2; driver_id++) {
        printf("Configuring Driver %d...\n", driver_id + 1);

        // Example Configuration (ADJUST BASED ON YOUR NEEDS AND DATASHEET!)
        // These values are illustrative placeholders.

        // Clear GSTAT flags (write 1 to clear)
        tmc_write_register(driver_id, TMC_REG_GSTAT, 0x07); // Clear reset, drv_err, uv_cp

        // Set currents (e.g., Run current 10/31, Hold current 5/31, Hold delay 4)
        // IHOLD_IRUN: IHOLD(4:0), IRUN(12:8), IHOLDDELAY(19:16)
        uint32_t ihold_irun = (10 << 8) | (5 << 0) | (4 << 16);
        tmc_write_register(driver_id, TMC_REG_IHOLD_IRUN, ihold_irun);

        // Set TPOWERDOWN (e.g., 20 = ~0.5 sec delay before power down)
        tmc_write_register(driver_id, TMC_REG_TPOWERDOWN, 20);

        // Set CHOPCONF (Chopper config - critical for performance/noise)
        // Example: TOFF=3, HSTRT=4, HEND=1, TBL=2, CHM=0 (SpreadCycle), MRES=2 (16 microsteps)
        // Refer to datasheet for bit meanings!
        uint32_t chopconf = (3 << 0) | (4 << 4) | (1 << 7) | (2 << 20) | (0 << 14) | (2 << 24);
        // Also set: intpol=1 (interpolation), vsense=0/1? (high sensitivity sense resistors?)
        chopconf |= (1 << 28); // intpol = 1
        // chopconf |= (1 << 17); // vsense = 1 if needed
        tmc_write_register(driver_id, TMC_REG_CHOPCONF, chopconf);

        // Set GCONF (Global Config)
        // Example: Enable diag0_error, diag1_stall, stealthChop(I_scale_analog=0)
        // uint32_t gconf = (1 << 3) | (1 << 4) | (0 << 0); // Diag pins active low?
        // tmc_write_register(driver_id, TMC_REG_GCONF, gconf);

        // Read back some registers to verify SPI communication (optional debug)
        uint32_t read_chopconf = tmc_read_register(driver_id, TMC_REG_CHOPCONF);
        uint32_t read_ihold = tmc_read_register(driver_id, TMC_REG_IHOLD_IRUN);
        printf("  Driver %d: Read CHOPCONF=0x%08lX, IHOLD_IRUN=0x%08lX\n",
               driver_id + 1, read_chopconf, read_ihold);

        // Add more initialization here: COOLSTEP, STALLGUARD thresholds etc. if used.
    }
    printf("TMC Driver initialization complete.\n");
}

// --- Write Register ---
void tmc_write_register(uint driver_id, uint8_t reg_addr, uint32_t value) {
    uint8_t data_tx[5]; // 1 byte address + 4 bytes data
    uint8_t data_rx[5]; // Dummy buffer for read part

    // Set write bit (MSB) on register address
    data_tx[0] = reg_addr | 0x80;

    // Data bytes (MSB first)
    data_tx[1] = (value >> 24) & 0xFF;
    data_tx[2] = (value >> 16) & 0xFF;
    data_tx[3] = (value >> 8) & 0xFF;
    data_tx[4] = value & 0xFF;

    tmc_spi_transfer(driver_id, data_tx, data_rx, 5);
    // Optional: Short delay after write?
    // sleep_us(5);
}

// --- Read Register ---
uint32_t tmc_read_register(uint driver_id, uint8_t reg_addr) {
    uint8_t data_tx[5] = {0}; // Address only needed for first transfer
    uint8_t data_rx[5] = {0};

    // Ensure read bit (MSB) is clear on register address
    data_tx[0] = reg_addr & 0x7F;

    // 1. Send the register address (write with read bit clear)
    // The TMC driver latches this address for the *next* transfer.
    tmc_spi_transfer(driver_id, data_tx, data_rx, 5);

    // Short delay might be necessary between transfers
    sleep_us(50); // Adjust delay as needed

    // 2. Send the address *again* (or dummy data like 0x00) to clock out the result
    // The data received during *this* transfer corresponds to the address sent *before*.
    memset(data_tx, 0, 5); // Send dummy bytes
    tmc_spi_transfer(driver_id, data_tx, data_rx, 5);

    // The status byte is in data_rx[0], data is in data_rx[1..4]
    uint32_t value = ((uint32_t)data_rx[1] << 24) |
                     ((uint32_t)data_rx[2] << 16) |
                     ((uint32_t)data_rx[3] << 8)  |
                     ((uint32_t)data_rx[4]);

    // You might want to return or log the status byte (data_rx[0]) as well
    // printf("TMC Read Addr %02X: Status=0x%02X, Value=0x%08lX\n", reg_addr, data_rx[0], value);

    return value;
}
