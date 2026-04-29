-- Store Mobile / carer structured responses separately from the request row.

create table if not exists public.office_practical_mobile_responses (
  id uuid primary key default gen_random_uuid(),
  message_id uuid not null references public.office_practical_messages(id) on delete cascade,
  primary_choice text not null check (primary_choice in ('yes', 'no', 'maybe')),
  note text not null default '',
  selected_option_ids jsonb not null default '[]'::jsonb,
  response_status text not null default 'submitted',
  submitted_by uuid,
  submitted_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists idx_office_practical_mobile_responses_message
  on public.office_practical_mobile_responses (message_id);

alter table public.office_practical_mobile_responses enable row level security;

drop policy if exists "office_practical_mobile_responses_care_home" on public.office_practical_mobile_responses;

create policy "office_practical_mobile_responses_care_home"
on public.office_practical_mobile_responses
for all
using (
  exists (
    select 1
    from public.office_practical_messages opm
    join public.care_home_users chu on chu.care_home_id = opm.care_home_id
    where opm.id = office_practical_mobile_responses.message_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
)
with check (
  exists (
    select 1
    from public.office_practical_messages opm
    join public.care_home_users chu on chu.care_home_id = opm.care_home_id
    where opm.id = office_practical_mobile_responses.message_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);
