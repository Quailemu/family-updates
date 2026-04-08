# Voice Message — Master System Plan
Finalised: 2026-02-22

## 0. How to use this document
This is the single reference document for how Voice Message works. It is designed to be readable end-to-end and to prevent decision drift. If something is unclear elsewhere, this file is the source of truth.

## 1. Purpose and philosophy
Voice Message is a low-urgency, social communication tool between families and care homes.
It is not clinical records, medication management, finance, or emergency messaging.
The design goal is calm usability and adoption. Security is proportionate and low-friction.

## 2. Product variants
- Family (end user)
- Care Hub — Mobile (carers on dedicated devices)
- Care Hub — Office (admin, onboarding, control)

## 3. Core constraint: Two-message model
Every interface shows only:
- Last message sent
- Last message received
No threads.

```mermaid
flowchart TB
  subgraph Link["Family ↔ Resident Link (one relationship)"]
    A[Last message from Family → Care] -->|replaced by new send| A
    B[Last message from Care → Family] -->|replaced by new send| B
  end
```

## 4. System overview diagram

```mermaid
flowchart LR
  F[Family Hub] -->|record/send| API[(Backend/API)]
  API -->|deliver latest| F

  M[Care Hub Mobile] -->|record/send| API
  API -->|deliver latest| M

  O[Care Hub Office] -->|admin, invites, devices| API
  API -->|status, logs, controls| O

  API --> DB[(Database)]
  API --> ST[(Audio Storage)]
```

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

## 14. Audit and logs (minimal and non-creepy)

Log only what is needed to support trust and incident resolution:

invite_sent / invite_accepted / access_revoked

device_disabled

message_recorded (optionally without content metadata)

## 15. Incident handling (runbook)

Lost device: disable device in Office (immediate lockout).

Wrong family invited: revoke link, resend correct invite.

Complaint: disable link, review basic audit events.

## 16. Pilot rollout plan (bite-sized)

Self-test end-to-end on dedicated devices.

Friendly family test.

Single care home pilot (one unit, short window).

Expand only after stability.

## 17. Future phases (explicitly not now)

Individual carer attribution

NFC badges

Advanced analytics

Threaded history

## 18. Change log

2026-02-22 Created master plan document.

## Visual Appendix (3-diagram quick view)

### A) Map (system context)

```mermaid
flowchart LR
  F[Family Hub] -->|record/send| API[(Backend/API)]
  API -->|deliver latest| F

  M[Care Hub Mobile] -->|record/send| API
  API -->|deliver latest| M

  O[Care Hub Office] -->|admin, invites, devices| API
  API -->|status, logs, controls| O

  API --> DB[(Database)]
  API --> ST[(Audio Storage)]
```

### B) Flow (invite → activate → message → revoke)

```mermaid
flowchart TD
  O1[Office creates invite] --> B1[Backend creates token]
  B1 --> C1[SMS/Email sends activation link]
  C1 --> F1[Family taps link and accepts terms]
  F1 --> B2[Session created]
  B2 --> M1[Family sends message]
  M1 --> B3[Latest Family→Care replaces previous]
  O2[Care records reply] --> B4[Latest Care→Family replaces previous]
  O3[Office revokes access] --> B5[Invalidate sessions + disable link]
```

### C) Entities (high-level data model)

```mermaid
erDiagram
  CARE_HOMES ||--o{ RESIDENTS : has
  CARE_HOMES ||--o{ DEVICES : owns
  CARE_HOMES ||--o{ CARE_HUB_USERS : has
  CARE_HOMES ||--o{ FAMILY_CONTACTS : has
  RESIDENTS ||--o{ FAMILY_LINKS : linked
  FAMILY_CONTACTS ||--o{ FAMILY_LINKS : linked
  RESIDENTS ||--o{ MESSAGES : has
  FAMILY_CONTACTS ||--o{ MESSAGES : contact_party
  CARE_HOMES ||--o{ INVITES : issues
  CARE_HOMES ||--o{ AUDIT_EVENTS : logs
```
