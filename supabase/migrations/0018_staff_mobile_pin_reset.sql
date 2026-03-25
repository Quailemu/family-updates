-- 0018_staff_mobile_pin_reset.sql
-- Office-only helper RPCs to manage per-staff Mobile PIN reset within a care home.

create or replace function public.list_care_home_staff_mobile_pin_status()
returns table (
  auth_user_id uuid,
  staff_email text,
  active boolean,
  mobile_pin_set boolean,
  mobile_pin_updated_at timestamptz
)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_care_home_id uuid;
begin
  select chu.care_home_id
  into v_care_home_id
  from public.care_home_users chu
  where chu.auth_user_id = auth.uid()
    and chu.active = true
  limit 1;

  if v_care_home_id is null then
    raise exception 'No active care_home_users row for auth user';
  end if;

  return query
    select
      chu.auth_user_id,
      coalesce(au.email, '')::text as staff_email,
      chu.active,
      (chu.mobile_pin_hash is not null) as mobile_pin_set,
      chu.mobile_pin_updated_at
    from public.care_home_users chu
    left join auth.users au
      on au.id = chu.auth_user_id
    where chu.care_home_id = v_care_home_id
    order by coalesce(au.email, ''), chu.created_at;
end;
$$;

revoke all on function public.list_care_home_staff_mobile_pin_status() from public;
grant execute on function public.list_care_home_staff_mobile_pin_status() to authenticated;

create or replace function public.reset_staff_mobile_pin(p_staff_auth_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_care_home_id uuid;
begin
  if p_staff_auth_user_id is null then
    raise exception 'Staff auth user id is required';
  end if;

  select chu.care_home_id
  into v_care_home_id
  from public.care_home_users chu
  where chu.auth_user_id = auth.uid()
    and chu.active = true
  limit 1;

  if v_care_home_id is null then
    raise exception 'No active care_home_users row for auth user';
  end if;

  update public.care_home_users
  set
    mobile_pin_hash = null,
    mobile_pin_updated_at = null
  where care_home_id = v_care_home_id
    and auth_user_id = p_staff_auth_user_id
    and active = true;

  if not found then
    raise exception 'Target staff account not found in this care home';
  end if;
end;
$$;

revoke all on function public.reset_staff_mobile_pin(uuid) from public;
grant execute on function public.reset_staff_mobile_pin(uuid) to authenticated;

