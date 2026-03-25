-- Per-care-home idle sign-out setting for Care Hub – Office and Care Hub – Mobile.

alter table public.care_homes
  add column if not exists care_hub_idle_timeout_seconds integer;

alter table public.care_homes
  alter column care_hub_idle_timeout_seconds set default 3600;

update public.care_homes
set care_hub_idle_timeout_seconds = 3600
where care_hub_idle_timeout_seconds is null;

alter table public.care_homes
  drop constraint if exists care_homes_idle_timeout_allowed;

alter table public.care_homes
  add constraint care_homes_idle_timeout_allowed
  check (care_hub_idle_timeout_seconds in (1800, 3600, 5400, 7200));
