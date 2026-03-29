![logo](../../assets/logo.png)

# Schema and RLS design

## Purpose

This document defines the Supabase schema and row-level security (RLS) rules for voicemessagecare.com. The goal is to enforce the documented scope in the database so the platform cannot exceed its intended role.

## Overview of scope enforcement

- One shared care home login per care home, mapped to a single care_home_users row.
- Family/friends use individual Supabase Auth accounts.
- Each message channel keeps only the latest message per resident/contact pair.
- RLS prevents family users from seeing any other family’s data.
- RLS allows care home users to see and manage all data within their care home.
- Storage is not directly accessible to clients; audio playback uses short-lived signed URLs.
- Lightweight security events are logged without content or email data.
- No review, moderation, or safeguarding features are included.
- Care home operational settings are stored per care home only.

## Tables

### 1) care_homes

Purpose: One row per care home (operator/data controller).

Fields (minimum):
- id (uuid, pk)
- name (text)
- created_at (timestamptz)
- active (boolean)

Notes:
- No care, medical, or staff identity data is stored here.

### 2) care_home_users

Purpose: Map the shared care home login (Supabase Auth user) to a care home.

Fields (minimum):
- id (uuid, pk)
- care_home_id (uuid, fk -> care_homes.id)
- auth_user_id (uuid, fk -> auth.users.id, unique)
- created_at (timestamptz)
- active (boolean)

Constraints:
- unique (care_home_id) to enforce one shared login per care home.

Notes:
- This table represents the shared login only; no staff profiles exist.

### 3) residents

Purpose: Minimal resident identifiers controlled by the care home.

Fields (minimum):
- id (uuid, pk)
- care_home_id (uuid, fk -> care_homes.id)
- preferred_display_name (text)
- care_home_reference (text)
- created_at (timestamptz)
- active (boolean)

Notes:
- No medical or care assessment fields are included.

### 4) family_contacts

Purpose: Profile for family/friend Supabase Auth users, managed by the care home.

Fields (minimum):
- id (uuid, pk)
- care_home_id (uuid, fk -> care_homes.id)
- auth_user_id (uuid, fk -> auth.users.id, unique)
- email (text)
- display_name (text)
- created_at (timestamptz)
- active (boolean)

Notes:
- Email is stored to support access management by the care home.

### 5) family_contact_access

Purpose: Link family contacts to residents they can message.

Fields (minimum):
- id (uuid, pk)
- resident_id (uuid, fk -> residents.id)
- family_contact_id (uuid, fk -> family_contacts.id)
- created_at (timestamptz)
- active (boolean)

Constraints:
- unique (resident_id, family_contact_id)

Notes:
- This table exists to keep access control explicit and auditable without adding new features.

### 6) messages

Purpose: Store the latest voice message per channel for each resident/contact pair.

Fields (minimum):
- id (uuid, pk)
- resident_id (uuid, fk -> residents.id)
- contact_user_id (uuid, fk -> auth.users.id) -- family contact auth user
- direction (text, enum: 'to_resident', 'from_resident')
- audio_storage_path (text)
- audio_mime_type (text)
- audio_bytes (integer)
- recorded_at (timestamptz)
- created_at (timestamptz)

Constraints (critical):
- unique (resident_id, contact_user_id, direction)

Notes:
- No history is stored. New messages overwrite previous ones using an upsert.
- No content analysis, moderation flags, or review fields are included.

### 7) security_events

Purpose: Minimal security event log for operational auditing without content or email data.

Fields (minimum):
- id (uuid, pk)
- care_home_id (uuid, fk -> care_homes.id)
- actor_user_id (uuid, fk -> auth.users.id, nullable)
- actor_role (text) -- e.g., 'care_home', 'family', 'system'
- event_type (text) -- short code, e.g., 'login', 'lock', 'message_recorded'
- resident_id (uuid, fk -> residents.id, nullable)
- created_at (timestamptz)

Notes:
- No message content, audio, or email addresses are stored here.
- This table is write-only for server-side components (no client insert).

### 8) resident_contact_playback_state

Purpose: Persist unread/playback state per resident-contact channel so queue behavior is deterministic across sessions.

