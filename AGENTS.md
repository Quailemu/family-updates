# voice-message.com — AGENTS.md (persistent instructions for Codex)

## Product identity (locked)
- Brand line: **voice-message.com — One message in. One message out.**
- Core rule: Only the most recent message from each sender is retained. A new message replaces the previous message from that sender. No message history / archive.

## Non-real-time (critical)
- This is NOT a real-time conversation product.
- NO push or instant reply notifications.
- NO delivery confirmations, read receipts, typing indicators, live status.
- Families must not expect replies; care home fits playback/recording around routines.

## No visible timestamps (critical)
- Do NOT show system-generated timestamps in the Family app.
- Do NOT show system-generated timestamps in Care Hub – Mobile.
- Internal audit timestamps may exist for security/compliance but must not become “performance metrics”.

## Role separation (hard rule)
Single codebase with three hard-locked variants only:
- Family
- Care Hub – Mobile
- Care Hub – Office
No cross-access. No fallback routes. No “mixed” UI.

## Governance boundaries (must be reflected in docs + UX)
- Care home is responsible for: safeguarding, consent/capacity suitability, regulatory compliance, staff supervision, content management (including inappropriate family messages), device security, operational decisions.
- Platform provides communication infrastructure only.
- Platform is not monitored in real time and does not moderate/screen/approve message content.

## Public pages and documents (must stay consistent)
Homepage banner: 
- voice-message.com
- One message in. One message out.
Optional small line: No threads. No pressure.
Homepage buttons (only):
- Family
- Care Hub – Mobile
- Care Hub – Office

## Pricing (public)
- Pilot: £75 + VAT (one-time), credited against first month if continuing
- Monthly subscription: flat per care home
  - Up to 50 residents: £195 + VAT / month
  - 51+ residents: £295 + VAT / month
- Invoiced monthly in advance
- Activation only after payment received

## Contract model (care home is customer)
- 30-day pilot
- Converts to monthly subscription
- Minimum 3 months post-pilot
- Suspension clause: provider may suspend immediately where reasonably necessary for security/legal compliance/serious misuse/safeguarding or reputational risk.
- Data: UK hosting, controller=care home, processor=platform
- Data deletion: delete personal data within 30 days after termination (align backups/rotation accordingly)

## UX copy requirements (important)
- Family UI must clearly state: “Not a live service. Messages are played when staff are available.”
- Avoid any copy implying response time guarantees.
- Avoid anything that encourages urgency or monitoring behaviour.

## Implementation approach
- Prefer small, high-confidence changes.
- Keep features calm, minimal, and governance-safe.
- Do not introduce “engagement” features that add pressure (notifications, receipts, timestamps, analytics).

## Canonical copy
When building public pages or in-app help text, use the exact wording in PLANS.md as the source of truth. If copy must be changed, update PLANS.md first, then implement.
