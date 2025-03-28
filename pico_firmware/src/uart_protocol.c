#include "uart_protocol.h"
#include "pico/stdlib.h"
#include "hardware/uart.h"
#include <string.h> // Not strictly needed now, but good practice if other string ops added
#include <stdio.h> // For debug printf

// --- Simple XOR Checksum ---
uint8_t calculate_checksum(const uint8_t *data, size_t len) {
    uint8_t checksum = 0;
    for (size_t i = 0; i < len; i++) {
        checksum ^= data[i];
    }
    return checksum;
}

// --- UART Processing ---
void handle_uart_rx(uart_inst_t *uart, volatile uint8_t *registers) {
    // Check if start byte is available (if using one)
    // Using uart_is_readable first prevents blocking unnecessarily if no data starts coming
    if (uart_is_readable(uart)) {
        uint8_t header[3]; // CMD, ADDR, LEN

        // Read the header (blocks until 3 bytes are received)
        uart_read_blocking(uart, header, 3);
        // If the function returns, we assume 3 bytes were successfully read.
        // Error handling here relies more on subsequent protocol validation.

        uint8_t cmd_type = header[0];
        uint8_t reg_addr = header[1];
        uint8_t data_len = header[2];

        // --- Validate Header ---
        // Check address and length validity *before* reading more data
        if (reg_addr >= REGISTER_MAP_SIZE || (reg_addr + data_len) > REGISTER_MAP_SIZE) {
            printf("UART RX Error: Invalid address/length (Addr: %02X, Len: %d, MapSize: %d)\n", reg_addr, data_len, REGISTER_MAP_SIZE);
            // How to recover? Flush remaining expected bytes or just NACK?
            // Let's try to read and discard expected remaining bytes based on cmd_type for robustness
            if (cmd_type == CMD_READ) {
                 uart_read_blocking(uart, header, 1); // Read/discard expected checksum byte
            } else if (cmd_type == CMD_WRITE) {
                 uint8_t discard_buf[16+1]; // Max size
                 if (data_len <= 16) { // Prevent overflow on discard read
                     uart_read_blocking(uart, discard_buf, data_len + 1); // Read/discard data+checksum
                 }
            }
            // Consider sending NACK here if protocol defines it
            return;
        }
        if (data_len > 16) { // Arbitrary limit
             printf("UART RX Error: Data length too large (%d > 16)\n", data_len);
             // Read and discard expected remaining bytes (checksum or data+checksum)
             if (cmd_type == CMD_READ) {
                 uart_read_blocking(uart, header, 1);
             } else if (cmd_type == CMD_WRITE) {
                 // Can't safely read data_len+1 if data_len > 16, UART buffer might fill
                 // Maybe just NACK and hope master resets? Or flush differently?
                 // For now, just return after logging.
             }
             // Consider sending NACK
             return;
        }

        // --- Handle READ Command ---
        if (cmd_type == CMD_READ) {
            uint8_t checksum_rx;

            // Read the expected checksum byte for the read command itself
            uart_read_blocking(uart, &checksum_rx, 1);
            // Assume 1 byte read successfully if function returns

            // Verify command checksum (CMD ^ ADDR ^ LEN)
            if (calculate_checksum(header, 3) != checksum_rx) {
                printf("UART RX Error: Read command checksum mismatch (Calc: %02X, Recv: %02X)\n", calculate_checksum(header, 3), checksum_rx);
                 // Optional NACK?
                 return;
            }

            // Prepare response buffer: [ADDR, LEN, DATA..., CHECKSUM]
            uint8_t response[2 + data_len + 1]; // Max size needed
            response[0] = reg_addr;
            response[1] = data_len;

            // ** CRITICAL SECTION START (if registers modified by interrupts) **
            // uint32_t saved_irq = save_and_disable_interrupts();
            // Copy data byte-by-byte from volatile registers
            for (size_t i = 0; i < data_len; ++i) {
                response[2 + i] = registers[reg_addr + i]; // Direct volatile read
            }
            // ** CRITICAL SECTION END **
            // restore_interrupts(saved_irq);

            // Calculate checksum over ADDR, LEN, DATA
            response[2 + data_len] = calculate_checksum(response, 2 + data_len);

            // Send the full response
            uart_write_blocking(uart, response, 2 + data_len + 1);

        }
        // --- Handle WRITE Command ---
        else if (cmd_type == CMD_WRITE) {
            uint8_t data_buffer[16 + 1]; // Buffer for data + checksum (max 16 data bytes)
            uint8_t checksum_rx;

            // Read data (if any) and checksum
            if (data_len > 0) {
                // Read data_len bytes into the start of the buffer
                uart_read_blocking(uart, data_buffer, data_len);
                // Assume data read successfully if returns
            }
            // Read the checksum byte (comes after data, or immediately if data_len is 0)
            uart_read_blocking(uart, &checksum_rx, 1);
            // Assume checksum byte read successfully if returns


            // Verify command checksum (CMD ^ ADDR ^ LEN ^ DATA...)
            uint8_t checksum_calc = header[0] ^ header[1] ^ header[2];
            if (data_len > 0) {
                checksum_calc = calculate_checksum(data_buffer, data_len) ^ checksum_calc; // XOR with data checksum part
            }

            if (checksum_calc != checksum_rx) {
                printf("UART RX Error: Write command checksum mismatch (Calc: %02X, Recv: %02X)\n", checksum_calc, checksum_rx);
                // Send NACK: [ADDR, 0xFF, CHECKSUM]
                uint8_t nack_response[3];
                nack_response[0] = reg_addr;
                nack_response[1] = 0xFF; // NACK code
                nack_response[2] = calculate_checksum(nack_response, 2);
                uart_write_blocking(uart, nack_response, 3);
                return;
            }

            // Checksum OK, write data to registers if data_len > 0
            if (data_len > 0) {
                // ** CRITICAL SECTION START (if registers modified by interrupts) **
                // uint32_t saved_irq = save_and_disable_interrupts();
                // Copy data byte-by-byte to volatile registers
                for (size_t i = 0; i < data_len; ++i) {
                    registers[reg_addr + i] = data_buffer[i]; // Direct volatile write
                }
                // ** CRITICAL SECTION END **
                // restore_interrupts(saved_irq);
            }

            // Send ACK: [ADDR, 0x00, CHECKSUM]
            uint8_t ack_response[3];
            ack_response[0] = reg_addr;
            ack_response[1] = 0x00; // Success code
            ack_response[2] = calculate_checksum(ack_response, 2);
            uart_write_blocking(uart, ack_response, 3);

        } else {
            printf("UART RX Error: Unknown command type %02X\n", cmd_type);
            // Unknown command - we don't know how many bytes might follow.
            // Maybe NACK? Maybe try to flush UART input? Difficult to recover gracefully.
            // Consider sending a specific NACK for unknown command if defined.
        }
    }
    // No data available to read when uart_is_readable() was checked
}