Fields (minimum):
- resident_id (uuid, fk -> residents.id)
- care_home_id (uuid, fk -> care_homes.id)
- contact_user_id (uuid, fk -> auth.users.id)
- last_played_recorded_at (timestamptz)
- updated_at (timestamptz)

Constraints:
- primary key (resident_id, contact_user_id)

Notes:
- Stores playback state only; no message content is stored.
- Supports unread tally behavior where only newly recorded contact messages remain unread after prior playback.

### 9) care_home_settings

Purpose: Operational security configuration per care home.

Fields (minimum):
- care_home_id (uuid, pk, fk -> care_homes.id)
- quick_lock_enabled (boolean)
- quick_lock_timeout_minutes (integer)
- desk_warning_minutes (integer)
- updated_at (timestamptz)

Notes:
- Stores operational configuration only (no staff identities, no audit data).
- Supports the shared operator login model with sleep-at-night security controls.

## RLS rules per table

The policies below use two helper checks:

- `is_care_home_user(care_home_id)`:
  true if a row exists in care_home_users with auth_user_id = auth.uid(), care_home_id = care_home_id, and active = true.
- `is_family_user()`:
  true if a row exists in family_contacts with auth_user_id = auth.uid() and active = true.

Short comments explain why each rule exists.

### care_homes

Policies:
- select: care home users can read their own care_home row (active users only).
  - Reason: allows operator to see their own organisation details.
- insert/update/delete: restricted to administrative setup (not exposed to clients).
  - Reason: prevents scope drift and accidental cross-home changes.

### care_home_users

Policies:
- select: allowed where auth_user_id = auth.uid() and active = true.
  - Reason: shared login can see its own mapping to a care home.
- insert/update/delete: restricted to administrative setup.
  - Reason: prevents client-side creation of new shared logins.

### residents

Policies:
- select: allowed for care home users in same care_home_id (active and inactive residents).
  - Reason: care home visibility is broader for management; inactive means no family access.
  - Reason: operator needs resident list to manage messages.
- insert/update/delete: allowed for care home users in same care_home_id.
  - Reason: care home controls resident identifiers and access.

### family_contacts

Policies:
- select: allowed for care home users in same care_home_id (active and inactive contacts).
  - Reason: care home visibility is broader for management; inactive means no family access.
  - Reason: operator manages family access.
- select (self): allowed where auth_user_id = auth.uid() and active = true.
  - Reason: family user can read their own profile only.
- insert/update/delete: allowed for care home users in same care_home_id.
  - Reason: access is managed by the care home, not the platform.

### family_contact_access

Policies:
- select: allowed for care home users in same care_home_id (derived via resident) and all links.
  - Reason: care home visibility is broader for management; inactive links block family access.
  - Reason: operator manages who can message which resident.
- select (self): allowed where family_contact_id belongs to auth.uid() and the link is active.
  - Reason: family user can see only their own linked residents.
- insert/update/delete: allowed for care home users in same care_home_id.
  - Reason: access changes are controlled by the care home.

### messages

Policies:
- select: allowed for care home users in same care_home_id (derived via resident), including inactive residents.
  - Reason: care home visibility is broader for management; inactive means no family access.
  - Reason: operator can view all messages in their home.
- select (self): allowed where contact_user_id = auth.uid() and an active access link exists for the resident.
  - Reason: prevents read-after-removal and enforces access control.
- insert/update (care home): allowed for care home users in same care_home_id (derived via resident).
  - Reason: staff record or assist with resident messages, limited to linked active contacts.
- insert/update (family): allowed where:
  - contact_user_id = auth.uid()
  - direction = 'to_resident'
  - an access row exists in family_contact_access for the resident
  - Reason: family can only send their own outbound messages to linked residents.
- delete: allowed for care home users in same care_home_id.
  - Reason: operator can remove messages if needed for supervision.

### security_events

Policies:
- select: allowed for care home users in same care_home_id.
  - Reason: care home can review its own operational security events.
- insert/update/delete: restricted to server-side components only.
  - Reason: prevents client-side tampering and keeps logs trustworthy.

### care_home_settings

Policies:
- select: allowed for care home users in same care_home_id.
  - Reason: operator can view its own operational settings.
