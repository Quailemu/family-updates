-- 0009_mobile_fair_playback_and_resident_broadcast.sql
-- 1) Resident->Family becomes one shared broadcast message per resident.
-- 2) Adds persistent per-resident playback pointer for fair mobile playback order.

-- Ensure family_id is present on resident-family rows.
update public.messages
set family_id = resident_id
where channel = 'resident_family'
  and family_id is null;

-- Collapse legacy resident->family per-contact rows into one latest shared row.
with ranked as (
  select
    id,
    resident_id,
    row_number() over (
      partition by resident_id
      order by recorded_at desc, created_at desc, id desc
    ) as rn
  from public.messages
  where channel = 'resident_family'
    and direction = 'from_resident'
),
to_keep as (
  select id, resident_id from ranked where rn = 1
),
to_drop as (
  select id from ranked where rn > 1
)
update public.messages m
set
  contact_user_id = null,
  family_id = m.resident_id
from to_keep k
where m.id = k.id;

delete from public.messages m
using to_drop d
where m.id = d.id;

-- Replace resident-family uniqueness with direction-specific constraints.
drop index if exists public.idx_messages_unique_resident_family;

create unique index if not exists idx_messages_unique_resident_family_to_resident
  on public.messages (resident_id, contact_user_id, direction, channel)
  where channel = 'resident_family'
    and direction = 'to_resident';

create unique index if not exists idx_messages_unique_resident_family_from_resident
  on public.messages (resident_id, family_id, direction, channel)
  where channel = 'resident_family'
    and direction = 'from_resident';

-- Family read policy: allow resident broadcast messages for any authorised contact.
drop policy if exists "messages_select_self" on public.messages;
create policy "messages_select_self"
on public.messages
for select
using (
  (
    channel = 'resident_family'
    and direction = 'to_resident'
    and contact_user_id = auth.uid()
    and exists (
      select 1
      from public.family_contacts fc
      join public.family_contact_access fca
        on fca.family_contact_id = fc.id
      join public.residents r on r.id = messages.resident_id
      where fc.auth_user_id = auth.uid()
        and fc.care_home_id = r.care_home_id
        and fca.resident_id = messages.resident_id
        and fca.active = true
        and fc.active = true
        and r.active = true
    )
  )
  or
  (
    channel = 'resident_family'
    and direction = 'from_resident'
    and family_id = resident_id
    and exists (
      select 1
      from public.family_contacts fc
      join public.family_contact_access fca
        on fca.family_contact_id = fc.id
      join public.residents r on r.id = messages.resident_id
      where fc.auth_user_id = auth.uid()
        and fc.care_home_id = r.care_home_id
        and fca.resident_id = messages.resident_id
        and fca.active = true
        and fc.active = true
        and r.active = true
    )
  )
  or
  (
    channel = 'office_family'
    and direction = 'office_to_family'
    and exists (
      select 1
      from public.family_contacts fc
      join public.family_contact_access fca
        on fca.family_contact_id = fc.id
      join public.residents r on r.id = messages.resident_id
      where fc.auth_user_id = auth.uid()
        and fc.care_home_id = r.care_home_id
        and fca.resident_id = messages.resident_id
        and fca.active = true
        and fc.active = true
        and r.active = true
    )
  )
);

-- Care-home write policies: permit shared resident broadcast writes.
drop policy if exists "messages_insert_care_home" on public.messages;
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
      and (
        (
          messages.channel = 'resident_family'
          and messages.direction = 'to_resident'
          and messages.contact_user_id is not null
          and exists (
            select 1
            from public.family_contacts fc
            join public.family_contact_access fca
              on fca.family_contact_id = fc.id
            where fc.auth_user_id = messages.contact_user_id
              and fc.care_home_id = r.care_home_id
              and fc.active = true
              and fca.resident_id = messages.resident_id
              and fca.active = true
          )
        )
        or
        (
          messages.channel = 'resident_family'
          and messages.direction = 'from_resident'
          and messages.contact_user_id is null
          and messages.family_id = messages.resident_id
        )
        or
        (
          messages.channel = 'office_family'
          and messages.direction = 'office_to_family'
          and messages.family_id = messages.resident_id
        )
      )
  )
);

drop policy if exists "messages_update_care_home" on public.messages;
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
      and (
        (
          messages.channel = 'resident_family'
          and messages.direction = 'to_resident'
          and messages.contact_user_id is not null
          and exists (
            select 1
            from public.family_contacts fc
            join public.family_contact_access fca
              on fca.family_contact_id = fc.id
            where fc.auth_user_id = messages.contact_user_id
              and fc.care_home_id = r.care_home_id
              and fc.active = true
              and fca.resident_id = messages.resident_id
              and fca.active = true
          )
        )
        or
        (
          messages.channel = 'resident_family'
          and messages.direction = 'from_resident'
          and messages.contact_user_id is null
          and messages.family_id = messages.resident_id
        )
        or
        (
          messages.channel = 'office_family'
          and messages.direction = 'office_to_family'
          and messages.family_id = messages.resident_id
        )
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
      and (
        (
          messages.channel = 'resident_family'
          and messages.direction = 'to_resident'
          and messages.contact_user_id is not null
          and exists (
            select 1
            from public.family_contacts fc
            join public.family_contact_access fca
              on fca.family_contact_id = fc.id
            where fc.auth_user_id = messages.contact_user_id
              and fc.care_home_id = r.care_home_id
              and fc.active = true
              and fca.resident_id = messages.resident_id
              and fca.active = true
          )
        )
        or
        (
          messages.channel = 'resident_family'
          and messages.direction = 'from_resident'
          and messages.contact_user_id is null
          and messages.family_id = messages.resident_id
        )
        or
        (
          messages.channel = 'office_family'
          and messages.direction = 'office_to_family'
          and messages.family_id = messages.resident_id
        )
      )
  )
);

-- Persistent playback pointer (per resident).
create table if not exists public.resident_playback_state (
  resident_id uuid primary key references public.residents(id) on delete cascade,
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  next_contact_user_id uuid references auth.users(id) on delete set null,
  updated_at timestamptz not null default now()
);

create index if not exists idx_resident_playback_state_care_home
  on public.resident_playback_state (care_home_id);

alter table public.resident_playback_state enable row level security;

drop policy if exists "resident_playback_state_select_care_home" on public.resident_playback_state;
create policy "resident_playback_state_select_care_home"
on public.resident_playback_state
for select
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = resident_playback_state.care_home_id
      and chu.active = true
  )
);

drop policy if exists "resident_playback_state_insert_care_home" on public.resident_playback_state;
create policy "resident_playback_state_insert_care_home"
on public.resident_playback_state
for insert
with check (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = resident_playback_state.care_home_id
      and chu.active = true
  )
);

drop policy if exists "resident_playback_state_update_care_home" on public.resident_playback_state;
create policy "resident_playback_state_update_care_home"
on public.resident_playback_state
for update
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = resident_playback_state.care_home_id
      and chu.active = true
  )
)
with check (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = resident_playback_state.care_home_id
      and chu.active = true
  )
);
