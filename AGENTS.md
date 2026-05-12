# familyupdates.care - AGENTS.md

## Product Direction

familyupdates.care is now the active product direction.

The live app should focus on a family-side coordination system, centred on a Family Organiser / Family Office. It begins when ordinary direct family communication is no longer enough.

The original care-home and voice-message system must be preserved where useful, but it should not shape the public product, onboarding, default routes, or family-facing copy unless a care-home-specific mode is deliberately being worked on.

See `docs/internal/product_direction_note.md` for the transition note.

## Core Product Rules

- One current item replaces the previous item in that channel.
- No threads.
- No archive.
- No live chat.
- No response-time pressure.
- No push or instant reply notifications.
- No delivery confirmations, read receipts, typing indicators, or live status.
- No system-generated timestamps in Family-facing or Mobile-facing communication views.

Internal audit timestamps may exist for security/compliance but must not become visible performance metrics.

## Active Family Model

The main live model is:

- Family Office: used mainly by the Family Organiser.
- Family Hub: used by wider Family Members.
- Mobile: reduced-tool interface for a carer, helper, supported person, or trusted family member.

The Family Organiser uses Office tools to keep current updates, requests, noticeboard information, and simple one-current-message channels manageable.

Mobile is part of the starting family model. If a Family Organiser is needed, the app should make room for a carer/helper/professional support role where appropriate, rather than implying the organiser should absorb caring work.

Mobile may reuse stable Care Hub Mobile code, but public/user-facing wording should fit the at-home family context unless explicitly working on the archived care-home product.

The active family situations are:

1. At home with Family Organiser + Mobile Support.
2. Care home with Family Organiser + Mobile Support.

There is no active "managing independently" app situation. In the care-home situation, familyupdates.care remains family-side and does not become the care home's operational system.

## Care-Home Code

Do not delete stable care-home code just because the public product has moved.

Care-home functionality may be useful later and should be archived, hidden, locked, or left internal/dev-only where appropriate. Prefer low-risk relabelling and routing changes over broad rewrites.

Internal identifiers such as `care_home`, `resident`, `office`, `mobile`, or older table names may remain if changing them would create risk without user-facing benefit.

## Public Pages and Documents

Canonical public copy comes from `PLANS.md`.

If public or in-app help copy needs changing, update `PLANS.md` first, then implement.

Public pages should present familyupdates.care as a Family Organiser / family coordination product, not as a care-home voice-message service.

## Governance and Boundaries

Keep the product calm, minimal, and non-urgent.

The app must not imply:

- emergency use
- live monitoring
- guaranteed reply times
- staff performance monitoring
- clinical/care record management
- safeguarding or complaint handling inside the app

Urgent, medical, safeguarding, legal, financial, private, or time-critical matters must stay outside the app and use normal direct contact routes.

## Implementation Approach

- Prefer small, high-confidence changes.
- Reuse stable code where it fits the Family Office / Family Hub / Mobile model.
- Hide or lock old care-home public surfaces before rewriting internals.
- Avoid risky database/code renames unless there is a clear user-facing or operational need.
- Keep features bounded; do not introduce engagement features that create pressure.