- update: allowed for care home users in same care_home_id.
  - Reason: operator can adjust its own operational settings.
- insert/delete: restricted to administrative setup.
  - Reason: one row per care home; prevents client-side tampering.

## Storage (audio files)

Audio is stored in a Supabase Storage bucket, but clients do not have direct access to storage.objects.

- Direct list/get access is denied for all clients (family and care home).
- Audio playback uses short-lived signed URLs issued by a server-side component (Edge Function).
- The Edge Function verifies the current messages row and RLS-equivalent access checks before issuing a URL.

Reason: storage list and get share the same SELECT policy, so blocking browsing requires blocking direct access and using a controlled server-side path.

## How this enforces scope and responsibility

- One-message-per-direction is enforced by the unique constraint on (resident_id, contact_user_id, direction), ensuring no history.
- Family users can only access their own messages and linked residents, preventing cross-family visibility.
- Care home users have full visibility within their care home, aligning with operational responsibility.
- No tables or fields exist for care updates, monitoring, alerts, or content review.
- RLS prevents the platform from acting as a data controller or moderator; the care home remains the operator.
- Storage access is mediated by server-side checks, making storage non-browsable by design.

## Implementation SQL (schema + RLS)

The SQL below implements the schema and RLS rules described above. It is intended for Supabase (PostgreSQL).

