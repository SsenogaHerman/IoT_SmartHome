import os
import io
import logging
import joblib
import boto3
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
import pandas as pd
import numpy as np
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from sklearn.ensemble import RandomForestRegressor, IsolationForest
from sklearn.preprocessing import StandardScaler

# === Load environment variables ===
load_dotenv()

# ===== Filebase Config =====
ENDPOINT_URL = os.getenv("endpoint_url")
BUCKET_NAME = os.getenv("bucket_name")
OBJECT_KEY = os.getenv("object_key")
LOCAL_FILE = os.getenv("local_file", "data/local.parquet")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
POLL_MINUTES = int(os.getenv("POLL_MINUTES", "5"))
MODEL_DIR = os.getenv("MODEL_DIR", "models")

os.makedirs('data', exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Sensor ML API")

# ✅ ADD CORS MIDDLEWARE - This is critical!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==== Filebase (S3-compatible) client ====
s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT_URL,
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

# ======== Helper Functions =========
def download_csv_from_filebase(bucket_name: str, object_key: str) -> str:
    """Download CSV file content from Filebase bucket with encoding fallback and save locally for inspection."""
    try:
        obj = s3.get_object(Bucket=bucket_name, Key=object_key)
        raw_bytes = obj['Body'].read()
        try:
            content = raw_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = raw_bytes.decode('utf-8-sig')
            except UnicodeDecodeError:
                content = raw_bytes.decode('latin1')
                logger.warning("CSV decoded using 'latin1' fallback")
        
        with open("data/downloaded_sensor_data.csv", "w", encoding="utf-8") as f:
            f.write(content)
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

# ======== Model Training =========
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

# ======== Processing Pipeline =========
def process_and_train():
    logger.info("Polling Filebase for CSV...")
    try:
        raw = download_csv_from_filebase(BUCKET_NAME, OBJECT_KEY)
    except Exception as e:
        logger.exception("Failed downloading CSV: %s", e)
        return
    
    try:
        df_remote = pd.read_csv(io.StringIO(raw))
    except pd.errors.ParserError as e:
        logger.error("CSV parsing failed: %s", e)
        return
    
    if df_remote.empty:
        logger.warning("Downloaded CSV is empty")
        return
    
    df_clean = clean_df(df_remote)
    if df_clean.empty:
        logger.warning("Cleaned dataframe is empty after processing")
        return
    
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
        logger.info("No new rows found in CSV.")
    else:
        logger.info("Found %d new rows. Saving and retraining.", new_rows)
        save_local(merged)
        train_and_save_models(merged)

# ======== Startup Scheduler =========
@app.on_event("startup")
def startup_event():
    # Run once on startup to ensure data exists
    try:
        process_and_train()
    except Exception as e:
        logger.error(f"Initial data processing failed: {e}")
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_and_train, 'interval', minutes=POLL_MINUTES)
    scheduler.start()
    app.state.scheduler = scheduler
    logger.info(f"Scheduler started, polling every {POLL_MINUTES} minutes")

# ======== API Endpoints =========
@app.get("/health")
def health():
    return {"status":"ok"}

# ✅ FIXED: Proper datetime serialization and null handling
@app.get("/analytics")
def get_analytics(limit: int = 50) -> Dict[str, Any]:
    """Return summary analytics for dashboard."""
    df = load_local()
    
    if df.empty:
        return {
            "avg_temperature": 0,
            "avg_humidity": 0,
            "avg_battery": 0,
            "recent_readings": []
        }
    
    # Calculate averages with proper null handling
    avg_temperature = float(df['Temperature'].mean()) if 'Temperature' in df.columns else 0.0
    avg_humidity = float(df['Humidity'].mean()) if 'Humidity' in df.columns else 0.0
    avg_battery = float(df['Battery'].mean()) if 'Battery' in df.columns else 0.0
    
    # Get recent readings and convert datetime to string
    recent_df = df.tail(limit).copy()
    recent_df['time'] = recent_df['time'].astype(str)
    
    # Convert to dict and ensure all values are JSON serializable
    recent_readings = recent_df.to_dict(orient="records")
    for reading in recent_readings:
        for key, value in reading.items():
            if pd.isna(value):
                reading[key] = None
            elif isinstance(value, (np.integer, np.floating)):
                reading[key] = float(value)
    
    return {
        "avg_temperature": round(avg_temperature, 2),
        "avg_humidity": round(avg_humidity, 2),
        "avg_battery": round(avg_battery, 2),
        "recent_readings": recent_readings
    }

