-- 0025_backfill_family_relationship_labels.sql
-- Backfill known family relationship labels where records were saved with blank/generic values.

do $$
begin
  if exists (
    select 1
    from information_schema.tables
    where table_schema = 'public' and table_name = 'family_user'
  ) then
    update public.family_user
    set relationship = 'daughter'
    where lower(trim(display_name)) = 'polly smith'
      and (
        relationship is null
        or trim(relationship) = ''
        or lower(trim(relationship)) = 'family member'
      );

    update public.family_user
    set relationship = 'cousin'
    where lower(trim(display_name)) = 'carol singer'
      and (
        relationship is null
        or trim(relationship) = ''
        or lower(trim(relationship)) = 'family member'
      );
  elsif exists (
    select 1
    from information_schema.tables
    where table_schema = 'public' and table_name = 'family_contacts'
  ) then
    update public.family_contacts
    set relationship = 'daughter'
    where lower(trim(display_name)) = 'polly smith'
      and (
        relationship is null
        or trim(relationship) = ''
        or lower(trim(relationship)) = 'family member'
      );

    update public.family_contacts
    set relationship = 'cousin'
    where lower(trim(display_name)) = 'carol singer'
      and (
        relationship is null
        or trim(relationship) = ''
        or lower(trim(relationship)) = 'family member'
      );
  end if;
end $$;

