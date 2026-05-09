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

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from xgb_forecast import (
    forecast_area_next_month,
    forecast_meter_next_month,
    get_available_months_area,
    get_available_months_meter,
)

router = APIRouter()


class XGBForecastRequest(BaseModel):
    meter_id: Optional[str] = None
    target_month: str  # "YYYY-MM"
    model: Literal["per_month", "area"]


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
            return {
                "meter_id": request.meter_id,
                "target_month": request.target_month,
                "model": request.model,
                **result,
            }
        else:  # area
            result = forecast_area_next_month(request.target_month)
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
