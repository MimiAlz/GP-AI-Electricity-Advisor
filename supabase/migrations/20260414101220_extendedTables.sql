-- Add bill and tariff tier columns to house_forecast
alter table public.house_forecast
    add column if not exists estimated_bill_jod numeric(10, 3),
    add column if not exists tariff_tier         text;
