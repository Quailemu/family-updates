-- 0011_office_practical_structured_replies.sql
-- Adds a lightweight Office<->Family structured response path for non-urgent practical messages.

create table if not exists public.office_practical_messages (
  id uuid primary key default gen_random_uuid(),
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  resident_id uuid not null references public.residents(id) on delete cascade,
  title text not null,
  body text not null,
  allow_note boolean not null default true,
  response_enabled boolean not null default true,
  status text not null default 'open',
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  closed_at timestamptz
);

create table if not exists public.office_practical_message_options (
  id uuid primary key default gen_random_uuid(),
  message_id uuid not null references public.office_practical_messages(id) on delete cascade,
  option_label text not null,
  sort_order integer not null default 1,
  created_at timestamptz not null default now()
);

create table if not exists public.office_practical_responses (
  id uuid primary key default gen_random_uuid(),
  message_id uuid not null references public.office_practical_messages(id) on delete cascade,
  family_contact_id uuid not null references public.family_contacts(id) on delete cascade,
  primary_choice text not null,
  note text,
  response_status text not null default 'submitted',
  submitted_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.office_practical_response_checks (
  response_id uuid not null references public.office_practical_responses(id) on delete cascade,
  option_id uuid not null references public.office_practical_message_options(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (response_id, option_id)
);

alter table public.office_practical_messages
  drop constraint if exists office_practical_messages_status_check;
alter table public.office_practical_messages
  add constraint office_practical_messages_status_check
  check (status in ('open', 'closed'));

alter table public.office_practical_responses
  drop constraint if exists office_practical_responses_primary_choice_check;
alter table public.office_practical_responses
  add constraint office_practical_responses_primary_choice_check
  check (primary_choice in ('yes', 'no', 'maybe'));

alter table public.office_practical_responses
  drop constraint if exists office_practical_responses_status_check;
alter table public.office_practical_responses
  add constraint office_practical_responses_status_check
  check (response_status in ('submitted'));

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'office_practical_responses_one_per_contact'
  ) then
    alter table public.office_practical_responses
      add constraint office_practical_responses_one_per_contact
      unique (message_id, family_contact_id);
  end if;
end $$;

create index if not exists idx_office_practical_messages_care_home
  on public.office_practical_messages (care_home_id);
create index if not exists idx_office_practical_messages_resident
  on public.office_practical_messages (resident_id);
create index if not exists idx_office_practical_messages_status
  on public.office_practical_messages (status);
create index if not exists idx_office_practical_options_message
  on public.office_practical_message_options (message_id);
create index if not exists idx_office_practical_responses_message
  on public.office_practical_responses (message_id);
create index if not exists idx_office_practical_responses_contact
  on public.office_practical_responses (family_contact_id);

alter table public.office_practical_messages enable row level security;
alter table public.office_practical_message_options enable row level security;
alter table public.office_practical_responses enable row level security;
alter table public.office_practical_response_checks enable row level security;

drop policy if exists "office_practical_messages_select_care_home" on public.office_practical_messages;
create policy "office_practical_messages_select_care_home"
on public.office_practical_messages
for select
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = office_practical_messages.care_home_id
      and chu.active = true
  )
);

drop policy if exists "office_practical_messages_write_care_home" on public.office_practical_messages;
create policy "office_practical_messages_write_care_home"
on public.office_practical_messages
for all
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = office_practical_messages.care_home_id
      and chu.active = true
  )
)
with check (
  exists (
    select 1
    from public.care_home_users chu
    where chu.auth_user_id = auth.uid()
      and chu.care_home_id = office_practical_messages.care_home_id
      and chu.active = true
  )
);

drop policy if exists "office_practical_messages_select_family" on public.office_practical_messages;
create policy "office_practical_messages_select_family"
on public.office_practical_messages
for select
using (
  exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r on r.id = office_practical_messages.resident_id
    where fc.auth_user_id = auth.uid()
      and fc.active = true
      and fca.active = true
      and fca.resident_id = office_practical_messages.resident_id
      and fc.care_home_id = r.care_home_id
  )
);

