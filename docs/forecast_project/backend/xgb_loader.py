"""
xgb_loader.py — Singleton loader for XGBoost forecasting assets.

Loads at startup (called from main.py):
  - xgb_per_meter_fold6.ubj   → per-meter Booster
  - xgb_area_fold6.ubj        → area-level Booster
  - feature_cols.json         → 20-feature list for per-meter model
  - meter_encoder.json        → building-id → int mapping (validation)
  - splits/fold6_test.csv     → ~50 MB per-meter feature matrix
  - splits/fold6_area_test.csv→ area feature matrix
"""

import json
from pathlib import Path

import pandas as pd
import xgboost as xgb

_BASE = Path(__file__).resolve().parent
_MODELS_DIR = _BASE / "models"
_SPLITS_DIR = _BASE / "splits"

# Area feature columns: all CSV columns except freeze_date and area_kwh_log,
# in the exact order they appear in fold6_area_test.csv.
AREA_FEAT_COLS: list[str] = [
    "slot_sin", "slot_cos", "dow_sin", "dow_cos",
    "month_sin", "month_cos", "year_sin", "year_cos",
    "is_weekend", "is_business_hour", "is_ramadan", "day_of_year",
    "lag_1", "lag_48", "lag_336", "roll_mean_48", "roll_std_48", "roll_mean_336",
]

_assets: dict = {}


def load_xgb_assets() -> None:
    """Load all XGBoost model assets into memory. Call once at startup."""
    global _assets

    # 1. Per-meter feature columns (exact training order from feature_cols.json)
    with open(_MODELS_DIR / "feature_cols.json") as f:
        feat_cols: list[str] = json.load(f)

    # 2. Meter encoder (B-code → int index, for validation only)
    with open(_MODELS_DIR / "meter_encoder.json") as f:
        meter_encoder: dict = json.load(f)

    # 3. XGBoost per-meter model (fold 6)
    per_model = xgb.Booster(params={"nthread": 1})
    per_model.load_model(str(_MODELS_DIR / "xgb_per_meter_fold6.ubj"))

    # 4. XGBoost area model (fold 6)
    area_model = xgb.Booster(params={"nthread": 1})
    area_model.load_model(str(_MODELS_DIR / "xgb_area_fold6.ubj"))

    # 5. Per-meter feature CSV (large file — loaded once, cached in memory)
    df_meter = pd.read_csv(
        _SPLITS_DIR / "fold6_test.csv",
        parse_dates=["freeze_date"],
    )

    # 6. Area feature CSV
    df_area = pd.read_csv(
        _SPLITS_DIR / "fold6_area_test.csv",
        parse_dates=["freeze_date"],
    )

    _assets = {
        "per_model": per_model,
        "area_model": area_model,
        "feat_cols": feat_cols,
        "meter_encoder": meter_encoder,
        "df_meter": df_meter,
        "df_area": df_area,
    }

    print(
        f"[xgb_loader] Loaded {len(df_meter):,} meter rows "
        f"({df_meter['meter_B'].nunique()} meters), "
        f"{len(df_area):,} area rows"
    )


def get_xgb_assets() -> dict:
    """Return the loaded XGBoost assets. Raises if load_xgb_assets() was not called."""
    if not _assets:
        raise RuntimeError("XGBoost assets not loaded — call load_xgb_assets() first")
    return _assets
