-- 0003_care_hub_mfa.sql
-- Optional TOTP 2FA for Care Hub – Office users.

create table if not exists public.care_hub_mfa (
  auth_user_id uuid primary key references auth.users(id) on delete cascade,
  totp_secret text not null,
  recovery_code_hashes text[] not null default '{}',
  enabled boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_care_hub_mfa_enabled
  on public.care_hub_mfa (enabled);

alter table public.care_hub_mfa enable row level security;

drop policy if exists "care_hub_mfa_select_self" on public.care_hub_mfa;
create policy "care_hub_mfa_select_self"
on public.care_hub_mfa
for select
using (
  auth_user_id = auth.uid()
  and exists (
    select 1 from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "care_hub_mfa_upsert_self" on public.care_hub_mfa;
create policy "care_hub_mfa_upsert_self"
on public.care_hub_mfa
for all
using (
  auth_user_id = auth.uid()
  and exists (
    select 1 from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.active = true
  )
)
with check (
  auth_user_id = auth.uid()
  and exists (
    select 1 from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);
