-- 0023_messages_transcript_columns.sql
-- Optional per-message transcript metadata stored on the current message row.
-- Replacement model remains unchanged: new message upsert overwrites these fields.

alter table public.messages
  add column if not exists transcript_text text,
  add column if not exists transcript_status text,
  add column if not exists transcript_model text,
  add column if not exists transcript_generated_at timestamptz;

