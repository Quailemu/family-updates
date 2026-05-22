-- Allow a deliberate "No response" structured reply.

alter table if exists public.office_practical_responses
  drop constraint if exists office_practical_responses_primary_choice_check;

alter table if exists public.office_practical_responses
  add constraint office_practical_responses_primary_choice_check
  check (primary_choice in ('no_response', 'yes', 'no', 'maybe'));

alter table if exists public.office_practical_mobile_responses
  drop constraint if exists office_practical_mobile_responses_primary_choice_check;

alter table if exists public.office_practical_mobile_responses
  add constraint office_practical_mobile_responses_primary_choice_check
  check (primary_choice in ('no_response', 'yes', 'no', 'maybe'));
