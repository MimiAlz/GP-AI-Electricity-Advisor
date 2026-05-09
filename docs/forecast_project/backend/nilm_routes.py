"""
nilm_routes.py
==============
FastAPI router for NILM disaggregation.

Data source
-----------
All NILM inference uses Electricity_P.csv (AMPds research dataset) located
inside the nilm/ directory.  Supabase is used ONLY to authorise the request
(confirm the house belongs to the logged-in user); no meter readings are
fetched from the database.

Endpoint
--------
POST /users/{national_id}/houses/{house_id}/nilm
Body : { "month": "YYYY-MM" }

Flow
----
1. Validate house belongs to user (Supabase auth check only).
2. Load & cache Electricity_P.csv via prepare_test_data.load_and_clean_ampds().
3. Filter to the requested calendar month.
4. For each appliance, detect ON/OFF transitions (50 W threshold already
   applied during CSV loading), extract each event window with lead/trail
   context, and call NILMBackend.predict_event().
5. Aggregate per-appliance: daily kWh, hourly kWh, total kWh, on-minutes,
   peak Watts.
6. Return results sorted descending by total kWh (ranking).

GET /users/{national_id}/houses/{house_id}/nilm/available-months
Returns the list of calendar months present in Electricity_P.csv.
"""

import os
import calendar

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from nilm_loader import get_nilm_backend
from supabase_client import get_supabase

# Import CSV utilities and constants from prepare_test_data
from nilm.prepare_test_data import (
    load_and_clean_ampds,
    CONTEXT_CONFIG,
    MIN_EVENT_DURATION,
    MAINS_COL,
    TARGET_APPLIANCES,
)

router = APIRouter()

HOUSES_TABLE = "house"

# Absolute path to the CSV, co-located with the nilm/ package
_NILM_DIR = os.path.join(os.path.dirname(__file__), "nilm")
_CSV_PATH  = os.path.join(_NILM_DIR, "Electricity_P.csv")

# Module-level cache so the CSV is loaded only once per server lifetime
_csv_cache: dict = {}


# ── Request / response models ─────────────────────────────────────────────────

class NilmRequest(BaseModel):
    month: str  # "YYYY-MM"


class ApplianceResult(BaseModel):
    name:        str
    total_kwh:   float
    on_minutes:  int
    peak_watts:  float
    daily_kwh:   list[float]   # one entry per calendar day in the month
    hourly_kwh:  list[float]   # 24 entries — kWh per hour-of-day


class NilmResponse(BaseModel):
    month:           str
    appliances:      list[ApplianceResult]
    ranking:         list[str]   # appliance names, descending by total_kwh
    total_mains_kwh: float


class AvailableMonthsResponse(BaseModel):
    house_id:         str
    available_months: list[str]   # ["YYYY-MM", ...] sorted ascending


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _get_csv_df() -> pd.DataFrame:
    """Load and cache the cleaned AMPds DataFrame (loaded once at first call)."""
    if "df" not in _csv_cache:
        if not os.path.exists(_CSV_PATH):
            raise HTTPException(
                status_code=503,
                detail=f"Electricity_P.csv not found at {_CSV_PATH}",
            )
        _csv_cache["df"] = load_and_clean_ampds(_CSV_PATH)
    return _csv_cache["df"]


def _csv_available_months() -> list[str]:
    """Return sorted list of 'YYYY-MM' strings present in the CSV."""
    df = _get_csv_df()
    return sorted(
        df.index.to_period("M").unique().strftime("%Y-%m").tolist()
    )


