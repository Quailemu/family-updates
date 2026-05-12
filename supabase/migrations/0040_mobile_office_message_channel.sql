-- 0040_mobile_office_message_channel.sql
-- Adds one-current-message channels between Family Office and Mobile/carer.

alter table public.messages
  drop constraint if exists messages_direction_check;

alter table public.messages
  drop constraint if exists messages_channel_check;

alter table public.messages
  drop constraint if exists messages_channel_direction_check;

alter table public.messages
  add constraint messages_direction_check
  check (
    direction in (
      'to_resident',
      'from_resident',
      'office_to_family',
      'office_to_mobile',
      'mobile_to_office'
    )
  );

alter table public.messages
  add constraint messages_channel_check
  check (channel in ('resident_family', 'office_family', 'mobile_office'));

alter table public.messages
  add constraint messages_channel_direction_check
  check (
    (channel = 'resident_family' and direction in ('to_resident', 'from_resident'))
    or (channel = 'office_family' and direction = 'office_to_family')
    or (channel = 'mobile_office' and direction in ('office_to_mobile', 'mobile_to_office'))
  );

create unique index if not exists idx_messages_unique_mobile_office
  on public.messages (resident_id, direction, channel)
  where channel = 'mobile_office';

do $$
declare
  family_table text;
  access_table text;
  family_id_column text;
begin
  if to_regclass('public.family_user') is not null then
    family_table := 'family_user';
    access_table := 'resident_access';
    family_id_column := 'family_user_id';
  else
    family_table := 'family_contacts';
    access_table := 'family_contact_access';
    family_id_column := 'family_contact_id';
  end if;

  drop policy if exists "messages_insert_care_home" on public.messages;
  execute format(
    $policy$
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
                from public.%I fu
                join public.%I ra
                  on ra.%I = fu.id
                where fu.auth_user_id = messages.contact_user_id
                  and fu.care_home_id = r.care_home_id
                  and fu.active = true
                  and ra.resident_id = messages.resident_id
                  and ra.active = true
              )
            )
            or
            (
              messages.channel = 'resident_family'
              and messages.direction = 'from_resident'
              and messages.contact_user_id is not null
              and exists (
                select 1
                from public.%I fu
                join public.%I ra
                  on ra.%I = fu.id
                where fu.auth_user_id = messages.contact_user_id
                  and fu.care_home_id = r.care_home_id
                  and fu.active = true
                  and ra.resident_id = messages.resident_id
                  and ra.active = true
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
            or
            (
              messages.channel = 'mobile_office'
              and messages.direction in ('office_to_mobile', 'mobile_to_office')
              and messages.contact_user_id is null
              and messages.family_id = messages.resident_id
            )
          )
      )
    )
    $policy$,
    family_table,
    access_table,
    family_id_column,
    family_table,
    access_table,
    family_id_column
  );

  drop policy if exists "messages_update_care_home" on public.messages;
  execute format(
    $policy$
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
                from public.%I fu
                join public.%I ra
                  on ra.%I = fu.id
                where fu.auth_user_id = messages.contact_user_id
                  and fu.care_home_id = r.care_home_id
                  and fu.active = true
                  and ra.resident_id = messages.resident_id
                  and ra.active = true
              )
            )
            or
            (
              messages.channel = 'resident_family'
              and messages.direction = 'from_resident'
              and messages.contact_user_id is not null
              and exists (
                select 1
                from public.%I fu
                join public.%I ra
                  on ra.%I = fu.id
                where fu.auth_user_id = messages.contact_user_id
                  and fu.care_home_id = r.care_home_id
                  and fu.active = true
                  and ra.resident_id = messages.resident_id
                  and ra.active = true
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
            or
            (
              messages.channel = 'mobile_office'
              and messages.direction in ('office_to_mobile', 'mobile_to_office')
              and messages.contact_user_id is null
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
                from public.%I fu
                join public.%I ra
                  on ra.%I = fu.id
                where fu.auth_user_id = messages.contact_user_id
                  and fu.care_home_id = r.care_home_id
                  and fu.active = true
                  and ra.resident_id = messages.resident_id
                  and ra.active = true
              )
            )
            or
            (
              messages.channel = 'resident_family'
              and messages.direction = 'from_resident'
              and messages.contact_user_id is not null
              and exists (
                select 1
                from public.%I fu
                join public.%I ra
                  on ra.%I = fu.id
                where fu.auth_user_id = messages.contact_user_id
                  and fu.care_home_id = r.care_home_id
                  and fu.active = true
                  and ra.resident_id = messages.resident_id
                  and ra.active = true
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
            or
            (
              messages.channel = 'mobile_office'
              and messages.direction in ('office_to_mobile', 'mobile_to_office')
              and messages.contact_user_id is null
              and messages.family_id = messages.resident_id
            )
          )
      )
    )
    $policy$,
    family_table,
    access_table,
    family_id_column,
    family_table,
    access_table,
    family_id_column,
    family_table,
    access_table,
    family_id_column,
    family_table,
    access_table,
    family_id_column
  );
end $$;
