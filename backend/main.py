import os, io, logging, joblib, boto3
from datetime import datetime
from typing import List
from dotenv import load_dotenv
import pandas as pd
import numpy as np

from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler

# === Load environment variables ===
load_dotenv()

# ===== Filebase Config =====
ENDPOINT_URL = os.getenv("endpoint_url")
BUCKET_NAME = os.getenv("bucket_name")
OBJECT_KEY = os.getenv("object_key")
LOCAL_FILE = os.getenv("local_file")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

POLL_MINUTES = int(os.getenv("POLL_MINUTES", "5"))
MODEL_DIR = os.getenv("MODEL_DIR", "models")

os.makedirs('data', exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sensor ML API")

# ==== Filebase (S3-compatible) client ====
s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

def download_csv_from_filebase(bucket_name: str, object_key: str) -> str:
    """Download CSV file content from Filebase bucket."""
    try:
        obj = s3.get_object(Bucket=bucket_name, Key=object_key)
        content = obj['Body'].read().decode('utf-8')
        return content
    except Exception as e:
        logger.error(f"Error downloading from Filebase: {e}")
        raise

def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    time_col_candidates = ['Time (Uganda)', 'Time', 'timestamp', 'Datetime', 'time']
    tcol = next((c for c in time_col_candidates if c in df.columns), None)
    if tcol is None:
        raise ValueError("No time column found")
    df = df.rename(columns={tcol: 'time'})
    df['time'] = pd.to_datetime(df['time'], errors='coerce')
    df = df.dropna(subset=['time'])
    for col in ['Battery', 'Humidity', 'Motion', 'Temperature']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.sort_values('time').reset_index(drop=True)
    df = df.set_index('time')
    num_cols = [c for c in ['Battery','Humidity','Motion','Temperature'] if c in df.columns]
    if num_cols:
        df[num_cols] = df[num_cols].interpolate(method='time', limit_direction='both')
        for c in num_cols:
            if df[c].isna().any():
                df[c].fillna(df[c].median(), inplace=True)
    df = df.reset_index()
    return df

def load_local() -> pd.DataFrame:
    if os.path.exists(LOCAL_FILE):
        return pd.read_parquet(LOCAL_FILE)
    return pd.DataFrame()

def save_local(df: pd.DataFrame):
    df.to_parquet(LOCAL_FILE, index=False)

def train_and_save_models(df: pd.DataFrame):
    df = df.sort_values('time').reset_index(drop=True)
    df['battery_drop'] = df['Battery'].diff().fillna(0)
    df['time_diff_minutes'] = pd.to_datetime(df['time']).diff().dt.total_seconds().div(60).fillna(0)
    df['battery_drop_per_min'] = df['battery_drop'] / df['time_diff_minutes'].replace(0, np.nan)
    df['battery_drop_per_min'].fillna(0, inplace=True)

    anom_features = [c for c in ['Battery','Humidity','Motion','Temperature','battery_drop_per_min'] if c in df.columns]
    X_anom = df[anom_features].fillna(0).values
    if len(X_anom) >= 10:
        anom = IsolationForest(n_estimators=200, contamination=0.02, random_state=42)
        anom.fit(X_anom)
        joblib.dump(anom, os.path.join(MODEL_DIR, 'anomaly_iforest.joblib'))
        logger.info("Saved anomaly model")

    df_sup = df.copy()
    df_sup['temp_target_next'] = df_sup['Temperature'].shift(-1)
    for lag in [1,2,3]:
        df_sup[f'temp_lag_{lag}'] = df_sup['Temperature'].shift(lag)
        df_sup[f'motion_lag_{lag}'] = df_sup['Motion'].shift(lag)
        df_sup[f'battery_lag_{lag}'] = df_sup['Battery'].shift(lag)
    df_model = df_sup.dropna(subset=['temp_target_next','temp_lag_1','temp_lag_2','temp_lag_3'])
    if len(df_model) >= 20:
        feature_cols = ['temp_lag_1','temp_lag_2','temp_lag_3','motion_lag_1','battery_lag_1']
        X = df_model[feature_cols].values
        y = df_model['temp_target_next'].values
        scaler = StandardScaler()
        Xs = scaler.fit_transform(X)
        rf = RandomForestRegressor(n_estimators=200, random_state=42)
        rf.fit(Xs, y)
        joblib.dump(rf, os.path.join(MODEL_DIR,'temp_rf_model.joblib'))
        joblib.dump(scaler, os.path.join(MODEL_DIR,'temp_scaler.joblib'))
        logger.info("Saved temperature model and scaler")
    else:
        logger.info("Not enough data to train temperature model yet")

def process_and_train():
    logger.info("Polling Filebase for CSV...")
    try:
        raw = download_csv_from_filebase(BUCKET_NAME, OBJECT_KEY)
    except Exception as e:
        logger.exception("Failed downloading CSV: %s", e)
        return
    df_remote = pd.read_csv(io.StringIO(raw))
    df_clean = clean_df(df_remote)
    df_local = load_local()
    if df_local.empty:
        merged = df_clean
        new_rows = len(df_clean)
    else:
        last_time = pd.to_datetime(df_local['time']).max()
        mask_new = pd.to_datetime(df_clean['time']) > last_time
        merged = pd.concat([df_local, df_clean[mask_new]], ignore_index=True).sort_values('time').reset_index(drop=True)
        new_rows = mask_new.sum()
    if new_rows == 0:
        logger.info("No new rows.")
    else:
        logger.info("Found %d new rows. Saving and retraining.", new_rows)
        save_local(merged)
        train_and_save_models(merged)

@app.on_event("startup")
def startup_event():
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_and_train, 'interval', minutes=POLL_MINUTES, next_run_time=datetime.now())
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(f"Scheduler started, polling every {POLL_MINUTES} minutes")

@app.get("/health")
def health():
    return {"status":"ok"}
