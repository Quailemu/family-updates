-- Persistent per-contact playback state for deterministic unread tally.

create table if not exists public.resident_contact_playback_state (
  resident_id uuid not null references public.residents(id) on delete cascade,
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  contact_user_id uuid not null references auth.users(id) on delete cascade,
  last_played_recorded_at timestamptz not null,
  updated_at timestamptz not null default now(),
  primary key (resident_id, contact_user_id)
);

create index if not exists idx_resident_contact_playback_state_care_home
  on public.resident_contact_playback_state (care_home_id);

alter table public.resident_contact_playback_state enable row level security;

drop policy if exists "resident_contact_playback_state_select_care_home" on public.resident_contact_playback_state;
create policy "resident_contact_playback_state_select_care_home"
on public.resident_contact_playback_state
for select
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = resident_contact_playback_state.care_home_id
      and chu.active = true
  )
);

drop policy if exists "resident_contact_playback_state_insert_care_home" on public.resident_contact_playback_state;
create policy "resident_contact_playback_state_insert_care_home"
on public.resident_contact_playback_state
for insert
with check (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = resident_contact_playback_state.care_home_id
      and chu.active = true
  )
);

drop policy if exists "resident_contact_playback_state_update_care_home" on public.resident_contact_playback_state;
create policy "resident_contact_playback_state_update_care_home"
on public.resident_contact_playback_state
for update
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = resident_contact_playback_state.care_home_id
      and chu.active = true
  )
)
with check (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = resident_contact_playback_state.care_home_id
      and chu.active = true
  )
);
