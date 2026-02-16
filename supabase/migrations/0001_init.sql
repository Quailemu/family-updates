-- 0001_init.sql
-- Initializes schema, RLS, and storage policies for voice-message.com (pilot rebuild).
-- Enforces "one-message only" per resident/contact/direction via a unique constraint.

-- a) extensions
create extension if not exists "pgcrypto";

-- b) enums
-- (none)

-- c) tables
create table if not exists public.care_homes (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now(),
  active boolean not null default true
);

create table if not exists public.care_home_users (
  id uuid primary key default gen_random_uuid(),
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  auth_user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  active boolean not null default true
);

create table if not exists public.residents (
  id uuid primary key default gen_random_uuid(),
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  preferred_display_name text not null,
  care_home_reference text not null,
  created_at timestamptz not null default now(),
  active boolean not null default true
);

create table if not exists public.family_contacts (
  id uuid primary key default gen_random_uuid(),
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  auth_user_id uuid not null references auth.users(id) on delete cascade,
  email text not null,
  display_name text not null,
  created_at timestamptz not null default now(),
  active boolean not null default true
);

create table if not exists public.family_contact_access (
  id uuid primary key default gen_random_uuid(),
  -- care_home_id is derived via residents to avoid cross-home mismatches.
  resident_id uuid not null references public.residents(id) on delete cascade,
  family_contact_id uuid not null references public.family_contacts(id) on delete cascade,
  created_at timestamptz not null default now(),
  active boolean not null default true
);

create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  -- care_home_id is derived via residents to avoid cross-home mismatches.
  resident_id uuid not null references public.residents(id) on delete cascade,
  contact_user_id uuid not null references auth.users(id) on delete cascade,
  direction text not null,
  audio_storage_path text not null,
  audio_mime_type text not null,
  audio_bytes integer not null,
  recorded_at timestamptz not null,
  created_at timestamptz not null default now()
);

create table if not exists public.security_events (
  id uuid primary key default gen_random_uuid(),
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  actor_user_id uuid references auth.users(id) on delete set null,
  actor_role text not null,
  event_type text not null,
  resident_id uuid references public.residents(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists public.care_home_settings (
  care_home_id uuid primary key references public.care_homes(id) on delete cascade,
  quick_lock_enabled boolean not null default true,
  quick_lock_timeout_minutes integer not null default 15,
  desk_warning_minutes integer not null default 120,
  updated_at timestamptz not null default now()
);

-- d) constraints and indexes
do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'care_home_users_auth_user_id_key'
  ) then
    alter table public.care_home_users
      add constraint care_home_users_auth_user_id_key unique (auth_user_id);
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'care_home_users_care_home_id_key'
  ) then
    alter table public.care_home_users
      add constraint care_home_users_care_home_id_key unique (care_home_id);
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'family_contacts_auth_user_id_key'
  ) then
    alter table public.family_contacts
      add constraint family_contacts_auth_user_id_key unique (auth_user_id);
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'family_contact_access_resident_contact_key'
  ) then
    alter table public.family_contact_access
      add constraint family_contact_access_resident_contact_key
      unique (resident_id, family_contact_id);
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'messages_one_current_per_direction'
  ) then
    alter table public.messages
      add constraint messages_one_current_per_direction
      unique (resident_id, contact_user_id, direction);
  end if;
end $$;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'messages_direction_check'
  ) then
    alter table public.messages
      add constraint messages_direction_check
      check (direction in ('to_resident', 'from_resident'));
  end if;
end $$;

create index if not exists idx_residents_care_home_id
  on public.residents (care_home_id);

create index if not exists idx_family_contacts_care_home_id
  on public.family_contacts (care_home_id);

create index if not exists idx_family_contact_access_resident_id
  on public.family_contact_access (resident_id);

create index if not exists idx_family_contact_access_family_contact_id
  on public.family_contact_access (family_contact_id);

create index if not exists idx_messages_resident_id
  on public.messages (resident_id);

create index if not exists idx_messages_contact_user_id
  on public.messages (contact_user_id);

create index if not exists idx_security_events_care_home_id
  on public.security_events (care_home_id);

create index if not exists idx_security_events_created_at
  on public.security_events (created_at);

-- e) helper functions
-- (none)

-- f) enable RLS
alter table public.care_homes enable row level security;
alter table public.care_home_users enable row level security;
alter table public.residents enable row level security;
alter table public.family_contacts enable row level security;
alter table public.family_contact_access enable row level security;
alter table public.messages enable row level security;
alter table public.security_events enable row level security;
alter table public.care_home_settings enable row level security;

-- g) create RLS policies
drop policy if exists "care_homes_select_own" on public.care_homes;
create policy "care_homes_select_own"
on public.care_homes
for select
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = care_homes.id
      and chu.auth_user_id = auth.uid()
      -- Active-only access for shared login.
      and chu.active = true
  )
);

