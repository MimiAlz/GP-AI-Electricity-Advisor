from uuid import uuid4

import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from forecasting_pipeline import forecast as run_forecast_pipeline
from supabase_client import get_supabase
from tariff import calc_bill_jod, get_tier

router = APIRouter()

# --- TEST ENDPOINT FOR DB LIMITATION DEBUGGING ---
from fastapi import Query

@router.get("/debug/smart_meter_sample")
def debug_smart_meter_sample(meter_id: str = Query("B1", description="Meter ID to fetch (default: B1)")):
    """
    Fetch up to 1776 rows for a single meter (default B1), using pagination.
    Return the count and a sample of the data for debugging DB limits.
    """
    client = get_supabase()
    all_rows = []
    page_size = 1000
    total_needed = 1776
    offset = 0
    while len(all_rows) < total_needed:
        fetch_to = offset + page_size - 1
        if fetch_to >= total_needed:
            fetch_to = total_needed - 1
        result = (
            client.table(SMART_METER_TABLE)
            .select("*")
            .eq("meter_B", meter_id)
            .order("freeze_date", desc=False)
            .range(offset, fetch_to)
            .execute()
        )
        rows = result.data or []
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break  # No more data
        offset += page_size
    sample = all_rows[:5] if len(all_rows) > 5 else all_rows
    return {"meter_id": meter_id, "row_count": len(all_rows), "sample": sample}

HOUSES_TABLE = "house"
FORECAST_MODEL_TABLE = "forecast_model"
FORECAST_RESULT_TABLE = "forecast_result"
HOUSE_FORECAST_TABLE = "house_forecast"
SMART_METER_TABLE = "smart_meter_reading"

DEFAULT_MODEL_ID = "default_v1"
DEFAULT_MODEL_NAME = "Default Forecast Model"
DEFAULT_MODEL_DESCRIPTION = "Auto-managed default model for house forecasting requests."

# preprocess.build_features requires at least this many rows (37 days × 48 half-hour slots)
MIN_ROWS_REQUIRED = 1776


class ForecastCreateRequest(BaseModel):
    forecast_month: str


def _ensure_house_belongs_to_user(client, national_id: str, house_id: str) -> None:
    house = (
        client.table(HOUSES_TABLE)
        .select("house_id")
        .eq("house_id", house_id)
        .eq("national_id", national_id)
        .limit(1)
        .execute()
    )
    if not house.data:
        raise HTTPException(status_code=404, detail="House not found for this user")


def _ensure_default_model(client) -> None:
    existing = (
        client.table(FORECAST_MODEL_TABLE)
        .select("model_id")
        .eq("model_id", DEFAULT_MODEL_ID)
        .limit(1)
        .execute()
    )
    if not existing.data:
        client.table(FORECAST_MODEL_TABLE).insert(
            {
                "model_id": DEFAULT_MODEL_ID,
                "model_name": DEFAULT_MODEL_NAME,
                "description": DEFAULT_MODEL_DESCRIPTION,
            }
        ).execute()


def _fetch_readings_for_house(client, house_id: str) -> tuple[list[str], list[float]]:
    """
    Fetch recent real meter readings from smart_meter_reading table, using pagination to bypass the 1000-row limit.

    Assumption:
      - house_id matches the meter id stored in "meter_B".
    """
    total_needed = MIN_ROWS_REQUIRED + 336
    page_size = 1000
    all_rows = []
    offset = 0
    while len(all_rows) < total_needed:
        fetch_to = offset + page_size - 1
        if fetch_to >= total_needed:
            fetch_to = total_needed - 1
        result = (
            client.table(SMART_METER_TABLE)
            .select("*")
            .eq("meter_B", house_id)
            .order("freeze_date", desc=True)
            .range(offset, fetch_to)
            .execute()
        )
        rows = result.data or []
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break  # No more data
        offset += page_size
    # Reverse to chronological order (oldest first)
    rows = list(reversed(all_rows))
    if len(rows) < MIN_ROWS_REQUIRED:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Not enough readings for meter '{house_id}'. "
                f"Found {len(rows)}, need at least {MIN_ROWS_REQUIRED}."
            ),
        )

    timestamps = [str(r["freeze_date"]) for r in rows]
    readings = [float(r["A+KWH"]) for r in rows]
    return timestamps, readings


