import os
import json
import logging
import threading
import time
from flask import Flask, request, jsonify, current_app
from flask_sqlalchemy import SQLAlchemy
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# --- Load Environment Variables ---
load_dotenv() # Load .env file if present

# --- Logging Setup ---
logging.basicConfig(
    level=os.environ.get('LOG_LEVEL', 'INFO').upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BackendApp")

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Configuration ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, 'database.db')

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', f'sqlite:///{DEFAULT_DB_PATH}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MQTT_BROKER'] = os.environ.get('MQTT_BROKER', 'localhost')
app.config['MQTT_PORT'] = int(os.environ.get('MQTT_PORT', 1883))
app.config['MQTT_USER'] = os.environ.get('MQTT_USER', None)
app.config['MQTT_PASS'] = os.environ.get('MQTT_PASS', None)
app.config['MQTT_CLIENT_ID'] = os.environ.get('MQTT_BACKEND_CLIENT_ID', 'backend_server')

# Add a simple in-memory cache for latest device status
# WARNING: This is lost on restart. For persistent status, use DB or Redis.
device_status_cache = {}
status_cache_lock = threading.Lock()

# --- Database Setup ---
db = SQLAlchemy(app)

# --- Database Model ---
class DeviceConfig(db.Model):
    __tablename__ = 'device_config'
    id = db.Column(db.String(80), primary_key=True) # Device ID (e.g., RPiStepper_001)
    config_json = db.Column(db.Text, nullable=False, default='{}') # Store config as JSON string
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def set_config(self, config_dict):
        try:
            self.config_json = json.dumps(config_dict)
        except TypeError as e:
             logger.error(f"Failed to serialize config to JSON for {self.id}: {e}")
             raise # Re-raise to indicate failure

    def get_config(self):
        try:
            # Return empty dict if json is null/empty or invalid
            return json.loads(self.config_json or '{}')
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON found in DB for device {self.id}. Returning empty config.")
            return {}

    def __repr__(self):
        return f'<DeviceConfig {self.id}>'

# --- MQTT Client Setup ---
mqtt_client = None
mqtt_connected = threading.Event()

def on_mqtt_connect(client, userdata, flags, rc):
    app_ctx = userdata['app_context']
    with app_ctx: # Need app context for logging/config
        if rc == 0:
            logger.info(f"MQTT Backend connected successfully to {current_app.config['MQTT_BROKER']}.")
            mqtt_connected.set()
            # Subscribe to status topics
            status_topic = "devices/+/status" # Wildcard for all devices
            conn_topic = "devices/+/connection" # Wildcard for LWT
            res_stat, _ = client.subscribe(status_topic, qos=0) # QoS 0 for status is often fine
            res_conn, _ = client.subscribe(conn_topic, qos=1) # QoS 1 for reliable connection status

            if res_stat == mqtt.MQTT_ERR_SUCCESS:
                 logger.info(f"Subscribed to device status topic: {status_topic}")
            else: logger.error(f"Failed to subscribe to {status_topic}: {mqtt.error_string(res_stat)}")

            if res_conn == mqtt.MQTT_ERR_SUCCESS:
                 logger.info(f"Subscribed to device connection topic: {conn_topic}")
            else: logger.error(f"Failed to subscribe to {conn_topic}: {mqtt.error_string(res_conn)}")

        else:
            logger.error(f"MQTT Backend connection failed, code {rc}: {mqtt.connack_string(rc)}")
            mqtt_connected.clear()

def on_mqtt_disconnect(client, userdata, rc):
    app_ctx = userdata['app_context']
    with app_ctx:
        mqtt_connected.clear()
        if rc == 0:
             logger.info("MQTT Backend disconnected gracefully.")
        else:
            logger.warning(f"Unexpected MQTT Backend disconnection (code {rc}). Will attempt reconnect.")
            # Paho loop_start handles basic reconnection attempts

