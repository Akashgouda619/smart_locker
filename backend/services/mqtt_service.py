import paho.mqtt.client as mqtt
import json

client = None
connected = False

def on_connect(mqtt_client, userdata, flags, rc, properties=None):
    global connected
    # rc is the connection status code. 0 is SUCCESS.
    # Depending on paho-mqtt version, rc could be a ReasonCode object.
    # In newer versions of paho-mqtt (>=2.0.0), we check rc.is_failure or compare directly.
    status_code = getattr(rc, "value", rc)
    if status_code == 0:
        connected = True
        print(">>> MQTT Broker connection established successfully.")
    else:
        print(f">>> MQTT connection failed with status code: {status_code}")

def on_disconnect(mqtt_client, userdata, disconnect_flags, rc, properties=None):
    global connected
    connected = False
    print(">>> MQTT client disconnected from broker.")

def init_mqtt():
    """Initializes the MQTT client and starts the background loop."""
    global client, connected
    try:
        # Use paho-mqtt version 2.x API callback style
        client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        
        # Configure connections
        # By default, connects to local Mosquitto broker running on localhost
        broker_ip = "broker.emqx.io"
        broker_port = 1883
        
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        
        # Asynchronous connect to prevent Flask startup block if broker is offline
        client.connect_async(broker_ip, broker_port, keepalive=60)
        client.loop_start()
        print(f">>> MQTT client background loop started. Connecting to {broker_ip}:{broker_port}")
    except Exception as e:
        print(f">>> Failed to initialize Paho MQTT client: {e}")

import paho.mqtt.publish as publish

def publish_command(locker_id, command_name, extra_payload=None):
    """Publishes a control JSON command to a locker topic (smartlocker_67da4/lockers/{locker_id}/commands)"""
    topic = f"smartlocker_67da4/lockers/{locker_id}/commands"
    payload = {
        "command": command_name,
        "locker_id": locker_id
    }
    if extra_payload:
        payload.update(extra_payload)
        
    json_str = json.dumps(payload)
    
    try:
        # Use single-shot publishing to guarantee delivery in multi-process/WSGI environments
        publish.single(
            topic,
            payload=json_str,
            hostname="broker.emqx.io",
            port=1883,
            qos=1
        )
        print(f"[MQTT Publish] Topic: {topic} | Payload: {json_str}")
        return True
    except Exception as e:
        print(f"[MQTT Publish Error] Failed to publish message to topic {topic}: {e}")
        return False