drop policy if exists "care_home_users_select_self" on public.care_home_users;
create policy "care_home_users_select_self"
on public.care_home_users
for select
using (
  auth_user_id = auth.uid()
  -- Deactivated shared logins cannot access data.
  and care_home_users.active = true
);

drop policy if exists "residents_select_care_home" on public.residents;
create policy "residents_select_care_home"
on public.residents
for select
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = residents.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
  -- Care home visibility includes inactive residents for management.
);

drop policy if exists "residents_write_care_home" on public.residents;
create policy "residents_write_care_home"
on public.residents
for all
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = residents.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
)
with check (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = residents.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "family_contacts_select_care_home" on public.family_contacts;
create policy "family_contacts_select_care_home"
on public.family_contacts
for select
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = family_contacts.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
  -- Care home visibility includes inactive contacts for management.
);

drop policy if exists "family_contacts_select_self" on public.family_contacts;
create policy "family_contacts_select_self"
on public.family_contacts
for select
using (auth_user_id = auth.uid() and family_contacts.active = true);

drop policy if exists "family_contacts_write_care_home" on public.family_contacts;
create policy "family_contacts_write_care_home"
on public.family_contacts
for all
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = family_contacts.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
)
with check (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = family_contacts.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "family_contact_access_select_care_home" on public.family_contact_access;
create policy "family_contact_access_select_care_home"
on public.family_contact_access
for select
using (
  exists (
    select 1 from public.care_home_users chu
    join public.residents r on r.id = family_contact_access.resident_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
  -- Care home visibility includes inactive links for management.
);

drop policy if exists "family_contact_access_select_self" on public.family_contact_access;
create policy "family_contact_access_select_self"
on public.family_contact_access
for select
using (
  exists (
    select 1
    from public.family_contacts fc
    join public.residents r on r.id = family_contact_access.resident_id
    where fc.id = family_contact_access.family_contact_id
      and fc.auth_user_id = auth.uid()
      and fc.care_home_id = r.care_home_id
      and fc.active = true
      and r.active = true
      and family_contact_access.active = true
  )
);

drop policy if exists "family_contact_access_write_care_home" on public.family_contact_access;
create policy "family_contact_access_write_care_home"
on public.family_contact_access
for all
using (
  exists (
    select 1 from public.care_home_users chu
    join public.residents r on r.id = family_contact_access.resident_id
    join public.family_contacts fc on fc.id = family_contact_access.family_contact_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
      and r.active = true
      -- Prevent cross-home linkage.
      and fc.care_home_id = r.care_home_id
      and fc.active = true
  )
)
with check (
  exists (
    select 1 from public.care_home_users chu
    join public.residents r on r.id = family_contact_access.resident_id
    join public.family_contacts fc on fc.id = family_contact_access.family_contact_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
      and r.active = true
      -- Prevent cross-home linkage.
      and fc.care_home_id = r.care_home_id
      and fc.active = true
  )
);

drop policy if exists "messages_select_care_home" on public.messages;
create policy "messages_select_care_home"
on public.messages
for select
using (
  exists (
    select 1
    from public.care_home_users chu
    join public.residents r on r.id = messages.resident_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
  -- Care home can read messages for inactive residents/contacts for management.
);

drop policy if exists "messages_select_self" on public.messages;
create policy "messages_select_self"
on public.messages
for select
using (
  contact_user_id = auth.uid()
  and exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r on r.id = messages.resident_id
    where fc.auth_user_id = auth.uid()
      -- Ensure contact belongs to the same care home as the resident.
      and fc.care_home_id = r.care_home_id
      and fca.resident_id = messages.resident_id
      -- Prevent read-after-removal.
      and fca.active = true
      and fc.active = true
      and r.active = true
  )
);

drop policy if exists "messages_write_care_home" on public.messages;
create policy "messages_write_care_home"
on public.messages
for all
using (
  exists (
    select 1
    from public.care_home_users chu
    join public.residents r on r.id = messages.resident_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
      and r.active = true
      -- No writes for inactive residents/contacts; prevents targeting unrelated auth users.
      and exists (
        select 1
        from public.family_contacts fc
        join public.family_contact_access fca
          on fca.family_contact_id = fc.id
        where fc.auth_user_id = messages.contact_user_id
          -- Ensure contact belongs to the same care home as the resident.
          and fc.care_home_id = r.care_home_id
          and fc.active = true
          and fca.resident_id = messages.resident_id
          and fca.active = true
      )
  )
)
with check (
  exists (
    select 1
    from public.care_home_users chu
    join public.residents r on r.id = messages.resident_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
      and r.active = true
      -- No writes for inactive residents/contacts; prevents targeting unrelated auth users.
      and exists (
        select 1
        from public.family_contacts fc
        join public.family_contact_access fca
          on fca.family_contact_id = fc.id
        where fc.auth_user_id = messages.contact_user_id
          -- Ensure contact belongs to the same care home as the resident.
          and fc.care_home_id = r.care_home_id
          and fc.active = true
          and fca.resident_id = messages.resident_id
          and fca.active = true
      )
  )
);

drop policy if exists "messages_write_family_to_resident_insert" on public.messages;
drop policy if exists "messages_write_family_to_resident_update" on public.messages;
create policy "messages_write_family_to_resident_insert"
on public.messages
for insert
with check (
  contact_user_id = auth.uid()
  and direction = 'to_resident'
  and exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r on r.id = messages.resident_id
    where fc.auth_user_id = auth.uid()
      -- Ensure contact belongs to the same care home as the resident.
      and fc.care_home_id = r.care_home_id
      and fca.resident_id = messages.resident_id
      and fc.active = true
      and fca.active = true
      and r.active = true
  )
);

create policy "messages_write_family_to_resident_update"
on public.messages
for update
using (
  contact_user_id = auth.uid()
  and direction = 'to_resident'
  and exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r on r.id = messages.resident_id
    where fc.auth_user_id = auth.uid()
      -- Ensure contact belongs to the same care home as the resident.
      and fc.care_home_id = r.care_home_id
      and fca.resident_id = messages.resident_id
      and fc.active = true
      and fca.active = true
      and r.active = true
  )
)
with check (
  contact_user_id = auth.uid()
  and direction = 'to_resident'
  and exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r on r.id = messages.resident_id
    where fc.auth_user_id = auth.uid()
      -- Ensure contact belongs to the same care home as the resident.
      and fc.care_home_id = r.care_home_id
      and fca.resident_id = messages.resident_id
      and fc.active = true
      and fca.active = true
      and r.active = true
  )
);

