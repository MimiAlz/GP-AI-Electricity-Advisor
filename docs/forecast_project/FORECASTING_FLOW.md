# Forecasting Flow — Backend Deep Dive

This document explains every backend step involved in producing a forecast for a house, from the moment the request arrives to the final values returned.

---

## Overview

When a user requests a forecast for their house, the backend goes through the following stages:

1. Authorization check
2. Smart meter data fetch (with pagination)
3. Data ordering and validation
4. Feature engineering (preprocessing)
5. Scaling
6. Model inference
7. Post-processing (inverse log transform)
8. Tariff and bill calculation
9. Database persistence
10. Response

---

## Step 1 — Authorization Check

**File:** `forecast_routes.py` → `_ensure_house_belongs_to_user()`

Before doing anything, the backend verifies that the requesting user actually owns the house they are requesting a forecast for.

It queries the `house` table:

```sql
SELECT house_id FROM house
WHERE house_id = 'B3' AND national_id = '<user_national_id>'
LIMIT 1;
```

If no row is returned, a `404 Not Found` error is raised immediately.

---

## Step 2 — Smart Meter Data Fetch (with Pagination)

**File:** `forecast_routes.py` → `_fetch_readings_for_house()`

The backend fetches the most recent smart meter readings for the house from the `smart_meter_reading` table, filtered by `meter_B = house_id`.

### Why pagination?

Supabase/PostgREST has a hard limit of 1000 rows per request. The forecasting pipeline needs at least **1776 rows** (37 days of half-hourly data) to work. To bypass this limit, the backend fetches data in chunks of 1000 rows using `.range(offset, to)` until the required number of rows is collected.

### How many rows are fetched?

The backend requests up to:

```
MIN_ROWS_REQUIRED + 336 = 1776 + 336 = 2112 rows
```

The extra 336 rows provide additional lag warmup buffer — see Step 4 for why.

### Fetch order

Rows are fetched in **descending date order** (newest first), so the most recent readings are prioritized in case the meter has more history than needed. After all chunks are collected, the list is **reversed** back to chronological (oldest → newest) order for the preprocessing step.

### Column used

| DB Column   | Description                   |
|-------------|-------------------------------|
| `meter_B`   | The meter identifier          |
| `freeze_date` | Timestamp of the reading (half-hourly) |
| `A+KWH`     | Cumulative energy reading (kWh) |

### Minimum data check

After fetching, if fewer than 1776 rows were found, the backend raises a `400 Bad Request` with a message indicating how many rows are available and how many are needed.

---

## Step 3 — Data Passed to Pipeline

**File:** `forecast_routes.py` → `_compute_forecast()`

The raw rows are unpacked into two parallel lists:

- `timestamps` — list of `freeze_date` strings e.g. `["2025-09-01 00:00:00", ...]`
- `readings` — list of `A+KWH` float values e.g. `[120.45, 120.47, ...]`

These are passed directly to the forecasting pipeline.

---

## Step 4 — Feature Engineering (Preprocessing)

**File:** `preprocess.py` → `build_features()`

This step transforms raw timestamp/reading pairs into the full feature matrix the model was trained on. The logic exactly replicates the training notebook's Section 10.

### Input requirements

- At least **1776 rows** (37 days × 48 half-hour slots)
- Rows must be in **chronological order**

### Step-by-step transformations

#### 4.1 — Sort and build DataFrame

The timestamps and readings are loaded into a pandas DataFrame and sorted by date to ensure chronological order.

#### 4.2 — Cyclical Time Features

To give the model a sense of time that wraps correctly (e.g. 23:30 and 00:00 are close), all time units are encoded as sine/cosine pairs:

| Feature      | Encodes              | Period |
|--------------|----------------------|--------|
| `slot_sin/cos` | Half-hour slot (0–47) | 48 slots/day |
| `dow_sin/cos`  | Day of week (0–6)     | 7 days |
| `month_sin/cos`| Month (1–12)          | 12 months |
| `year_sin/cos` | Day of year (1–365)   | 365.25 days |

