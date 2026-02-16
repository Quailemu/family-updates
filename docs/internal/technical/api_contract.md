# Minimal API contract (secure)

## Overview

This contract defines the minimum secure API surface between the app and the Edge Function. It avoids storage browsing and enforces access in the function.

Base URL:
- `https://<PROJECT_REF>.supabase.co/functions/v1`

Required headers (all endpoints):
- `Authorization: Bearer <JWT>`
- `apikey: <ANON_KEY>`

## Endpoint: GET /get_audio_signed_url

Purpose: Generate a short‑lived signed URL for a single audio object.

Query parameters:
- `message_id` (uuid, required)

Request example:
```
GET /get_audio_signed_url?message_id=<UUID>
```

Response (success):
```json
{"signed_url":"https://...","expires_in":60}
```

Response (errors, generic where possible):
```json
{"error":"missing_authorization"}
{"error":"invalid_authorization_format"}
{"error":"invalid_token"}
{"error":"missing_message_id"}
{"error":"message_not_found"}
{"error":"access_denied"}
{"error":"sign_failed"}
```

Access rules:
- Care home operator: allowed if the message’s resident belongs to their care home.
- Family contact: allowed only if:
  - the message’s `contact_user_id` matches the caller
  - the family contact is active
  - the resident is active
  - the access link is active

Input validation:
- Reject non‑UUID `message_id`.
- Reject missing Authorization header.

Rate limits:
- 10 / minute / user
- 60 / hour / user
- Global IP cap: 300 / 5 min
- 429 with Retry-After on limit exceeded

Error handling (no existence leaks):
- Use `message_not_found` when the message cannot be retrieved.
- Use `access_denied` for inactive or unlinked cases.

Rate limiting (expectations):
- Log all 429 events and repeated 401/403 in `security_events`.

## Notes

- Storage is never accessed directly by clients.
- Signed URLs expire quickly and are single‑object only.
- Access control is enforced at the database level and re‑checked in the function.