def on_mqtt_message(client, userdata, msg):
    app_ctx = userdata['app_context']
    with app_ctx: # Need app context for logging/cache access
        logger.debug(f"MQTT message received on topic {msg.topic}")
        topic_parts = msg.topic.split('/')

        # Expected formats: devices/{id}/status or devices/{id}/connection
        if len(topic_parts) == 3 and topic_parts[0] == 'devices':
            device_id = topic_parts[1]
            msg_type = topic_parts[2]

            try:
                payload_str = msg.payload.decode('utf-8')
                if not payload_str:
                    logger.warning(f"Received empty payload on {msg.topic}")
                    return
                payload = json.loads(payload_str)

                if msg_type == 'status':
                    logger.debug(f"Received status for {device_id}: {payload}")
                    # Update in-memory cache
                    with status_cache_lock:
                        device_status_cache[device_id] = payload
                    # Optional: Persist to database or time-series DB if needed
                    # Optional: Forward to WebSockets for real-time UI updates

                elif msg_type == 'connection':
                    conn_status = payload.get("status", "unknown")
                    logger.info(f"Device connection update for {device_id}: {conn_status}")
                    # Update cache or DB with connection status
                    with status_cache_lock:
                         # Ensure status entry exists
                         if device_id not in device_status_cache:
                              device_status_cache[device_id] = {}
                         device_status_cache[device_id]['connection_status'] = conn_status
                         device_status_cache[device_id]['connection_updated_at'] = time.time()
                    # Optional: Forward to WebSockets

            except json.JSONDecodeError:
                logger.warning(f"Received non-JSON MQTT message on {msg.topic}: {msg.payload}")
            except UnicodeDecodeError:
                 logger.warning(f"Received non-UTF8 MQTT message on {msg.topic}: {msg.payload}")
            except Exception as e:
                logger.error(f"Error processing MQTT message from {msg.topic}: {e}", exc_info=True)
        else:
            logger.debug(f"Ignoring message on unrecognized topic: {msg.topic}")


def setup_mqtt(flask_app):
    global mqtt_client
    if mqtt_client:
        logger.warning("MQTT client already initialized.")
        return mqtt_client

    client = mqtt.Client(client_id=flask_app.config['MQTT_CLIENT_ID'], clean_session=True)
    client.user_data_set({'app_context': flask_app.app_context()}) # Pass app context

    if flask_app.config['MQTT_USER']:
        client.username_pw_set(flask_app.config['MQTT_USER'], flask_app.config['MQTT_PASS'])

    client.on_connect = on_mqtt_connect
    client.on_disconnect = on_mqtt_disconnect
    client.on_message = on_mqtt_message

    try:
        logger.info(f"Connecting MQTT client to {flask_app.config['MQTT_BROKER']}:{flask_app.config['MQTT_PORT']}...")
        client.connect_async(flask_app.config['MQTT_BROKER'], flask_app.config['MQTT_PORT'], 60)
        client.loop_start() # Start background thread
        mqtt_client = client
        # Wait briefly for connection attempt
        mqtt_connected.wait(timeout=5.0)
        if not mqtt_connected.is_set():
             logger.warning("MQTT client did not connect within timeout during setup.")

    except Exception as e:
        logger.error(f"Failed to initiate MQTT connection: {e}")
        mqtt_client = None

    return mqtt_client

# --- API Routes ---
@app.route('/api/health', methods=['GET'])
def health_check():
    # Basic health check
    mqtt_status = "connected" if mqtt_connected.is_set() else "disconnected"
    db_status = "unknown"
    try:
        # Try a simple DB query
        db.session.execute('SELECT 1')
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "error"

    return jsonify({
        "status": "ok",
        "mqtt_status": mqtt_status,
        "db_status": db_status
        }), 200


@app.route('/api/devices/<string:device_id>/config', methods=['GET'])
def get_device_config(device_id):
    logger.info(f"GET /api/devices/{device_id}/config")
    device = DeviceConfig.query.get(device_id)
    if device:
        return jsonify(device.get_config()), 200
    else:
        logger.warning(f"Device config not found for ID: {device_id}")
        return jsonify({"error": "Device configuration not found"}), 404

@app.route('/api/devices/<string:device_id>/config', methods=['PUT'])
def update_device_config(device_id):
    logger.info(f"PUT /api/devices/{device_id}/config")
    if not request.is_json:
        logger.warning("PUT config request received without JSON body.")
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    if not isinstance(data, dict):
         logger.warning("PUT config request received with invalid JSON (not an object).")
         return jsonify({"error": "Request body must be a JSON object"}), 400

    device = DeviceConfig.query.get(device_id)
    if not device:
        # Create new device entry if it doesn't exist
        logger.info(f"Creating new device config entry for ID: {device_id}")
        device = DeviceConfig(id=device_id)
        db.session.add(device)

    try:
        device.set_config(data) # This also validates basic JSON serialization
        db.session.commit()
        logger.info(f"Successfully updated config for device {device_id}")

        # Optional: Publish a notification that config was updated?
        # if mqtt_connected.is_set():
        #     mqtt_client.publish(f"devices/{device_id}/config_update", payload=json.dumps({"status": "updated"}), qos=0)

        return jsonify({"message": "Configuration updated successfully"}), 200
    except TypeError as e:
         db.session.rollback()
         logger.error(f"Failed to serialize config data for {device_id}: {e}")
         return jsonify({"error": f"Invalid configuration data format: {e}"}), 400
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database error updating config for {device_id}: {e}", exc_info=True)
        return jsonify({"error": "Failed to update configuration in database"}), 500

