import random
import json
import asyncio
import websockets
import paho.mqtt.client as mqtt
import os
import ssl
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler


# Global list of connected WebSocket clients
websocket_clients = []

load_dotenv()

messages = 0
troughput = 0


fakedata = [
    {"name": "Roudnice", "latitude": 50.422, "longitude": 14.259},
    {"name": "Litomerice", "latitude": 50.533, "longitude": 14.131},
    {"name": "Chomutov", "latitude": 50.460, "longitude": 13.417},
    {"name": "Teplice", "latitude": 50.640, "longitude": 13.824},
    {"name": "Chlumec", "latitude": 50.425, "longitude": 15.547},
    {"name": "Decin", "latitude": 50.7783, "longitude": 14.2083},
    {"name": "Bilina", "latitude": 50.545, "longitude": 13.775},
    {"name": "Dolni Zleb", "latitude": 50.666, "longitude": 14.033},
    {"name": "Kadan", "latitude": 50.383, "longitude": 13.270},
    {"name": "Klasterec nad Ohri", "latitude": 50.387, "longitude": 13.171},
    {"name": "Krupka", "latitude": 50.656, "longitude": 13.864},
    {"name": "Louny", "latitude": 50.356, "longitude": 13.796},
    {"name": "Lovosice", "latitude": 50.517, "longitude": 14.052},
    {"name": "Melnik", "latitude": 50.350, "longitude": 14.474},
    {"name": "Most", "latitude": 50.503, "longitude": 13.636},
    {"name": "Rumburk", "latitude": 50.952, "longitude": 14.537},
    {"name": "Varnsdorf", "latitude": 50.911, "longitude": 14.619},
    {"name": "Litvinov", "latitude": 50.606, "longitude": 13.618},
]


def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe("#")


def on_message(client, userdata, msg):
    global messages, troughput
    messages += 1
    troughput += len(msg.payload)
    if "ttndata" in msg.topic or "Bilina" in msg.topic or "vodomery/decin" in msg.topic:
        msg.payload = msg.payload.decode()
        coordinates = extract_gateway_coordinates(msg.payload, msg.topic)
        asyncio.run(send_to_websockets(json.dumps(coordinates)))


async def send_to_websockets(message):
    if websocket_clients:
        # Create tasks from coroutines before waiting on them
        tasks = [asyncio.create_task(client.send(message))
                 for client in websocket_clients]
        await asyncio.wait(tasks)

# WebSocket handling


def every_second():
    global messages, troughput
    print(f"Zprav za sekundu: {messages}, Datovy tok: {troughput} B/s")

    asyncio.run(send_to_websockets(json.dumps(
        {"messages": messages, "troughput": troughput})))
    messages = 0
    troughput = 0


def faker():
    global fakedata
    asyncio.run(send_to_websockets(json.dumps(random.choice(fakedata))))
    asyncio.run(send_to_websockets(json.dumps(random.choice(fakedata))))
    asyncio.run(send_to_websockets(json.dumps(random.choice(fakedata))))
    asyncio.run(send_to_websockets(json.dumps(random.choice(fakedata))))


scheduler = BackgroundScheduler()
scheduler.add_job(every_second, 'interval', seconds=1)
scheduler.add_job(faker, 'interval', seconds=1)
scheduler.start()


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
                    gateway_coordinates["latitude"] = 50.673119610684594
                    gateway_coordinates["longitude"] = 14.049129474739555
                elif location:
                    gateway_coordinates["name"] = "unknown"
                    gateway_coordinates["latitude"] = location['latitude']
                    gateway_coordinates["longitude"] = location['longitude']
        elif topic == "/vodomery/decin":
            gateway_coordinates["name"] = "vodomery/decin"
            gateway_coordinates["latitude"] = 50.7783
            gateway_coordinates["longitude"] = 14.2083
        elif "/Bilina/" in topic:
            gateway_coordinates["name"] = "Bilina"
            gateway_coordinates["latitude"] = 50.545
            gateway_coordinates["longitude"] = 13.775
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
    mqtt_user = os.getenv("MQTT_USERNAME")
    mqtt_password = os.getenv("MQTT_PASSWORD")

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
