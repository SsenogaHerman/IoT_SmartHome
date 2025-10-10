import boto3

# ====== Filebase Config ======
endpoint_url = "https://s3.filebase.com"
bucket_name = "iot-data"
object_key = "sensor_data.csv"  # the file name on Filebase
local_file = "downloaded_sensor_data.csv"

# Replace these with your Filebase Access Keys
ACCESS_KEY = "5EBB915AC86F860E876D"
SECRET_KEY = "UgS97WjaIqDwaI4b2NdUKc6p8qeloEUuw77vGKUD"
# ==============================

# Create the S3 client
s3 = boto3.client(
    "s3",
    endpoint_url=endpoint_url,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

try:
    print("Downloading file from Filebase...")
    s3.download_file(bucket_name, object_key, local_file)
    print(f"✅ File downloaded successfully as '{local_file}'")

    # (Optional) Read and display first few lines
    with open(local_file, "r") as f:
        for i in range(5):
            line = f.readline()
            if not line:
                break
            print(line.strip())

except Exception as e:
    print("❌ Error:", e)
