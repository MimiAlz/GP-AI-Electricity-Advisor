from fastapi import APIRouter
from pydantic import BaseModel
from forecasting_pipeline import forecast

router = APIRouter()

class ForecastRequest(BaseModel):
    meter_id: str
    timestamps: list[str]
    readings: list[float]

@router.post("/forecast")
def run_forecast(request: ForecastRequest):
    result = forecast(request.timestamps, request.readings, request.meter_id)

    return {
        "status": "success",
        "forecast": result
    }