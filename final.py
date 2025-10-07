import paho.mqtt.client as mqtt
import json
import requests
import csv
import os
import boto3
from datetime import datetime
import pytz

# ================= CONFIGURATION =================
broker = "eu1.cloud.thethings.network"
port = 1883
username = "bd-test-app2@ttn"
password = "NNSXS.NGFSXX4UXDX55XRIDQZS6LPR4OJXKIIGSZS56CQ.6O4WUAUHFUAHSTEYRWJX6DDO7TL2IBLC7EV2LS4EHWZOOEPCEUOA"
device_id = "lht65n-01-temp-humidity-sensor"
app_id = "bd-test-app2"

csv_file = "sensor_data.csv"

# ===== FILEBASE CONFIGURATION =====
FILEBASE_BUCKET = "iot-data"
FILEBASE_ACCESS_KEY = "5EBB915AC86F860E876D"
FILEBASE_SECRET_KEY = "UgS97WjaIqDwaI4b2NdUKc6p8qeloEUuw77vGKUD"
FILEBASE_REGION = "us-east-1"  # default region for Filebase
# ==================================

# ---------- Convert UTC → Uganda Time ----------
def to_uganda_time(utc_str):
    utc_dt = datetime.fromisoformat(utc_str.replace("Z", "+00:00"))
    uganda_tz = pytz.timezone("Africa/Kampala")
    return utc_dt.astimezone(uganda_tz)

# ---------- Ensure CSV has headers ----------
if not os.path.exists(csv_file):
    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Time (Uganda)", "Battery", "Humidity", "Motion", "Temperature"])

# ---------- Load existing timestamps ----------
def load_existing_timestamps():
    if not os.path.exists(csv_file):
        return set()
    with open(csv_file, "r") as f:
        return {row.split(",")[0] for row in f.readlines()[1:]}
existing_times = load_existing_timestamps()

# ---------- Get latest timestamp in CSV ----------
def get_latest_timestamp():
    if not os.path.exists(csv_file):
        return None
    with open(csv_file, "r") as f:
        lines = f.readlines()
        if len(lines) > 1:
            last_line = lines[-1].strip()
            if last_line:
                return last_line.split(",")[0]
    return None

# ---------- Upload to Filebase ----------
def upload_to_filebase():
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url="https://s3.filebase.com",
            aws_access_key_id=FILEBASE_ACCESS_KEY,
            aws_secret_access_key=FILEBASE_SECRET_KEY,
            region_name=FILEBASE_REGION,
        )
        s3.upload_file(csv_file, FILEBASE_BUCKET, os.path.basename(csv_file))
        print("☁️ Uploaded latest CSV to Filebase successfully.")
    except Exception as e:
        print("⚠️ Error uploading to Filebase:", e)

# ---------- Save one record ----------
def save_to_csv(time_str, battery, humidity, motion, temperature):
    if time_str not in existing_times:
        with open(csv_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([time_str, battery, humidity, motion, temperature])
        existing_times.add(time_str)
        print(f"Saved record @ {time_str}")

        # Upload to Filebase after saving a new record
        upload_to_filebase()
    else:
        print(f"Skipped duplicate @ {time_str}")

# ---------- Fetch historical data (optimized) ----------
def get_historical_sensor_data():
    latest_saved = get_latest_timestamp()
    headers = {"Authorization": f"Bearer {password}"}
    url = f"https://{broker}/api/v3/as/applications/{app_id}/devices/{device_id}/packages/storage/uplink_message"

    params = {"format": "json", "order": "received_at"}
    if latest_saved:
        # Convert last local timestamp → UTC ISO for TTN
        uganda_tz = pytz.timezone("Africa/Kampala")
        last_local_dt = uganda_tz.localize(datetime.strptime(latest_saved, "%Y-%m-%d %H:%M:%S"))
        last_utc = last_local_dt.astimezone(pytz.utc)
        params["after"] = last_utc.isoformat()
        print(f"Fetching data after {params['after']}")
    else:
        params["last"] = "48h"
        print("No previous data found → Fetching last 48 hours")

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
        print("Historical fetch complete ✅")
    else:
        print("Error fetching historical data:", response.status_code, response.text)

# ---------- MQTT callbacks ----------
topic = f"v3/{username}/devices/{device_id}/up"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to TTN MQTT broker!")
        client.subscribe(topic)
    else:
        print("Failed to connect, code:", rc)

def on_message(client, userdata, msg):
    try:
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
    except Exception as e:
        print("Error handling live message:", e)

# ---------- MAIN ----------
if __name__ == "__main__":
    print("Starting script...\n")
    get_historical_sensor_data()   # Catch up first
    print("\nNow listening for real-time data...\n")

    client = mqtt.Client()
    client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(broker, port, 60)
    client.loop_forever()
