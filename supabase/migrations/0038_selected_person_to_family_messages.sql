-- 0038_selected_person_to_family_messages.sql
-- Person/resident -> family messages may be either:
-- 1) one current shared message to the family group, or
-- 2) one current direct message to a selected Family Member.

drop index if exists public.idx_messages_unique_resident_family_from_resident;

create unique index if not exists idx_messages_unique_resident_family_from_resident_group
  on public.messages (resident_id, family_id, direction, channel)
  where channel = 'resident_family'
    and direction = 'from_resident'
    and contact_user_id is null;

create unique index if not exists idx_messages_unique_resident_family_from_resident_contact
  on public.messages (resident_id, contact_user_id, direction, channel)
  where channel = 'resident_family'
    and direction = 'from_resident'
    and contact_user_id is not null;

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

  drop policy if exists "messages_select_self" on public.messages;
  execute format(
    $policy$
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
          from public.%I fu
          join public.%I ra
            on ra.%I = fu.id
          join public.residents r on r.id = messages.resident_id
          where fu.auth_user_id = auth.uid()
            and fu.care_home_id = r.care_home_id
            and ra.resident_id = messages.resident_id
            and ra.active = true
            and fu.active = true
            and r.active = true
        )
      )
      or
      (
        channel = 'resident_family'
        and direction = 'from_resident'
        and contact_user_id = auth.uid()
        and exists (
          select 1
          from public.%I fu
          join public.%I ra
            on ra.%I = fu.id
          join public.residents r on r.id = messages.resident_id
          where fu.auth_user_id = auth.uid()
            and fu.care_home_id = r.care_home_id
            and ra.resident_id = messages.resident_id
            and ra.active = true
            and fu.active = true
            and r.active = true
        )
      )
      or
      (
        channel = 'resident_family'
        and direction = 'from_resident'
        and contact_user_id is null
        and family_id = resident_id
        and exists (
          select 1
          from public.%I fu
          join public.%I ra
            on ra.%I = fu.id
          join public.residents r on r.id = messages.resident_id
          where fu.auth_user_id = auth.uid()
            and fu.care_home_id = r.care_home_id
            and ra.resident_id = messages.resident_id
            and ra.active = true
            and fu.active = true
            and r.active = true
        )
      )
      or
      (
        channel = 'office_family'
        and direction = 'office_to_family'
        and exists (
          select 1
          from public.%I fu
          join public.%I ra
            on ra.%I = fu.id
          join public.residents r on r.id = messages.resident_id
          where fu.auth_user_id = auth.uid()
            and fu.care_home_id = r.care_home_id
            and ra.resident_id = messages.resident_id
            and ra.active = true
            and fu.active = true
            and r.active = true
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