def _run_nilm_csv(backend, df_month: pd.DataFrame, n_days: int) -> dict:
    """
    Event-based NILM disaggregation on a month-filtered AMPds DataFrame.

    For each appliance:
      1. Detect ON/OFF transitions (50 W threshold already applied in CSV loading).
      2. Extract each event window (with per-appliance lead/trail context).
      3. Call backend.predict_event() → PredictionResult.
      4. Accumulate into daily_kwh[n_days], hourly_kwh[24], total_kwh, etc.

    Returns dict with keys: daily_kwh, hourly_kwh, total_kwh, on_minutes,
    peak_watts, total_mains_kwh.
    """
    appliances = backend.appliances

    # Per-appliance accumulators
    daily_kwh  = {a: np.zeros(n_days, dtype=np.float64) for a in appliances}
    hourly_kwh = {a: np.zeros(24,     dtype=np.float64) for a in appliances}
    total_wh   = {a: 0.0 for a in appliances}
    on_minutes = {a: 0   for a in appliances}
    peak_watts = {a: 0.0 for a in appliances}

    mains_arr = df_month[MAINS_COL].values.astype(np.float64)
    n         = len(df_month)
    times     = df_month.index

    for app in appliances:
        if app not in df_month.columns:
            continue

        app_arr  = df_month[app].values.astype(np.float64)
        c        = CONTEXT_CONFIG.get(app, {"lead": 10, "trail": 10})
        lead     = c["lead"]
        trail    = c["trail"]
        min_dur  = MIN_EVENT_DURATION.get(app, 2)

        # Detect ON/OFF transitions
        is_on = (app_arr > 0).astype(int)
        diff  = np.diff(is_on, prepend=0)
        starts = list(np.where(diff == 1)[0])
        ends   = list(np.where(diff == -1)[0])
        if len(starts) > len(ends):
            ends.append(n - 1)

        for s, e in zip(starts, ends):
            if (e - s) < min_dur:
                continue

            i_start    = max(0, s - lead)
            i_end      = min(n, e + trail)
            window_w   = mains_arr[i_start:i_end].astype(np.float32)
            window_ts  = times[i_start:i_end]

            if len(window_w) == 0:
                continue

            try:
                res = backend.predict_event(app, window_w, window_ts)
            except Exception:
                continue

            # Use event ON-start time for calendar binning
            event_ts = times[s]
            day_idx  = min(event_ts.day - 1, n_days - 1)
            hr_idx   = event_ts.hour

            daily_kwh[app][day_idx] += res.energy_wh / 1000.0
            hourly_kwh[app][hr_idx] += res.energy_wh / 1000.0
            total_wh[app]           += res.energy_wh
            on_minutes[app]         += int(res.is_on.sum())
            if len(res.power_watts):
                peak_watts[app] = max(peak_watts[app], float(res.power_watts.max()))

    # total mains kWh: Watts × 1 min → Wh → kWh
    total_mains_kwh = float(mains_arr.sum()) / 60.0 / 1000.0

    return {
        "daily_kwh":       {a: daily_kwh[a].tolist()  for a in appliances},
        "hourly_kwh":      {a: hourly_kwh[a].tolist() for a in appliances},
        "total_kwh":       {a: total_wh[a] / 1000.0   for a in appliances},
        "on_minutes":      on_minutes,
        "peak_watts":      peak_watts,
        "total_mains_kwh": total_mains_kwh,
    }


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/users/{national_id}/houses/{house_id}/nilm", response_model=NilmResponse)
def run_nilm_disaggregation(national_id: str, house_id: str, body: NilmRequest):
    """
    Disaggregate Electricity_P.csv for the requested month using the trained
    BiLSTM NILM models.  House ownership is validated against Supabase;
    the raw consumption data always comes from the CSV.
    """
    backend = get_nilm_backend()
    client  = get_supabase()

    # 1. Authorise
    _ensure_house_belongs_to_user(client, national_id, house_id)

    # 2. Parse month
    try:
        year, mon = map(int, body.month.split("-"))
    except ValueError:
        raise HTTPException(status_code=422, detail="month must be in YYYY-MM format")
    n_days = calendar.monthrange(year, mon)[1]

    # 3. Load CSV (cached) and filter to the requested month
    df = _get_csv_df()
    period    = pd.Period(body.month, "M")
    df_month  = df[df.index.to_period("M") == period]

    if df_month.empty:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No AMPds data found for {body.month}. "
                f"Available months: {_csv_available_months()}"
            ),
        )

    # 4. Run event-based NILM
    try:
        results = _run_nilm_csv(backend, df_month, n_days)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"NILM inference failed: {exc}") from exc

    # 5. Build response
    appliance_results = []
    for app in backend.appliances:
        appliance_results.append(
            ApplianceResult(
                name       = app,
                total_kwh  = round(results["total_kwh"][app], 3),
                on_minutes = results["on_minutes"][app],
                peak_watts = round(results["peak_watts"][app], 1),
                daily_kwh  = [round(v, 3) for v in results["daily_kwh"][app]],
                hourly_kwh = [round(v, 4) for v in results["hourly_kwh"][app]],
            )
        )

    appliance_results.sort(key=lambda x: x.total_kwh, reverse=True)
    ranking = [a.name for a in appliance_results]

    return NilmResponse(
        month           = body.month,
        appliances      = appliance_results,
        ranking         = ranking,
        total_mains_kwh = round(results["total_mains_kwh"], 3),
    )


@router.get("/nilm/appliances")
def list_nilm_appliances():
    """Return the list of appliances the NILM backend can disaggregate."""
    backend = get_nilm_backend()
    return {"appliances": backend.appliances}


@router.get(
    "/users/{national_id}/houses/{house_id}/nilm/available-months",
    response_model=AvailableMonthsResponse,
)
def get_available_months(national_id: str, house_id: str):
    """
    Return the list of calendar months (YYYY-MM) present in Electricity_P.csv.
    House ownership is validated before returning the list.
    """
    client = get_supabase()
    _ensure_house_belongs_to_user(client, national_id, house_id)

    months = _csv_available_months()
    return AvailableMonthsResponse(house_id=house_id, available_months=months)

