#ifndef UART_PROTOCOL_H
#define UART_PROTOCOL_H

#include "hardware/uart.h"
#include "registers.h"

// Define the structure of your UART protocol here
// Example Simple Protocol:
// Master -> Pico: [CMD_BYTE] [REG_ADDR] [DATA_LEN] [DATA_0] ... [DATA_N] [CHECKSUM]
// Pico -> Master (Read): [REG_ADDR] [DATA_LEN] [DATA_0] ... [DATA_N] [CHECKSUM]
// Pico -> Master (Write ACK): [REG_ADDR] [0x00] [CHECKSUM]
// Pico -> Master (Write NACK): [REG_ADDR] [0xFF] [CHECKSUM]

// Example Command Bytes
#define CMD_READ  0x01
#define CMD_WRITE 0x02

// Function to process incoming UART data and update/read registers
// This should be called periodically from the main loop or triggered by UART RX interrupt
void handle_uart_rx(uart_inst_t *uart, volatile uint8_t *registers);

// Function to calculate checksum (example: simple XOR)
uint8_t calculate_checksum(const uint8_t *data, size_t len);

#endif // UART_PROTOCOL_H
