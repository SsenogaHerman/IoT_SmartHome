import time
import json
import requests
import paho.mqtt.client as mqtt
from datetime import datetime, timedelta, timezone
import pytz
import threading
import os

# ================== CONFIGURATION ==================
TTN_BROKER = "eu1.cloud.thethings.network"
TTN_PORT = 1883
TTN_USERNAME = "bd-test-app2@ttn"
TTN_PASSWORD = "NNSXS.NGFSXX4UXDX55XRIDQZS6LPR4OJXKIIGSZS56CQ.6O4WUAUHFUAHSTEYRWJX6DDO7TL2IBLC7EV2LS4EHWZOOEPCEUOA"
DEVICE_ID = "lht65n-01-temp-humidity-sensor"
APP_ID = "bd-test-app2"

THINGSPEAK_WRITE_API_KEY = "Z044OAB9E0YA5UNB"
THINGSPEAK_URL = "https://api.thingspeak.com/update"

HISTORY_HOURS = 48  # Keep track of last 48h to prevent duplicates
TIMESTAMP_FILE = "sent_timestamps.txt"
# ====================================================

# ---------- Ensure timestamp storage exists ----------
if not os.path.exists(TIMESTAMP_FILE):
    open(TIMESTAMP_FILE, "w").close()

# ---------- Load sent timestamps ----------
def load_sent_timestamps():
    with open(TIMESTAMP_FILE, "r") as f:
        return set(line.strip() for line in f.readlines())

sent_timestamps = load_sent_timestamps()

# ---------- Save a sent timestamp ----------
def save_sent_timestamp(ts):
    global sent_timestamps
    sent_timestamps.add(ts)
    # Keep only last HISTORY_HOURS timestamps
    now = datetime.now(timezone.utc)
    to_keep = {
        t for t in sent_timestamps
        if now - datetime.fromisoformat(t.replace("Z", "+00:00")) <= timedelta(hours=HISTORY_HOURS)
    }
    sent_timestamps = to_keep
    with open(TIMESTAMP_FILE, "w") as f:
        for t in sent_timestamps:
            f.write(f"{t}\n")

# ---------- Map telemetry to ThingSpeak ----------
def map_to_thingspeak_fields(telemetry):
    mapping = {
        "temperature": "field1",
        "humidity": "field2",
        "motion": "field3",
        "battery": "field4",
        "pred_temperature": "field5",
        "pred_humidity": "field6",
        "pred_motion": "field7",
        "pred_custom": "field8",
    }
    data = {"api_key": THINGSPEAK_WRITE_API_KEY}
    for key, field in mapping.items():
        value = telemetry.get(key)
        if value is not None:
            data[field] = value
    # Include timestamp if available
    if "timestamp" in telemetry and telemetry["timestamp"]:
        data["created_at"] = telemetry["timestamp"]
    return data

# ---------- Send telemetry safely (no duplicates) ----------
def send_to_thingspeak_safe(telemetry):
    ts = telemetry.get("timestamp")
    if ts in sent_timestamps:
        print(f"Skipping duplicate timestamp: {ts}")
        return
    send_to_thingspeak(telemetry)
    save_sent_timestamp(ts)

# ---------- Send telemetry ----------
def send_to_thingspeak(telemetry):
    try:
        data = map_to_thingspeak_fields(telemetry)
        response = requests.post(THINGSPEAK_URL, params=data)
        if response.status_code not in [200, 201]:
            print("Failed to send to ThingSpeak:", response.status_code, response.text)
        else:
            print("Sent to ThingSpeak:", data)
    except Exception as e:
        print("Error sending to ThingSpeak:", e)

# ---------- Fetch historical data ----------
def fetch_historical_data(hours=20, delay=15):
    tz = pytz.timezone("Africa/Kampala")
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)
    start_utc = start_time.isoformat()
    end_utc = now.isoformat()

    url = f"https://{TTN_BROKER}/api/v3/as/applications/{APP_ID}/devices/{DEVICE_ID}/packages/storage/uplink_message"
    headers = {"Authorization": f"Bearer {TTN_PASSWORD}"}
    params = {"after": start_utc, "before": end_utc, "format": "json", "order": "received_at"}

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        results = []
        for line in response.text.strip().splitlines():
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                print("Skipped invalid line in TTN response")
        print(f"Fetched {len(results)} historical messages.")

        for i, msg in enumerate(results):
            uplink = msg.get("result", {}).get("uplink_message", {})
            decoded = uplink.get("decoded_payload", {})
            timestamp = msg.get("result", {}).get("received_at")
            if decoded and timestamp:
                telemetry = {
                    "temperature": decoded.get("field5"),
                    "humidity": decoded.get("field3"),
                    "motion": decoded.get("field4"),
                    "battery": decoded.get("field1"),
                    "timestamp": timestamp,
                    "pred_temperature": None,
                    "pred_humidity": None,
                    "pred_motion": None,
                    "pred_custom": None
                }
                send_to_thingspeak_safe(telemetry)
            else:
                print(f"No decoded payload for message {i+1}")
            time.sleep(delay)
    else:
        print("Error fetching historical data:", response.status_code, response.text)

# ---------- MQTT Callbacks ----------
TOPIC = f"v3/{TTN_USERNAME}/devices/{DEVICE_ID}/up"

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to TTN MQTT broker!")
        client.subscribe(TOPIC)
    else:
        print("Failed to connect, return code", rc)

def on_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    uplink = payload.get("uplink_message", {})
    decoded = uplink.get("decoded_payload", {})
    timestamp = payload.get("received_at") or uplink.get("received_at")
    if decoded and timestamp:
        telemetry = {
            "temperature": decoded.get("field5"),
            "humidity": decoded.get("field3"),
            "motion": decoded.get("field4"),
            "battery": decoded.get("field1"),
            "timestamp": timestamp,
            "pred_temperature": None,
            "pred_humidity": None,
            "pred_motion": None,
            "pred_custom": None
        }
        threading.Thread(target=lambda: [send_to_thingspeak_safe(telemetry), time.sleep(15)]).start()

# ---------- Main ----------
if __name__ == "__main__":
    client = mqtt.Client()
    client.username_pw_set(TTN_USERNAME, TTN_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(TTN_BROKER, TTN_PORT, 60)

    client.loop_start()
    last_historical_day = None

    try:
        while True:
            now = datetime.now(pytz.timezone("Africa/Kampala"))
            # Fetch historical data once per day
            if last_historical_day != now.day:
                print("Fetching historical TTN data...")
                fetch_historical_data(hours=20, delay=15)
                last_historical_day = now.day
            time.sleep(60)
    except KeyboardInterrupt:
        client.loop_stop()
        print("Script stopped.")
