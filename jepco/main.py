from fastapi import FastAPI, HTTPException
import pandas as pd
import numpy as np
import xgboost as xgb
import json
from pathlib import Path

app = FastAPI()

# ── globals loaded at startup ─────────────────────────────────────────────────
model_meter  = None
model_area   = None
meter_enc    = None
feature_cols = None
test_data    = {}   # key: "2025-06" → df of that month's test rows (all meters)
area_data    = {}   # key: "2025-06" → df of that month's area test rows

# ── tariff ────────────────────────────────────────────────────────────────────
MIN_CHARGE_KWH = 35.0
MIN_CHARGE_JOD = 1.75

def calc_bill_jod(kwh: float) -> float:
    if kwh <= 0:              return 0.0
    if kwh <= MIN_CHARGE_KWH: return MIN_CHARGE_JOD
    cost, rem = 0.0, float(kwh)
    for cap, rate in [(300, 50), (300, 100), (float("inf"), 200)]:
        used = min(rem, cap); cost += used * rate; rem -= used
        if rem <= 0: break
    return round(cost / 1000, 3)

def tier_label(kwh: float) -> str:
    if kwh <= 300: return "T1 (0–300 kWh)"
    if kwh <= 600: return "T2 (301–600 kWh)"
    return               "T3 (>600 kWh)"

def expm1_safe(x):
    return float(np.expm1(np.clip(x, 0, 20)))

# ── startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def load_everything():
    global model_meter, model_area, meter_enc, feature_cols, test_data, area_data

    # Models
    model_meter = xgb.XGBRegressor()
    model_meter.load_model("models/xgb_per_meter_fold6.ubj")

    model_area = xgb.XGBRegressor()
    model_area.load_model("models/xgb_area_fold6.ubj")

    # Metadata
    with open("models/meter_encoder.json") as f:
        meter_enc = json.load(f)
    with open("models/feature_cols.json") as f:
        feature_cols = json.load(f)

    # Test splits — index by month string
    for fold in range(1, 7):
        df = pd.read_csv(f"splits/fold{fold}_test.csv", parse_dates=["freeze_date"])
        month = df["freeze_date"].dt.to_period("M").iloc[0]
        test_data[str(month)] = df

        df_area = pd.read_csv(f"splits/fold{fold}_area_test.csv", parse_dates=["freeze_date"])
        area_data[str(month)] = df_area

    print("✔ Models and test data loaded")
    print(f"  Available months: {sorted(test_data.keys())}")

# ── endpoints ─────────────────────────────────────────────────────────────────
@app.get("/meters")
def get_meters():
    all_meters = set()
    for df in test_data.values():
        all_meters.update(df["meter_B"].unique().tolist())
    return {"meters": sorted(all_meters)}

@app.get("/months")
def get_months():
    return {"months": sorted(test_data.keys())}

@app.get("/forecast")
def get_forecast(meter_id: str, month: str):
    # Validate month
    if month not in test_data:
        raise HTTPException(404, f"Month {month} not available. Choose from {sorted(test_data.keys())}")

    df_month = test_data[month]

    # Validate meter
    df_meter = df_month[df_month["meter_B"] == meter_id].copy()
    if df_meter.empty:
        raise HTTPException(404, f"Meter {meter_id} not found in month {month}")

    # Encode meter
    df_meter["meter_id"] = meter_enc.get(meter_id, 0)
    feat_cols = feature_cols + ["meter_id"]

    # Drop rows with NaN in features
    df_clean = df_meter.dropna(subset=feat_cols)
    if df_clean.empty:
        raise HTTPException(422, f"No complete feature rows for {meter_id} / {month}")

    # Predict
    X = df_clean[feat_cols].values.astype("float32")
    y_log = model_meter.predict(X)
    y_kwh = np.expm1(np.clip(y_log, 0, 20))

    forecast_kwh = float(y_kwh.sum())
    forecast_bill = calc_bill_jod(forecast_kwh)
    forecast_tier = tier_label(forecast_kwh)

    return {
        "meter_id":             meter_id,
        "month":                month,
        "forecast_kwh_monthly": round(forecast_kwh, 2),
        "forecast_bill_jod":    forecast_bill,
        "forecast_tier":        forecast_tier,
    }

@app.get("/forecast/area")
def get_area_forecast(month: str):
    if month not in area_data:
        raise HTTPException(404, f"Month {month} not available.")

    df_area = area_data[month].dropna(subset=feature_cols)
    if df_area.empty:
        raise HTTPException(422, f"No complete feature rows for area / {month}")

    X = df_area[feature_cols].values.astype("float32")
    y_log = model_area.predict(X)
    y_kwh = np.expm1(np.clip(y_log, 0, 20))

    return {
        "month":                    month,
        "forecast_area_mean_kwh":   round(float(y_kwh.mean()), 4),
        "forecast_area_total_kwh":  round(float(y_kwh.sum()),  2),
    }