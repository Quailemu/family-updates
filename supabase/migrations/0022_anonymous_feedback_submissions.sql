-- 0022_anonymous_feedback_submissions.sql
-- Stores anonymous public feedback questionnaire responses.

create table if not exists public.feedback_submissions (
  id uuid primary key default gen_random_uuid(),
  audience text not null check (audience in ('family', 'resident_supported', 'carer')),
  q1_score smallint not null check (q1_score between 1 and 5),
  q2_score smallint not null check (q2_score between 1 and 5),
  q3_score smallint not null check (q3_score between 1 and 5),
  comment text,
  created_at timestamptz not null default now()
);

alter table public.feedback_submissions
  alter column comment type text;

alter table public.feedback_submissions
  add constraint feedback_submissions_comment_len
  check (comment is null or char_length(comment) <= 500);

alter table public.feedback_submissions enable row level security;

drop policy if exists feedback_submissions_insert on public.feedback_submissions;
create policy feedback_submissions_insert
  on public.feedback_submissions
  for insert
  to anon, authenticated
  with check (true);
