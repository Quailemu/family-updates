-- Transitional safety: if an earlier local build used selected_family, convert it
-- to transparent directed_family targeting.

alter table public.office_practical_messages
  drop constraint if exists office_practical_messages_target_type_check;

update public.office_practical_messages
set target_type = 'directed_family'
where target_type = 'selected_family';

alter table public.office_practical_messages
  add constraint office_practical_messages_target_type_check
  check (target_type in ('all_family', 'directed_family', 'mobile'));

drop policy if exists "office_practical_messages_select_family" on public.office_practical_messages;

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

  execute format($policy$
    create policy "office_practical_messages_select_family"
    on public.office_practical_messages
    for select
    using (
      exists (
        select 1
        from public.%I fu
        join public.%I ra
          on ra.%I = fu.id
        join public.residents r on r.id = office_practical_messages.resident_id
        where fu.auth_user_id = auth.uid()
          and fu.active = true
          and ra.active = true
          and ra.resident_id = office_practical_messages.resident_id
          and fu.care_home_id = r.care_home_id
          and office_practical_messages.target_type in ('all_family', 'directed_family')
      )
    )
  $policy$, family_table, access_table, family_id_column);
end $$;
