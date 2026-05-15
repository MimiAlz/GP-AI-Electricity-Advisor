-- =============================================================================
-- Migration: add XGBoost forecast result tables + NILM result tables
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- XGBoost per-meter forecast cache
-- One row per (meter_b, target_month); upserted on each forecast request.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.xgb_meter_forecast (
    id                 bigserial       primary key,
    meter_b            text            not null,
    target_month       text            not null,              -- 'YYYY-MM'
    predicted_kwh      double precision not null check (predicted_kwh >= 0),
    estimated_bill_jod numeric(10, 3)  not null,
    tariff_tier        text            not null,
    created_at         timestamptz     not null default now(),
    unique (meter_b, target_month)
);

create index if not exists xgb_meter_forecast_meter_idx
    on public.xgb_meter_forecast (meter_b);

create index if not exists xgb_meter_forecast_month_idx
    on public.xgb_meter_forecast (target_month);

-- ─────────────────────────────────────────────────────────────────────────────
-- XGBoost area-level forecast cache
-- One row per target_month; upserted on each area forecast request.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.xgb_area_forecast (
    id                 bigserial       primary key,
    target_month       text            not null unique,       -- 'YYYY-MM'
    predicted_kwh      double precision not null check (predicted_kwh >= 0),
    estimated_bill_jod numeric(10, 3)  not null,
    tariff_tier        text            not null,
    created_at         timestamptz     not null default now()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- NILM disaggregation result header
-- One row per (house_id, month); upserted each time disaggregation is run.
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.nilm_result (
    id              bigserial        primary key,
    house_id        text             not null references public.house(house_id) on delete cascade,
    national_id     text             not null references public.user(national_id) on delete cascade,
    month           text             not null,               -- 'YYYY-MM'
    total_mains_kwh double precision not null,
    created_at      timestamptz      not null default now(),
    unique (house_id, month)
);

create index if not exists nilm_result_house_idx
    on public.nilm_result (house_id);

create index if not exists nilm_result_national_id_idx
    on public.nilm_result (national_id);

-- ─────────────────────────────────────────────────────────────────────────────
-- NILM per-appliance breakdown
-- One row per (nilm_result_id, appliance); upserted alongside the header.
-- daily_kwh  : JSON array — one float per calendar day in the month
-- hourly_kwh : JSON array — 24 floats, kWh per hour-of-day averaged over month
-- ─────────────────────────────────────────────────────────────────────────────
create table if not exists public.nilm_appliance_result (
    id             bigserial        primary key,
    nilm_result_id bigint           not null references public.nilm_result(id) on delete cascade,
    appliance      text             not null,
    total_kwh      double precision not null,
    on_minutes     integer          not null,
    peak_watts     double precision not null,
    ranking        integer          not null,                -- 1 = highest consumer
    daily_kwh      jsonb            not null,               -- list[float]
    hourly_kwh     jsonb            not null,               -- list[float], 24 entries
    unique (nilm_result_id, appliance)
);

create index if not exists nilm_appliance_result_parent_idx
    on public.nilm_appliance_result (nilm_result_id);
