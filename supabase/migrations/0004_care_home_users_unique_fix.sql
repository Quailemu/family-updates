-- 0004_care_home_users_unique_fix.sql
-- Allow multiple staff users per care home.

do $$
begin
  if exists (
    select 1
    from pg_constraint
    where conname = 'care_home_users_care_home_id_key'
  ) then
    alter table public.care_home_users
      drop constraint care_home_users_care_home_id_key;
  end if;
end $$;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'care_home_users_care_home_auth_user_key'
  ) then
    alter table public.care_home_users
      add constraint care_home_users_care_home_auth_user_key
      unique (care_home_id, auth_user_id);
  end if;
end $$;
