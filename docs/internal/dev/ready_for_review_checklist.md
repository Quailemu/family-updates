![logo](../../assets/logo.png)

# Readiness review checklist (tick-box)

Date:
Site:
Care home ID in use:
Reviewer:

---

## 1) Scope & product claims (no drift)

- [ ] Scope matches `docs/support/scope_statement.md`.
- [ ] Only non-urgent social voice messages are described.
- [ ] Current-message-only and overwrite behaviour confirmed (no history).
- [ ] No care updates, health info, monitoring, assessment, or care planning implied.

## 2) Roles & responsibilities

- [ ] Care home is the operator and Data Controller.
- [ ] Platform provides technical tooling only (no verification of identity/consent/content).
- [ ] Consent/LPA, supervision, and access ownership are assigned to the care home.
- [ ] Role separation enforced: Families use Family app only, carers use Care Hub – Mobile only, office staff use Care Hub – Office only.

## 3) Security controls enforced

- [ ] Auth + JWT checks enforced server-side (Edge Function).
- [ ] RLS enforced at database level per role.
- [ ] Storage is non-browsable; access via signed URLs only.
- [ ] Rate limits and incident response are documented in the security checklist.

## 4) Data minimisation & retention

- [ ] Overwrite behaviour confirmed (no history stored or exposed).
- [ ] Attempting to access a previous message fails without revealing existence.
- [ ] Resident identifiers are care-home-defined only.
- [ ] Retention notes are consistent with `audit_evidence.md`.

## 5) UI & UX constraints

- [ ] UI matches `docs/support/ui_page_map.md` and `docs/support/ui_wireframes.md`.
- [ ] No urgency cues (no badges, timestamps, "new" labels).
- [ ] No IDs shown; no global search.
- [ ] Generic denial/error messages only.
- [ ] Documents are available only in Care Hub – Office.

## 6) Testing complete

- [ ] Test walkthrough executed end-to-end against the service environment.
- [ ] Pass/fail outcomes recorded and reviewed.
- [ ] Any failures resolved or explicitly accepted for review.

## 7) Operational readiness

- [ ] Care home consent/LPA owner identified.
- [ ] Care home access owner identified (adds/removes family).
- [ ] Support contact confirmed (care home + platform).
- [ ] Incident response roles confirmed (from the security checklist).
- [ ] Care home has instructed families that the service is non-urgent and urgent matters use normal contact methods.

## 8) Go/No-Go sign-off

- [ ] Document pack reviewed via the document pack index.
- [ ] Final decision recorded (Go/No-Go).

Sign-off:
Date:
Name/Initials:
Decision:

---

## Reference documents (authoritative)

- `docs/support/scope_statement.md`
- Document pack index
- Security checklist
- `security_summary_layman.md`
- `audit_evidence.md`
- `api_contract.md`
- `docs/support/ui_page_map.md`
- `docs/support/ui_wireframes.md`
- Test walkthrough