@app.route('/api/devices/<string:device_id>/command', methods=['POST'])
def send_device_command(device_id):
    logger.info(f"POST /api/devices/{device_id}/command")
    if not request.is_json:
        logger.warning("POST command request received without JSON body.")
        return jsonify({"error": "Request must be JSON"}), 400

    command_data = request.get_json()
    if not isinstance(command_data, dict):
         logger.warning("POST command request received with invalid JSON (not an object).")
         return jsonify({"error": "Request body must be a JSON object"}), 400

    topic = f"devices/{device_id}/command"

    if not mqtt_connected.is_set():
         logger.error("MQTT client not connected, cannot send command.")
         # Optionally try to reconnect here, but better handled by background loop
         return jsonify({"error": "Backend MQTT client is not connected"}), 503 # Service Unavailable

    try:
        payload = json.dumps(command_data)
        # Use QoS 1 for commands to ensure delivery attempt
        rc, mid = mqtt_client.publish(topic, payload, qos=1)

        if rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"Published command to {topic}: {payload} (MID: {mid})")
            return jsonify({"message": "Command accepted for sending", "mid": mid}), 202 # Accepted
        elif rc == mqtt.MQTT_ERR_NO_CONN:
             logger.error(f"Failed to publish command to {topic}: No connection.")
             mqtt_connected.clear() # Update flag
             return jsonify({"error": "Backend MQTT client lost connection"}), 503
        else:
            logger.error(f"Failed to publish command to {topic}: {mqtt.error_string(rc)}")
            return jsonify({"error": "Failed to publish MQTT command"}), 500
    except TypeError as e:
         logger.error(f"Failed to serialize command data for {device_id}: {e}")
         return jsonify({"error": f"Invalid command data format: {e}"}), 400
    except Exception as e:
        logger.error(f"Error sending command via MQTT: {e}", exc_info=True)
        return jsonify({"error": "Internal server error while sending command"}), 500

@app.route('/api/devices/<string:device_id>/status', methods=['GET'])
def get_device_status(device_id):
    """Returns the latest cached status for the device."""
    logger.info(f"GET /api/devices/{device_id}/status")
    with status_cache_lock:
        status = device_status_cache.get(device_id)

    if status:
        return jsonify(status), 200
    else:
        # Check if device config exists as indicator device is known
        device_exists = DeviceConfig.query.get(device_id) is not None
        if device_exists:
             logger.warning(f"Status requested for known device {device_id}, but no status cached.")
             return jsonify({"error": "Device status not available yet"}), 404 # Or 200 with empty body?
        else:
             logger.warning(f"Status requested for unknown device ID: {device_id}")
             return jsonify({"error": "Device not found"}), 404


@app.route('/api/devices', methods=['GET'])
def list_devices():
    """Lists devices known by config and/or cached status."""
    logger.info("GET /api/devices")
    known_devices = set()

    # Devices from Config DB
    try:
        config_devices = db.session.query(DeviceConfig.id).all()
        known_devices.update([d.id for d in config_devices])
    except Exception as e:
         logger.error(f"Error querying devices from DB: {e}")
         # Don't fail the request, just might miss some devices

    # Devices from Status Cache
    with status_cache_lock:
        known_devices.update(device_status_cache.keys())

    device_list = []
    for dev_id in sorted(list(known_devices)):
         with status_cache_lock:
              status = device_status_cache.get(dev_id, {})
         device_list.append({
             "id": dev_id,
             "connection_status": status.get("connection_status", "unknown"),
             "last_status_update": status.get("timestamp"),
             "last_connection_update": status.get("connection_updated_at"),
         })

    return jsonify(device_list), 200


# --- Initialization within Application Context ---
@app.before_first_request
def initialize_app():
    """Perform initialization before the first request."""
    with app.app_context():
        logger.info("Performing initial application setup...")
        # Create database tables if they don't exist
        try:
            db.create_all()
            logger.info("Database tables checked/created.")
        except Exception as e:
            logger.error(f"CRITICAL: Failed to create database tables: {e}", exc_info=True)
            # Might want to exit if DB setup fails depending on requirements

        # Setup MQTT client
        setup_mqtt(current_app)


# --- Main Entry Point (for development) ---
if __name__ == '__main__':
    # WARNING: This is for development only!
    # Use a production WSGI server like Gunicorn in production.
    logger.info("Starting Flask development server...")
    # Need to run init manually if using `flask run` or this block
    with app.app_context():
         try:
              db.create_all()
              logger.info("Database tables checked/created (main).")
         except Exception as e:
              logger.error(f"CRITICAL: Failed to create database tables (main): {e}", exc_info=True)
         setup_mqtt(app)

    # Consider using threaded=True for dev server if needed, but be wary of context issues
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_DEBUG', 'False').lower() == 'true')
