# Product Direction Note

## Current Direction

familyupdates.care is now the active product.

The app is being repositioned away from the original care-home voice-message product and toward a family-side coordination system. The entry point is when ordinary direct family communication is no longer enough.

The product is no longer primarily about voice messages in a care home. It is about family coordination around care, with one current item in each channel and no threads or archive.

## Why This Matters

The original app was built for a care-home setting. Later, family coordination outside the care home was added. The current plan is to focus on the family use case first because it is easier to understand, easier to adopt, and does not require the full care-home governance model at the public entry point.

This does not mean the care-home work is wasted. The underlying structure remains useful:

- Office can become Family Office for the Family Organiser.
- Family Hub can remain the wider family interface.
- Mobile is the reduced-tool interface for a carer, helper, supported person, or trusted family member.
- The one-current-message model still applies.

Mobile is part of the starting family model, not a cosmetic later add-on. If a Family Organiser is needed, the system should also make room for support from a carer/helper/professional where appropriate. The app should reduce pressure on the Family Organiser, not turn them into the default carer.

The active situations are:

1. At home with Family Organiser + Mobile Support.
2. Care home with Family Organiser + Mobile Support.

There is no active "managing independently" app situation. If the person or couple is managing independently with ordinary direct communication, they may not need familyupdates.care.

In the care-home situation, familyupdates.care remains family-side. The care home handles direct care, safeguarding, and operational communication. The family still coordinates visits, outside appointments, belongings, questions, family occasions, outings, friends, and family updates.

## What To Preserve

Keep stable care-home-era code where it still supports the new model or may be useful later.

Do not rewrite working internals simply to rename everything. Internal names such as `care_home`, `resident`, `Care Hub`, `office`, `mobile`, or old database fields may stay if changing them would add risk without improving the user-facing product.

Care-home-specific features should be preserved, archived, hidden, or locked rather than casually deleted.

## What To Change First

Prioritise visible product alignment:

- public homepage and public documents
- onboarding and help text
- default routes and public navigation
- Family Office / Family Hub / Mobile labels
- wording that still implies a care-home-first product
- wording that still implies voice-message.com or voice-message-only use

Public-facing copy should make familyupdates.care feel like a Family Organiser / family coordination tool.

## What To Avoid

Avoid visible copy that makes the live product feel like:

- a care-home operational platform
- a resident playback workflow
- a voice-message-only service
- live chat or urgent messaging
- a monitoring or notification system
- a clinical, safeguarding, legal, or financial record system

Avoid broad code/database renames unless they are necessary. The first objective is product clarity with minimal technical risk.

## Working Rule For Codex

When reviewing or changing code, classify old care-home/voice-message elements as:

1. Keep and relabel if stable code supports Family Office, Family Hub, or Mobile.
2. Hide or lock if it is care-home-only and not part of the current public familyupdates.care product.
3. Archive docs/copy if useful later but misleading now.
4. Leave internal if renaming would create risk without user-facing benefit.

Use `PLANS.md` as the canonical source for current public and in-app copy.
