![logo](../../../assets/logo.png)

# External services and subscriptions register

Purpose: track every third-party website/app/service used by voicemailcare.com, including subscriptions, credentials ownership, legal links, and renewal dates.

## Register table

| Service / website | Purpose in voicemailcare.com | Owner | Contract / terms location | Renewal date | Data processed | Notes |
|---|---|---|---|---|---|---|
| Supabase | Database, auth, storage, edge functions |  |  |  | Personal data + message metadata/audio | Core infrastructure |
| Render (`voicemailcare-main`) | Live application hosting/runtime |  |  |  | Application/session metadata | Active live service mapped to `voicemailcare.com` |
| Domain/DNS provider | Domain and DNS management |  |  |  | Low/no personal data | Operational dependency |
| Email delivery provider (if separate) | Auth links / transactional email |  |  |  | Contact email addresses | Confirm retention and DPA terms |
| Monitoring/logging tooling (if used) | Operational monitoring and incidents |  |  |  | Operational/security events | Ensure data minimisation |

## Active vs legacy deployment note

- Active runtime is the Render service `voicemailcare-main` on custom domain `voicemailcare.com`.
- Media delivery domain is `media.voicemailcare.com`.
- Any old Render projects or env groups renamed with `old-` prefixes are legacy and must not be treated as active infrastructure.

## Mandatory checks per service

- Contract or terms accepted and stored
- DPA/sub-processor terms reviewed where personal data is processed
- Named owner responsible for renewals
- Offboarding/exit plan documented
- Security contact and incident route recorded

## Update frequency

- Review monthly during pilot
- Review immediately on new service adoption or material change