drop policy if exists "office_practical_options_select_care_home" on public.office_practical_message_options;
create policy "office_practical_options_select_care_home"
on public.office_practical_message_options
for select
using (
  exists (
    select 1
    from public.office_practical_messages opm
    join public.care_home_users chu on chu.care_home_id = opm.care_home_id
    where opm.id = office_practical_message_options.message_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "office_practical_options_write_care_home" on public.office_practical_message_options;
create policy "office_practical_options_write_care_home"
on public.office_practical_message_options
for all
using (
  exists (
    select 1
    from public.office_practical_messages opm
    join public.care_home_users chu on chu.care_home_id = opm.care_home_id
    where opm.id = office_practical_message_options.message_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
)
with check (
  exists (
    select 1
    from public.office_practical_messages opm
    join public.care_home_users chu on chu.care_home_id = opm.care_home_id
    where opm.id = office_practical_message_options.message_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "office_practical_options_select_family" on public.office_practical_message_options;
create policy "office_practical_options_select_family"
on public.office_practical_message_options
for select
using (
  exists (
    select 1
    from public.office_practical_messages opm
    join public.family_contact_access fca on fca.resident_id = opm.resident_id
    join public.family_contacts fc on fc.id = fca.family_contact_id
    where opm.id = office_practical_message_options.message_id
      and fc.auth_user_id = auth.uid()
      and fc.active = true
      and fca.active = true
  )
);

drop policy if exists "office_practical_responses_select_care_home" on public.office_practical_responses;
create policy "office_practical_responses_select_care_home"
on public.office_practical_responses
for select
using (
  exists (
    select 1
    from public.office_practical_messages opm
    join public.care_home_users chu on chu.care_home_id = opm.care_home_id
    where opm.id = office_practical_responses.message_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "office_practical_responses_select_family" on public.office_practical_responses;
create policy "office_practical_responses_select_family"
on public.office_practical_responses
for select
using (
  exists (
    select 1
    from public.family_contacts fc
    where fc.id = office_practical_responses.family_contact_id
      and fc.auth_user_id = auth.uid()
      and fc.active = true
  )
);

drop policy if exists "office_practical_responses_write_family" on public.office_practical_responses;
create policy "office_practical_responses_write_family"
on public.office_practical_responses
for all
using (
  exists (
    select 1
    from public.family_contacts fc
    join public.office_practical_messages opm on opm.id = office_practical_responses.message_id
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
      and fca.resident_id = opm.resident_id
    where fc.id = office_practical_responses.family_contact_id
      and fc.auth_user_id = auth.uid()
      and fc.active = true
      and fca.active = true
      and opm.status = 'open'
      and opm.response_enabled = true
  )
)
with check (
  exists (
    select 1
    from public.family_contacts fc
    join public.office_practical_messages opm on opm.id = office_practical_responses.message_id
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
      and fca.resident_id = opm.resident_id
    where fc.id = office_practical_responses.family_contact_id
      and fc.auth_user_id = auth.uid()
      and fc.active = true
      and fca.active = true
      and opm.status = 'open'
      and opm.response_enabled = true
  )
);

drop policy if exists "office_practical_checks_select_care_home" on public.office_practical_response_checks;
create policy "office_practical_checks_select_care_home"
on public.office_practical_response_checks
for select
using (
  exists (
    select 1
    from public.office_practical_responses opr
    join public.office_practical_messages opm on opm.id = opr.message_id
    join public.care_home_users chu on chu.care_home_id = opm.care_home_id
    where opr.id = office_practical_response_checks.response_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "office_practical_checks_select_family" on public.office_practical_response_checks;
create policy "office_practical_checks_select_family"
on public.office_practical_response_checks
for select
using (
  exists (
    select 1
    from public.office_practical_responses opr
    join public.family_contacts fc on fc.id = opr.family_contact_id
    where opr.id = office_practical_response_checks.response_id
      and fc.auth_user_id = auth.uid()
      and fc.active = true
  )
);

drop policy if exists "office_practical_checks_write_family" on public.office_practical_response_checks;
create policy "office_practical_checks_write_family"
on public.office_practical_response_checks
for all
using (
  exists (
    select 1
    from public.office_practical_responses opr
    join public.office_practical_messages opm on opm.id = opr.message_id
    join public.family_contacts fc on fc.id = opr.family_contact_id
    where opr.id = office_practical_response_checks.response_id
      and fc.auth_user_id = auth.uid()
      and fc.active = true
      and opm.status = 'open'
      and opm.response_enabled = true
  )
)
with check (
  exists (
    select 1
    from public.office_practical_responses opr
    join public.office_practical_messages opm on opm.id = opr.message_id
    join public.family_contacts fc on fc.id = opr.family_contact_id
    join public.office_practical_message_options opmo on opmo.id = office_practical_response_checks.option_id
    where opr.id = office_practical_response_checks.response_id
      and opmo.message_id = opr.message_id
      and fc.auth_user_id = auth.uid()
      and fc.active = true
      and opm.status = 'open'
      and opm.response_enabled = true
  )
);
