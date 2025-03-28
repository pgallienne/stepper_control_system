import paho.mqtt.client as mqtt
import json
import logging
import time

logger = logging.getLogger("MqttClient")

class MqttClient:
    def __init__(self, broker, port, device_id, username=None, password=None):
        self.broker = broker
        self.port = port
        self.device_id = device_id
        self.command_topic = f"devices/{device_id}/command"
        self.status_topic = f"devices/{device_id}/status"
        self.will_topic = f"devices/{device_id}/connection" # LWT Topic
        self.command_callback = None
        self._client = mqtt.Client(client_id=f"agent_{device_id}", clean_session=True)

        # Last Will and Testament (LWT)
        lwt_payload = json.dumps({"status": "offline", "reason": "unexpected disconnect"})
        self._client.will_set(self.will_topic, payload=lwt_payload, qos=1, retain=True)

        if username:
            self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.on_publish = self._on_publish # Optional: For QoS > 0 confirmation

        self._connected = False
        self._connecting = False
        self._last_connection_attempt = 0

    def set_command_callback(self, callback):
        self.command_callback = callback

    def _on_connect(self, client, userdata, flags, rc):
        self._connecting = False
        if rc == 0:
            logger.info(f"Successfully connected to MQTT Broker: {self.broker}")
            self._connected = True
            # Publish online status via LWT mechanism (by publishing normally to the same topic)
            online_payload = json.dumps({"status": "online"})
            self._client.publish(self.will_topic, payload=online_payload, qos=1, retain=True)
            # Subscribe to command topic
            res, mid = self._client.subscribe(self.command_topic, qos=1) # Use QoS 1 for commands
            if res == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Subscribed to command topic: {self.command_topic}")
            else:
                 logger.error(f"Failed to subscribe to {self.command_topic}: {mqtt.error_string(res)}")
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code {rc}: {mqtt.connack_string(rc)}")
            self._connected = False

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        self._connecting = False
        if rc == 0:
            logger.info("MQTT client disconnected gracefully.")
        else:
            logger.warning(f"Unexpected MQTT disconnection (code {rc}). Will attempt to reconnect.")
            # Reconnection logic is usually handled by loop_start or explicitly in main loop

    def _on_message(self, client, userdata, msg):
        logger.debug(f"MQTT message received on topic {msg.topic} (QoS {msg.qos})")
        if msg.topic == self.command_topic:
            try:
                # Decode payload
                payload_str = msg.payload.decode('utf-8')
                if not payload_str:
                    logger.warning("Received empty command payload.")
                    return
                payload = json.loads(payload_str)

                # Execute callback
                if self.command_callback:
                    try:
                        self.command_callback(payload)
                    except Exception as e:
                         logger.error(f"Error executing command callback for payload {payload}: {e}", exc_info=True)
                else:
                     logger.warning("Command received but no callback is set.")

            except json.JSONDecodeError:
                logger.warning(f"Received non-JSON MQTT message on command topic: {msg.payload}")
            except UnicodeDecodeError:
                 logger.warning(f"Received non-UTF8 MQTT message on command topic: {msg.payload}")
            except Exception as e:
                logger.error(f"Unexpected error processing MQTT message: {e}", exc_info=True)

    def _on_publish(self, client, userdata, mid):
        # Optional: Log confirmation for QoS 1/2 messages
        logger.debug(f"MQTT message published successfully (MID: {mid})")

    def connect(self):
        if self._connected or self._connecting:
            return # Already connected or connection in progress

        now = time.time()
        # Throttle connection attempts
        if now - self._last_connection_attempt < 5: # Wait 5 seconds between attempts
            return

        logger.info(f"Attempting to connect to MQTT broker {self.broker}:{self.port}...")
        self._connecting = True
        self._last_connection_attempt = now
        try:
            self._client.connect_async(self.broker, self.port, 60)
            self._client.loop_start() # Start background thread for network loop & reconnect logic
        except ConnectionRefusedError:
             logger.error(f"MQTT connection refused by broker {self.broker}:{self.port}.")
             self._connecting = False
        except OSError as e:
             logger.error(f"MQTT OS error during connect: {e}")
             self._connecting = False
        except Exception as e:
            logger.error(f"Unexpected MQTT connection error: {e}")
            self._connecting = False


    def disconnect(self):
        if self._connected:
             # Clear the LWT retain message by publishing an empty retained message (or non-retained offline)
             logger.info("Publishing offline status and disconnecting MQTT...")
             offline_payload = json.dumps({"status": "offline", "reason": "graceful shutdown"})
             self._client.publish(self.will_topic, payload=offline_payload, qos=1, retain=True)
             # Allow a moment for message to send before disconnecting
             time.sleep(0.5)

        self._client.loop_stop() # Stop background thread
        self._client.disconnect() # This triggers _on_disconnect with rc=0

    def publish(self, topic, payload, qos=0, retain=False):
        if not self._connected:
            logger.warning(f"MQTT not connected, cannot publish to {topic}.")
            return False

        try:
            json_payload = json.dumps(payload)
            rc, mid = self._client.publish(topic, json_payload, qos=qos, retain=retain)
            if rc == mqtt.MQTT_ERR_SUCCESS:
               logger.debug(f"Publish initiated to {topic} (MID: {mid}, QoS: {qos})")
               return True
            elif rc == mqtt.MQTT_ERR_NO_CONN:
                 logger.warning(f"Failed to publish to {topic}: No connection.")
                 self._connected = False # Mark as disconnected
                 return False
            else:
                 logger.warning(f"Failed to publish MQTT message to {topic}: {mqtt.error_string(rc)}")
                 return False
        except Exception as e:
            logger.error(f"Error encoding or publishing MQTT message: {e}")
            return False

    def is_connected(self):
        # Check internal flag and potentially the underlying client status if available
        # Note: paho's is_connected() might not be reliable immediately after disconnect event
        return self._connected
