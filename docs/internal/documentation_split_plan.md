# Documentation split plan

The product now has four active lifecycle stages plus preparation guidance. The existing documentation was mostly written for the original care-home-only model, so documents should be split by use context instead of patched one phrase at a time.

## Document groups

### 1. At-home guidance

For Stage 1, Stage 2, and Stage 3.

Use this wording:

- person / people
- home / setup
- coordinator / family / supporter / carer
- normal direct contact route
- shared at-home coordination

Avoid this wording unless referring to a later care-home stage:

- resident
- care home
- room
- care-home staff
- care-home responsibility

Current source candidates:

- `docs/circle/05_circle_guide.md`
- `docs/circle/10_registering_circle_contacts.md`
- `docs/circle/10_faq.md`
- `docs/circle/11_family_qa.md`
- `docs/circle/12_mobile_qa.md`
- `docs/circle/common_questions_qa.md`
- `docs/circle/circle_onboarding_script.md`
- `docs/circle/circle_handover_checklist.md`

High-priority rewrite targets:

- at-home Office guide
- at-home Mobile guide
- at-home Family guide
- registering a Family Member / contact
- at-home FAQ

### 2. Stage 4 Care Home Office guidance

For the care-home workspace only.

Use this wording:

- resident
- care home
- room / care home reference
- care-home staff
- Care Home Office
- Care Home Mobile
- care-home responsibility

Keep these documents care-home-specific:

- `docs/office/04_care_home_responsibilities.md`
- `docs/office/05_care_home_guide.md`
- `docs/office/08_care_hub_access_summary.md`
- `docs/office/09_safeguarding_consent.md`
- `docs/office/care_home_handover_checklist.md`
- `docs/office/care_home_onboarding_script.md`
- `docs/public/07_resident_participation.md`
- `docs/public/15_mobile_training_instructions.md`
- care-home contracts and DPA templates

These documents may need clearer headings saying they apply to Stage 4 Care Home Office, not at-home stages.

### 3. Stage 4 Family Coordinator guidance

Planned later. Do not write as care-home operations.

Use this wording:

- Family Coordinator Office
- Family Coordinator Mobile
- family-side workspace
- wider family
- visits
- questions for the care home
- practical help
- no connection to Care Home Office

Avoid:

- care-home staff workflow
- room management
- resident admin
- care-home responsibility for the family workspace

Future documents needed:

- Family Coordinator Office guide
- Family Coordinator Mobile guide
- Family-side Family Hub guide
- Family Coordinator FAQ
- Family Coordinator workspace privacy/boundary note

## Public and legal documents

Public, privacy, terms, safeguarding, and contract documents should not be casually rewritten during UI wording work.

They need a separate legal/data-protection review because the current documents often assume a care-home customer/controller model.

Before any real pilot or payment, prepare a legal review pack covering:

- at-home stages
- Stage 4 Care Home Office
- future Stage 4 Family Coordinator workspace
- data controller / processor positions for each context
- disclaimer wording
- privacy notice variants
- terms of use variants

## Rewrite order

1. High-traffic in-app docs and help pages.
2. At-home user guides based on `docs/circle`.
3. Stage 4 care-home docs with clearer Stage 4 headings.
4. Future Family Coordinator docs after the workspace design is stable.
5. Legal/privacy/terms after product boundaries are stable and before real users.
