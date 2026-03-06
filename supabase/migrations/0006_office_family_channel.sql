-- 0006_office_family_channel.sql
-- Adds an independent office->family broadcast channel while preserving
-- one-current-message semantics for resident<->family directions.

alter table public.messages
  add column if not exists channel text;

alter table public.messages
  add column if not exists family_id uuid references public.residents(id) on delete cascade;

update public.messages
set channel = 'resident_family'
where channel is null;

update public.messages
set family_id = resident_id
where family_id is null;

alter table public.messages
  alter column channel set default 'resident_family';

alter table public.messages
  alter column channel set not null;

do $$
begin
  if exists (
    select 1
    from pg_constraint
    where conname = 'messages_one_current_per_direction'
  ) then
    alter table public.messages
      drop constraint messages_one_current_per_direction;
  end if;
end $$;

do $$
begin
  if exists (
    select 1
    from pg_constraint
    where conname = 'messages_direction_check'
  ) then
    alter table public.messages
      drop constraint messages_direction_check;
  end if;
end $$;

alter table public.messages
  alter column contact_user_id drop not null;

alter table public.messages
  drop constraint if exists messages_channel_check;

alter table public.messages
  drop constraint if exists messages_channel_direction_check;

alter table public.messages
  add constraint messages_direction_check
  check (direction in ('to_resident', 'from_resident', 'office_to_family'));

alter table public.messages
  add constraint messages_channel_check
  check (channel in ('resident_family', 'office_family'));

alter table public.messages
  add constraint messages_channel_direction_check
  check (
    (channel = 'resident_family' and direction in ('to_resident', 'from_resident'))
    or (channel = 'office_family' and direction = 'office_to_family')
  );

create unique index if not exists idx_messages_unique_resident_family
  on public.messages (resident_id, contact_user_id, direction, channel)
  where channel = 'resident_family';

create unique index if not exists idx_messages_unique_office_family
  on public.messages (resident_id, family_id, direction, channel)
  where channel = 'office_family';

create index if not exists idx_messages_family_id
  on public.messages (family_id);

drop policy if exists "messages_select_self" on public.messages;
create policy "messages_select_self"
on public.messages
for select
using (
  (
    channel = 'resident_family'
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
          messages.channel = 'office_family'
          and messages.direction = 'office_to_family'
          and messages.family_id = messages.resident_id
        )
      )
  )
);

drop policy if exists "messages_write_family_to_resident_insert" on public.messages;
create policy "messages_write_family_to_resident_insert"
on public.messages
for insert
with check (
  contact_user_id = auth.uid()
  and direction = 'to_resident'
  and channel = 'resident_family'
  and exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r on r.id = messages.resident_id
    where fc.auth_user_id = auth.uid()
      and fc.care_home_id = r.care_home_id
      and fca.resident_id = messages.resident_id
      and fc.active = true
      and fca.active = true
      and r.active = true
  )
);

drop policy if exists "messages_write_family_to_resident_update" on public.messages;
create policy "messages_write_family_to_resident_update"
on public.messages
for update
using (
  contact_user_id = auth.uid()
  and direction = 'to_resident'
  and channel = 'resident_family'
  and exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r on r.id = messages.resident_id
    where fc.auth_user_id = auth.uid()
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
  and channel = 'resident_family'
  and exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r on r.id = messages.resident_id
    where fc.auth_user_id = auth.uid()
      and fc.care_home_id = r.care_home_id
      and fca.resident_id = messages.resident_id
      and fc.active = true
      and fca.active = true
      and r.active = true
  )
);
