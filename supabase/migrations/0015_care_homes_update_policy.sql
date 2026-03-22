-- Allow active care-home users to update their own care-home profile fields,
-- including optional branding banner content.

drop policy if exists "care_homes_update_own" on public.care_homes;
create policy "care_homes_update_own"
on public.care_homes
for update
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.care_home_id = care_homes.id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
)
with check (
  exists (
    select 1
    from public.care_home_users chu
    where chu.care_home_id = care_homes.id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

