from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from forecasting_pipeline import forecast

router = APIRouter()

class ForecastRequest(BaseModel):
    values: List[float]
    steps: int

@router.post("/forecast")
def run_forecast(request: ForecastRequest):
    result = forecast(request.values, request.steps)

    return {
        "status": "success",
        "forecast": result
    }