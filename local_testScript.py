import paho.mqtt.client as mqtt
import json
import csv
from datetime import datetime, timedelta, timezone
import time
import os
import requests
import pandas as pd

# Configuration
broker = "eu1.cloud.thethings.network"
port = 1883
username = "bd-test-app2@ttn"
password = "NNSXS.NGFSXX4UXDX55XRIDQZS6LPR4OJXKIIGSZS56CQ.6O4WUAUHFUAHSTEYRWJX6DDO7TL2IBLC7EV2LS4EHWZOOEPCEUOA"
device_id = "lht65n-01-temp-humidity-sensor"
csv_file = "sensor_data.csv"


# Function: Save a row to CSV if not duplicate
def save_to_csv(data):
    if not os.path.exists(csv_file):
        # create with header
        with open(csv_file, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            writer.writeheader()
            writer.writerow(data)
        return

    # Load existing data to check for duplicates
    df = pd.read_csv(csv_file)
    if data["timestamp"] not in df["timestamp"].values:
        with open(csv_file, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=data.keys())
            writer.writerow(data)


# Function: Convert UTC to Uganda Time
def to_uganda_time(utc_time_str):
    utc_dt = datetime.fromisoformat(utc_time_str.replace("Z", "+00:00"))
    uganda_time = utc_dt + timedelta(hours=3)
    return uganda_time.strftime("%Y-%m-%d %H:%M:%S")


# Fetch historical data (48 hours)
def get_historical_sensor_data():
    app_id = "bd-test-app2"
    api_key = password  # reuse same key

    url = f"https://{broker}/api/v3/as/applications/{app_id}/devices/{device_id}/packages/storage/uplink_message"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"last": "48h"}  # fetch last 48 hours

    print("Fetching 48 hours of historical data...")
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        messages = response.text.strip().split("\n")
        for msg_text in messages:
            msg = json.loads(msg_text)
            fields = msg.get("uplink_message", {}).get("decoded_payload", {})
            received_at = msg.get("received_at")

            if not received_at or not fields:
                continue

            data = {
                "timestamp": to_uganda_time(received_at),
                "temperature_C": fields.get("field5"),
                "humidity_%": fields.get("field3"),
                "motion_count": fields.get("field4"),
                "battery_V": fields.get("field1"),
            }

            save_to_csv(data)
        print("Historical data saved successfully.")
    else:
        print("Error fetching historical data:", response.status_code, response.text)


# MQTT callback: connected
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to TTN MQTT broker!")
        topic = f"v3/{username}/devices/{device_id}/up"
        client.subscribe(topic)
    else:
        print(f"Failed to connect, return code {rc}")
        print("Retrying in 5 minutes...")
        time.sleep(300)


# MQTT callback: new message
def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    fields = payload.get("uplink_message", {}).get("decoded_payload", {})
    received_at = payload.get("received_at")

    if not received_at or not fields:
        return

    data = {
        "timestamp": to_uganda_time(received_at),
        "temperature_C": fields.get("field5"),
        "humidity_%": fields.get("field3"),
        "motion_count": fields.get("field4"),
        "battery_V": fields.get("field1"),
    }

    save_to_csv(data)
    print(f"New data saved: {data}")


# Main execution
if __name__ == "__main__":
    # Step 1: Fetch 48-hour historical data
    get_historical_sensor_data()

    # Step 2: Listen for new MQTT data
    client = mqtt.Client()
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(broker, port, 60)
    client.loop_forever()
