-- 0036_care_homes_communication_level.sql
-- Store how much of the communication system is switched on.

alter table public.care_homes
  add column if not exists communication_level smallint not null default 4;

alter table public.care_homes
  drop constraint if exists care_homes_communication_level_check;

alter table public.care_homes
  add constraint care_homes_communication_level_check
  check (communication_level between 1 and 5);