drop policy if exists "security_events_select_care_home" on public.security_events;
create policy "security_events_select_care_home"
on public.security_events
for select
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = security_events.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "care_home_settings_select" on public.care_home_settings;
create policy "care_home_settings_select"
on public.care_home_settings
for select
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = care_home_settings.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "care_home_settings_update" on public.care_home_settings;
create policy "care_home_settings_update"
on public.care_home_settings
for update
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = care_home_settings.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
)
with check (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = care_home_settings.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

-- h) storage bucket creation + storage RLS policies
insert into storage.buckets (id, name, public)
values ('voice_messages', 'voice_messages', false)
on conflict (id) do nothing;

alter table storage.objects enable row level security;

drop policy if exists "storage_read_care_home" on storage.objects;
drop policy if exists "storage_write_care_home" on storage.objects;
drop policy if exists "storage_read_family" on storage.objects;
drop policy if exists "storage_write_family" on storage.objects;
drop policy if exists "storage_deny_select" on storage.objects;
drop policy if exists "storage_deny_insert" on storage.objects;
drop policy if exists "storage_deny_update" on storage.objects;
drop policy if exists "storage_deny_delete" on storage.objects;

create policy "storage_deny_select"
on storage.objects
for select
using (false);

create policy "storage_deny_insert"
on storage.objects
for insert
with check (false);

create policy "storage_deny_update"
on storage.objects
for update
using (false)
with check (false);

create policy "storage_deny_delete"
on storage.objects
for delete
using (false);

-- Verification (commented)
-- 1) List tables
-- select tablename from pg_tables where schemaname = 'public';
-- 2) RLS enabled flags
-- select relname, relrowsecurity from pg_class where relname in ('care_homes','care_home_users','residents','family_contacts','family_contact_access','messages','security_events','care_home_settings');
-- 3) Policies present
-- select schemaname, tablename, policyname from pg_policies where tablename in ('care_homes','care_home_users','residents','family_contacts','family_contact_access','messages','security_events','care_home_settings');
-- 4) Unique constraint for one-message-per-direction
-- select conname, conrelid::regclass from pg_constraint where conname = 'messages_one_current_per_direction';
-- 5) Check constraint for direction
-- select conname, conrelid::regclass from pg_constraint where conname = 'messages_direction_check';
-- 6) Ensure messages have no care_home_id column
-- select column_name from information_schema.columns where table_schema='public' and table_name='messages';
-- 7) Ensure family_contact_access has no care_home_id column
-- select column_name from information_schema.columns where table_schema='public' and table_name='family_contact_access';
-- 8) Storage bucket exists
-- select id, name, public from storage.buckets where id = 'voice_messages';
-- 9) Storage policies present
-- select policyname from pg_policies where schemaname = 'storage' and tablename = 'objects';
-- 10) Confirm storage access is tied to messages (manual inspection of policies above)
