-- 0035_messages_text_updates.sql
-- Allow update channels to hold a current text update as an alternative to audio.

alter table public.messages
  add column if not exists message_kind text not null default 'voice',
  add column if not exists text_title text,
  add column if not exists text_body text;

alter table public.messages
  drop constraint if exists messages_message_kind_check;

alter table public.messages
  add constraint messages_message_kind_check
  check (message_kind in ('voice', 'text'));
