-- 0044_mobile_office_messages_per_mobile_user.sql
-- Keep one current Mobile/Office message per Mobile Support user.

drop index if exists public.idx_messages_unique_mobile_office;

create unique index if not exists idx_messages_unique_mobile_office_per_user
  on public.messages (resident_id, contact_user_id, direction, channel)
  where channel = 'mobile_office'
    and contact_user_id is not null;

create unique index if not exists idx_messages_unique_mobile_office_shared
  on public.messages (resident_id, direction, channel)
  where channel = 'mobile_office'
    and contact_user_id is null;

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
              and messages.family_id = messages.resident_id
              and (
                (
                  coalesce(chu.care_access_level, 'office') = 'office'
                  and messages.direction in ('office_to_mobile', 'mobile_to_office')
                  and (
                    messages.contact_user_id is null
                    or exists (
                      select 1
                      from public.care_home_users target_chu
                      where target_chu.care_home_id = r.care_home_id
                        and target_chu.auth_user_id = messages.contact_user_id
                        and target_chu.active = true
                        and coalesce(target_chu.care_access_level, 'office') = 'mobile'
                    )
                  )
                )
                or
                (
                  coalesce(chu.care_access_level, 'office') = 'mobile'
                  and messages.direction = 'mobile_to_office'
                  and messages.contact_user_id = auth.uid()
                )
              )
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
              and messages.family_id = messages.resident_id
              and (
                (
                  coalesce(chu.care_access_level, 'office') = 'office'
                  and messages.direction in ('office_to_mobile', 'mobile_to_office')
                  and (
                    messages.contact_user_id is null
                    or exists (
                      select 1
                      from public.care_home_users target_chu
                      where target_chu.care_home_id = r.care_home_id
                        and target_chu.auth_user_id = messages.contact_user_id
                        and target_chu.active = true
                        and coalesce(target_chu.care_access_level, 'office') = 'mobile'
                    )
                  )
                )
                or
                (
                  coalesce(chu.care_access_level, 'office') = 'mobile'
                  and messages.direction = 'mobile_to_office'
                  and messages.contact_user_id = auth.uid()
                )
              )
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
end $$;

create or replace function public.list_mobile_support_users()
returns table (
  auth_user_id uuid,
  staff_email text,
  active boolean
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_care_home_id uuid;
begin
  select chu.care_home_id
  into v_care_home_id
  from public.care_home_users chu
  where chu.auth_user_id = auth.uid()
    and chu.active = true
    and coalesce(chu.care_access_level, 'office') = 'office'
  limit 1;

  if v_care_home_id is null then
    raise exception 'No active Office user row for auth user';
  end if;

  return query
    select
      chu.auth_user_id,
      coalesce(au.email, '')::text as staff_email,
      chu.active
    from public.care_home_users chu
    left join auth.users au
      on au.id = chu.auth_user_id
    where chu.care_home_id = v_care_home_id
      and chu.active = true
      and coalesce(chu.care_access_level, 'office') = 'mobile'
    order by coalesce(au.email, ''), chu.created_at;
end;
$$;

revoke all on function public.list_mobile_support_users() from public;
grant execute on function public.list_mobile_support_users() to authenticated;
