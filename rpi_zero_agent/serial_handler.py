import serial
import time
import logging
import threading
from collections import deque

logger = logging.getLogger("SerialHandler")

class ProtocolError(Exception):
    """Custom exception for serial communication protocol errors."""
    pass

class SerialHandler:
    def __init__(self, port, baudrate, timeout=0.5, read_timeout=0.2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout          # General timeout for operations
        self.read_timeout = read_timeout # Specific timeout for byte reads
        self.ser = None
        self._lock = threading.Lock()   # Lock for ensuring thread-safe serial access
        self._connect()

    def _connect(self):
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout, # Write timeout
                write_timeout=self.timeout
            )
            # Set a specific read timeout different from write/general timeout
            self.ser.read_timeout = self.read_timeout
            logger.info(f"Serial port {self.port} opened successfully.")
            # Optional: Flush input/output buffers after connect
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            time.sleep(0.1) # Short pause after setup

        except serial.SerialException as e:
            logger.error(f"Failed to open serial port {self.port}: {e}")
            self.ser = None # Ensure ser is None if connection failed
            raise # Re-raise the exception

    def close(self):
        with self._lock:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                    logger.info(f"Serial port {self.port} closed.")
                except Exception as e:
                     logger.error(f"Error closing serial port {self.port}: {e}")
            self.ser = None

    def is_open(self):
         return self.ser is not None and self.ser.is_open

    def _calculate_checksum(self, data):
        """Calculates simple XOR checksum."""
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum

    def _send_cmd(self, command_bytes):
        """Sends bytes over serial, handling potential errors."""
        if not self.is_open():
            raise ProtocolError("Serial port not open.")
        try:
            written = self.ser.write(command_bytes)
            # self.ser.flush() # Often needed, ensures data is sent immediately
            if written != len(command_bytes):
                raise ProtocolError(f"Serial write error: Only wrote {written}/{len(command_bytes)} bytes.")
            logger.debug(f"Serial TX ({len(command_bytes)} bytes): {command_bytes.hex()}")
        except serial.SerialTimeoutException:
             raise ProtocolError(f"Serial write timeout on port {self.port}")
        except serial.SerialException as e:
             self.close() # Close port on potentially fatal error
             raise ProtocolError(f"Serial write error: {e}")

    def _read_response(self, expected_len):
        """Reads a specific number of bytes, handling timeouts and errors."""
        if not self.is_open():
            raise ProtocolError("Serial port not open.")
        try:
            response = self.ser.read(expected_len)
            if len(response) != expected_len:
                 # Distinguish timeout from other issues
                 if len(response) == 0:
                      raise ProtocolError(f"Serial read timeout: Expected {expected_len} bytes, got 0.")
                 else:
                      raise ProtocolError(f"Serial read error: Expected {expected_len} bytes, got {len(response)}: {response.hex()}")
            logger.debug(f"Serial RX ({len(response)} bytes): {response.hex()}")
            return response
        except serial.SerialException as e:
            self.close() # Close port on potentially fatal error
            raise ProtocolError(f"Serial read error: {e}")

    # --- High-Level Protocol Functions ---

    def write_register(self, reg_addr, data_bytes):
        """
        Sends a write command according to the defined protocol.
        Protocol: [CMD_WRITE] [REG_ADDR] [DATA_LEN] [DATA_0]...[DATA_N] [CHECKSUM]
        Expects ACK: [REG_ADDR] [0x00] [CHECKSUM]
        """
        with self._lock: # Ensure exclusive access to serial port
            if not self.is_open():
                 logger.error("Attempted write while serial port closed.")
                 return False
            try:
                cmd_byte = 0x02 # CMD_WRITE
                data_len = len(data_bytes)
                if data_len > 16: # Safety limit
                    raise ValueError("Data length exceeds maximum allowed (16 bytes).")

                # Construct header and calculate checksum for payload part
                header = bytes([cmd_byte, reg_addr, data_len])
                payload_checksum = self._calculate_checksum(data_bytes)
                # Total checksum includes header and data checksum byte (or full data?)
                # Assuming checksum covers: CMD, ADDR, LEN, DATA...
                full_payload = header + data_bytes
                total_checksum = self._calculate_checksum(full_payload)

                # Send command
                command_to_send = full_payload + bytes([total_checksum])
                self._send_cmd(command_to_send)

                # Wait for ACK/NACK: [ADDR] [STATUS] [CHECKSUM] (3 bytes)
                ack_response = self._read_response(3)

                # Validate ACK checksum
                ack_checksum_calc = self._calculate_checksum(ack_response[:2])
                if ack_checksum_calc != ack_response[2]:
                    raise ProtocolError(f"Write ACK checksum mismatch for reg {reg_addr:#04x}. Got {ack_response.hex()}, calcCS={ack_checksum_calc:#04x}")

                # Check ACK content
                if ack_response[0] != reg_addr:
                     raise ProtocolError(f"Write ACK address mismatch for reg {reg_addr:#04x}. Got {ack_response[0]:#04x}.")
                if ack_response[1] == 0x00: # Success ACK code
                    logger.debug(f"Write successful for reg {reg_addr:#04x}")
                    return True
                elif ack_response[1] == 0xFF: # NACK code
                     logger.warning(f"Write NACK received for reg {reg_addr:#04x}.")
                     return False
                else:
                     raise ProtocolError(f"Write ACK unknown status code {ack_response[1]:#04x} for reg {reg_addr:#04x}.")

            except ProtocolError as e:
                 logger.error(f"Write Register Protocol Error (Reg {reg_addr:#04x}): {e}")
                 self._flush_input() # Attempt to clear buffer after error
                 return False
            except ValueError as e:
                 logger.error(f"Write Register Value Error (Reg {reg_addr:#04x}): {e}")
                 return False
            except Exception as e:
                 logger.error(f"Unexpected error during write_register (Reg {reg_addr:#04x}): {e}", exc_info=True)
                 return False


    def read_register(self, reg_addr, num_bytes):
        """
        Sends a read command and returns the received data bytes.
        Protocol: [CMD_READ] [REG_ADDR] [NUM_BYTES] [CHECKSUM]
        Expects Response: [REG_ADDR] [NUM_BYTES] [DATA_0]...[DATA_N] [CHECKSUM]
        """
        with self._lock: # Ensure exclusive access
            if not self.is_open():
                 logger.error("Attempted read while serial port closed.")
                 return None
            try:
                cmd_byte = 0x01 # CMD_READ
                if num_bytes > 16: # Safety limit
                     raise ValueError("Requested read length exceeds maximum allowed (16 bytes).")

                # Construct command
                command_payload = bytes([cmd_byte, reg_addr, num_bytes])
                checksum = self._calculate_checksum(command_payload)
                command_to_send = command_payload + bytes([checksum])

                # Send command
                self._send_cmd(command_to_send)

                # Expecting response: [ADDR, LEN, DATA..., CHECKSUM]
                expected_len = 2 + num_bytes + 1 # Addr, Len, Data, Checksum
                response = self._read_response(expected_len)

                # Validate checksum (covers Addr, Len, Data)
                response_payload = response[:-1] # All bytes except checksum
                checksum_calc = self._calculate_checksum(response_payload)
                checksum_recv = response[-1]

                if checksum_calc != checksum_recv:
                    raise ProtocolError(f"Read response checksum mismatch for reg {reg_addr:#04x}. Got {response.hex()}, calcCS={checksum_calc:#04x}")

                # Validate header
                if response[0] != reg_addr:
                     raise ProtocolError(f"Read response address mismatch for reg {reg_addr:#04x}. Expected {reg_addr:#04x}, got {response[0]:#04x}.")
                if response[1] != num_bytes:
                     raise ProtocolError(f"Read response length mismatch for reg {reg_addr:#04x}. Expected {num_bytes}, got {response[1]}.")

                # Extract data
                data = response[2:-1] # Bytes between header and checksum
                logger.debug(f"Read successful for reg {reg_addr:#04x}: {data.hex()}")
                return data

            except ProtocolError as e:
                 logger.error(f"Read Register Protocol Error (Reg {reg_addr:#04x}, Len {num_bytes}): {e}")
                 self._flush_input() # Attempt to clear buffer after error
                 return None
            except ValueError as e:
                 logger.error(f"Read Register Value Error (Reg {reg_addr:#04x}): {e}")
                 return None
            except Exception as e:
                 logger.error(f"Unexpected error during read_register (Reg {reg_addr:#04x}): {e}", exc_info=True)
                 return None

    def _flush_input(self):
        """Safely attempts to flush the serial input buffer."""
        if self.is_open():
            try:
                # Read any remaining bytes with a short timeout
                self.ser.timeout = 0.05
                junk = self.ser.read(1024)
                self.ser.timeout = self.read_timeout # Restore original read timeout
                if junk:
                    logger.warning(f"Flushed {len(junk)} unexpected bytes from serial input: {junk.hex()}")
                self.ser.reset_input_buffer() # Also try reset method
            except Exception as e:
                logger.error(f"Error flushing serial input buffer: {e}")
