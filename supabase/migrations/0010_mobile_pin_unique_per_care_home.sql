-- 0010_mobile_pin_unique_per_care_home.sql
-- Enforce unique Mobile PIN hash per care home (active staff rows only).
-- Existing legacy v1 hashes are cleared so users set a new v2 PIN on next login.

update public.care_home_users
set
  mobile_pin_hash = null,
  mobile_pin_updated_at = null
where mobile_pin_hash is not null
  and mobile_pin_hash not like 'v2:%';

create unique index if not exists idx_care_home_users_unique_mobile_pin_per_home
  on public.care_home_users (care_home_id, mobile_pin_hash)
  where active = true
    and mobile_pin_hash is not null;
