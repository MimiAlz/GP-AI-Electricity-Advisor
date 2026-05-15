"""
xgb_routes.py — FastAPI router for XGBoost-based forecasting.

POST /xgb/forecast
  Body: { meter_id, target_month, model: "per_month" | "area" }
  Returns: { meter_id?, target_month, model, predicted_kwh,
             estimated_bill_jod, tariff_tier }

GET /xgb/available-months?model=per_month&meter_id=B132
GET /xgb/available-months?model=area
  Returns: { model, meter_id?, available_months: ["YYYY-MM", ...] }
"""

import logging
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from supabase_client import get_supabase
from xgb_forecast import (
    forecast_area_next_month,
    forecast_meter_next_month,
    get_available_months_area,
    get_available_months_meter,
)

log = logging.getLogger(__name__)

router = APIRouter()


class XGBForecastRequest(BaseModel):
    meter_id: Optional[str] = None
    target_month: str  # "YYYY-MM"
    model: Literal["per_month", "area"]
    national_id: Optional[str] = None  # set by frontend from AuthContext


@router.post("/xgb/forecast")
def xgb_forecast(request: XGBForecastRequest):
    try:
        if request.model == "per_month":
            if not request.meter_id:
                raise HTTPException(
                    status_code=400,
                    detail="meter_id is required for model='per_month'",
                )
            result = forecast_meter_next_month(request.meter_id, request.target_month)
            _save_meter_forecast(request.meter_id, request.target_month, result, request.national_id)
            return {
                "meter_id": request.meter_id,
                "target_month": request.target_month,
                "model": request.model,
                **result,
            }
        else:  # area
            result = forecast_area_next_month(request.target_month)
            _save_area_forecast(request.target_month, result, request.national_id)
            return {
                "target_month": request.target_month,
                "model": request.model,
                **result,
            }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Forecast failed: {exc}") from exc


def _save_meter_forecast(meter_id: str, target_month: str, result: dict, national_id: Optional[str]) -> None:
    """Upsert a per-meter XGBoost forecast result into xgb_meter_forecast."""
    try:
        get_supabase().table("xgb_meter_forecast").upsert(
            {
                "national_id": national_id,
                "meter_b": meter_id,
                "target_month": target_month,
                "predicted_kwh": result["predicted_kwh"],
                "estimated_bill_jod": float(result["estimated_bill_jod"]),
                "tariff_tier": result["tariff_tier"],
            },
            on_conflict="national_id,meter_b,target_month",
            returning="minimal",
        ).execute()
    except Exception as exc:
        log.error("Failed to persist meter forecast to DB: %s", exc)


def _save_area_forecast(target_month: str, result: dict, national_id: Optional[str]) -> None:
    """Upsert an area-level XGBoost forecast result into xgb_area_forecast."""
    try:
        get_supabase().table("xgb_area_forecast").upsert(
            {
                "national_id": national_id,
                "target_month": target_month,
                "predicted_kwh": result["predicted_kwh"],
                "estimated_bill_jod": float(result["estimated_bill_jod"]),
                "tariff_tier": result["tariff_tier"],
            },
            on_conflict="national_id,target_month",
            returning="minimal",
        ).execute()
    except Exception as exc:
        log.error("Failed to persist area forecast to DB: %s", exc)


@router.get("/xgb/available-months")
def xgb_available_months(
    model: Literal["per_month", "area"] = Query(...),
    meter_id: Optional[str] = Query(None),
):
    try:
        if model == "per_month":
            if not meter_id:
                raise HTTPException(
                    status_code=400,
                    detail="meter_id is required for model='per_month'",
                )
            months = get_available_months_meter(meter_id)
            return {"model": model, "meter_id": meter_id, "available_months": months}
        else:
            months = get_available_months_area()
            return {"model": model, "available_months": months}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Available months lookup failed: {exc}") from exc
