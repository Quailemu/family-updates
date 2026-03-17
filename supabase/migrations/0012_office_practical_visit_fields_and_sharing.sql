-- 0012_office_practical_visit_fields_and_sharing.sql
-- Adds optional visit-coordination fields and optional family-sharing flag.

alter table public.office_practical_messages
  add column if not exists context_type text not null default 'general';

alter table public.office_practical_messages
  add column if not exists requested_date text;

alter table public.office_practical_messages
  add column if not exists requested_time_window text;

alter table public.office_practical_messages
  drop constraint if exists office_practical_messages_context_type_check;

alter table public.office_practical_messages
  add constraint office_practical_messages_context_type_check
  check (context_type in ('general', 'visit'));

alter table public.office_practical_responses
  add column if not exists planned_visit_time text;

alter table public.office_practical_responses
  add column if not exists share_with_family boolean not null default false;

create index if not exists idx_office_practical_messages_context_type
  on public.office_practical_messages (context_type);

create index if not exists idx_office_practical_responses_share_with_family
  on public.office_practical_responses (share_with_family);

drop policy if exists "office_practical_responses_select_family" on public.office_practical_responses;
create policy "office_practical_responses_select_family"
on public.office_practical_responses
for select
using (
  (
    exists (
      select 1
      from public.family_contacts fc
      where fc.id = office_practical_responses.family_contact_id
        and fc.auth_user_id = auth.uid()
        and fc.active = true
    )
  )
  or
  (
    office_practical_responses.share_with_family = true
    and exists (
      select 1
      from public.office_practical_messages opm
      join public.family_contact_access fca
        on fca.resident_id = opm.resident_id
      join public.family_contacts fc
        on fc.id = fca.family_contact_id
      where opm.id = office_practical_responses.message_id
        and fc.auth_user_id = auth.uid()
        and fc.active = true
        and fca.active = true
    )
  )
);