```sql
-- Enable required extensions (if not already enabled)
create extension if not exists "pgcrypto";

-- 1) care_homes
create table if not exists public.care_homes (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz not null default now(),
  active boolean not null default true
);

alter table public.care_homes enable row level security;

-- 2) care_home_users (one shared login per care home)
create table if not exists public.care_home_users (
  id uuid primary key default gen_random_uuid(),
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  auth_user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz not null default now(),
  active boolean not null default true,
  unique (auth_user_id),
  unique (care_home_id)
);

alter table public.care_home_users enable row level security;

-- 3) residents
create table if not exists public.residents (
  id uuid primary key default gen_random_uuid(),
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  preferred_display_name text not null,
  care_home_reference text not null,
  created_at timestamptz not null default now(),
  active boolean not null default true
);

alter table public.residents enable row level security;

-- 4) family_contacts
create table if not exists public.family_contacts (
  id uuid primary key default gen_random_uuid(),
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  auth_user_id uuid not null references auth.users(id) on delete cascade,
  email text not null,
  display_name text not null,
  created_at timestamptz not null default now(),
  active boolean not null default true,
  unique (auth_user_id)
);

alter table public.family_contacts enable row level security;

-- 5) family_contact_access (contact <-> resident links)
create table if not exists public.family_contact_access (
  id uuid primary key default gen_random_uuid(),
  -- care_home_id is derived via residents to avoid cross-home mismatches.
  resident_id uuid not null references public.residents(id) on delete cascade,
  family_contact_id uuid not null references public.family_contacts(id) on delete cascade,
  created_at timestamptz not null default now(),
  active boolean not null default true,
  unique (resident_id, family_contact_id)
);

alter table public.family_contact_access enable row level security;

-- 6) messages (latest message per channel)
create table if not exists public.messages (
  id uuid primary key default gen_random_uuid(),
  -- care_home_id is derived via residents to avoid cross-home mismatches.
  resident_id uuid not null references public.residents(id) on delete cascade,
  contact_user_id uuid not null references auth.users(id) on delete cascade,
  direction text not null check (direction in ('to_resident', 'from_resident')),
  audio_storage_path text not null,
  audio_mime_type text not null,
  audio_bytes integer not null,
  recorded_at timestamptz not null,
  created_at timestamptz not null default now(),
  unique (resident_id, contact_user_id, direction)
);

alter table public.messages enable row level security;

-- 7) security_events (minimal, no content or email data)
create table if not exists public.security_events (
  id uuid primary key default gen_random_uuid(),
  care_home_id uuid not null references public.care_homes(id) on delete cascade,
  actor_user_id uuid references auth.users(id) on delete set null,
  actor_role text not null,
  event_type text not null,
  resident_id uuid references public.residents(id) on delete set null,
  created_at timestamptz not null default now()
);

alter table public.security_events enable row level security;

-- 8) care_home_settings (operational configuration only)
create table if not exists public.care_home_settings (
  care_home_id uuid primary key references public.care_homes(id) on delete cascade,
  quick_lock_enabled boolean not null default true,
  quick_lock_timeout_minutes integer not null default 15,
  desk_warning_minutes integer not null default 120,
  updated_at timestamptz not null default now()
);

alter table public.care_home_settings enable row level security;

-- RLS policies

-- care_homes
create policy "care_homes_select_own"
on public.care_homes
for select
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = care_homes.id
      and chu.auth_user_id = auth.uid()
      -- Active-only access for shared login.
      and chu.active = true
  )
);
-- No insert/update/delete policies for client access.

-- care_home_users
create policy "care_home_users_select_self"
on public.care_home_users
for select
using (
  auth_user_id = auth.uid()
  -- Deactivated shared logins cannot access data.
  and care_home_users.active = true
);
-- No insert/update/delete policies for client access.

-- residents
create policy "residents_select_care_home"
on public.residents
for select
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = residents.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
  -- Care home visibility includes inactive residents for management.
);

create policy "residents_write_care_home"
on public.residents
for insert, update, delete
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = residents.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
)
with check (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = residents.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

-- family_contacts
create policy "family_contacts_select_care_home"
on public.family_contacts
for select
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = family_contacts.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
  -- Care home visibility includes inactive contacts for management.
);

create policy "family_contacts_select_self"
on public.family_contacts
for select
using (auth_user_id = auth.uid() and family_contacts.active = true);

create policy "family_contacts_write_care_home"
on public.family_contacts
for insert, update, delete
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = family_contacts.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
)
with check (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = family_contacts.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

-- family_contact_access
create policy "family_contact_access_select_care_home"
on public.family_contact_access
for select
using (
  exists (
    select 1 from public.care_home_users chu
    join public.residents r on r.id = family_contact_access.resident_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
  -- Care home visibility includes inactive links for management.
);

create policy "family_contact_access_select_self"
on public.family_contact_access
for select
using (
  exists (
    select 1
    from public.family_contacts fc
    join public.residents r on r.id = family_contact_access.resident_id
    where fc.id = family_contact_access.family_contact_id
      and fc.auth_user_id = auth.uid()
      and fc.care_home_id = r.care_home_id
      and fc.active = true
      and r.active = true
      and family_contact_access.active = true
  )
);

create policy "family_contact_access_write_care_home"
on public.family_contact_access
for insert, update, delete
using (
  exists (
    select 1 from public.care_home_users chu
    join public.residents r on r.id = family_contact_access.resident_id
    join public.family_contacts fc on fc.id = family_contact_access.family_contact_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
      and r.active = true
      -- Prevent cross-home linkage.
      and fc.care_home_id = r.care_home_id
      and fc.active = true
  )
)
with check (
  exists (
    select 1 from public.care_home_users chu
    join public.residents r on r.id = family_contact_access.resident_id
    join public.family_contacts fc on fc.id = family_contact_access.family_contact_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
      and r.active = true
      -- Prevent cross-home linkage.
      and fc.care_home_id = r.care_home_id
      and fc.active = true
  )
);

-- messages
create policy "messages_select_care_home"
on public.messages
for select
using (
  exists (
    select 1
    from public.care_home_users chu
    join public.residents r on r.id = messages.resident_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
  -- Care home can read messages for inactive residents/contacts for management.
);

create policy "messages_select_self"
on public.messages
for select
using (
  contact_user_id = auth.uid()
  and exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r on r.id = messages.resident_id
    where fc.auth_user_id = auth.uid()
      -- Ensure contact belongs to the same care home as the resident.
      and fc.care_home_id = r.care_home_id
      and fca.resident_id = messages.resident_id
      -- Prevent read-after-removal.
      and fca.active = true
      and fc.active = true
      and r.active = true
  )
);

create policy "messages_write_care_home"
on public.messages
for insert, update, delete
using (
  exists (
    select 1
    from public.care_home_users chu
    join public.residents r on r.id = messages.resident_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
      and r.active = true
      -- No writes for inactive residents/contacts; prevents targeting unrelated auth users.
      and exists (
        select 1
        from public.family_contacts fc
        join public.family_contact_access fca
          on fca.family_contact_id = fc.id
        where fc.auth_user_id = messages.contact_user_id
          -- Ensure contact belongs to the same care home as the resident.
          and fc.care_home_id = r.care_home_id
          and fc.active = true
          and fca.resident_id = messages.resident_id
          and fca.active = true
      )
  )
)
with check (
  exists (
    select 1
    from public.care_home_users chu
    join public.residents r on r.id = messages.resident_id
    where chu.care_home_id = r.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
      and r.active = true
      -- No writes for inactive residents/contacts; prevents targeting unrelated auth users.
      and exists (
        select 1
        from public.family_contacts fc
        join public.family_contact_access fca
          on fca.family_contact_id = fc.id
        where fc.auth_user_id = messages.contact_user_id
          -- Ensure contact belongs to the same care home as the resident.
          and fc.care_home_id = r.care_home_id
          and fc.active = true
          and fca.resident_id = messages.resident_id
          and fca.active = true
      )
  )
);

create policy "messages_write_family_to_resident"
on public.messages
for insert, update
using (
  contact_user_id = auth.uid()
  and direction = 'to_resident'
  and exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r on r.id = messages.resident_id
    where fc.auth_user_id = auth.uid()
      -- Ensure contact belongs to the same care home as the resident.
      and fc.care_home_id = r.care_home_id
      and fca.resident_id = messages.resident_id
      and fc.active = true
      and fca.active = true
      and r.active = true
  )
)
with check (
  contact_user_id = auth.uid()
  and direction = 'to_resident'
  and exists (
    select 1
    from public.family_contacts fc
    join public.family_contact_access fca
      on fca.family_contact_id = fc.id
    join public.residents r on r.id = messages.resident_id
    where fc.auth_user_id = auth.uid()
      -- Ensure contact belongs to the same care home as the resident.
      and fc.care_home_id = r.care_home_id
      and fca.resident_id = messages.resident_id
      and fc.active = true
      and fca.active = true
      and r.active = true
  )
);

-- security_events
create policy "security_events_select_care_home"
on public.security_events
for select
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = security_events.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);
-- No insert/update/delete policies for client access.

create policy "care_home_settings_select"
on public.care_home_settings
for select
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = care_home_settings.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);

create policy "care_home_settings_update"
on public.care_home_settings
for update
using (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = care_home_settings.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
)
with check (
  exists (
    select 1 from public.care_home_users chu
    where chu.care_home_id = care_home_settings.care_home_id
      and chu.auth_user_id = auth.uid()
      and chu.active = true
  )
);
```

