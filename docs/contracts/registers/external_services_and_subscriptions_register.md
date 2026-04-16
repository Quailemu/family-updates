![logo](../../../assets/logo.png)

# External services and subscriptions register

Purpose: track every third-party website/app/service used by voicemailcare.com, including subscriptions, credentials ownership, legal links, and renewal dates.

## Register table

| Service / website | Purpose in voicemailcare.com | Owner | Contract / terms location | Renewal date | Data processed | Notes |
|---|---|---|---|---|---|---|
| Supabase (project + Auth + Postgres) | Database, authentication, auth links, role/session data | TBC | Supabase dashboard billing + legal pages | Monthly (if paid plan) | Personal data, account data, message metadata | Core infrastructure |
| Supabase Storage (`voice-messages`) | Audio object storage and signed URL playback | TBC | Supabase dashboard | Monthly (if paid plan) | Voice recordings + storage paths | Confirm bucket policies + retention |
| Supabase Edge Functions (`get_audio_signed_url`) | Signed media URL generation path (if enabled) | TBC | Supabase dashboard | N/A | Access tokens + object paths | Keep function secrets reviewed |
| Render (`voicemailcare-main`) | Live app runtime hosting | TBC | Render billing + service settings | Monthly | Runtime/session metadata + app logs | Active service on `voicemailcare.com` |
| Cloudflare (DNS + domain + R2) | DNS records, domain, media delivery (`media.voicemailcare.com`) | TBC | Cloudflare billing + domain registration + R2 terms | Domain annual + usage monthly | DNS metadata + media objects | Keep `www` redirect and cert status checked |
| GitHub (repo + access) | Source control, deployment source, audit trail | TBC | GitHub billing/settings | Monthly (if paid) | Source code + issue/commit metadata | Review collaborators and branch protections |
| OpenAI API | Optional transcription at upload time | TBC | OpenAI billing + usage pages | Usage-based monthly | Audio snippets sent for transcription + transcript text | Rotate API key and set spend alerts |
| Postmark (if configured as SMTP) | Transactional auth email delivery | TBC | Postmark billing + server config | Monthly | Recipient email addresses + delivery metadata | Confirm bounce handling + retention |
| Microsoft 365 (`hello@voicemailcare.com`) | Operations/support mailbox and business email | TBC | Microsoft 365 admin billing | Monthly/annual (plan dependent) | Support and operational email content | Ensure MFA and mailbox access review |
| Office authenticator app dependency | TOTP second factor for Care Hub - Office | TBC | Internal security procedure | N/A | OTP secrets stored in auth app/device | Document break-glass and recovery code handling |
| Search webmaster tools (Google/Bing, if used) | Sitemap submission, recrawl requests, search visibility hygiene | TBC | Search Console / Bing Webmaster settings | N/A | Site indexing metadata | Useful for stale snippet/index cleanup |

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

## Operations checklist (recommended)

### Monthly checks

- Verify service billing status and upcoming renewals for Supabase, Render, Cloudflare, OpenAI, Postmark, Microsoft 365.
- Verify domain and certificate health: `voicemailcare.com` and `www.voicemailcare.com`.
- Verify canonical/redirect posture: custom domain preferred, old preview hosts not preferred for indexing.
- Run authentication smoke tests:
  - Family magic link
  - Care Hub - Mobile login + PIN
  - Care Hub - Office login + MFA
- Run media smoke tests:
  - Systems, Mobile, Family, Office videos on `/public/help-videos`
  - Sample message record/playback flow
- Review access lists for Supabase, Render, Cloudflare, GitHub, OpenAI, Postmark, Microsoft 365.
- Confirm backup/retention and deletion expectations still match policy and contract wording.

### Quarterly checks

- Rotate high-risk secrets: `OPENAI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `AUTH_COOKIE_SIGNING_KEY`.
- Review DPA/sub-processor terms and update contract records.
- Review incident contacts/escalation routes for each provider.
- Test recovery paths: lost MFA device, expired links, auth callback failures, media fallback behavior.
- Confirm legacy infrastructure remains clearly marked as legacy (`old-*`) and not used in active runtime.
