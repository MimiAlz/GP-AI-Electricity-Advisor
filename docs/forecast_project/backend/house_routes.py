from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from supabase_client import get_supabase

router = APIRouter()
HOUSES_TABLE = "house"


class HouseCreateRequest(BaseModel):
    house_id: str
    address: str


class HouseUpdateRequest(BaseModel):
    address: str


@router.get("/users/{national_id}/houses")
def list_user_houses(national_id: str):
    try:
        client = get_supabase()
        result = (
            client.table(HOUSES_TABLE)
            .select("house_id,address,national_id,created_at")
            .eq("national_id", national_id)
            .order("created_at", desc=False)
            .execute()
        )
        return {"status": "success", "houses": result.data or []}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list houses: {exc}") from exc


@router.post("/users/{national_id}/houses")
def create_house(national_id: str, request: HouseCreateRequest):
    try:
        client = get_supabase()
        existing = (
            client.table(HOUSES_TABLE)
            .select("house_id")
            .eq("house_id", request.house_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            raise HTTPException(status_code=409, detail="House ID already exists")

        created = (
            client.table(HOUSES_TABLE)
            .insert(
                {
                    "house_id": request.house_id,
                    "address": request.address,
                    "national_id": national_id,
                }
            )
            .execute()
        )
        return {"status": "success", "house": (created.data or [None])[0]}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to create house: {exc}") from exc


@router.get("/users/{national_id}/houses/{house_id}")
def get_house_details(national_id: str, house_id: str):
    try:
        client = get_supabase()
        result = (
            client.table(HOUSES_TABLE)
            .select("house_id,address,national_id,created_at")
            .eq("house_id", house_id)
            .eq("national_id", national_id)
            .limit(1)
            .execute()
        )
        if not result.data:
            raise HTTPException(status_code=404, detail="House not found")

        return {"status": "success", "house": result.data[0]}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch house details: {exc}") from exc


@router.put("/users/{national_id}/houses/{house_id}")
def update_house(national_id: str, house_id: str, request: HouseUpdateRequest):
    try:
        client = get_supabase()
        updated = (
            client.table(HOUSES_TABLE)
            .update({"address": request.address})
            .eq("house_id", house_id)
            .eq("national_id", national_id)
            .execute()
        )
        if not updated.data:
            raise HTTPException(status_code=404, detail="House not found")

        return {"status": "success", "house": updated.data[0]}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to update house: {exc}") from exc


@router.delete("/users/{national_id}/houses/{house_id}")
def delete_house(national_id: str, house_id: str):
    try:
        client = get_supabase()
        deleted = (
            client.table(HOUSES_TABLE)
            .delete()
            .eq("house_id", house_id)
            .eq("national_id", national_id)
            .execute()
        )
        if not deleted.data:
            raise HTTPException(status_code=404, detail="House not found")

        return {"status": "success", "message": "House deleted"}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete house: {exc}") from exc