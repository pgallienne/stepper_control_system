#include "uart_protocol.h"
#include "pico/stdlib.h"
#include "hardware/uart.h"
#include <string.h> // For memcpy
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
// This is a basic blocking implementation. An interrupt-driven approach with
// a ring buffer would be more robust for handling continuous data streams.
void handle_uart_rx(uart_inst_t *uart, volatile uint8_t *registers) {
    // Check if start byte is available (if using one)
    if (uart_is_readable(uart)) {
        uint8_t header[3]; // CMD, ADDR, LEN

        // Try to read the header
        int bytes_read = uart_read_blocking(uart, header, 3);
        if (bytes_read != 3) {
             // Didn't receive full header, maybe timeout or partial message
             // Flush input buffer? Or handle partial reads more gracefully.
             printf("UART RX Error: Incomplete header (%d bytes)\n", bytes_read);
             // Simple flush: while(uart_is_readable(uart)) uart_getc(uart);
             return;
        }

        uint8_t cmd_type = header[0];
        uint8_t reg_addr = header[1];
        uint8_t data_len = header[2];

        // --- Validate Header ---
        if (reg_addr + data_len > REGISTER_MAP_SIZE) {
            printf("UART RX Error: Invalid address/length (Addr: %02X, Len: %d)\n", reg_addr, data_len);
            // Send NACK? Flush buffer?
            // Simple flush: while(uart_is_readable(uart)) uart_getc(uart);
            return; // Or send NACK
        }
        if (data_len > 16) { // Arbitrary limit to prevent large buffer overflows
             printf("UART RX Error: Data length too large (%d)\n", data_len);
             return; // Or send NACK
        }

        // --- Handle READ Command ---
        if (cmd_type == CMD_READ) {
            uint8_t checksum_rx;
            uart_read_blocking(uart, &checksum_rx, 1); // Read expected checksum

            // Verify checksum (CMD ^ ADDR ^ LEN)
            if (calculate_checksum(header, 3) != checksum_rx) {
                printf("UART RX Error: Read checksum mismatch\n");
                 // Send NACK?
                 return;
            }

            // Prepare response buffer: [ADDR, LEN, DATA..., CHECKSUM]
            uint8_t response[2 + data_len + 1];
            response[0] = reg_addr;
            response[1] = data_len;
            // ** CRITICAL SECTION START (if using interrupts) **
            // task_suspend_all(); // Example suspend if needed
            memcpy(&response[2], (const void*)&registers[reg_addr], data_len); // Read registers
            // ** CRITICAL SECTION END **
            // task_resume_all(); // Example resume

            response[2 + data_len] = calculate_checksum(response, 2 + data_len); // Calculate checksum

            uart_write_blocking(uart, response, sizeof(response));
            // printf("UART TX Read Rsp: Addr %02X, Len %d\n", reg_addr, data_len); // Debug
        }
        // --- Handle WRITE Command ---
        else if (cmd_type == CMD_WRITE) {
            uint8_t data_buffer[16 + 1]; // Buffer for data + checksum

            // Read data and checksum
            int data_bytes_read = uart_read_blocking(uart, data_buffer, data_len + 1);
            if (data_bytes_read != data_len + 1) {
                printf("UART RX Error: Incomplete Write data (%d / %d bytes)\n", data_bytes_read, data_len + 1);
                // Simple flush: while(uart_is_readable(uart)) uart_getc(uart);
                return; // Or send NACK
            }

            uint8_t checksum_rx = data_buffer[data_len];

            // Verify checksum (CMD ^ ADDR ^ LEN ^ DATA...)
            uint8_t checksum_calc = header[0] ^ header[1] ^ header[2];
            checksum_calc = calculate_checksum(data_buffer, data_len) ^ checksum_calc; // XOR with data checksum part

            if (checksum_calc != checksum_rx) {
                printf("UART RX Error: Write checksum mismatch\n");
                // Send NACK: [ADDR, 0xFF, CHECKSUM]
                uint8_t nack_response[3];
                nack_response[0] = reg_addr;
                nack_response[1] = 0xFF;
                nack_response[2] = calculate_checksum(nack_response, 2);
                uart_write_blocking(uart, nack_response, 3);
                return;
            }

            // Checksum OK, write data to registers
            // ** CRITICAL SECTION START (if using interrupts) **
            // task_suspend_all(); // Example suspend if needed
            memcpy((void*)&registers[reg_addr], data_buffer, data_len);
            // ** CRITICAL SECTION END **
            // task_resume_all(); // Example resume

            // Send ACK: [ADDR, 0x00, CHECKSUM]
            uint8_t ack_response[3];
            ack_response[0] = reg_addr;
            ack_response[1] = 0x00; // Success code
            ack_response[2] = calculate_checksum(ack_response, 2);
            uart_write_blocking(uart, ack_response, 3);
            // printf("UART TX Write Ack: Addr %02X, Len %d\n", reg_addr, data_len); // Debug

        } else {
            printf("UART RX Error: Unknown command type %02X\n", cmd_type);
            // Flush or ignore?
        }
    }
    // No data available to read
}
