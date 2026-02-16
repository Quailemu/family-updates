-- Audit log (pilot-safe)
create table if not exists public.audit_log (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  actor_user_id uuid not null references auth.users(id) on delete set null,
  actor_role text not null,
  care_home_id uuid references public.care_homes(id) on delete set null,
  action text not null,
  target_id text
);

create index if not exists idx_audit_log_care_home_id
  on public.audit_log (care_home_id);
create index if not exists idx_audit_log_actor_user_id
  on public.audit_log (actor_user_id);
create index if not exists idx_audit_log_created_at
  on public.audit_log (created_at);

alter table public.audit_log enable row level security;

drop policy if exists "audit_log_insert_family" on public.audit_log;
drop policy if exists "audit_log_insert_care_hub" on public.audit_log;
drop policy if exists "audit_log_select_care_hub" on public.audit_log;

create policy "audit_log_insert_family"
on public.audit_log
for insert
with check (
  actor_user_id = auth.uid()
  and actor_role = 'family'
  and exists (
    select 1
    from public.family_contacts fc
    where fc.auth_user_id = auth.uid()
      and fc.care_home_id = audit_log.care_home_id
      and fc.active = true
  )
);

create policy "audit_log_insert_care_hub"
on public.audit_log
for insert
with check (
  actor_user_id = auth.uid()
  and actor_role = 'care_hub'
  and exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = audit_log.care_home_id
      and chu.active = true
  )
);

create policy "audit_log_select_care_hub"
on public.audit_log
for select
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = audit_log.care_home_id
      and chu.active = true
  )
);

-- Messages: disallow delete, split care home writes into insert/update only.
drop policy if exists "messages_write_care_home" on public.messages;

create policy "messages_insert_care_home"
on public.messages
for insert
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

create policy "messages_update_care_home"
on public.messages
for update
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
