-- Store durable object paths for audio payloads so delivery can move from
-- base64-in-row to Supabase Storage objects.

alter table public.messages
  add column if not exists audio_object_path text;

alter table public.messages
  add column if not exists audio_source text;

update public.messages
set audio_source = 'inline'
where audio_source is null;

alter table public.messages
  alter column audio_source set default 'inline';

create index if not exists idx_messages_audio_object_path
  on public.messages (audio_object_path)
  where audio_object_path is not null;

alter table public.messages
  drop constraint if exists messages_audio_source_check;

alter table public.messages
  add constraint messages_audio_source_check
  check (audio_source in ('inline', 'storage'));
