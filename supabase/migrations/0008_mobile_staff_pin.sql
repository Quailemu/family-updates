-- 0008_mobile_staff_pin.sql
-- Adds per-staff mobile PIN support for Care Hub - Mobile.

alter table public.care_home_users
  add column if not exists mobile_pin_hash text;

alter table public.care_home_users
  add column if not exists mobile_pin_updated_at timestamptz;

create or replace function public.set_mobile_pin_hash(p_pin_hash text)
returns void
language plpgsql
security definer
set search_path = public
as $$
begin
  update public.care_home_users
  set
    mobile_pin_hash = p_pin_hash,
    mobile_pin_updated_at = now()
  where auth_user_id = auth.uid()
    and active = true;

  if not found then
    raise exception 'No active care_home_users row for auth user';
  end if;
end;
$$;

revoke all on function public.set_mobile_pin_hash(text) from public;
grant execute on function public.set_mobile_pin_hash(text) to authenticated;

