import time
import threading
import configparser
import logging
import json
import struct

from mqtt_client import MqttClient
from serial_handler import SerialHandler, ProtocolError
from backend_comm import get_config_from_backend

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AgentMain")

# --- Configuration ---
config = configparser.ConfigParser()
try:
    config.read('config.ini')

    DEVICE_ID = config['DEFAULT']['DeviceID']
    SERIAL_PORT = config['DEFAULT']['SerialPort']
    BAUD_RATE = int(config['DEFAULT']['BaudRate'])
    BACKEND_URL = config['DEFAULT']['BackendURL']
    MQTT_BROKER = config['MQTT']['BrokerAddress']
    MQTT_PORT = int(config['MQTT']['BrokerPort'])
    MQTT_USER = config['MQTT'].get('Username', None)
    MQTT_PASS = config['MQTT'].get('Password', None)
except KeyError as e:
    logger.error(f"Configuration Error: Missing key {e} in config.ini")
    exit(1)
except Exception as e:
    logger.error(f"Error reading config.ini: {e}")
    exit(1)


# --- Register Map Constants (Mirror from Pico's registers.h) ---
REG_STATUS = 0x00
REG_SWITCH_STATUS = 0x01
REG_ERROR_FLAGS = 0x02
REG_MOTOR1_CONTROL = 0x10
REG_MOTOR1_TARGET_POS_L = 0x11
REG_MOTOR1_CURRENT_POS_L = 0x15
REG_MOTOR1_MAX_SPEED_L = 0x19
REG_MOTOR1_ACCEL_L = 0x1B
REG_MOTOR1_CONFIG = 0x1D
REG_MOTOR2_CONTROL = 0x20
REG_MOTOR2_TARGET_POS_L = 0x21
REG_MOTOR2_CURRENT_POS_L = 0x25
REG_MOTOR2_MAX_SPEED_L = 0x29
REG_MOTOR2_ACCEL_H = 0x2A
REG_MOTOR2_ACCEL_L = 0x2B
REG_MOTOR2_CONFIG = 0x2D

# --- Global Objects ---
serial_handler = None
mqtt_client = None
stop_event = threading.Event()
last_status = {} # Cache last sent status to avoid redundant messages

# --- Helper Functions ---
def pack_u16(value):
    return struct.pack('<H', value) # Little-endian unsigned short

def pack_i32(value):
    return struct.pack('<i', value) # Little-endian signed int

def unpack_u8(byte_data):
    return struct.unpack('<B', byte_data)[0]

def unpack_u16(byte_data):
    return struct.unpack('<H', byte_data)[0]

def unpack_i32(byte_data):
    return struct.unpack('<i', byte_data)[0]

# --- Apply Configuration from Backend ---
def apply_config(config_data):
    """Writes configuration values received from backend to Pico registers."""
    global serial_handler
    if not serial_handler or not config_data:
        logger.warning("Cannot apply config: Serial handler not ready or no config data.")
        return

    logger.info("Applying configuration from backend...")
    applied_count = 0
    try:
        # Example: Motor 1 Config (assuming 2 bytes)
        if 'motor1_config' in config_data:
            val = int(config_data['motor1_config'])
            if serial_handler.write_register(REG_MOTOR1_CONFIG, pack_u16(val)):
                 logger.info(f"Applied M1 Config (Reg {REG_MOTOR1_CONFIG:#04x}): {val}")
                 applied_count += 1
            else: logger.warning(f"Failed to apply M1 Config (Reg {REG_MOTOR1_CONFIG:#04x})")

        # Example: Motor 1 Speed (assuming 2 bytes)
        if 'motor1_max_speed' in config_data:
            val = int(config_data['motor1_max_speed'])
            if serial_handler.write_register(REG_MOTOR1_MAX_SPEED_L, pack_u16(val)):
                logger.info(f"Applied M1 Max Speed (Reg {REG_MOTOR1_MAX_SPEED_L:#04x}): {val}")
                applied_count += 1
            else: logger.warning(f"Failed to apply M1 Max Speed (Reg {REG_MOTOR1_MAX_SPEED_L:#04x})")

        # Example: Motor 1 Acceleration (assuming 2 bytes)
        if 'motor1_accel' in config_data:
            val = int(config_data['motor1_accel'])
            if serial_handler.write_register(REG_MOTOR1_ACCEL_L, pack_u16(val)):
                logger.info(f"Applied M1 Accel (Reg {REG_MOTOR1_ACCEL_L:#04x}): {val}")
                applied_count += 1
            else: logger.warning(f"Failed to apply M1 Accel (Reg {REG_MOTOR1_ACCEL_L:#04x})")

        # Add similar blocks for Motor 2 configuration...
        if 'motor2_config' in config_data:
            val = int(config_data['motor2_config'])
            if serial_handler.write_register(REG_MOTOR2_CONFIG, pack_u16(val)):
                 logger.info(f"Applied M2 Config (Reg {REG_MOTOR2_CONFIG:#04x}): {val}")
                 applied_count += 1
            else: logger.warning(f"Failed to apply M2 Config (Reg {REG_MOTOR2_CONFIG:#04x})")
        # ... M2 Speed, M2 Accel ...

        logger.info(f"Configuration application finished. Applied {applied_count} values.")

    except ValueError as e:
        logger.error(f"Configuration Error: Invalid value type in config data - {e}")
    except ProtocolError as e:
         logger.error(f"Serial Protocol Error during config apply: {e}")
    except Exception as e:
        logger.error(f"Unexpected error applying configuration: {e}")

