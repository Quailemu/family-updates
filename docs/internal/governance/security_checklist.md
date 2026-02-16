# Security checklist (tick-box)

Scope reference: `docs/support/scope_statement.md`

Date:
Site:
Care home ID in use: c4d1a1f9-652d-4c58-acf4-73b0b7a3cacd

## Auth & session management

- [ ] JWTs are short-lived and refreshed only via normal auth flow.
- [ ] Care Hub – Mobile devices use inactivity warning + lock (target 15–20 mins).
- [ ] Care Hub – Office devices provide a visible “Lock session” control.
- [ ] Care home confirms device OS lock (PIN/password) is enabled.

## Roles & access-control model

- [ ] One shared operator login per care home (no staff accounts).
- [ ] Family accounts are individual and not shared.
- [ ] Family access is limited to linked residents only.
- [ ] Role mismatch handling (family on care hub routes, care hub on family routes).
- [ ] Missing mapping row behavior handled safely (no access, safe empty state).

## RLS coverage (per table)

- [ ] care_homes: operator read only.
- [ ] care_home_users: operator read self only.
- [ ] care_home_settings: operator read/update only.
- [ ] residents: operator read/write; family read only when linked and active.
- [ ] family_contacts: operator read/write; family read self only.
- [ ] family_contact_access: operator read/write; family read self when active.
- [ ] messages: operator read/write; family read/write own and linked only.
- [ ] security_events: operator read only; no client writes.

## Storage protections + signed URL constraints

- [ ] Storage bucket is private (no public listing).
- [ ] Direct storage list/get is denied by policy.
- [ ] Signed URLs are short-lived (60s) and single-object only.
- [ ] Signed URL flow checks active link + resident/contact status.

## Audit logging & evidence retention

- [ ] security_events logs access decisions (no content or emails).
- [ ] Signed URL issuance and denied access are recorded.
- [ ] Log retention policy is documented (duration + access controls).

## Rate limiting / abuse prevention

- [ ] Edge Function has a conservative request limit policy.
- [ ] Repeated failures are monitored (security_events + dashboard logs).

### Rate limiting & abuse prevention (explicit values)

Principle: Prefer false negatives (block/slow suspicious traffic) over false positives (allow abuse). Keep limits conservative.

Enforcement behaviour:
- On limit exceeded: return 429 Too Many Requests.
- Include Retry-After header (seconds).
- Apply exponential backoff for repeated violations.
- Escalation: cooldown -> temporary account lock -> manual review flag.
- All limit events are logged with: timestamp, user_id (if known), role, IP hash, endpoint name, decision, correlation_id.

Default limits (conservative):
- Auth / login-like operations
  - 5 attempts / 10 min / IP -> 15 min cooldown
  - 10 attempts / hour / account identifier -> temporary lock (1 hour)
- Signed URL generation endpoint
  - 10 / minute / user
  - 60 / hour / user
  - If exceeded: cooldown + "suspicious access" flag
- Write endpoints (send message / create record)
  - 30 / minute / user (burst)
  - 300 / day / user (cap; adjustable)
- Read endpoints
  - 60 / minute / user
  - Prefer caching server-side where safe (avoid repeated expensive reads)
- Global IP safety cap
  - Any single IP > 300 requests / 5 min -> temporary block + log

Abuse scenarios to specifically detect:
- Credential stuffing / rapid auth attempts
- Signed-URL "spray" (rapid generation requests)
- Enumeration attempts (trying random IDs / paths)
- Token replay / repeated requests with same token at high rate
- Cross-tenant probing (attempts against other care_home_id)

Logging & alerting:
- Log all 429 decisions + escalations
- Alert when:
  - any user hits signed-URL hourly limit
  - any IP triggers global cap
  - repeated 401/403 at high rate (possible probing)

Checklist:
- [ ] Rate limits defined per endpoint + per role
- [ ] 429 behaviour documented + consistent
- [ ] Escalation path documented (cooldown/lock/manual review)
- [ ] Abuse scenarios enumerated + logging/alerts defined
- [ ] Limits reviewed before scope expansion

## Data minimisation & privacy basics

- [ ] Only necessary identifiers are stored (no health/care data).
- [ ] Messages store current audio only (no history).
- [ ] Resident identifiers are care-home-defined only.

## Data retention & deletion procedure

- [ ] Message overwrite behavior is verified (no history).
- [ ] Deletion requests are routed via the care home.
- [ ] Process for account removal is documented.

## Backups & restore considerations

- [ ] Backups are limited to operational data only.
- [ ] Restore procedures avoid re‑exposing deleted messages.

## Incident response basics

- [ ] Security contact is defined (care home + platform).
- [ ] Incident steps documented (contain, assess, notify).

### Incident response (role owners + timelines)

Principle: Role-based ownership (no personal names in repo). Clear response times.

Roles:
- Security Owner (role): triage, containment decisions, evidence preservation
- Data Protection Lead (role): personal data impact assessment, notification decisions
- Engineering On-call (role): hotfix, deploy, rollback, infrastructure changes
- Care Ops Lead (role): communication with care home, user impact coordination

Severity levels (simple version):
- Sev 1: confirmed/likely unauthorised access to personal data
- Sev 2: suspected probing or partial control failure, no confirmed data exfil
- Sev 3: nuisance abuse / rate-limit events / minor misconfig caught early

Timelines (conservative):
- Acknowledge suspected incident: within 4 hours
- Contain/disable risky access: within 12 hours
- Initial written incident summary: within 24 hours
- Post-incident review + preventive actions: within 7 days

Immediate containment playbook:
- Disable affected endpoint(s) via feature flag / env toggle where possible
- Reduce signed-URL TTL if needed
- Revoke sessions / rotate keys if compromise suspected
- Increase rate limits strictness temporarily (tighten caps)
- Preserve logs (no deletion) and record correlation IDs

Checklist:
- [ ] Roles assigned (role names only)
- [ ] Sev definitions present
- [ ] Timelines documented
- [ ] Containment steps documented
- [ ] Evidence preservation documented

## Evidence links

- [ ] `audit_evidence.md` completed and recent.
- [ ] `supabase/rls_test_log.md` updated with date and outcomes.