#### 4.3 — Calendar Flags

Binary flags that tell the model about the context of each reading:

| Feature           | Value | Condition                        |
|-------------------|-------|----------------------------------|
| `is_weekend`      | 1/0   | Friday or Saturday               |
| `is_business_hour`| 1/0   | Hour between 08:00 and 15:00     |
| `is_ramadan`      | 1/0   | Date falls in Ramadan window     |

> **Note:** Ramadan dates are hardcoded in `preprocess.py` and must be updated each year.

#### 4.4 — Area-Level Features (set to zero)

During training, area-level load features were included for models trained on grid-level data. Since the production system is forecasting individual household meters (not grid areas), these are always set to zero:

| Feature                  | Value |
|--------------------------|-------|
| `area_load_lag_48`       | 0.0   |
| `area_load_roll_mean_336`| 0.0   |

#### 4.5 — Individual Lag Features

These features let the model look back at historical consumption at specific time offsets:

| Feature      | Looks back        | Purpose                            |
|--------------|-------------------|------------------------------------|
| `lag_1`      | 30 minutes ago    | Immediate prior reading            |
| `lag_48`     | 24 hours ago      | Same time yesterday                |
| `lag_336`    | 7 days ago        | Same time last week                |

`lag_336` requires at least 336 prior rows to be valid — this is why the minimum row requirement is `1440 + 336 = 1776`.

#### 4.6 — Rolling Statistics

Rolling windows capture recent trends and variability:

| Feature         | Window     | Description                     |
|-----------------|------------|---------------------------------|
| `roll_mean_48`  | 48 slots (24h) | 24-hour rolling mean        |
| `roll_std_48`   | 48 slots (24h) | 24-hour rolling std dev     |
| `roll_mean_336` | 336 slots (7d) | 7-day rolling mean          |

#### 4.7 — Billing Features

These tell the model how much cumulative energy has been used so far in the billing month and which tariff tier the household is currently in:

| Feature           | Description                                  |
|-------------------|----------------------------------------------|
| `cumkwh_in_month` | Running total kWh used in the current month  |
| `billing_tier`    | 0 = T1 (≤300 kWh), 1 = T2 (≤600), 2 = T3 (>600) |

#### 4.8 — is_imputed

During training, some missing slots were filled with imputed values and flagged. For live data, all readings are assumed clean, so this is always:

```
is_imputed = 0
```

#### 4.9 — NaN Fill

Any NaN values introduced by lag warmup (the first few rows have no prior readings to look back to) are filled with `0`.

#### 4.10 — Final Window

The function takes only the **last 1440 rows** of the processed DataFrame. This is the exact sequence length (30 days × 48 slots) the LSTM model was trained on.

The columns are reordered to exactly match the feature order from `forecast_model.pkl` to guarantee compatibility with the trained model.

**Output shape:** `(1440, n_feats)` as `float32`

---

## Step 5 — Scaling

**File:** `forecasting_pipeline.py`

The `(1440, n_feats)` feature matrix is scaled using the `StandardScaler` that was saved during training and stored in `forecast_model.pkl`.

```python
window_scaled = scaler.transform(window)
```

This ensures the model receives input in the same numerical range as its training data. Each feature is scaled independently using its training mean and standard deviation.

Any remaining NaNs in the matrix are replaced with `0` before scaling.

---

## Step 6 — Model Inference

**File:** `forecasting_pipeline.py`, `model.py`

The scaled matrix is converted to a PyTorch tensor and fed into the trained `MinimalLSTM` model:

```python
xb = torch.tensor(window_scaled, dtype=torch.float32).unsqueeze(0)
# shape: (1, 1440, n_feats) — batch size 1
raw_output = float(model(xb).item())
```