@app.get("/predict")
def predict_temperature() -> Dict[str, Any]:
    """Return next temperature prediction based on last row."""
    df = load_local()
    
    if df.empty:
        return {"predicted_next_temperature": None}
    
    try:
        rf = joblib.load(os.path.join(MODEL_DIR, 'temp_rf_model.joblib'))
        scaler = joblib.load(os.path.join(MODEL_DIR, 'temp_scaler.joblib'))
    except FileNotFoundError:
        return {"predicted_next_temperature": None}
    
    last_row = df.iloc[-1]
    features = np.array([[
        last_row['Temperature'],
        last_row['Temperature'],
        last_row['Temperature'],
        last_row['Motion'],
        last_row['Battery']
    ]])
    features_scaled = scaler.transform(features)
    pred = rf.predict(features_scaled)
    
    return {"predicted_next_temperature": round(float(pred[0]), 2)}

@app.get("/anomalies")
def get_anomalies(limit: int = 50) -> List[Dict[str, Any]]:
    """Return anomaly rows for dashboard."""
    df = load_local()
    
    if df.empty:
        return []
    
    try:
        anom_model = joblib.load(os.path.join(MODEL_DIR, 'anomaly_iforest.joblib'))
    except FileNotFoundError:
        return []
    
    # Add battery_drop_per_min if not present
    if 'battery_drop_per_min' not in df.columns:
        df['battery_drop'] = df['Battery'].diff().fillna(0)
        df['time_diff_minutes'] = pd.to_datetime(df['time']).diff().dt.total_seconds().div(60).fillna(0)
        df['battery_drop_per_min'] = df['battery_drop'] / df['time_diff_minutes'].replace(0, np.nan)
        df['battery_drop_per_min'].fillna(0, inplace=True)
    
    features = [c for c in ['Battery','Humidity','Motion','Temperature','battery_drop_per_min'] if c in df.columns]
    X = df[features].fillna(0).values
    scores = anom_model.decision_function(X)
    
    df_anom = df.copy()
    df_anom['anomaly_score'] = scores
    df_anom['time'] = df_anom['time'].astype(str)
    
    anomalies = df_anom[df_anom['anomaly_score'] < 0].tail(limit)
    
    # Convert to dict and clean up
    result = anomalies[['time', 'Battery', 'Humidity', 'Motion', 'Temperature']].to_dict(orient="records")
    for reading in result:
        for key, value in reading.items():
            if pd.isna(value):
                reading[key] = None
            elif isinstance(value, (np.integer, np.floating)):
                reading[key] = float(value)
    
    return result

@app.get("/debug_csv")
def debug_csv(limit: int = 5):
    """Return first few rows of downloaded CSV for inspection."""
    try:
        df = pd.read_csv("data/downloaded_sensor_data.csv")
        return df.head(limit).to_dict(orient="records")
    except Exception as e:
        return {"error": str(e)}

# ✅ NEW: Debug endpoint to check data status
@app.get("/debug/status")
def debug_status():
    """Return current data and model status."""
    df = load_local()
    return {
        "data_loaded": not df.empty,
        "row_count": len(df) if not df.empty else 0,
        "columns": list(df.columns) if not df.empty else [],
        "model_exists": os.path.exists(os.path.join(MODEL_DIR, 'temp_rf_model.joblib')),
        "anomaly_model_exists": os.path.exists(os.path.join(MODEL_DIR, 'anomaly_iforest.joblib'))
    }