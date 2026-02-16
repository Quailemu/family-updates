# RLS test log

Date: 2026-01-11

## Scope

- Logged current results only (latest schema and policies).
- Tests run in Supabase SQL editor with `set role authenticated` and `request.jwt.claims` for auth simulation.

## Results

### Security and compliance (priority)

- Storage is non-browsable by clients; audio access uses signed URLs only.
- Edge Function validates the requester and enforces active link checks.
- Care home settings are operator-only; family cannot read or change them.

### Test outcomes

- Care home settings (Test L):
  - Care home operator (A) can read settings for its own care home.
  - Care home operator (A) can update settings for its own care home.
  - Family user cannot read settings (count = 0).
  - Family user cannot update settings (no rows returned).
- Signed URL (Edge Function):
  - Family A received a signed URL for message `964aac2d-5295-4bf1-99d2-256e5e25116e` (expires_in = 60).

## Lay explanation

We have locked down audio so nobody can browse files directly. The only way to listen is to request a short‑lived link, and the system checks that the person asking is allowed to access that resident’s message. Family accounts cannot see or change care‑home settings. This keeps access narrow, reduces accidental exposure, and leaves the care home in control. 

---

Date: 2026-01-12

## Record

- Added: `docs/support/scope_statement.md` (authoritative scope reference)
- Added: `pilot_security_checklist.md`
- Added: `audit_evidence.md`
- Added: `api_contract.md`
- Added: `security_summary_layman.md`
- Updated: `supabase/README.md`
- Updated: `supabase/functions/get_audio_signed_url/index.ts`
- Added: `supabase/config.toml`
- Updated: `supabase/rls_test_log.md` (this entry)
- Updated: `pilot_security_checklist.md` (rate limits + incident response)
- Added: `docs/support/pilot_handover_checklist.md` (care home pilot handover)
- Added: `docs/support/scope_compliance_checklist.md` (quick scope audit)
- Added: `docs/support/ui_page_map.md` (Pilot UI v1 spec, scope frozen)
- Added: `docs/support/ui_wireframes.md` (component order + states, signed URL points)
- Updated: `docs/support/pilot_pack_index.md` (UI section + links)
- Added: `docs/support/pilot_test_walkthrough.md` (pilot test steps + acceptance criteria)
- Updated: `docs/support/pilot_test_walkthrough.md` (wording aligned to UI copy)
- Updated: `docs/support/pilot_test_walkthrough.md` (labels verified against UI docs)
- Added: `app.py` (Streamlit UI Phase 1 skeleton; no backend)
- Added: `docs/support/ready_for_pilot_review_checklist.md` (pilot review sign-off)
- Updated: `docs/support/pilot_pack_index.md` (pilot review link)
- Updated: `docs/support/ready_for_pilot_review_checklist.md` (finalised)
- Added: `docs/support/care_home_onboarding_script.md` (pilot onboarding script)
- Updated: `docs/support/pilot_pack_index.md` (onboarding link)
- Updated: `app.py` (UI Phase 2: real auth + role routing; dev nav behind flag)
- Added: `docs/support/ui_ux_brief_scope_aligned.md` (Royal Mail-style behaviour, scope-aligned)
- Updated: `docs/support/pilot_pack_index.md` (UI brief link)
- Updated: `app.py` (added Back button to each page)
- Updated: `docs/support/care_home_onboarding_script.md` (privacy expectation language)
- Updated: `docs/support/ui_page_map.md` (global privacy note on all screens)
- Updated: `docs/support/ui_wireframes.md` (privacy note on all screens)
- Updated: `app.py` (header hierarchy + privacy note wording)
- Updated: `docs/support/ui_page_map.md` (header sizing guidance)
- Updated: `docs/support/ui_wireframes.md` (privacy note wording)
- Added: `README.md` (local env vars for UI)
- Updated: `README.md` (local run command)

## Why (security/compliance)

- Provide a repeatable, evidence‑based pilot pack for external scrutiny.
- Clarify access rules and failure modes in plain language.
- Make storage access non‑browsable and enforce signed URL flow.
- Add explicit rate limits and incident response ownership to reduce abuse risk.
- Align UI guidance with strict scope (audio-only, current-only, no history).

## Assumptions/constraints

- Active care home ID: c4d1a1f9-652d-4c58-acf4-73b0b7a3cacd
- Signed URL requires an existing object at `voice_messages/pilot/to_resident.webm`
- Scope wording corrected to audio-only and current-message-only.

## Housekeeping (2026-01-12)

Removed early exploratory UI references that no longer reflect the agreed scope; Pilot UI v1 is authoritative.

---

Date: 2026-01-13

## Pending RLS checks (role gating + tamper tests)

- [ ] Family user cannot read or update any other family_contact rows.
- [ ] Family user cannot select or write care_home_users rows.
- [ ] Care hub user cannot read family_contact_access rows for other care homes.
- [ ] Care hub user cannot read messages for residents in other care homes.
- [ ] Family message insert fails if resident_id is not linked via family_contact_access.
- [ ] Family message insert fails if contact_user_id is not auth.uid().
- [ ] Care hub message update fails if resident_id belongs to another care home.
- [ ] Audit log insert fails if care_home_id does not match mapping.
