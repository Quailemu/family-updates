-- 0024_care_homes_transcript_policy_mode.sql
-- Add transcript playback policy control at care-home level.

alter table public.care_homes
  add column if not exists transcript_policy_mode text not null default 'assist';

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'care_homes_transcript_policy_mode_check'
      and conrelid = 'public.care_homes'::regclass
  ) then
    alter table public.care_homes
      add constraint care_homes_transcript_policy_mode_check
      check (transcript_policy_mode in ('off', 'assist', 'precheck'));
  end if;
end $$;