# --- MQTT Command Handling ---
def handle_command(payload):
    """Processes commands received from MQTT."""
    global serial_handler
    if not serial_handler:
        logger.warning("Serial handler not ready, ignoring command.")
        return

    logger.info(f"Received command: {payload}")
    try:
        action = payload.get('action')
        motor_id = payload.get('motor') # 1 or 2
        value = payload.get('value')

        # Determine register base based on motor_id
        if motor_id == 1:
            reg_control = REG_MOTOR1_CONTROL
            reg_target_pos = REG_MOTOR1_TARGET_POS_L
            reg_max_speed = REG_MOTOR1_MAX_SPEED_L
            reg_accel = REG_MOTOR1_ACCEL_L
        elif motor_id == 2:
            reg_control = REG_MOTOR2_CONTROL
            reg_target_pos = REG_MOTOR2_TARGET_POS_L
            reg_max_speed = REG_MOTOR2_MAX_SPEED_L
            reg_accel = REG_MOTOR2_ACCEL_L
        else:
            # Handle general commands or invalid motor_id
            if action == 'resend_config':
                 logger.info("Re-fetching and applying configuration...")
                 config_data = get_config_from_backend(BACKEND_URL, DEVICE_ID)
                 apply_config(config_data)
            else:
                 logger.warning(f"Unknown command or missing/invalid motor ID: {payload}")
            return # Exit early for non-motor specific commands or errors

        # --- Process Motor Specific Actions ---
        if action == "set_target":
            if value is not None:
                target_pos = int(value)
                if serial_handler.write_register(reg_target_pos, pack_i32(target_pos)):
                    logger.info(f"Set Motor {motor_id} target to {target_pos} (Reg {reg_target_pos:#04x})")
                    # Optionally trigger move immediately? Or require separate 'start' command?
                    # Set the 'start move' bit in the control register
                    if serial_handler.write_register(reg_control, bytes([0x01])): # Write 1 to start
                        logger.info(f"Triggered Motor {motor_id} move (Reg {reg_control:#04x})")
                    else: logger.warning(f"Failed to trigger Motor {motor_id} move (Reg {reg_control:#04x})")
                else: logger.warning(f"Failed to set Motor {motor_id} target (Reg {reg_target_pos:#04x})")
            else: logger.warning("Missing 'value' for set_target command.")

        elif action == "start_move": # Assumes target is already set
             if serial_handler.write_register(reg_control, bytes([0x01])): # Write 1 to start
                 logger.info(f"Triggered Motor {motor_id} move (Reg {reg_control:#04x})")
             else: logger.warning(f"Failed to trigger Motor {motor_id} move (Reg {reg_control:#04x})")

        elif action == "stop_move":
             if serial_handler.write_register(reg_control, bytes([0x02])): # Write 2 to stop
                 logger.info(f"Sent Motor {motor_id} stop command (Reg {reg_control:#04x})")
             else: logger.warning(f"Failed to send Motor {motor_id} stop (Reg {reg_control:#04x})")

        elif action == "set_speed":
             if value is not None:
                 speed = int(value)
                 if serial_handler.write_register(reg_max_speed, pack_u16(speed)):
                      logger.info(f"Set Motor {motor_id} max speed to {speed} (Reg {reg_max_speed:#04x})")
                 else: logger.warning(f"Failed to set Motor {motor_id} speed (Reg {reg_max_speed:#04x})")
             else: logger.warning("Missing 'value' for set_speed command.")

        elif action == "set_accel":
             if value is not None:
                 accel = int(value)
                 if serial_handler.write_register(reg_accel, pack_u16(accel)):
                     logger.info(f"Set Motor {motor_id} accel to {accel} (Reg {reg_accel:#04x})")
                 else: logger.warning(f"Failed to set Motor {motor_id} accel (Reg {reg_accel:#04x})")
             else: logger.warning("Missing 'value' for set_accel command.")

        # Add more command handlers (e.g., homing)

        else:
            logger.warning(f"Unknown action '{action}' for motor {motor_id}")

    except (ValueError, TypeError) as e:
        logger.error(f"Invalid data type in command payload: {payload} - {e}")
    except ProtocolError as e:
        logger.error(f"Serial Protocol Error processing command: {e}")
    except Exception as e:
        logger.error(f"Unexpected error processing command {payload}: {e}", exc_info=True)

