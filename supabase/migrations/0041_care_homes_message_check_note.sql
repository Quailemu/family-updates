-- 0041_care_homes_message_check_note.sql
-- Optional Family Office note for when/how often the organiser expects to check non-urgent messages.

alter table public.care_homes
  add column if not exists message_check_note text;
