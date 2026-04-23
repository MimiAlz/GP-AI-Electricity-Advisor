# =============================================================================
# preprocess.py — JEPCO Feature Engineering for Production
# =============================================================================
# This file replicates Section 10 of the pipeline notebook exactly.
# It takes raw half-hourly meter readings and produces the feature matrix
# that the model was trained on.
#
# INPUT:
#   timestamps : list of datetime strings  e.g. ["2025-09-01 00:00:00", ...]
#   readings   : list of float kWh values  e.g. [0.12, 0.15, ...]
#   feats      : the feature list loaded from forecast_model.pkl
#                (this guarantees the column order matches training exactly)
#
# OUTPUT:
#   numpy array of shape (1440, n_feats) — ready to be scaled then fed to model
#
# IMPORTANT:
#   - You must send at least 1440 + 336 = 1776 rows (37 days) of raw readings
#     so that lag_336 and roll_mean_336 have enough history for the last 1440 rows.
#   - The function always takes the LAST 1440 rows after feature engineering.
#   - is_imputed is set to 0 for all rows (live data is assumed clean).
# =============================================================================

import numpy as np
import pandas as pd

# Ramadan window — update this every year for the new Ramadan dates
RAMADAN_START = pd.Timestamp("2025-03-01")
RAMADAN_END   = pd.Timestamp("2025-03-30")


def build_features(timestamps: list, readings: list, feats: list) -> np.ndarray:
    """
    Convert raw meter readings into the model's input feature matrix.

    Parameters
    ----------
    timestamps : list of str
        Half-hourly datetime strings. Must have at least 1776 entries (37 days).
    readings   : list of float
        kWh reading for each timestamp. Same length as timestamps.
    feats      : list of str
        Exact feature column names in correct order, loaded from forecast_model.pkl.

    Returns
    -------
    np.ndarray of shape (1440, n_feats), dtype float32
    """

    # ── Build dataframe from raw input ────────────────────────────────────────
    # Supabase returns timezone-aware timestamps (UTC); strip tz to keep naive
    # datetimes consistent with RAMADAN_START/END and training data.
    df = pd.DataFrame({
        "freeze_date": pd.to_datetime(timestamps, utc=True).tz_convert(None),
        "A+KWH":       np.array(readings, dtype="float32"),
    }).sort_values("freeze_date").reset_index(drop=True)

    if len(df) < 1776:
        raise ValueError(
            f"Need at least 1776 rows (37 days) of readings to compute lag_336, "
            f"but only got {len(df)}. Send more historical data."
        )

    fd   = df["freeze_date"]
    slot = fd.dt.hour * 2 + (fd.dt.minute == 30).astype(int)

    # ── 1. Cyclical Time Features (pipeline Section 10, block 1) ─────────────
    df["slot_sin"]  = np.sin(2 * np.pi * slot / 48).astype("float32")
    df["slot_cos"]  = np.cos(2 * np.pi * slot / 48).astype("float32")
    df["dow_sin"]   = np.sin(2 * np.pi * fd.dt.dayofweek / 7).astype("float32")
    df["dow_cos"]   = np.cos(2 * np.pi * fd.dt.dayofweek / 7).astype("float32")
    df["month_sin"] = np.sin(2 * np.pi * (fd.dt.month - 1) / 12).astype("float32")
    df["month_cos"] = np.cos(2 * np.pi * (fd.dt.month - 1) / 12).astype("float32")
    df["year_sin"]  = np.sin(2 * np.pi * fd.dt.dayofyear / 365.25).astype("float32")
    df["year_cos"]  = np.cos(2 * np.pi * fd.dt.dayofyear / 365.25).astype("float32")

    # ── 2. Calendar Flags (pipeline Section 10, block 2) ─────────────────────
    df["is_weekend"]       = fd.dt.dayofweek.isin([4, 5]).astype("int8")
    df["is_business_hour"] = fd.dt.hour.between(8, 15).astype("int8")
    df["is_ramadan"]       = fd.between(RAMADAN_START, RAMADAN_END).astype("int8")

    # ── 3. Area-Level Features — set to zero (not forecasting area) ──────────
    df["area_load_lag_48"]        = np.float32(0)
    df["area_load_roll_mean_336"] = np.float32(0)

    # ── 4. Individual Lags & Rolling Statistics (pipeline Section 10, block 4) 
    kwh = df["A+KWH"]
    df["lag_1"]         = kwh.shift(1).astype("float32")
    df["lag_48"]        = kwh.shift(48).astype("float32")
    df["lag_336"]       = kwh.shift(336).astype("float32")
    df["roll_mean_48"]  = kwh.rolling(48,  min_periods=12).mean().astype("float32")
    df["roll_std_48"]   = kwh.rolling(48,  min_periods=12).std().astype("float32")
    df["roll_mean_336"] = kwh.rolling(336, min_periods=48).mean().astype("float32")

    # ── 5. Billing Features (pipeline Section 10, block 5) ───────────────────
    # Since A+KWH is already per-slot consumption (NOT cumulative),
    # we DO NOT compute cumulative sum.

    df["cumkwh_in_month"] = np.float32(0)
    df["billing_tier"] = np.int8(0)

    # ── 6. is_imputed — always 0 for live data ───────────────────────────────
    # During training this flagged imputed slots. Live readings are assumed clean.
    df["is_imputed"] = np.int8(0)

    # ── 7. Fill any NaNs from lag warmup with 0 ──────────────────────────────
    df = df.fillna(0)

    # ── 8. Take last 1440 rows and return in correct feature order ────────────
    # feats comes from the .pkl so the column order matches training exactly.
    window = df.tail(1440)[feats].values.astype("float32")

    if window.shape != (1440, len(feats)):
        raise ValueError(
            f"Expected output shape (1440, {len(feats)}) but got {window.shape}. "
            f"Check that all feature columns are present."
        )

    return window