# --- Periodic Status Update ---
def status_update_loop():
    """Periodically reads status from Pico and publishes to MQTT."""
    global serial_handler, mqtt_client, stop_event, last_status
    logger.info("Starting status update loop...")
    status_read_errors = 0

    while not stop_event.is_set():
        start_time = time.monotonic()
        if not serial_handler:
            logger.warning("Status Loop: Serial handler not available.")
            stop_event.wait(5) # Wait longer if serial is down
            continue
        if not mqtt_client or not mqtt_client.is_connected():
            logger.warning("Status Loop: MQTT client not connected.")
            stop_event.wait(2)
            continue

        try:
            # --- Read Status Registers ---
            # Combine reads if protocol supports multi-register reads
            status_bytes = serial_handler.read_register(REG_STATUS, 1)
            switches_bytes = serial_handler.read_register(REG_SWITCH_STATUS, 1)
            errors_bytes = serial_handler.read_register(REG_ERROR_FLAGS, 1)
            m1_pos_bytes = serial_handler.read_register(REG_MOTOR1_CURRENT_POS_L, 4)
            m2_pos_bytes = serial_handler.read_register(REG_MOTOR2_CURRENT_POS_L, 4)

            if not all([status_bytes, switches_bytes, errors_bytes, m1_pos_bytes, m2_pos_bytes]):
                logger.warning("Failed to read one or more status registers from Pico.")
                status_read_errors += 1
                if status_read_errors > 5:
                    logger.error("Multiple consecutive status read failures. Check Pico connection.")
                    # Consider attempting serial reconnect?
                stop_event.wait(2) # Wait longer after error
                continue # Skip publishing if reads failed

            status_read_errors = 0 # Reset error count on success

            # --- Unpack Data ---
            status_flags = unpack_u8(status_bytes)
            switch_flags = unpack_u8(switches_bytes)
            error_flags = unpack_u8(errors_bytes)
            motor1_pos = unpack_i32(m1_pos_bytes)
            motor2_pos = unpack_i32(m2_pos_bytes)

            # --- Prepare Payload ---
            current_status = {
                "timestamp": time.time(),
                "status_flags": status_flags,
                "switch_flags": switch_flags,
                "error_flags": error_flags,
                "motor1_pos": motor1_pos,
                "motor2_pos": motor2_pos,
                # Add other readable registers if needed (e.g., current speed, config readback)
            }

            # --- Publish if Status Changed ---
            # Compare with last sent status to reduce MQTT traffic
            if current_status != last_status:
                mqtt_client.publish(f"devices/{DEVICE_ID}/status", current_status)
                logger.debug(f"Published status: {current_status}")
                last_status = current_status # Update cache
            else:
                 logger.debug("Status unchanged, skipping publish.")

        except ProtocolError as e:
            logger.error(f"Serial Protocol Error in status loop: {e}")
            status_read_errors += 1
            # Consider attempting serial reconnect?
            stop_event.wait(5) # Wait longer after protocol error
        except Exception as e:
            logger.error(f"Unexpected error in status update loop: {e}", exc_info=True)
            status_read_errors += 1
            stop_event.wait(5)

        # --- Loop Timing ---
        elapsed = time.monotonic() - start_time
        sleep_time = max(0, 1.0 - elapsed) # Target loop time 1 second
        if sleep_time > 0:
            stop_event.wait(sleep_time) # Use event wait for clean shutdown

    logger.info("Status update loop stopped.")


