![logo](../../assets/logo.png)

# Scope compliance checklist (quick audit)

Date:
Reviewer:
Care home ID in use:

## Content scope (must remain true)

- [ ] Audio-only (no text, no video, no live calls).
- [ ] Social and non-urgent only.
- [ ] No care updates, health info, safeguarding alerts, monitoring, or assessment.
- [ ] No care planning or care notes.
- [ ] No moderation, review queues, or content analysis.

## Message handling (data minimisation)

- [ ] Only the current message is stored per direction.
- [ ] New messages overwrite previous messages.
- [ ] No message history, timeline, or feed visible to users.

## Roles and responsibility

- [ ] Care home operates the service and is the Data Controller.
- [ ] Care home handles identity, consent/LPA, supervision, access, devices, disputes.
- [ ] Platform provides technical tooling only (no verification of identity/consent/content).
- [ ] Role separation enforced: Families use Family app only, carers use Care Hub – Mobile only, office staff use Care Hub – Office only.
- [ ] Documents are accessible only in Care Hub – Office.

## UI/UX scope guards

- [ ] No global search across residents/users.
- [ ] No IDs shown in UI (resident_id, care_home_id, message_id).
- [ ] Generic denial/error messages (no existence leaks).
- [ ] "If urgent, contact the care home directly" copy shown where relevant.

## Security controls (must remain)

- [ ] RLS enforces isolation at the database level.
- [ ] Storage is non-browsable; audio access is via short-lived signed URLs only.
- [ ] Rate limits are defined and documented.
- [ ] Incident response roles and timelines are documented.

## Sign-off

- [ ] Scope statement reviewed (`docs/support/scope_statement.md`).
- [ ] Checklist completed and saved in the document pack.
