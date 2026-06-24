-- Fodão Player: shared catalogue, user profiles and administrator roles.
-- Run this file in Supabase Dashboard > SQL Editor > New query.

create type public.app_role as enum ('user', 'admin');

create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  display_name text,
  role public.app_role not null default 'user',
  is_active boolean not null default true,
  expires_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.categories (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  sort_order integer not null default 0,
  is_adult boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.content_groups (
  id uuid primary key default gen_random_uuid(),
  category_id uuid not null references public.categories(id) on delete cascade,
  name text not null,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  unique (category_id, name)
);

create table public.streams (
  id uuid primary key default gen_random_uuid(),
  category_id uuid not null references public.categories(id) on delete cascade,
  group_id uuid references public.content_groups(id) on delete set null,
  name text not null,
  stream_url text not null,
  logo_url text,
  stream_type text not null default 'ao-vivo',
  is_active boolean not null default true,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (group_id, name)
);

create table public.favorites (
  user_id uuid not null references auth.users(id) on delete cascade,
  stream_id uuid not null references public.streams(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, stream_id)
);

create index streams_category_id_idx on public.streams(category_id);
create index streams_group_id_idx on public.streams(group_id);
create index streams_active_idx on public.streams(is_active);
create index favorites_user_id_idx on public.favorites(user_id);

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_set_updated_at before update on public.profiles
for each row execute function public.set_updated_at();
create trigger streams_set_updated_at before update on public.streams
for each row execute function public.set_updated_at();

create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, display_name)
  values (new.id, new.email, coalesce(new.raw_user_meta_data ->> 'display_name', split_part(new.email, '@', 1)));
  return new;
end;
$$;

create trigger on_auth_user_created
after insert on auth.users
for each row execute procedure public.handle_new_user();

-- Add profiles for any users that existed before this migration.
insert into public.profiles (id, email, display_name)
select id, email, split_part(email, '@', 1)
from auth.users
on conflict (id) do nothing;

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin' and is_active = true
  );
$$;

alter table public.profiles enable row level security;
alter table public.categories enable row level security;
alter table public.content_groups enable row level security;
alter table public.streams enable row level security;
alter table public.favorites enable row level security;

create policy "Users read their own profile" on public.profiles
for select to authenticated using (id = auth.uid() or public.is_admin());
create policy "Admins manage profiles" on public.profiles
for all to authenticated using (public.is_admin()) with check (public.is_admin());

create policy "Authenticated users read categories" on public.categories
for select to authenticated using (true);
create policy "Admins manage categories" on public.categories
for all to authenticated using (public.is_admin()) with check (public.is_admin());

create policy "Authenticated users read groups" on public.content_groups
for select to authenticated using (true);
create policy "Admins manage groups" on public.content_groups
for all to authenticated using (public.is_admin()) with check (public.is_admin());

create policy "Users read active streams" on public.streams
for select to authenticated using (is_active = true or public.is_admin());
create policy "Admins manage streams" on public.streams
for all to authenticated using (public.is_admin()) with check (public.is_admin());

create policy "Users manage their favorites" on public.favorites
for all to authenticated using (user_id = auth.uid()) with check (user_id = auth.uid());

insert into public.categories (slug, name, sort_order, is_adult)
values
  ('ao-vivo', 'TV ao vivo', 10, false),
  ('filmes', 'Filmes', 20, false),
  ('series', 'Séries', 30, false),
  ('esportes', 'Esportes', 40, false),
  ('adultos', 'Adultos +18', 50, true)
on conflict (slug) do update
set name = excluded.name, sort_order = excluded.sort_order, is_adult = excluded.is_adult;
