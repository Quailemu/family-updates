-- 0030_four_active_lifecycle_stages.sql
-- Convert lifecycle_stage from the earlier five-stage model to four active app stages.
-- Planning & Organisation is now preparation guidance, not a selectable app stage.
--
-- Old 1 Planning & Organisation                 -> New 1 Maintaining Independence at Home
-- Old 2 Maintaining Independence at Home        -> New 1 Maintaining Independence at Home
-- Old 3 Family-Supported Coordination at Home   -> New 2 Family-Supported Coordination at Home
-- Old 4 Carer + Family at Home                  -> New 3 Carer + Family at Home
-- Old 5 Care Home + Family Coordination         -> New 4 Care Home + Family Coordination

alter table public.care_homes
  drop constraint if exists care_homes_lifecycle_stage_check;

update public.care_homes
set lifecycle_stage = case
  when lifecycle_stage <= 2 then 1
  when lifecycle_stage = 3 then 2
  when lifecycle_stage = 4 then 3
  else 4
end;

alter table public.care_homes
  alter column lifecycle_stage set default 3;

alter table public.care_homes
  add constraint care_homes_lifecycle_stage_check
  check (lifecycle_stage between 1 and 4);
