import json
import asyncio
import websockets
import paho.mqtt.client as mqtt
import os
import ssl
from dotenv import load_dotenv
from datetime import datetime


# Global list of connected WebSocket clients
websocket_clients = []

load_dotenv()

# Database connection setup
maria_user = os.getenv("maria_user")
maria_password = os.getenv("maria_password")
db_host = os.getenv("db_host")
db_port = os.getenv("db_port")
database = os.getenv("database")

DATABASE_URL = f"""mysql+pymysql://{maria_user}:{
    maria_password}@{db_host}:{db_port}/{database}"""


def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe("/ttndata/#")


def on_message(client, userdata, msg):
    msg.payload = msg.payload.decode()
    coordinates = extract_gateway_coordinates(msg.payload, msg.topic)
    asyncio.run(send_to_websockets(str(coordinates)))


async def send_to_websockets(message):
    if websocket_clients:
        # Create tasks from coroutines before waiting on them
        tasks = [asyncio.create_task(client.send(message))
                 for client in websocket_clients]
        await asyncio.wait(tasks)

# WebSocket handling


def extract_gateway_coordinates(json_message, topic):
    try:
        data = json.loads(json_message)

        # Extracting gateway IDs and their corresponding coordinates
        gateway_coordinates = {}
        if "/ttndata" in topic:
            for gateway in data.get('uplink_message', {}).get('rx_metadata', []):
                gateway_id = gateway.get('gateway_ids', {}).get('gateway_id')
                location = gateway.get('location', {})
                if gateway_id and location:
                    gateway_coordinates["name"] = gateway_id
                    gateway_coordinates["latitude"] = location['latitude']
                    gateway_coordinates["longitude"] = location['longitude']

                elif gateway_id:
                    gateway_coordinates["name"] = gateway_id
                    gateway_coordinates["latitude"] = "50.673119610684594", 
                    gateway_coordinates["longitude"] = "14.049129474739555"
                elif location:
                    gateway_coordinates["name"] = "unknown"
                    gateway_coordinates["latitude"] = location['latitude']
                    gateway_coordinates["longitude"] = location['longitude']
        elif topic == "/vodomery/decin":
            gateway_coordinates["name"] = "vodomery/decin"
            gateway_coordinates["latitude"] = "50.7783"
            gateway_coordinates["longitude"] = "14.2083"
        elif "/Bilina/" in topic:
            gateway_coordinates["name"] = "Bilina"
            gateway_coordinates["latitude"] = "50.545"
            gateway_coordinates["longitude"] = "13.775"
        else:
            return

        return gateway_coordinates
    except json.JSONDecodeError:
        print("Invalid JSON format")
        return {"error": "Invalid JSON format"}


async def websocket_handler(websocket, path):
    websocket_clients.append(websocket)
    try:
        async for message in websocket:
            pass  # WebSocket clients are not expected to send messages
    except websockets.ConnectionClosed:
        pass
    finally:
        websocket_clients.remove(websocket)


async def main():
    server = await websockets.serve(websocket_handler, '0.0.0.0', 8765)
    print("WebSocket server started at ws://0.0.0.0:8765")
    await server.wait_closed()

# Starting MQTT client


def start_mqtt_client():
    broker_address = "mqtt.portabo.cz"
    port = 8883
    mqtt_user = os.getenv("mqtt_user")
    mqtt_password = os.getenv("mqtt_password")
    print(mqtt_user, mqtt_password)

    client = mqtt.Client()
    client.username_pw_set(mqtt_user, mqtt_password)
    client.on_connect = on_connect
    client.on_message = on_message

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    client.tls_set_context(ssl_ctx)
    client.tls_insecure_set(True)

    client.connect(broker_address, port, 60)
    client.loop_start()


if __name__ == "__main__":
    start_mqtt_client()
    asyncio.run(main())