def _compute_forecast(client, house_id: str) -> dict:
    """
    Read meter data from DB, run the forecasting pipeline,
    then return predicted_energy_kwh, estimated_bill_jod, and tariff_tier.
    """
    timestamps, readings = _fetch_readings_for_house(client, house_id)

    try:
        prediction = run_forecast_pipeline(timestamps=timestamps, readings=readings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Forecasting pipeline failed: {exc}") from exc

    kwh = float(prediction["predicted_kwh"])
    return {
        "predicted_energy_kwh": kwh,
        "estimated_bill_jod":   calc_bill_jod(kwh),
        "tariff_tier":          get_tier(kwh),
    }


@router.get("/users/{national_id}/houses/{house_id}/forecasts")
def list_house_forecasts(national_id: str, house_id: str):
    try:
        client = get_supabase()
        _ensure_house_belongs_to_user(client, national_id, house_id)

        result = (
            client.table(HOUSE_FORECAST_TABLE)
            .select(
                "forecast_id,house_id,predicted_energy_kwh,estimated_bill_jod,tariff_tier,created_at,"
                "forecast_result!inner(forecast_month,created_at,model_id)"
            )
            .eq("house_id", house_id)
            .order("created_at", desc=True)
            .execute()
        )
        return {"status": "success", "forecasts": result.data or []}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch house forecasts: {exc}") from exc


@router.get("/users/{national_id}/houses/{house_id}/forecasts/{forecast_id}")
def get_house_forecast(national_id: str, house_id: str, forecast_id: str):
    try:
        client = get_supabase()
        _ensure_house_belongs_to_user(client, national_id, house_id)

        result = (
            client.table(HOUSE_FORECAST_TABLE)
            .select(
                "forecast_id,house_id,predicted_energy_kwh,estimated_bill_jod,tariff_tier,created_at,"
                "forecast_result!inner(forecast_month,created_at,model_id)"
            )
            .eq("house_id", house_id)
            .eq("forecast_id", forecast_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="Forecast not found")

        return {"status": "success", "forecast": result.data[0]}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch forecast details: {exc}") from exc


@router.post("/users/{national_id}/houses/{house_id}/forecasts")
def create_house_forecast(national_id: str, house_id: str, request: ForecastCreateRequest):
    try:
        client = get_supabase()
        _ensure_house_belongs_to_user(client, national_id, house_id)
        _ensure_default_model(client)

        computed = _compute_forecast(client, house_id)
        forecast_id = str(uuid4())

        client.table(FORECAST_RESULT_TABLE).insert(
            {
                "forecast_id": forecast_id,
                "forecast_month": request.forecast_month,
                "model_id": DEFAULT_MODEL_ID,
            }
        ).execute()

        linked = (
            client.table(HOUSE_FORECAST_TABLE)
            .insert(
                {
                    "forecast_id":        forecast_id,
                    "house_id":           house_id,
                    "predicted_energy_kwh": computed["predicted_energy_kwh"],
                    "estimated_bill_jod": computed["estimated_bill_jod"],
                    "tariff_tier":        computed["tariff_tier"],
                }
            )
            .execute()
        )

        row = (linked.data or [{}])[0]
        return {
            "status":   "success",
            "forecast": {
                **row,
                # Always expose these even if the DB row omits them
                "predicted_energy_kwh": computed["predicted_energy_kwh"],
                "estimated_bill_jod":   computed["estimated_bill_jod"],
                "tariff_tier":          computed["tariff_tier"],
                "forecast_month":       request.forecast_month,
            },
            "model_id": DEFAULT_MODEL_ID,
        }
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create forecast: {exc}") from exc
