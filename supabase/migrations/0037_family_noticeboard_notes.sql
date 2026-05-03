-- 0037_family_noticeboard_notes.sql
-- Transparent latest-only family noticeboard notes for practical coordination.

create table if not exists public.family_noticeboard_notes (
  id uuid primary key default gen_random_uuid(),
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  resident_id uuid not null references public.residents(id) on delete cascade,
  family_user_id uuid not null,
  note_body text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint family_noticeboard_notes_body_nonempty check (length(btrim(note_body)) > 0),
  constraint family_noticeboard_notes_one_per_family unique (resident_id, family_user_id)
);

do $$
begin
  if to_regclass('public.family_user') is not null then
    if not exists (
      select 1
      from pg_constraint
      where conname = 'family_noticeboard_notes_family_user_id_fkey'
    ) then
      alter table public.family_noticeboard_notes
        add constraint family_noticeboard_notes_family_user_id_fkey
        foreign key (family_user_id) references public.family_user(id) on delete cascade;
    end if;
  elsif to_regclass('public.family_contacts') is not null then
    if not exists (
      select 1
      from pg_constraint
      where conname = 'family_noticeboard_notes_family_contact_id_fkey'
    ) then
      alter table public.family_noticeboard_notes
        add constraint family_noticeboard_notes_family_contact_id_fkey
        foreign key (family_user_id) references public.family_contacts(id) on delete cascade;
    end if;
  end if;
end $$;

create index if not exists idx_family_noticeboard_notes_resident
  on public.family_noticeboard_notes (resident_id, updated_at desc);

create index if not exists idx_family_noticeboard_notes_care_home
  on public.family_noticeboard_notes (care_home_id);

create index if not exists idx_family_noticeboard_notes_family_user
  on public.family_noticeboard_notes (family_user_id);

alter table public.family_noticeboard_notes enable row level security;

drop policy if exists "family_noticeboard_notes_select_care_home" on public.family_noticeboard_notes;
create policy "family_noticeboard_notes_select_care_home"
on public.family_noticeboard_notes
for select
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.care_home_id = family_noticeboard_notes.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

drop policy if exists "family_noticeboard_notes_select_family_linked" on public.family_noticeboard_notes;
do $$
declare
  family_table text;
  access_table text;
  family_id_column text;
begin
  if to_regclass('public.family_user') is not null then
    family_table := 'family_user';
    access_table := 'resident_access';
    family_id_column := 'family_user_id';
  else
    family_table := 'family_contacts';
    access_table := 'family_contact_access';
    family_id_column := 'family_contact_id';
  end if;

  execute format($policy$
    create policy "family_noticeboard_notes_select_family_linked"
    on public.family_noticeboard_notes
    for select
    using (
      exists (
        select 1
        from public.%I fu
        join public.%I ra
          on ra.%I = fu.id
        join public.residents r
          on r.id = ra.resident_id
        where fu.auth_user_id = auth.uid()
          and fu.active = true
          and ra.active = true
          and r.active = true
          and ra.resident_id = family_noticeboard_notes.resident_id
          and fu.care_home_id = family_noticeboard_notes.care_home_id
          and r.care_home_id = family_noticeboard_notes.care_home_id
      )
    )
  $policy$, family_table, access_table, family_id_column);
end $$;

drop policy if exists "family_noticeboard_notes_insert_own" on public.family_noticeboard_notes;
do $$
declare
  family_table text;
  access_table text;
  family_id_column text;
begin
  if to_regclass('public.family_user') is not null then
    family_table := 'family_user';
    access_table := 'resident_access';
    family_id_column := 'family_user_id';
  else
    family_table := 'family_contacts';
    access_table := 'family_contact_access';
    family_id_column := 'family_contact_id';
  end if;

  execute format($policy$
    create policy "family_noticeboard_notes_insert_own"
    on public.family_noticeboard_notes
    for insert
    with check (
      exists (
        select 1
        from public.%I fu
        join public.%I ra
          on ra.%I = fu.id
        join public.residents r
          on r.id = ra.resident_id
        where fu.id = family_noticeboard_notes.family_user_id
          and fu.auth_user_id = auth.uid()
          and fu.active = true
          and ra.active = true
          and r.active = true
          and ra.resident_id = family_noticeboard_notes.resident_id
          and fu.care_home_id = family_noticeboard_notes.care_home_id
          and r.care_home_id = family_noticeboard_notes.care_home_id
      )
    )
  $policy$, family_table, access_table, family_id_column);
end $$;

drop policy if exists "family_noticeboard_notes_update_own" on public.family_noticeboard_notes;
do $$
declare
  family_table text;
  access_table text;
  family_id_column text;
begin
  if to_regclass('public.family_user') is not null then
    family_table := 'family_user';
    access_table := 'resident_access';
    family_id_column := 'family_user_id';
  else
    family_table := 'family_contacts';
    access_table := 'family_contact_access';
    family_id_column := 'family_contact_id';
  end if;

  execute format($policy$
    create policy "family_noticeboard_notes_update_own"
    on public.family_noticeboard_notes
    for update
    using (
      exists (
        select 1
        from public.%I fu
        join public.%I ra
          on ra.%I = fu.id
        where fu.id = family_noticeboard_notes.family_user_id
          and fu.auth_user_id = auth.uid()
          and fu.active = true
          and ra.active = true
          and ra.resident_id = family_noticeboard_notes.resident_id
      )
    )
    with check (
      exists (
        select 1
        from public.%I fu
        join public.%I ra
          on ra.%I = fu.id
        join public.residents r
          on r.id = ra.resident_id
        where fu.id = family_noticeboard_notes.family_user_id
          and fu.auth_user_id = auth.uid()
          and fu.active = true
          and ra.active = true
          and r.active = true
          and ra.resident_id = family_noticeboard_notes.resident_id
          and fu.care_home_id = family_noticeboard_notes.care_home_id
          and r.care_home_id = family_noticeboard_notes.care_home_id
      )
    )
  $policy$, family_table, access_table, family_id_column, family_table, access_table, family_id_column);
end $$;

drop policy if exists "family_noticeboard_notes_delete_own" on public.family_noticeboard_notes;
do $$
declare
  family_table text;
begin
  if to_regclass('public.family_user') is not null then
    family_table := 'family_user';
  else
    family_table := 'family_contacts';
  end if;

  execute format($policy$
    create policy "family_noticeboard_notes_delete_own"
    on public.family_noticeboard_notes
    for delete
    using (
      exists (
        select 1
        from public.%I fu
        where fu.id = family_noticeboard_notes.family_user_id
          and fu.auth_user_id = auth.uid()
          and fu.active = true
      )
    )
  $policy$, family_table);
end $$;

drop policy if exists "family_noticeboard_notes_delete_care_home" on public.family_noticeboard_notes;
create policy "family_noticeboard_notes_delete_care_home"
on public.family_noticeboard_notes
for delete
using (
  exists (
    select 1
    from public.care_home_users chu
    where chu.care_home_id = family_noticeboard_notes.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);
