"""
xgb_forecast.py — XGBoost inference helpers.

Two forecast modes:
  per_month — filters fold6_test.csv by (meter_id, month), predict per slot,
              expm1 + clip + sum → monthly kWh.
  area      — filters fold6_area_test.csv by month, same predict/sum flow.

Both modes apply the Jordan stepped tariff (tariff.py) to produce
estimated_bill_jod and tariff_tier.
"""

import numpy as np
import xgboost as xgb

from tariff import calc_bill_jod, get_tier
from xgb_loader import AREA_FEAT_COLS, get_xgb_assets


def _ym_to_int(target_month: str) -> tuple[int, int]:
    """Parse 'YYYY-MM' into (year, month) ints."""
    parts = target_month.split("-")
    if len(parts) != 2:
        raise ValueError(f"target_month must be 'YYYY-MM', got {target_month!r}")
    return int(parts[0]), int(parts[1])


def forecast_meter_next_month(meter_id: str, target_month: str) -> dict:
    """
    Per-meter XGBoost forecast.

    Filters fold6_test.csv rows where meter_B == meter_id and freeze_date
    falls in the requested month. Runs the model over those rows (one row
    per half-hour slot), applies expm1, clips negatives, and sums to produce
    the monthly kWh total.
    """
    assets = get_xgb_assets()
    year, month = _ym_to_int(target_month)

    df = assets["df_meter"]
    feat_cols = assets["feat_cols"]
    model = assets["per_model"]

    mask = (
        (df["meter_B"] == meter_id)
        & (df["freeze_date"].dt.year == year)
        & (df["freeze_date"].dt.month == month)
    )
    subset = df.loc[mask, feat_cols]

    if subset.empty:
        raise ValueError(
            f"No data for meter '{meter_id}' in {target_month}. "
            "Check /xgb/available-months?model=per_month for valid months."
        )

    X = xgb.DMatrix(subset.values.astype("float32"))
    raw_preds = model.predict(X)                    # log1p-space per-slot
    monthly_kwh = float(np.expm1(raw_preds).clip(0).sum())

    return {
        "predicted_kwh": round(monthly_kwh, 2),
        "estimated_bill_jod": calc_bill_jod(monthly_kwh),
        "tariff_tier": get_tier(monthly_kwh),
    }


def forecast_area_next_month(target_month: str) -> dict:
    """
    Area-level XGBoost forecast.

    Filters fold6_area_test.csv rows for the requested month, runs the
    area model per slot, applies expm1, clips negatives, sums to monthly kWh.
    """
    assets = get_xgb_assets()
    year, month = _ym_to_int(target_month)

    df = assets["df_area"]
    model = assets["area_model"]

    mask = (
        (df["freeze_date"].dt.year == year)
        & (df["freeze_date"].dt.month == month)
    )
    subset = df.loc[mask, AREA_FEAT_COLS]

    if subset.empty:
        raise ValueError(
            f"No area data for {target_month}. "
            "Check /xgb/available-months?model=area for valid months."
        )

    X = xgb.DMatrix(subset.values.astype("float32"))
    raw_preds = model.predict(X)
    monthly_kwh = float(np.expm1(raw_preds).clip(0).sum())

    return {
        "predicted_kwh": round(monthly_kwh, 2),
        "estimated_bill_jod": calc_bill_jod(monthly_kwh),
        "tariff_tier": get_tier(monthly_kwh),
    }


def get_available_months_meter(meter_id: str) -> list[str]:
    """Return sorted list of 'YYYY-MM' strings available for the given meter."""
    assets = get_xgb_assets()
    df = assets["df_meter"]
    subset = df[df["meter_B"] == meter_id]
    months = subset["freeze_date"].dt.to_period("M").astype(str).unique().tolist()
    return sorted(months)


def get_available_months_area() -> list[str]:
    """Return sorted list of 'YYYY-MM' strings available in the area CSV."""
    assets = get_xgb_assets()
    df = assets["df_area"]
    months = df["freeze_date"].dt.to_period("M").astype(str).unique().tolist()
    return sorted(months)
