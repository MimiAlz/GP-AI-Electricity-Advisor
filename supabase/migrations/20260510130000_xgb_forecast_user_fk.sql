-- =============================================================================
-- Migration: add national_id FK to xgb_meter_forecast and xgb_area_forecast
-- =============================================================================

-- ── xgb_meter_forecast ───────────────────────────────────────────────────────
-- 1. Add column (nullable so rows inserted before this migration are preserved)
alter table public.xgb_meter_forecast
    add column if not exists national_id text
        references public.user(national_id) on delete set null;

-- 2. Replace old unique(meter_b, target_month) with per-user unique
alter table public.xgb_meter_forecast
    drop constraint if exists xgb_meter_forecast_meter_b_target_month_key;

alter table public.xgb_meter_forecast
    add constraint xgb_meter_forecast_user_meter_month_key
    unique (national_id, meter_b, target_month);

create index if not exists xgb_meter_forecast_national_id_idx
    on public.xgb_meter_forecast (national_id);

-- ── xgb_area_forecast ────────────────────────────────────────────────────────
alter table public.xgb_area_forecast
    add column if not exists national_id text
        references public.user(national_id) on delete set null;

alter table public.xgb_area_forecast
    drop constraint if exists xgb_area_forecast_target_month_key;

alter table public.xgb_area_forecast
    add constraint xgb_area_forecast_user_month_key
    unique (national_id, target_month);

create index if not exists xgb_area_forecast_national_id_idx
    on public.xgb_area_forecast (national_id);
