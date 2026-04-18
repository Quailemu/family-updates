-- Normalize operating_mode values to setup-context terms.
-- Existing values from earlier rollout:
--   care_home  -> care_organisation
--   family_led -> personal_use

update public.care_homes
set operating_mode = 'care_organisation'
where operating_mode = 'care_home';

update public.care_homes
set operating_mode = 'personal_use'
where operating_mode = 'family_led';

alter table public.care_homes
  alter column operating_mode set default 'care_organisation';

alter table public.care_homes
  drop constraint if exists care_homes_operating_mode_check;

alter table public.care_homes
  add constraint care_homes_operating_mode_check
  check (operating_mode in ('care_organisation', 'personal_use'));
