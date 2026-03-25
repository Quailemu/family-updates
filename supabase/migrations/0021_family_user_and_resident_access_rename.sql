-- Terminology alignment:
-- - person/account: family_user
-- - access mapping: resident_access

do $$
begin
  if exists (
    select 1
    from information_schema.tables
    where table_schema = 'public' and table_name = 'family_contacts'
  ) and not exists (
    select 1
    from information_schema.tables
    where table_schema = 'public' and table_name = 'family_user'
  ) then
    alter table public.family_contacts rename to family_user;
  end if;
end $$;

do $$
begin
  if exists (
    select 1
    from information_schema.tables
    where table_schema = 'public' and table_name = 'family_contact_access'
  ) and not exists (
    select 1
    from information_schema.tables
    where table_schema = 'public' and table_name = 'resident_access'
  ) then
    alter table public.family_contact_access rename to resident_access;
  end if;
end $$;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'resident_access'
      and column_name = 'family_contact_id'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'resident_access'
      and column_name = 'family_user_id'
  ) then
    alter table public.resident_access rename column family_contact_id to family_user_id;
  end if;
end $$;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'office_practical_responses'
      and column_name = 'family_contact_id'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'office_practical_responses'
      and column_name = 'family_user_id'
  ) then
    alter table public.office_practical_responses rename column family_contact_id to family_user_id;
  end if;
end $$;

do $$
begin
  if exists (
    select 1
    from pg_constraint
    where conname = 'family_contact_access_resident_contact_key'
  ) then
    alter table public.resident_access
      rename constraint family_contact_access_resident_contact_key
      to resident_access_resident_family_user_key;
  end if;
end $$;

do $$
begin
  if exists (
    select 1
    from pg_class
    where relname = 'idx_family_contact_access_resident_id'
  ) then
    alter index public.idx_family_contact_access_resident_id rename to idx_resident_access_resident_id;
  end if;

  if exists (
    select 1
    from pg_class
    where relname = 'idx_family_contact_access_family_contact_id'
  ) then
    alter index public.idx_family_contact_access_family_contact_id rename to idx_resident_access_family_user_id;
  end if;
end $$;
