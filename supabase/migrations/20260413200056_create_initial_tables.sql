create extension if not exists "pgcrypto";

create table if not exists public.user (
  national_id text primary key,
  username text not null,
  password_hash text not null,
  created_at timestamptz not null default now()
);