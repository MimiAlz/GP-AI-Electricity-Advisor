create table if not exists public.house (
	house_id text primary key,
	address text not null,
	national_id text not null references public.user(national_id) on delete cascade,
	created_at timestamptz not null default now()
);

create index if not exists house_national_id_idx
on public.house (national_id);
