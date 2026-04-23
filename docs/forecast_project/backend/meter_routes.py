from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from supabase_client import get_supabase

router = APIRouter()

HOUSES_TABLE = "house"
METER_READING_TABLE = "meter_reading"

# Minimum rows required by preprocess.build_features (37 days × 48 slots)
MIN_ROWS_REQUIRED = 1776


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


class MeterReadingItem(BaseModel):
    ts: str                 # ISO-8601 datetime string, e.g. "2025-09-01 00:00:00"
    kwh_reading: float

    @field_validator("kwh_reading")
    @classmethod
    def kwh_non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("kwh_reading must be >= 0")
        return v


class BulkMeterReadingRequest(BaseModel):
    readings: list[MeterReadingItem]

    @field_validator("readings")
    @classmethod
    def not_empty(cls, v):
        if not v:
            raise ValueError("readings list must not be empty")
        return v


@router.get("/users/{national_id}/houses/{house_id}/meter-readings")
def list_meter_readings(national_id: str, house_id: str, limit: int = 2016):
    """
    Return the most recent `limit` half-hourly readings for a house (default 2016 = 6 weeks).
    """
    try:
        client = get_supabase()
        _ensure_house_belongs_to_user(client, national_id, house_id)

        result = (
            client.table(METER_READING_TABLE)
            .select("reading_id,ts,kwh_reading,created_at")
            .eq("house_id", house_id)
            .order("ts", desc=True)
            .limit(limit)
            .execute()
        )
        readings = list(reversed(result.data or []))  # return chronological order
        return {
            "status": "success",
            "house_id": house_id,
            "count": len(readings),
            "has_enough_data": len(readings) >= MIN_ROWS_REQUIRED,
            "min_rows_required": MIN_ROWS_REQUIRED,
            "readings": readings,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch meter readings: {exc}") from exc


@router.post("/users/{national_id}/houses/{house_id}/meter-readings")
def bulk_upsert_meter_readings(national_id: str, house_id: str, request: BulkMeterReadingRequest):
    """
    Bulk-upsert meter readings for a house.
    Duplicate (house_id, ts) pairs are updated in place (upsert).
    """
    try:
        client = get_supabase()
        _ensure_house_belongs_to_user(client, national_id, house_id)

        rows = [
            {"house_id": house_id, "ts": r.ts, "kwh_reading": r.kwh_reading}
            for r in request.readings
        ]

        result = (
            client.table(METER_READING_TABLE)
            .upsert(rows, on_conflict="house_id,ts")
            .execute()
        )

        # Count current total for this house so the caller knows if they have enough
        count_result = (
            client.table(METER_READING_TABLE)
            .select("reading_id", count="exact")
            .eq("house_id", house_id)
            .execute()
        )
        total = count_result.count or 0

        return {
            "status": "success",
            "inserted_or_updated": len(rows),
            "total_readings": total,
            "has_enough_data": total >= MIN_ROWS_REQUIRED,
            "min_rows_required": MIN_ROWS_REQUIRED,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to upsert meter readings: {exc}") from exc


@router.delete("/users/{national_id}/houses/{house_id}/meter-readings")
def delete_all_meter_readings(national_id: str, house_id: str):
    """
    Delete all meter readings for a house. Use with care.
    """
    try:
        client = get_supabase()
        _ensure_house_belongs_to_user(client, national_id, house_id)

        client.table(METER_READING_TABLE).delete().eq("house_id", house_id).execute()
        return {"status": "success", "house_id": house_id}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete meter readings: {exc}") from exc
