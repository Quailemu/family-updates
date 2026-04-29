-- Allow practical structured requests to be sent either to all family members
-- or directed to one named family member while remaining visible to all linked family.

alter table public.office_practical_messages
  add column if not exists target_type text not null default 'all_family';

alter table public.office_practical_messages
  add column if not exists target_family_user_id uuid;

alter table public.office_practical_messages
  drop constraint if exists office_practical_messages_target_type_check;

alter table public.office_practical_messages
  add constraint office_practical_messages_target_type_check
  check (target_type in ('all_family', 'directed_family'));

create index if not exists idx_office_practical_messages_target
  on public.office_practical_messages (resident_id, status, target_type, target_family_user_id);

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