## Implementation SQL (storage policies)

Storage is intentionally non-browsable. Clients do not have direct access to storage.objects.

This assumes:
- a bucket named `voice_messages`
- audio access is mediated by a server-side component (Edge Function) that issues short-lived signed URLs

```sql
-- Storage bucket (example)
insert into storage.buckets (id, name, public)
values ('voice_messages', 'voice_messages', false)
on conflict (id) do nothing;

-- Enable RLS on storage.objects if not already enabled
alter table storage.objects enable row level security;

-- Explicitly deny all client access to storage.objects (no browsing, no direct get)
create policy "storage_deny_select"
on storage.objects
for select
using (false);

create policy "storage_deny_insert"
on storage.objects
for insert
with check (false);

create policy "storage_deny_update"
on storage.objects
for update
using (false)
with check (false);

create policy "storage_deny_delete"
on storage.objects
for delete
using (false);
```

## Notes for implementation

- The unique constraint on `messages` supports an upsert model to overwrite previous audio per direction.
- The storage bucket is private, and direct client access is denied by policy.
- Audio playback uses short-lived signed URLs generated server-side after access checks.
- No service-role key is required in client code; service role is used server-side only.

## Storage policy rationale

Storage is not browsable. Direct list/get access is denied to all clients. Audio access is only provided via short-lived signed URLs after server-side checks, which prevents browsing and reduces accidental disclosure. Families lose access immediately when the resident, contact, or link becomes inactive because signed URLs are only issued for current, permitted messages.
