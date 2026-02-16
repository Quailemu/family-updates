# RLS test plan (no app code)

This plan validates critical security properties using the Supabase SQL editor and minimal auth simulation. It assumes a fresh project with the migration applied.

## How to simulate auth in SQL

Supabase supports setting JWT claims in the SQL editor to simulate `auth.uid()`:

```sql
select set_config('request.jwt.claims', json_build_object('sub','<USER_UUID>')::text, true);
```

Use this before queries to simulate a logged-in user. To reset:

```sql
select set_config('request.jwt.claims', null, true);
```

If your SQL editor does not support this, skip the auth simulation steps and use the curl examples under each test.

## Minimal test dataset (SQL)

Run as service role (SQL editor).

```sql
-- Care homes
insert into public.care_homes (id, name) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Care Home A'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Care Home B');

-- Care home shared logins (auth.users must exist with these UUIDs)
insert into public.care_home_users (care_home_id, auth_user_id, active) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', true),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '22222222-2222-2222-2222-222222222222', true);

-- Residents (one per home)
insert into public.residents (id, care_home_id, preferred_display_name, care_home_reference, active) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'Margaret', 'Room 1', true),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbb0001', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', 'Arthur', 'Room 2', true);

-- Family contacts (auth.users must exist with these UUIDs)
insert into public.family_contacts (id, care_home_id, auth_user_id, email, display_name, active) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaafc01', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '33333333-3333-3333-3333-333333333333', 'family.a@example.com', 'Family A', true),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbfc01', 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '44444444-4444-4444-4444-444444444444', 'family.b@example.com', 'Family B', true);

-- Access links (only Family A is linked to Resident A)
insert into public.family_contact_access (resident_id, family_contact_id, active) values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaafc01', true);

-- Messages (one each direction for Resident A / Family A)
insert into public.messages (resident_id, contact_user_id, direction, audio_storage_path, audio_mime_type, audio_bytes, recorded_at)
values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001', '33333333-3333-3333-3333-333333333333', 'to_resident', 'voice_messages/a/to_resident.webm', 'audio/webm', 1234, now()),
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001', '33333333-3333-3333-3333-333333333333', 'from_resident', 'voice_messages/a/from_resident.webm', 'audio/webm', 2345, now());
```

## Tests

### A) Care-home isolation

Purpose: Care home A cannot see residents/messages of care home B.

Setup:
- Ensure both care homes and residents are created (above).

Action (SQL):
```sql
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111"}', true);
select id, preferred_display_name from public.residents;
```

Expected result:
- Only Resident A is returned.

Action (SQL):
```sql
select set_config('request.jwt.claims', '{"sub":"22222222-2222-2222-2222-222222222222"}', true);
select id, preferred_display_name from public.residents;
```

Expected result:
- Only Resident B is returned.

### B) Immediate revocation

Purpose: When access link is deactivated, family user loses DB and Storage access immediately.

Setup (SQL):
```sql
update public.family_contact_access
set active = false
where resident_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001'
  and family_contact_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaafc01';
```

Action (SQL):
```sql
select set_config('request.jwt.claims', '{"sub":"33333333-3333-3333-3333-333333333333"}', true);
select * from public.messages;
```

Expected result:
- No rows returned.

Action (Storage read test, curl):
```bash
curl -i \
  -H "Authorization: Bearer <JWT_FOR_3333>" \
  -H "apikey: <ANON_KEY>" \
  "https://<PROJECT_REF>.supabase.co/storage/v1/object/voice_messages/a/to_resident.webm"
```

Expected result:
- 403 or equivalent access denied.

### C) Active flag enforcement

Purpose: Inactive resident/contact/link blocks family access, but care home can still view inactive rows.

Setup (SQL):
```sql
update public.residents
set active = false
where id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001';
```

Action (family, SQL):
```sql
select set_config('request.jwt.claims', '{"sub":"33333333-3333-3333-3333-333333333333"}', true);
select * from public.messages;
```

Expected result:
- No rows returned.

Action (care home, SQL):
```sql
select set_config('request.jwt.claims', '{"sub":"11111111-1111-1111-1111-111111111111"}', true);
select id, preferred_display_name, active from public.residents;
```

Expected result:
- Resident A is visible with active = false.

### D) One-message-only rule

Purpose: New message overwrites prior for same (resident_id, contact_user_id, direction).

Action (SQL, service role or care home user):
```sql
insert into public.messages (resident_id, contact_user_id, direction, audio_storage_path, audio_mime_type, audio_bytes, recorded_at)
values ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaa0001', '33333333-3333-3333-3333-333333333333', 'to_resident',
        'voice_messages/a/to_resident_v2.webm', 'audio/webm', 3456, now())
on conflict (resident_id, contact_user_id, direction)
do update set
  audio_storage_path = excluded.audio_storage_path,
  audio_mime_type = excluded.audio_mime_type,
  audio_bytes = excluded.audio_bytes,
  recorded_at = excluded.recorded_at;
```

Expected result:
- The row is updated (not duplicated). A select should show exactly one row for that tuple.

### E) No storage browsing

Purpose: Users cannot list storage objects; access is only via current message rows.

Action (family, curl):
```bash
curl -i \
  -H "Authorization: Bearer <JWT_FOR_3333>" \
  -H "apikey: <ANON_KEY>" \
  "https://<PROJECT_REF>.supabase.co/storage/v1/object/list/voice_messages"
```

Expected result:
- 403 or equivalent access denied.

Action (care home, curl):
```bash
curl -i \
  -H "Authorization: Bearer <JWT_FOR_1111>" \
  -H "apikey: <ANON_KEY>" \
  "https://<PROJECT_REF>.supabase.co/storage/v1/object/list/voice_messages"
```

Expected result:
- 403 or equivalent access denied.

## Notes

- Replace placeholder UUIDs with real auth user IDs created in Supabase Auth.
- If `set_config('request.jwt.claims', ...)` is not supported in your SQL editor, use the curl examples with real JWTs.
