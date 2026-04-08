# System Overview

Master plan: `docs/VOICE_MESSAGE_MASTER_PLAN.md`

## Product variants (Family, Care Hub Mobile, Care Hub Office)

## System overview diagram

```mermaid
flowchart LR
  F[Family App] -->|record/send| API[(Backend/API)]
  API -->|deliver latest| F

  M[Care Hub Mobile] -->|record/send| API
  API -->|deliver latest| M

  O[Care Hub Office] -->|admin, invites, devices| API
  API -->|status, logs, controls| O

  API --> DB[(Database)]
  API --> ST[(Audio Storage)]
```

## Message model (one message each way, no threads)

Optional transcript assist is available when recording in Family, Care Hub Mobile, and Care Hub Office.
When available, transcript text is attached to the current message only (no transcript history).
Transcript text may contain errors; voice remains the source of truth.

## Authentication & security (link to docs/security/SECURITY_MODEL.md)

## Family onboarding & registration (placeholder)
- `docs/registration/FAMILY_REGISTRATION.md`

## Care home onboarding (placeholder)

## Audit logging (placeholder)

## Data retention & deletion (placeholder)

## Support & incident handling (placeholder)

## 5. Boundaries: what it is / what it is not
### 5.1 What it is

A calm, constrained channel for short social voice messages.

Designed to reduce pressure and remove “reply anxiety”.

### 5.2 What it is not

No urgent clinical info

No threaded chat

No archive browsing

No export tools

## 6. Roles and responsibilities

Care home staff use Mobile for recording/playing.

Office users control onboarding, invites, revocation, devices.

Families receive/send within strict limits.

## 7. Devices (non-negotiable)

Dedicated devices provided for Voice Message only.

No personal phones.

Devices remain on-site.

OS auto-lock: 2–5 minutes.

OS device PIN is enabled.

## 8. Authentication and access control
### 8.1 Care Hub Mobile: shared care-home PIN (final decision)

One shared 4-digit PIN per care home (hashed; changeable in Office).

Inactivity timeout: 15–20 minutes (re-enter PIN).

Primary protections are device control + no export + remote disable.

```mermaid
sequenceDiagram
  participant User as Carer (on-site)
  participant Device as Dedicated Device
  participant App as Care Hub Mobile
  participant API as Backend

  User->>Device: Wake device
  Device-->>User: Device unlock (OS PIN if locked)
  User->>App: Open app
  App->>User: Enter care-home shared PIN
  App->>API: Verify PIN
  API-->>App: Session granted
  Note over App: Inactivity timeout 15–20 min\nDevice auto-lock 2–5 min
  App-->>User: Shows last sent + last received
```

### 8.2 Care Hub Office: accounts + TOTP 2FA

Office uses individual accounts.

Office requires TOTP MFA.

Office holds all sensitive controls (invites, revocation, device disable).

### 8.3 Family: 30-day remembered session + magic link fallback

Family activates via invite link.

Family session persists up to 30 days for usability.

If logged out/new device: request magic link by SMS/email.

## 9. Family onboarding (invite-based self-activation)
### 9.1 Invite creation (Office)

Office creates invite: resident + family contact (SMS/email).

### 9.2 Activation (Family)

Family taps activation link, accepts terms, session created.

```mermaid
sequenceDiagram
  participant Office as Care Hub Office
  participant API as Backend
  participant SMS as SMS/Email Provider
  participant Family as Family User

  Office->>API: Create invite (resident + contact)
  API->>SMS: Send activation link
  Family->>Family: Tap activation link
  Family->>API: Accept invite + accept terms
  API-->>Family: Session created (remembered up to 30 days)
```

### 9.3 Revocation

Office can revoke family access instantly; sessions invalidate immediately.

```mermaid
flowchart TD
  O[Office] -->|Disable family link| API[(Backend)]
  O -->|Disable device| API
  API --> DB[(DB updates: revoked/enabled=false)]
  API --> M[Mobile: next check locks out]
  API --> F[Family: session invalidates]
```

## 10. Message lifecycle
### 10.1 Family → Care

When family records a new message, it replaces prior family→care message for that link.

UI shows only “last sent”.

### 10.2 Care → Family

When care records a new message, it replaces prior care→family message for that link.

UI shows only “last received”.

### 10.3 Storage & caching

No bulk export.

Avoid permanent device storage; stream or short-lived cache.

## 11. Screen behaviour by app
### 11.1 Family UI (must show two tiles)

Last message sent (playback)

Last message received (playback)

Record new message (replaces last sent)

### 11.2 Mobile UI

Same: last sent + last received

Record/Play only; no archive.

### 11.3 Office UI

Same two messages per link

Admin controls: invites, revoke, device disable, settings.

## 12. Data model overview (high-level)

(Placeholder for tables/entities: care_homes, residents, family_links, devices, messages, invites, audit_events)

## 13. Security model (proportionate)

Key controls:

Dedicated devices only

OS auto-lock + device PIN

Shared mobile PIN + inactivity timeout

No export/bulk history

Remote device disable

Office MFA
