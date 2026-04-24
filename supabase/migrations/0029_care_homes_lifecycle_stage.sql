-- 0029_care_homes_lifecycle_stage.sql
-- Add lifecycle stage (1..5) to support staged system configuration.

alter table public.care_homes
  add column if not exists lifecycle_stage smallint not null default 4;

alter table public.care_homes
  drop constraint if exists care_homes_lifecycle_stage_check;

alter table public.care_homes
  add constraint care_homes_lifecycle_stage_check
  check (lifecycle_stage between 1 and 5);