# --- Main Execution ---
if __name__ == "__main__":
    logger.info(f"--- Starting RPi Agent for Device ID: {DEVICE_ID} ---")

    # 1. Initialize Serial Communication
    try:
        serial_handler = SerialHandler(SERIAL_PORT, BAUD_RATE, timeout=0.5) # Shorter timeout
        logger.info(f"Serial port {SERIAL_PORT} opened.")
        # Brief pause to allow Pico to settle after potential reset on connect
        time.sleep(2.0)
        # Perform a simple read to test connection?
        # test_read = serial_handler.read_register(REG_STATUS, 1)
        # if not test_read: logger.warning("Initial serial test read failed.")
        # else: logger.info("Initial serial test read successful.")

    except Exception as e:
        logger.error(f"CRITICAL: Failed to open serial port {SERIAL_PORT}: {e}")
        # Optionally, could retry here or enter a state waiting for serial
        exit(1) # Exit for now if serial fails initially

    # 2. Fetch Initial Configuration from Backend
    initial_config = None
    try:
        logger.info(f"Fetching initial configuration from {BACKEND_URL}...")
        initial_config = get_config_from_backend(BACKEND_URL, DEVICE_ID)
        if initial_config:
            logger.info("Successfully fetched initial configuration.")
            apply_config(initial_config)
        else:
            logger.warning("No initial configuration found or failed to fetch from backend.")
    except Exception as e:
        logger.error(f"Failed during initial configuration fetch/apply: {e}")
        # Continue running even if config fetch fails? Or exit? Depends on requirements.

    # 3. Initialize MQTT Client
    mqtt_client = MqttClient(MQTT_BROKER, MQTT_PORT, DEVICE_ID, MQTT_USER, MQTT_PASS)
    mqtt_client.set_command_callback(handle_command)
    mqtt_client.connect()

    # 4. Start Status Update Thread
    status_thread = threading.Thread(target=status_update_loop, name="StatusLoop", daemon=True)
    status_thread.start()

    # 5. Keep Main Thread Alive & Monitor Connections
    logger.info("Agent running. Press Ctrl+C to stop.")
    try:
        while not stop_event.is_set():
            if not mqtt_client.is_connected():
                logger.warning("MQTT disconnected. Attempting reconnect...")
                mqtt_client.connect() # Library might handle reconnects, but good to check/trigger

            # Add check for serial connection health if desired
            # e.g., serial_handler.is_open() or occasional test reads
            # if not serial_handler.is_alive(): # Need an is_alive method in SerialHandler
            #    logger.error("Serial connection lost! Attempting reconnect...")
            #    try:
            #        serial_handler.close()
            #        serial_handler = SerialHandler(SERIAL_PORT, BAUD_RATE, timeout=0.5)
            #        logger.info("Serial reconnected.")
            #    except Exception as e:
            #        logger.error(f"Failed to reconnect serial: {e}")
            #        serial_handler = None # Ensure it's marked as down

            stop_event.wait(5.0) # Check connections every 5 seconds

    except KeyboardInterrupt:
        logger.info("Shutdown signal received (Ctrl+C).")
    finally:
        logger.info("Shutting down agent...")
        stop_event.set()

        if status_thread.is_alive():
            logger.info("Waiting for status loop to finish...")
            status_thread.join(timeout=2.0) # Wait max 2 seconds
            if status_thread.is_alive():
                logger.warning("Status loop did not terminate gracefully.")

        if mqtt_client:
            logger.info("Disconnecting MQTT client...")
            mqtt_client.disconnect()

        if serial_handler:
            logger.info("Closing serial port...")
            serial_handler.close()

        logger.info("--- RPi Agent Stopped ---")
