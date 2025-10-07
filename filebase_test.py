import boto3

ACCESS_KEY = "5EBB915AC86F860E876D"
SECRET_KEY = "UgS97WjaIqDwaI4b2NdUKc6p8qeloEUuw77vGKUD"
BUCKET_NAME = "iot-data"

s3 = boto3.client(
    "s3",
    endpoint_url="https://s3.filebase.com",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

# Upload a test file
s3.upload_file("sensor_data.csv", BUCKET_NAME, "sensor_data.csv")

print("✅ Uploaded successfully to Filebase!")
