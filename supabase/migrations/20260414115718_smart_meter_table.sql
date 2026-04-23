create table if not exists public.smart_meter_reading (
	reading_id bigserial primary key,
	"meter_B" text not null,
	freeze_date timestamptz not null,
	"A+KWH" double precision not null check ("A+KWH" >= 0),
	created_at timestamptz not null default now(),
	unique ("meter_B", freeze_date)
);

create index if not exists smart_meter_reading_meter_idx
on public.smart_meter_reading ("meter_B");

create index if not exists smart_meter_reading_freeze_date_idx
on public.smart_meter_reading (freeze_date desc);

create index if not exists smart_meter_reading_meter_date_idx
on public.smart_meter_reading ("meter_B", freeze_date desc);
