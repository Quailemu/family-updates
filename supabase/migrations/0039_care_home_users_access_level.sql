-- 0039_care_home_users_access_level.sql
-- Split Care Hub staff access so carers can be Mobile-only.

alter table public.care_home_users
  add column if not exists care_access_level text not null default 'office';

alter table public.care_home_users
  drop constraint if exists care_home_users_care_access_level_check;

alter table public.care_home_users
  add constraint care_home_users_care_access_level_check
  check (care_access_level in ('office', 'mobile'));

update public.care_home_users
set care_access_level = 'office'
where care_access_level is null
   or care_access_level not in ('office', 'mobile');
