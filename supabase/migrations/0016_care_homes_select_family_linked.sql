-- Allow Family users to read their linked care-home row for name/banner rendering.

drop policy if exists "care_homes_select_family_linked" on public.care_homes;
create policy "care_homes_select_family_linked"
on public.care_homes
for select
using (
  care_homes.active = true
  and exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r
      on r.id = fca.resident_id
    where fc.auth_user_id = auth.uid()
      and fc.active = true
      and fca.active = true
      and r.active = true
      and fc.care_home_id = care_homes.id
      and r.care_home_id = care_homes.id
  )
);
