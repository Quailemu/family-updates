create table if not exists public.one_message_public_tests (
    id uuid primary key default gen_random_uuid(),
    test_id text not null unique,
    a_key text not null,
    b_key text not null,
    a_message text not null default '',
    b_message text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    expires_at timestamptz not null default (now() + interval '24 hours'),
    constraint one_message_public_tests_a_message_length check (char_length(a_message) <= 220),
    constraint one_message_public_tests_b_message_length check (char_length(b_message) <= 220)
);

create index if not exists idx_one_message_public_tests_test_id
    on public.one_message_public_tests (test_id);

create index if not exists idx_one_message_public_tests_expires_at
    on public.one_message_public_tests (expires_at);

alter table public.one_message_public_tests enable row level security;

revoke all on table public.one_message_public_tests from anon, authenticated;
grant select, insert on table public.one_message_public_tests to anon, authenticated;
grant update (a_message, b_message, updated_at) on table public.one_message_public_tests to anon, authenticated;

drop policy if exists one_message_public_tests_insert_public on public.one_message_public_tests;
create policy one_message_public_tests_insert_public
    on public.one_message_public_tests
    for insert
    to anon, authenticated
    with check (
        expires_at > now()
        and expires_at <= now() + interval '2 days'
        and char_length(a_message) <= 220
        and char_length(b_message) <= 220
    );

drop policy if exists one_message_public_tests_select_public on public.one_message_public_tests;
create policy one_message_public_tests_select_public
    on public.one_message_public_tests
    for select
    to anon, authenticated
    using (expires_at > now());

drop policy if exists one_message_public_tests_update_public on public.one_message_public_tests;
create policy one_message_public_tests_update_public
    on public.one_message_public_tests
    for update
    to anon, authenticated
    using (expires_at > now())
    with check (
        expires_at > now()
        and char_length(a_message) <= 220
        and char_length(b_message) <= 220
    );
