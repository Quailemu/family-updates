-- Minimal seed data for pilot (no auth.users inserts).
-- Replace placeholder UUIDs with real values before running.

-- Care home
insert into public.care_homes (id, name)
values ('<CARE_HOME_ID>', 'Care Home Pilot')
on conflict (id) do nothing;

-- Care home settings (one per care home)
insert into public.care_home_settings (care_home_id)
values ('<CARE_HOME_ID>')
on conflict (care_home_id) do nothing;

-- Resident
insert into public.residents (id, care_home_id, preferred_display_name, care_home_reference)
values ('<RESIDENT_ID>', '<CARE_HOME_ID>', 'Margaret', 'Room 25')
on conflict (id) do nothing;

-- Note:
-- Create auth.users separately in Supabase Auth, then link the shared care home login
-- using public.care_home_users with the real auth user UUID.
