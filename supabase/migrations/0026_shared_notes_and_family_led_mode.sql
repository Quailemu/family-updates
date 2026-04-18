-- Lightweight shared Notes timeline + family-led mode labels.
-- Keeps existing app architecture and adds optional, low-pressure note sharing.

alter table public.care_homes
  add column if not exists operating_mode text not null default 'care_home',
  add column if not exists main_contact_name text;

alter table public.care_homes
  drop constraint if exists care_homes_operating_mode_check;

alter table public.care_homes
  add constraint care_homes_operating_mode_check
  check (operating_mode in ('care_home', 'family_led'));

create table if not exists public.shared_notes (
  id uuid primary key default gen_random_uuid(),
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  resident_id uuid not null references public.residents(id) on delete cascade,
  author_user_id uuid not null references auth.users(id) on delete restrict,
  author_name text not null default 'User',
  note_body text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  edited_at timestamptz
);

alter table public.shared_notes
  drop constraint if exists shared_notes_note_body_nonempty;

alter table public.shared_notes
  add constraint shared_notes_note_body_nonempty
  check (length(btrim(note_body)) > 0);

create index if not exists idx_shared_notes_resident_created
  on public.shared_notes (resident_id, created_at desc);

create index if not exists idx_shared_notes_care_home_created
  on public.shared_notes (care_home_id, created_at desc);

create index if not exists idx_shared_notes_author_user
  on public.shared_notes (author_user_id);

alter table public.shared_notes enable row level security;

drop policy if exists "shared_notes_select_care_home" on public.shared_notes;
create policy "shared_notes_select_care_home"
on public.shared_notes
for select
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.care_home_id = shared_notes.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "shared_notes_select_family_linked" on public.shared_notes;
create policy "shared_notes_select_family_linked"
on public.shared_notes
for select
using (
  exists (
    select 1
    from public.family_user fu
    join public.resident_access ra
      on ra.family_user_id = fu.id
    join public.residents r
      on r.id = ra.resident_id
    where fu.auth_user_id = auth.uid()
      and fu.active = true
      and ra.active = true
      and r.active = true
      and ra.resident_id = shared_notes.resident_id
      and fu.care_home_id = shared_notes.care_home_id
      and r.care_home_id = shared_notes.care_home_id
  )
);

drop policy if exists "shared_notes_insert_care_home" on public.shared_notes;
create policy "shared_notes_insert_care_home"
on public.shared_notes
for insert
with check (
  author_user_id = auth.uid()
  and exists (
    select 1
    from public.care_home_users chu
    where chu.care_home_id = shared_notes.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "shared_notes_insert_family_linked" on public.shared_notes;
create policy "shared_notes_insert_family_linked"
on public.shared_notes
for insert
with check (
  author_user_id = auth.uid()
  and exists (
    select 1
    from public.family_user fu
    join public.resident_access ra
      on ra.family_user_id = fu.id
    join public.residents r
      on r.id = ra.resident_id
    where fu.auth_user_id = auth.uid()
      and fu.active = true
      and ra.active = true
      and r.active = true
      and ra.resident_id = shared_notes.resident_id
      and fu.care_home_id = shared_notes.care_home_id
      and r.care_home_id = shared_notes.care_home_id
  )
);

drop policy if exists "shared_notes_update_own" on public.shared_notes;
create policy "shared_notes_update_own"
on public.shared_notes
for update
using (
  author_user_id = auth.uid()
  and (
    exists (
      select 1
      from public.care_home_users chu
      where chu.care_home_id = shared_notes.care_home_id
        and chu.auth_user_id = auth.uid()
        and chu.active = true
    )
    or exists (
      select 1
      from public.family_user fu
      join public.resident_access ra
        on ra.family_user_id = fu.id
      join public.residents r
        on r.id = ra.resident_id
      where fu.auth_user_id = auth.uid()
        and fu.active = true
        and ra.active = true
        and r.active = true
        and ra.resident_id = shared_notes.resident_id
        and fu.care_home_id = shared_notes.care_home_id
        and r.care_home_id = shared_notes.care_home_id
    )
  )
)
with check (
  author_user_id = auth.uid()
);
