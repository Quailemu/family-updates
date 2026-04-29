-- Add Office -> Mobile practical requests with one current Mobile structured response.

alter table public.office_practical_messages
  drop constraint if exists office_practical_messages_target_type_check;

alter table public.office_practical_messages
  add constraint office_practical_messages_target_type_check
  check (target_type in ('all_family', 'directed_family', 'mobile'));

alter table public.office_practical_messages
  add column if not exists mobile_response_choice text;

alter table public.office_practical_messages
  add column if not exists mobile_response_note text;

alter table public.office_practical_messages
  add column if not exists mobile_response_option_ids jsonb not null default '[]'::jsonb;

alter table public.office_practical_messages
  add column if not exists mobile_response_status text;

alter table public.office_practical_messages
  add column if not exists mobile_response_updated_by uuid;

alter table public.office_practical_messages
  add column if not exists mobile_response_updated_at timestamptz;

alter table public.office_practical_messages
  drop constraint if exists office_practical_messages_mobile_response_choice_check;

alter table public.office_practical_messages
  add constraint office_practical_messages_mobile_response_choice_check
  check (mobile_response_choice is null or mobile_response_choice in ('yes', 'no', 'maybe'));
