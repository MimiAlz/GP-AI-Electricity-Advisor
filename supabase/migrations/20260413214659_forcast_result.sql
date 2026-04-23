create table if not exists public.forecast_model (
	model_id text primary key,
	model_name text not null,
	description text
);

create table if not exists public.forecast_result (
	forecast_id text primary key,
	forecast_month text not null,
	created_at timestamptz not null default now(),
	model_id text not null references public.forecast_model(model_id) on delete restrict
);

create index if not exists forecast_result_model_id_idx
on public.forecast_result (model_id);

create table if not exists public.house_forecast (
	forecast_id text primary key references public.forecast_result(forecast_id) on delete cascade,
	house_id text not null references public.house(house_id) on delete cascade,
	predicted_energy_kwh double precision not null check (predicted_energy_kwh >= 0),
	created_at timestamptz not null default now()
);

create index if not exists house_forecast_house_id_idx
on public.house_forecast (house_id);
