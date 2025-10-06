import paho.mqtt.client as mqtt
import json
import requests
import csv
import os
from datetime import datetime, timedelta
import pytz
import time

# Configuration
broker = "eu1.cloud.thethings.network"
port = 1883
username = "bd-test-app2@ttn"
password = "NNSXS.NGFSXX4UXDX55XRIDQZS6LPR4OJXKIIGSZS56CQ.6O4WUAUHFUAHSTEYRWJX6DDO7TL2IBLC7EV2LS4EHWZOOEPCEUOA"
device_id = "lht65n-01-temp-humidity-sensor"

csv_file = "sensor_data.csv"

# Convert UTC → Uganda Time
def to_uganda_time(utc_str):
    utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    uganda_tz = pytz.timezone("Africa/Kampala")
    return utc_dt.astimezone(uganda_tz)

# Ensure CSV file has headers
if not os.path.exists(csv_file):
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Time (Uganda)", "Battery", "Humidity", "Motion", "Temperature"])

# Load existing timestamps to prevent duplicates
def load_existing_timestamps():
    if not os.path.exists(csv_file):
        return set()
    with open(csv_file, "r") as f:
        return {row.split(",")[0] for row in f.readlines()[1:]}
existing_times = load_existing_timestamps()

# Save one record (if not duplicate)
def save_to_csv(time_str, battery, humidity, motion, temperature):
    if time_str not in existing_times:
        with open(csv_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([time_str, battery, humidity, motion, temperature])
        existing_times.add(time_str)

# --- HISTORICAL DATA FETCH ---
def get_historical_sensor_data():
    app_id = "bd-test-app2"
    api_key = password
    url = f"https://{broker}/api/v3/as/applications/{app_id}/devices/{device_id}/packages/storage/uplink_message"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"last": "48h"}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        lines = response.text.strip().splitlines()
        for line in lines:
            try:
                data = json.loads(line)["result"]
                payload = data["uplink_message"]["decoded_payload"]
                timestamp = to_uganda_time(data["received_at"]).strftime("%Y-%m-%d %H:%M:%S")
                save_to_csv(
                    timestamp,
                    payload.get("field1"),
                    payload.get("field3"),
                    payload.get("field4"),
                    payload.get("field5")
                )
            except Exception as e:
                print("Error decoding record:", e)
    else:
        print("Error:", response.status_code, response.text)

# --- REAL-TIME MQTT LISTENER ---
topic = f"v3/{username}/devices/{device_id}/up"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to TTN MQTT broker!")
        client.subscribe(topic)
    else:
        print("Failed to connect, code:", rc)

def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    decoded = payload["uplink_message"]["decoded_payload"]
    timestamp = to_uganda_time(payload["received_at"]).strftime("%Y-%m-%d %H:%M:%S")
    save_to_csv(
        timestamp,
        decoded.get("field1"),
        decoded.get("field3"),
        decoded.get("field4"),
        decoded.get("field5")
    )
    print(f"Saved real-time record @ {timestamp}")

# Fetch last 48 hours once on startup
get_historical_sensor_data()

# Connect and listen
client = mqtt.Client()
client.username_pw_set(username, password)
client.on_connect = on_connect
client.on_message = on_message
client.connect(broker, port, 60)
client.loop_forever()
