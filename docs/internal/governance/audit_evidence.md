# Audit evidence (repeatable)

Active care home ID: c4d1a1f9-652d-4c58-acf4-73b0b7a3cacd

Assumptions:
- Family A auth user id: b70b70db-4c87-4b43-b809-b35a63322dd0
- Operator for care home exists in `care_home_users`
- Message id used for signed URL tests: 964aac2d-5295-4bf1-99d2-256e5e25116e
- Storage object exists at `voice_messages/pilot/to_resident.webm`

## Role allow/deny tests (SQL editor)

Use authenticated role simulation:
```sql
set role authenticated;
select set_config('request.jwt.claims', '{"sub":"<AUTH_USER_UUID>"}', true);
```
Reset after tests:
```sql
reset role;
```

### care_home_settings (operator allow, family deny)

Operator allow:
```sql
set role authenticated;
select set_config('request.jwt.claims', '{"sub":"<OPERATOR_UUID>"}', true);
select * from public.care_home_settings
where care_home_id = 'c4d1a1f9-652d-4c58-acf4-73b0b7a3cacd';
reset role;
```
Expected: 1 row.

Family deny:
```sql
set role authenticated;
select set_config('request.jwt.claims', '{"sub":"b70b70db-4c87-4b43-b809-b35a63322dd0"}', true);
select count(*) as cnt from public.care_home_settings;
reset role;
```
Expected: cnt = 0.

### messages (family allow only for linked active resident)

```sql
set role authenticated;
select set_config('request.jwt.claims', '{"sub":"b70b70db-4c87-4b43-b809-b35a63322dd0"}', true);
select id from public.messages
where id = '964aac2d-5295-4bf1-99d2-256e5e25116e';
reset role;
```
Expected: 1 row (if link + active flags are true).

## Storage protections (non-browsable)

### Storage list should be denied

```bash
curl -i \
  -H "Authorization: Bearer <FAMILY_JWT>" \
  -H "apikey: <ANON_KEY>" \
  "https://<PROJECT_REF>.supabase.co/storage/v1/object/list/voice_messages"
```
Expected: 403 (no listing).

### Direct storage get should be denied

```bash
curl -i \
  -H "Authorization: Bearer <FAMILY_JWT>" \
  -H "apikey: <ANON_KEY>" \
  "https://<PROJECT_REF>.supabase.co/storage/v1/object/voice_messages/pilot/to_resident.webm"
```
Expected: 403 (no direct access).

## Signed URL flow (Edge Function)

### Success path

```bash
curl -s \
  -H "Authorization: Bearer <FAMILY_JWT>" \
  -H "apikey: <ANON_KEY>" \
  "https://<PROJECT_REF>.supabase.co/functions/v1/get_audio_signed_url?message_id=964aac2d-5295-4bf1-99d2-256e5e25116e"
```
Expected: JSON with `signed_url` and `expires_in` (60).

### Failure path: missing object

Temporarily point the message to a non-existent path and retry:
```sql
update public.messages
set audio_storage_path = 'voice_messages/pilot/missing.webm'
where id = '964aac2d-5295-4bf1-99d2-256e5e25116e';
```
Expected: `{"error":"sign_failed"}`.

Revert afterward:
```sql
update public.messages
set audio_storage_path = 'voice_messages/pilot/to_resident.webm'
where id = '964aac2d-5295-4bf1-99d2-256e5e25116e';
```

## Rate limiting verification

Rate limits are enforced at the gateway/function layer. Verification is manual:
- Send repeated requests until a 429 is observed.
- Confirm Retry-After header is present.
- Check `security_events` and function logs for 429 entries.

## Role mismatch handling (app routes)

Goal: confirm family creds cannot access care hub flows and care hub creds cannot access family flows.

Family user tries care hub:
1) Sign in as a family user.
2) Navigate to `/care-hub/login` and `/care-hub/inbox`.
Expected: access denied or redirect to correct family flow; no care hub data shown.

Care hub user tries family:
1) Sign in as a care hub operator.
2) Navigate to `/family/login` and `/family/send`.
Expected: access denied or redirect to correct care hub flow; no family data shown.

Record: note route, observed behavior, and any redirect target.

## Missing mapping row behavior (auth OK, mapping missing)

Goal: confirm app handles missing mapping/link rows safely.

Family user without resident link:
1) Sign in as a family user that has no active resident link.
2) Attempt to load `/family/send`.
Expected: no resident auto-selected; app shows a safe message (no data) and prevents sending.

Care hub operator without mapping:
1) Sign in as an operator with no valid care_home mapping or inactive mapping.
2) Attempt to load `/care-hub/inbox`.
Expected: access denied or safe empty state; no resident data shown.

Record: user id, route, and observed UI/state.

## PASS/FAIL meaning

- PASS: access is granted only within explicit scope.
- FAIL: any unexpected data visibility or storage browsing.