The model processes the full 1440-step sequence and outputs a single scalar — the log-transformed predicted energy usage.

---

## Step 7 — Inverse Log Transform

**File:** `forecasting_pipeline.py`

During training, the target variable (monthly kWh) was log-transformed using `np.log1p(...)` to reduce skew. The model's raw output must be reversed with `np.expm1(...)`:

```python
pred_kwh = float(max(np.expm1(raw_output), 0.0))
```

The `max(..., 0.0)` clamps negative predictions to zero (physically impossible energy usage).

---

## Step 8 — Tariff and Bill Calculation

**File:** `tariff.py`

The predicted kWh is used to determine the user's tariff tier and estimated bill in Jordanian Dinars (JOD), based on JEPCO's tiered billing structure:

| Tier | Range       | Rate (fils/kWh) |
|------|-------------|-----------------|
| T1   | 0 – 300 kWh | 50              |
| T2   | 301 – 600 kWh | 100           |
| T3   | > 600 kWh   | 200             |

> First 85 kWh: flat fee of 1.75 JOD

The bill is calculated cumulatively across tiers (not flat-rate per tier).

### Tier labels returned

- `"T1 (0-300)"` — if predicted_kwh ≤ 300
- `"T2 (301-600)"` — if predicted_kwh ≤ 600
- `"T3 (>600)"` — otherwise

---

## Step 9 — Database Persistence

**File:** `forecast_routes.py` → `create_house_forecast()`

After the forecast is computed, the result is persisted in two tables:

### `forecast_result`

| Column           | Value                        |
|------------------|------------------------------|
| `forecast_id`    | New UUID                     |
| `forecast_month` | Month string from request body (e.g. `"2026-05"`) |
| `model_id`       | `"default_v1"`               |

### `house_forecast`

| Column                 | Value                          |
|------------------------|--------------------------------|
| `forecast_id`          | Same UUID as above             |
| `house_id`             | The house (e.g. `"B3"`)       |
| `predicted_energy_kwh` | Result from model              |
| `estimated_bill_jod`   | Calculated JOD amount          |
| `tariff_tier`          | Tier label string              |

---

## Step 10 — Response

The backend returns:

```json
{
  "status": "success",
  "forecast": {
    "forecast_id": "...",
    "house_id": "B3",
    "predicted_energy_kwh": 412.5,
    "estimated_bill_jod": 16.25,
    "tariff_tier": "T2 (301-600)",
    "forecast_month": "2026-05",
    "created_at": "..."
  },
  "model_id": "default_v1"
}
```

---

## Fallback Behavior

If the feature engineering or model inference raises an unexpected exception, `_compute_forecast()` falls back to returning the **mean of the raw readings** as the predicted kWh. This keeps the endpoint functional but the value will not be a real model prediction.

---

## Summary Diagram

```
POST /users/{national_id}/houses/B3/forecasts
        │
        ▼
┌─────────────────────────┐
│  1. Auth check          │  Is B3 owned by this user?
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  2. Fetch smart meter   │  Up to 2112 rows, paginated
│     readings for B3     │  1000 rows per DB request
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  3. Reverse to chrono   │  Oldest → newest order
│     order, validate     │  Needs ≥ 1776 rows
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  4. Feature engineering │  Cyclical time, calendar flags,
│     (preprocess.py)     │  lags, rolling stats, billing tier
│                         │  Output: (1440, n_feats) float32
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  5. Scale features      │  StandardScaler from training
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  6. LSTM inference      │  MinimalLSTM, shape (1, 1440, n_feats)
│                         │  Output: single log-transformed float
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  7. Inverse log         │  np.expm1(raw_output), clamped ≥ 0
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  8. Tariff & bill calc  │  JEPCO tiered rates → JOD amount
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  9. Persist to DB       │  forecast_result + house_forecast
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  10. Return response    │  predicted_kwh, bill, tier
└─────────────────────────┘
```
