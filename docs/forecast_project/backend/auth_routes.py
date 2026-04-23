import bcrypt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from supabase_client import get_supabase

router = APIRouter()
USERS_TABLE = "user"


class SignupRequest(BaseModel):
    national_id: str
    username: str
    password: str


class LoginRequest(BaseModel):
    identifier: str
    password: str


@router.post("/auth/signup")
def auth_signup(request: SignupRequest):
    try:
        client = get_supabase()

        existing = (
            client.table(USERS_TABLE)
            .select("national_id")
            .eq("national_id", request.national_id)
            .limit(1)
            .execute()
        )
        if existing.data:
            raise HTTPException(status_code=409, detail="National ID already registered")

        password_hash = bcrypt.hashpw(
            request.password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        client.table(USERS_TABLE).insert(
            {
                "national_id": request.national_id,
                "username": request.username,
                "password_hash": password_hash,
            }
        ).execute()

        return {"status": "success", "message": "User created successfully"}
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Signup failed: {exc}") from exc


@router.post("/auth/login")
def auth_login(request: LoginRequest):
    try:
        client = get_supabase()
        identifier = request.identifier.strip()

        result = (
            client.table(USERS_TABLE)
            .select("national_id,username,password_hash")
            .eq("national_id", identifier)
            .limit(1)
            .execute()
        )

        if not result.data:
            result = (
                client.table(USERS_TABLE)
                .select("national_id,username,password_hash")
                .eq("username", identifier)
                .limit(1)
                .execute()
            )

        if not result.data:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user = result.data[0]
        stored_hash = user["password_hash"].encode("utf-8")
        valid = bcrypt.checkpw(request.password.encode("utf-8"), stored_hash)
        if not valid:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        return {
            "status": "success",
            "message": "Login successful",
            "user": {
                "national_id": user["national_id"],
                "username": user["username"],
            },
        }
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Login failed: {exc}") from exc


@router.get("/supabase/test-read")
def supabase_test_read(table: str):
    try:
        client = get_supabase()
        result = client.table(table).select("*").limit(1).execute()
        return {"status": "success", "table": table, "rows": result.data}
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Supabase query failed: {exc}") from exc


@router.delete("/users/{national_id}")
def delete_user_account(national_id: str):
    try:
        client = get_supabase()

        deleted = (
            client.table(USERS_TABLE)
            .delete()
            .eq("national_id", national_id)
            .execute()
        )

        if not deleted.data:
            raise HTTPException(status_code=404, detail="User not found")

        # House and forecast rows are removed by FK cascade rules.
        return {
            "status": "success",
            "message": "Account and related data deleted",
        }
    except HTTPException:
        raise
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Account deletion failed: {exc}") from exc