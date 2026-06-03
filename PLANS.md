# PLANS.md â€” Canonical Copy (source of truth)

Reference: `docs/security/SECURITY_MODEL.md` (final security/login model)

## Current product direction - streamlined Family version

familyupdates.care is now focused on the family-side coordination system: Family Office, Family Hub, and Mobile Support.

The trigger is not age, diagnosis, or a care-home move. The trigger is when a person becomes temporarily or permanently unable to manage part of their own life, ordinary direct family communication is no longer enough, and one family member or trusted friend becomes the organiser or primary point of contact.

Examples include elderly parents needing support, dementia, serious illness, recovery after surgery, stroke, accident or injury, temporary incapacity, long-term disability, mental health crisis, and other situations where family or friends need to coordinate support around one person.

Current active situations:

1. At home with Family Organiser + Mobile Support.
2. Care home with Family Organiser + Mobile Support.

There is no active "managing independently" app situation. familyupdates.care is for situations where family coordination is needed because normal direct communication has started to overload one organiser and essential information is getting lost in chat.

The Family Organiser role is a coordination role, not a default unpaid caring role. If a Family Organiser is needed, the system should also make the practical support role visible through Mobile Support. Mobile Support may be a paid carer, professional support worker, spouse, family member, neighbour, or trusted helper. If a family member uses Mobile, they are acting in a distinct support role, not simply as a Family Member.

In the care-home situation, familyupdates.care remains family-side. The care home handles direct care, safeguarding, and operational communication. The family still coordinates visits, outside appointments, belongings, questions, birthdays, Christmas, Easter, other occasions, outings, meeting friends, social contact, and family updates.

The live product offer is:
- one current family update
- one current specific Family Organiser message
- one current practical request with structured replies
- one current noticeboard note per Family Member
- no threads, no archive, no live chat
- no family communication archive for the organiser to maintain
- no family-to-dependent voice messages
- no dependent-to-family voice messages
- no care-home mobile/playback workflow

The earlier care-home/voice-message system is archived as a possible later product and should not drive the public app, onboarding, or at-home Family user interface.

## Homepage banner (public)
familyupdates.care
One message in. One message out.
(Optional small line) No threads. No pressure.

Homepage buttons (only):
- Family

Canonical interface sentence:
The platform has three active family interfaces: Family Office, Family Hub, and Mobile Support.
The Family system may continue when a person is living in a care home, but it remains a family-side coordination system. It does not connect to a care home.

Architecture decision:
Build the streamlined Family system first. The archived care-home/voice-message system must not add visible complexity to the Family product.

User-facing help rule:
Use short, plain-language, outcome-led explanations. Do not show system diagrams, walkthrough videos, or screen recordings in the app. Diagrams and recordings may be kept as internal product/design references only.

Homepage public info copy (before feedback section):
## Familiar voices
A structured, non-urgent family coordination system for when one person becomes the point of contact.

familyupdates.care keeps essential family coordination separate from chat.

There are three roles for the family to fill:

1. Family Organiser.
2. Person available for urgent/emergency phone contact and emergency protocol.
3. Care support.

familyupdates.care is for non-urgent coordination only.

The app provides one current update to family, one current specific organiser message, one current practical request, and noticeboard-style information. The Family Organiser has full access to the family tools; Family Members and carers can use their own enabled channels directly. One current item replaces the last, with no threads, no archive, no direct replies to the general update, and no pressure to reply instantly.

Families use the app when repeated updates, questions, and practical coordination have started to create communication overload for the organiser. Carers may use the app directly where enabled, or text the Family Organiser. Care homes may email. The Family Organiser tells the family when and how frequently they will check messages.

Emergencies follow the agreed protocol, otherwise all messages are treated as non-urgent.

## A simple way to explore the idea
familyupdates.care can be introduced through a simple one-to-one walkthrough.

The session uses a simple example family update, practical request, and noticeboard note, introducing the idea in a natural way.

There is no obligation to adopt anything, simply an opportunity to see how this might help communication for you.

Non-real-time reinforcement (homepage or family entry page, short):
This is non-urgent and not live messaging. Messages are checked at agreed intervals.

Family security session statement (family-facing, short):
For security, Family sessions sign out after 30 minutes of inactivity. If signed out, request a new secure email link.

Family preparation statement (family-facing, short):
Keep updates short, practical, and non-urgent.

No notifications / date-only statement (family-facing, short):
The service does not send live notifications. Main care communication views show message date only (no clock time).

Transcript assist statement:
Transcript assist belongs to the archived care-home/voice-message product. It should not drive the current familyupdates.care public app.

Role-based access:
Family Office, Family Hub, and Mobile Support are separate, role-based experiences.

Playback and control statement:
Each role sees only the channels intended for that role. Each current item may only be replaced from the interface that created it.

Office update statement:
Family updates are sent from Family Office to keep the wider family informed. Updates are one-way and are for non-urgent, non-medical information only.

Office practical messages are optional structured requests linked to the person being supported (for example visits, attendance, reminders, belongings, outside appointments, or item requests). Family Members and Mobile Support can reply where enabled with a minimal structured response (No response / Yes / No / Maybe), optional fixed tick-box options, and an optional short context note. This is still non-urgent and not live messaging.

Family noticeboard notes are optional practical notes from Family Members, visible to all linked Family Members and to the relevant Office workspace. Each Family Member has one current noticeboard note per person. A new note replaces that Family Member's previous note, and the note may be cleared when no longer useful. Noticeboard notes are for practical coordination only, not private health, care, legal, financial, safeguarding, or urgent matters.

For urgent, medical, safeguarding, or other time-sensitive matters, families must use normal direct communication outside familyupdates.care.

Service overview purpose statement:
familyupdates.care is a simple family coordination system for situations where one person has become the family point of contact. It helps a Family Organiser keep one current family update, specific organiser messages, practical requests, and noticeboard notes current without creating live chat, long threads, or a permanent communication archive.

Family Office updates are one-way informational messages.

Family Office may also publish a practical message that allows each registered Family Member or Mobile Support user, where enabled, to send a structured non-urgent reply (No response / Yes / No / Maybe, optional fixed tick-boxes, and an optional short context note).

Where enabled, Family Members may also add one current family noticeboard note for practical coordination. Noticeboard notes are visible to linked Family Members and the relevant Family Office workspace, and are not private messages.

The service is not intended for care updates, health information, safeguarding communication, or urgent enquiries.

Data boundary (hard):
- The platform is for non-urgent communication and coordination only.
- The platform does not store or manage sensitive records or document repositories.
- Users must handle sensitive matters outside the platform using their own external arrangements.
- The platform may provide minimal planning guidance only and does not provide legal, medical, financial, or safeguarding advice.

Short in-app data boundary copy:
Keep sensitive records outside the app. Use this only for simple communication and coordination.

Must not store in-platform:
- Legal authority documents (including LPA/LPOA forms and extracts).
- Clinical records, medication/treatment records, or formal care records.
- Financial account, investment, tax, pension, or transaction records.
- Identity documents or identity numbers.
- Safeguarding investigation files/evidence.
- Carer Pack files/documents.
- Authentication secrets (passwords, PINs, recovery codes, private keys).

Essential platform data only:
- Account, role, and access mapping data.
- Resident/contact linkage needed for routing.
- Latest-message channel state required for "one message in, one message out."
- Minimal operational metadata and security/audit logs needed to run the service.

## How familyupdates.care Works

familyupdates.care helps structure communication when someone needs support and one family member or trusted friend has become the organiser.

It is for moments when a person becomes temporarily or permanently unable to manage part of their own life, for example elderly parent support, dementia, serious illness, recovery after surgery, stroke, accident or injury, temporary incapacity, long-term disability, mental health crisis, or another situation where family and friends need to coordinate around one person.

There are three roles for the family to fill:

1. Family Organiser.
2. Person available for urgent/emergency phone contact and emergency protocol.
3. Care support.

familyupdates.care is for non-urgent communication only.

familyupdates.care keeps communication current, and as in real life conversation there are no threads or stored history, just one message at a time.

Families use the app for non-urgent support management: structured requests, updates, noticeboard-style information, and simple current messages. The Family Organiser gets the app, introduces it to Family Members, and tells the family when and how frequently they will check messages.

familyupdates.care does not remove the need for care, support, or professional help. But where repeated updates, questions, and practical coordination are adding to the organiser's strain, it can help by making communication calmer, more current, and more bounded.

Emergency and everyday communication:
Emergencies: follow the agreed emergency protocol, then phone the agreed emergency contact.

Emergencies follow the agreed protocol, otherwise all messages are treated as non-urgent.

Families use the app for everyday communication. Carers may use the app directly where enabled, or text the Family Organiser. Care homes may email. The Family Organiser has full access to the family tools; Family Members and carers can use their own enabled channels directly.

All messages shown in the app are current messages.

What the app does:
- One current update from the Family Organiser to the family group.
- One current specific message each way between the Family Organiser and each Family Member.
- One current update/request each way between the Family Organiser and Mobile Support, if required.
- One practical request from the Family Organiser, with structured responses from Family Members.
- One current noticeboard note from each Family Member, visible to the family group.

Each person's new message replaces their own previous message in that channel. One sender does not overwrite another sender's message. There are no threads, no archive, and no live chat.

Family Organiser role boundary:
The Family Organiser is not agreeing to be available all the time, solve everything, or act as everyone's private messenger. The Family Organiser is offering to keep a small number of family communication channels current. The general update is not a discussion thread and does not take direct replies.

familyupdates.care is for situations where family coordination is needed. It has the core tools needed for non-urgent support management: updates, specific organiser messages, practical requests, noticeboard-style information, and Mobile Support.

### Where the app may be used

There are two settings: at home, and care home.

* **At home with Family Organiser + Mobile Support** - The person is at home and family coordination has become necessary because support, questions, updates, or practical arrangements now need one clear point of coordination and can get lost in chat. The Family Organiser coordinates communication. Mobile Support is used by the person providing practical support, paid or unpaid.
* **Care home with Family Organiser + Mobile Support** - The person is living in a care home, but family organisation continues. The care home handles care operations. familyupdates.care handles family-side non-urgent focussed communications where needed.

### Notes

*Mobile Support: a distinct practical support role. It may be paid or unpaid, but it is separate from the Family Organiser role and from ordinary Family Member access.*

## Starting simply

In preparation for using the app, your external filing system should be organised and for data security use your own secure file management and storage system. The information should be organised, separated, and accessible to the right person when needed. The six files we recommend that you prepare are:

Once the external filing system is in place, start small: one calm update to registered Family Members. There are no replies in that update channel, no thread, and the next update replaces the previous one.

Then add only the communication tools that are useful: specific organiser messages to individual Family Members, practical requests, family noticeboard notes, and structured replies.

Where family noticeboard notes are enabled, each Family Member may keep one current practical note visible to the family group. This is for simple coordination, such as visits or items to bring. It is not a private notes area and must not be used for sensitive health, care, legal, financial, safeguarding, or urgent matters.

There are two settings: at home, and care home.

Targeted request boundary:
Requests and structured replies are for non-urgent, non-essential coordination only. Family requests remain visible to all linked Family Members and may name an intended responder, such as Sarah, Tom, or Coordinator. Office-to-Mobile/carer requests are a separate working channel where enabled. Replies use fixed structured choices, optional fixed tick-boxes, and an optional short context note only: no private chat, no threads, and no back-and-forth conversation. Essential, urgent, sensitive, or time-critical matters should use normal direct communication outside familyupdates.care, such as phone, text, WhatsApp, email, or existing care-home channels.

Family noticeboard boundary:
Noticeboard notes are transparent practical notes, visible to linked Family Members and the relevant Office workspace. Each Family Member has one current note per person/resident. Noticeboard notes must not be used for private health, care, legal, financial, safeguarding, or urgent matters.

Lifecycle model:
The app uses two active situations to describe the real-life setting. Situation policy controls visible framing; it must not assign fixed role ownership.
The user should choose the situation, not a separate organisation mode. Preparation of documents and information sits outside the app. It is not an active app communication situation. Planning & Organisation guidance belongs in the Life File Guide and other help areas only.

- Preparation of documents: this is not an active app communication situation. It is the external filing system step: Life Log, Contacts, Admin and Key Documents, Private Finance, Private Health Notes, and Carer and Housekeeping Notes. The files remain outside familyupdates.care.

Both situations use the same Family system principles: one current message, no threads, no live chat, and practical structured replies where helpful. Family Office coordinates the family-side work. Mobile Support is the distinct practical support role and may be used by a paid carer, professional support worker, spouse, family member, neighbour, or trusted helper.

- At home with Family Organiser + Mobile Support: this is for when the person is at home and family coordination has become necessary because essential information is getting lost in chat. The Family Organiser coordinates communication; Mobile Support is used by the person providing practical support.
- Care home with Family Organiser + Mobile Support: this is for when the person is living in a care home, but family organisation continues. The care home handles care operations, safeguarding, and direct care communication. familyupdates.care handles family-side non-urgent focussed communications where needed.

Care-home separation rule:
The care home and Family Organiser remain separate. They may relate to the same real-life person, but care-home operational systems do not connect to the familyupdates.care Family Office.

This means:
- No shared inbox between the two offices.
- No shared requests.
- No shared updates.
- No shared admin tools.
- No cross-access.
- No care-home data visible in the Family Organiser Office.
- No Family Organiser Office data visible in the Care Home Office.
- No handover workflow or internal linking between them.

The care home belongs to the care organisation and its operational responsibilities. The Family Organiser Office belongs to family-side coordination only.

Care-home wording:
Care-home operational systems should use care-home wording and the actual care home name. Do not label care-home operations as the person's family workspace.

The Family Organiser Office should use its own separate Organiser/family workspace name, for example "Hill family coordination" or "David's family coordination". It should not use the care home name, and it should not use the person's home name. It is for the organiser and family, not for the care home, and it must not connect to the Care Home Office.

Care-home situation mobile separation:
- Mobile Support belongs to the family-side workspace, not the care-home workspace.
- Mobile Support may support quick family updates, visit updates, and simple family coordination requests.
- Mobile Support must not connect to care-home operational data.
- Care-home tools and family-organiser tools may use similar UI patterns, but they are separate products/workspaces.

Care-home situation family-side purpose:
The Family Organiser Office and Mobile Support exist to help the wider family help out. They should make it easy to share one update with everyone, coordinate visits or practical help, and reduce pressure on one overloaded organiser. They must not duplicate care-home operations.

Family Organiser workspace architecture:
This should not be built by extending care-home operational tables/workflow unless there is a deliberate separation layer.

Purpose:
The Family Organiser workspace helps the family coordinate around someone now living in a care home. It is not a care-home tool and is not connected to the Care Home Office.

Planned interfaces:
- Family Organiser Office: used by the main organiser or family admin person. It may send family updates, create simple family coordination requests, review structured replies, and manage family-side contacts.
- Mobile Support: used by the person providing practical support, paid or unpaid, for quick family-side updates during visits, errands, or conversations.
- Family Hub: family members receive and respond where enabled using the same calm, non-live, latest-message-only model.

Possible family-side channels:
- Organiser/family update to all family.
- Visiting family/mobile update to all family.
- Mobile Support update to all family.
- Simple family coordination request.
- Structured replies visible to the Organiser/family workspace.

Hard boundaries:
- No care-home resident list.
- No room numbers.
- No care-home admin tools.
- No care-home staff workflow.
- No Care Home Office inbox.
- No Care Home Mobile connection.
- No handover workflow.
- No shared requests, updates, or messages with the Care Home Office.

Preferred data direction:
Reuse stable workspace patterns where practical rather than creating a reduced family-only system. The Family system and any archived/future care-home system must remain separate and must not share inboxes, requests, updates, settings, contacts, people/residents, or operational data.

Workspace label policy:
- Every workspace should resolve to one workspace type: Family system or Care Home system.
- Family system labels: Family Office, Mobile Support, Family Hub, person/people, Family Organiser, no room field.
- Care Home system labels: Care Home Office, Care Home Mobile, Care Home Family Hub, resident/residents, care home coordinator, room field visible.
- Product behaviour should stay functionally identical unless an Operational Variable deliberately switches a feature off.
- Avoid scattered wording conditionals. Use one central workspace-label policy so the same feature can render correctly in either system.

Mobile channel principle:
Mobile Support is the simple in-the-moment channel for the distinct practical support role. It may be used by a paid carer, professional support worker, spouse, family member, neighbour, or trusted helper. If a family member uses Mobile Support, they are acting in that distinct support role rather than ordinary Family Member access.
Mobile Support may send shared updates and structured practical requests where enabled. This is useful when the person providing practical support can ask the wider family for help without routing every request through the Family Organiser.

At-home setup model:
For the at-home situation, the visible setup should be a home/person setup, not a care-home setup. Reuse existing backend tables where practical, but label the UI as Setup name, Person 1, Person 2 optional, and Main supporter / organiser.

Situation wording:
When the at-home situation is active, avoid visible "Care organisation", "Care Home", and "Resident" framing where the context is at-home coordination. Prefer "shared at-home coordination" and "person/people" wording while keeping the existing backend routing intact.
Prefer "shared update", "shared request", "shared coordination", and "[Surname] Family Office" wording over care-home Office wording where the user is doing routine at-home coordination.

At-home How it works copy:
familyupdates.care helps structure communication when someone needs support and one family member or trusted friend has become the organiser.

It is used when ordinary direct family communication is no longer enough because repeated updates, questions, or practical coordination are creating communication overload for one organiser.

There are three roles for the family to fill:

1. Family Organiser.
2. Person available for urgent/emergency phone contact and emergency protocol.
3. Care support.

familyupdates.care is for non-urgent coordination only.

The external filing system should be organised first, before starting updates. familyupdates.care does not store those files.

Once the external filing system is in place, users can start with one calm current update to registered Family Members. There are no replies in that update channel, no thread, and the next update replaces the previous one.

Add only the communication tools that are useful: family updates, specific organiser messages, practical requests, noticeboard notes, structured replies, and Mobile Support where a practical support role is involved. One message replaces the last message in that channel.

At home uses [Surname] Family Office, Mobile Support, and Family Hub. Mobile Support makes the practical support role visible from the start of the app model. What changes over time is the setting, not a new technical system.

Private notes and records stay outside familyupdates.care, in the person's or Family Organiser's own filing system.

Use "[Surname] Family Office" for the main at-home message area when a surname is available, for example "Hill Family Office". Use "Family Office" as the fallback.

Documentation boundary:
The original care-home documentation is archived as possible later product material. Do not dilute it into at-home wording and do not let it drive the current public app.

The active Family product needs a smaller separate help set. Do not show the full care-home Office documentation pack unless a page has been rewritten for familyupdates.care. Family guidance should focus on simple messages, shared coordination, registering family/contact access, Life File Guide, practical requests, and Mobile Support where enabled.

Office model shorthand:
Single -> Shared -> Split.

Life File Guide (in-app help):
The Life File Guide explains a simple external notes/files approach. It should help users organise important information outside the app, using paper, computer files, or phone notes.

Canonical Life File Guide copy:
Use this guide to organise important information outside the app. Paper, computer files, and phone notes are all fine.

The important point is that information is organised, accessible to the right person when needed, and separated so private information is not shared by accident.

This is preparation before family coordination becomes difficult. This external filing system helps the person stay independent for longer, reduces family friction, and avoids important information being sorted out in a rush.

The app may suggest the file structure, but the files themselves remain in the person's or Family Organiser's own external system.

familyupdates.care does not store the contents of notebooks, documents, medical records, financial records, legal documents, care logs, passwords, or private long-form notes.

Keep private information separate from practical information that a carer, helper, or family member may need.

Do not put medical records, financial records, legal documents, passwords, care logs, or private long-form notes into familyupdates.care.

Suggested external file names:
- 1. [Person's name] - Life Log
- 2. [Person's name] - Contacts
- 3. [Person's name] - Admin and Key Documents
- 4. [Person's name] - Private Finance
- 5. [Person's name] - Private Health Notes
- 6. [Person's name] - Carer and Housekeeping Notes

Use plain names that explain who the file is about and what it contains, so the right file can be found quickly on a computer or phone.

Sharing principle:
Share only what is needed. A carer may need practical housekeeping notes. They should not normally need private finance, private health, or key document information.

Legal / professional advice boundary:
familyupdates.care may suggest that users organise authority contact details and consider whether formal authority, such as financial or health/welfare LPA, LPOA, or similar arrangements, is relevant. It must not give legal or financial advice. Use wording such as "you may want to", "where relevant", and "seek professional advice where needed." Do not say the app requires any authority document.

Use gentle optional wording:
- "you may want to"
- "suggested items"
- "useful additions"
- "when needed"

Avoid:
- "required"
- "mandatory"
- "must complete"

Life File Guide sections:
- Life Log: day-to-day notes and observations; changes in health or mood; missed medication or concerns; appointment notes; things to remember; questions for family, GP, or carer; emergency contacts.
- Contacts: family and close contacts; GP / doctor; pharmacy; dentist, optician, audiology, or other regular services; carer, cleaner, gardener, or trusted helper; emergency contacts; solicitor, accountant, financial adviser, or other professional contacts.
- Admin and Key Documents: where important documents are kept; property, tenancy, insurance, pension, benefit, and utility references; solicitor / LPA or LPOA contact details; who is authorised to help with admin; renewal dates, reference numbers, and useful instructions; do not include passwords or full identity document copies.
- Private Finance: bank, pension, investment, and benefit overview; bills, subscriptions, direct debits, and regular payments; insurance and tax information; financial adviser and bank contact details; who has financial LPA/LPOA or similar authority, where relevant; keep detailed statements, account numbers, passwords, and access codes secure and separate.
- Private Health Notes: health summary and key conditions; current medication list; allergies and important risks; appointments, questions, and observations; GP, pharmacy, hospital, and clinic contacts; who has health and welfare LPA/LPOA or similar authority, where relevant; keep formal medical records outside familyupdates.care.
- Carer and Housekeeping Notes: first page with important information for helpers; emergency contacts; house access instructions; allergies; medication schedule summary; daily routine; mobility / falls risk notes; food and drink preferences; housekeeping notes, deliveries, bins, pets, or keys; what to do if something changes.
- Authority and professional advice: you may want to consider whether formal authority, such as financial or health/welfare LPA, LPOA, or similar arrangements, is relevant; people coordinating care or paid support may need to know who has authority to make decisions or arrange costs; keep authority documents outside familyupdates.care and share only with people who need them; this is not legal or financial advice; seek professional advice where needed.
- If a care home becomes involved: care home contact details; Family Organiser contact; preferences and routines; financial / admin contacts; visiting arrangements; important family updates; notes of care home meetings; questions for care home staff.

Internal diagram/video reference rule:
System diagrams and recordings are internal product/design references only. Keep reference assets in `assets/` when useful for coding and product thinking, but do not expose them in normal user-facing app help.

---

## Pricing page (public)
# Pricing
Simple, transparent pricing per care home.

## Pilot Programme
We offer a structured 30-day pilot to allow care homes to evaluate the service within their setting.

**Â£75 + VAT one-time pilot fee**

â€¢ Formal agreement required
â€¢ 30-day duration
â€¢ Credited against the first monthâ€™s subscription if continuing
â€¢ Access activated once payment is received

## Monthly Subscription
A flat monthly subscription per care home.
No per-message fees. No hidden charges.

### Up to 50 residents
**Â£195 + VAT per month**

### 51+ residents
**Â£295 + VAT per month**

â€¢ Minimum commitment: 3 months following pilot
â€¢ 30 daysâ€™ written notice thereafter
â€¢ Invoiced monthly in advance
â€¢ Access activated once payment is received

## Whatâ€™s Included
â€¢ Family access
â€¢ Care Home Mobile access
â€¢ Care Home Office access
â€¢ Secure hosting
â€¢ Ongoing platform availability
â€¢ Technical support for platform-related issues

## Important
familyupdates.care provides a communication platform.
Each participating care home remains responsible for care delivery, safeguarding, and regulatory compliance.

---

## Complaints & Concerns page (public)
# Complaints & Concerns
We take concerns seriously and aim to respond promptly and fairly.

## 1) Concerns relating to care or platform use within a care home
familyupdates.care provides a communication platform to care homes under a subscription agreement.

Each participating care home is responsible for:
â€¢ Care delivery and safeguarding
â€¢ How the platform is used within their service
â€¢ Staff access, supervision, and training
â€¢ Responding to families through the platform
â€¢ Local governance and regulatory compliance

If your concern relates to care, staff conduct, safeguarding, or how the platform is being used within a specific care home, please contact the care home directly in the first instance.

The care home remains responsible for operational decisions and oversight.

## 2) Concerns relating to the familyupdates.care service
If your concern relates to:
â€¢ Access or login issues
â€¢ Technical faults
â€¢ System errors
â€¢ Data protection queries
â€¢ Contract or subscription matters

You may contact familyupdates.care directly.

Email: hello@familyupdates.care

## 3) What happens next
For platform-related complaints, we will:
â€¢ Acknowledge your complaint within 2 working days
â€¢ Review the matter promptly
â€¢ Provide a response within 10 working days where possible

If more time is required, we will explain why.

Where appropriate, we may liaise with the relevant care home.

## 4) Important clarification
familyupdates.care does not:
â€¢ Provide care services
â€¢ Supervise care home staff
â€¢ Make care decisions
â€¢ Replace a care homeâ€™s own complaints process

The care home remains responsible under its own regulatory framework.

---

## Care Home Office page (public info path)
# Care Home Office
Oversight and administrative control for participating care homes.

## Purpose
Care Home Office provides management-level access to the familyupdates.care platform within your service.

It supports oversight of how the platform is used, while maintaining the care homeâ€™s existing governance framework.

## How the Platform Operates
The messaging system uses two types of channels linked to each resident: two-way contact channels and a one-way Office update channel.

Channel directions:
- Family/Friend -> Resident (created/replaced in Family Hub)
- Resident -> Family/Friend (created/replaced in Care Home Mobile)
- Office -> Family/Friend (created/replaced in Care Home Office)

Each channel keeps only the latest message.
When a new message is sent in a channel, the previous message in that channel is replaced.

Messages in a contact channel may only be played by users designated by the care home for that specific channel. Other family members, friends, or other individuals designated by the care home cannot access those messages. Care home staff using Care Home Mobile and Care Home Office may also play messages for operational support.

This structure helps keep communication simple and manageable within care settings.

## Management Functions
Care Home Office allows personnel designated by the care home to:
â€¢ Manage staff access
â€¢ Enable or disable resident participation
â€¢ Monitor platform usage
â€¢ Maintain oversight of subscription status

Access is restricted to management users designated by the care home.

## Governance Position
familyupdates.care provides a communication platform.

The care home remains responsible for:
â€¢ Care delivery and safeguarding
â€¢ Regulatory compliance
â€¢ Staff conduct and supervision
â€¢ Decisions regarding resident participation
â€¢ Responding appropriately to family messages

The platform does not replace the care homeâ€™s own policies, safeguarding systems, or complaints procedures.

## Subscription & Agreement
The service is provided under a formal Subscription Agreement.

The current version of the Care Home Subscription Agreement is available here:
**Care Home Subscription Agreement â€“ Version 1.0**
(Download link)

## Support
Platform-related support is available via email.
Care-related concerns should be addressed through the care homeâ€™s own procedures.

---

## Family and Friends Guide (public info path)
# Family and Friends Guide

## Purpose
This guide explains how familyupdates.care is used for simple, non-urgent social messages between residents and their family or friends.

It sets out how the service works and its intended use.

## App Version
Families and friends use the **Family Hub only**.
The Family Hub does not include Care Home system features.

## How the Service Works

### Sending a voice message
You can record a short audio message for the resident.

This is not a live service. Messages are played when staff are available, to fit around care routines.

For security, Family sessions sign out after 30 minutes of inactivity. If signed out, request a new secure email link.

Plan your message before recording. Most messages only need a few seconds.

### Receiving a reply
Residents can record a reply when appropriate support is available.

Replies are not immediate, and timing will vary depending on care home routines.

### Message replacement
The service operates on a channel-based â€œone message in, one message outâ€ structure.

Family/Friend -> Resident and Resident -> Family/Friend are separate directions.
Office -> Family/Friend is an additional one-way direction.

Each channel keeps only the latest message.
When a new message is sent in a channel, the previous message in that channel is replaced.

There is no message history or archive within the service.

The service does not send live notifications. Main care communication views show message date only (no clock time).

## Intended Use
The service is for non-urgent, social messages.

It is not designed for care updates, medical information, safeguarding concerns, or complaints about care.

For those matters, please contact the care home directly.

## Access and Use
Access is managed by the care home.
Each individual uses their own access credentials.
The service is not a monitored care communication channel.

## Privacy in a Care Setting
Messages are used within a care home environment.
Staff may assist residents with listening to or recording messages.
Messages may be played in shared spaces and are not guaranteed to be private.

## Further Information
For information on consent and safeguarding responsibilities, refer to the Safeguarding and Consent section.

---

## Care Home Mobile Guide (public info path)
# Care Home Mobile Guide

## Purpose
This guide explains how Care Home Mobile is used within the care home to support residents in sending and receiving simple, non-urgent voice messages.

## App Version
Care Home Mobile is used by staff designated by the care home on care home devices.
It does not include Office-level administrative features.

## How the Service Works

### Listening to a family message
When a family member sends a voice message, the most recent message becomes available for the resident to hear.
Staff may assist the resident with playback where appropriate.

### Recording a resident reply
Staff may assist a resident in recording a reply.
Once recorded, that reply replaces the previous reply from the resident.

### Message replacement
The service operates on a channel-based â€œone message in, one message outâ€ structure.
Each channel keeps only the latest message (Family/Friend -> Resident, Resident -> Family/Friend, and Office -> Family/Friend).
There is no message history or archive within the service.

## Intended Use
The service is for non-urgent, social messages.
It is not designed for:
â€¢ Care updates
â€¢ Clinical communication
â€¢ Safeguarding reporting
â€¢ Complaints handling

Care-related matters must be handled through the care homeâ€™s existing procedures.

## Staff Responsibilities
Staff are responsible for:
â€¢ Supporting residents appropriately
â€¢ Using devices designated by the care home only
â€¢ Logging out where required
â€¢ Following the care homeâ€™s internal policies

The platform does not replace existing safeguarding or communication procedures.

## Privacy in a Care Setting
Messages may be played in shared areas.
Staff may assist residents with listening or recording.
Messages are not guaranteed to be private.

---

## Safeguarding and Consent (public)
# Safeguarding and Consent

## Purpose
This section explains how safeguarding and consent responsibilities operate when using familyupdates.care within a care setting.

## Safeguarding Responsibility
familyupdates.care provides a communication platform only.

Each participating care home remains fully responsible for:
â€¢ Safeguarding residents
â€¢ Assessing risk
â€¢ Monitoring staff conduct
â€¢ Responding to safeguarding concerns
â€¢ Compliance with regulatory obligations

The platform is not monitored in real time and is not reviewed for safeguarding purposes.

The service does not replace the care homeâ€™s existing safeguarding procedures.

Any safeguarding concern must be handled through the care homeâ€™s established processes.

## Managing Inappropriate Messages
The care home is responsible for managing the use of the platform within its service. This includes:
â€¢ Determining whether messages are appropriate
â€¢ Addressing inappropriate, distressing, or unsuitable content
â€¢ Managing or restricting family access where necessary
â€¢ Taking action in accordance with internal policies

familyupdates.care does not moderate, screen, or approve message content.

## Consent to Participate
The care home is responsible for determining whether a resident is suitable to participate in the service.
This includes:
â€¢ Assessing capacity where required
â€¢ Obtaining appropriate consent
â€¢ Involving family or representatives where applicable
â€¢ Reviewing participation where circumstances change

familyupdates.care does not assess resident capacity or consent.

## Appropriate Use
The service is not intended for clinical communication, safeguarding reporting, or formal complaints.

## Privacy in a Care Environment
Messages are used within a care home setting.
Staff may assist residents with listening to or recording messages.
Playback may occur in shared spaces.
Messages are not guaranteed to be private.
The care home is responsible for managing privacy within its environment.

## Reporting Concerns
If a family member has a safeguarding concern, they should contact the care home directly.
Platform-related issues may be directed to familyupdates.care.

---

## Privacy Notice (public)
# Privacy Notice
Version 1.0
Effective Date: [Insert Date]

familyupdates.care provides a communication platform to care homes under a Subscription Agreement.

We are committed to protecting personal data and complying with applicable UK data protection law.

## 1) Our Role
When a care home subscribes to the service:
â€¢ The care home acts as the Data Controller for resident and family data entered into the platform.
â€¢ familyupdates.care acts as the Data Processor, processing data on behalf of the care home.

## 2) What Data Is Processed
The platform may process:
â€¢ Resident name
â€¢ Family member name
â€¢ Email address
â€¢ Voice messages uploaded through the platform
â€¢ Basic usage data (such as login activity)

Only the most recent message from each sender is retained.
The platform is not designed to store long-term communication histories.

The platform is not intended to process or store legal authority documents, clinical records, finance/investment records, identity document data, safeguarding case files, or Carer Pack documents.

## 3) Where Data Is Stored
Data is stored within secure UK-based cloud infrastructure operated by familyupdates.care.
Logical separation is maintained between participating care homes.

## 4) Purpose of Processing
Data is processed solely to:
â€¢ Enable voice message exchange
â€¢ Maintain platform functionality
â€¢ Provide technical support
â€¢ Meet contractual obligations

The platform is intended for non-urgent social communication.

## 5) Data Retention
The system operates on a â€œone message in, one message outâ€ structure.
When a new message is sent, the previous message from that sender is replaced.

Upon termination of the Subscription Agreement, personal data will be retained for up to 30 days to allow for administrative processing and potential reactivation.
After this period, personal data will be permanently deleted from active systems.

## 6) Security
We implement reasonable technical and organisational measures to protect data, including:
â€¢ Secure hosting
â€¢ Access controls
â€¢ Restricted administrative access

Care homes remain responsible for managing local device security and staff access.

## 7) Individual Rights
Requests relating to resident or family data should be directed to the relevant care home as Data Controller.

Platform-related data enquiries may be directed to:
hello@familyupdates.care

---

## Family Terms of Use (public)
# Family Terms of Use
Version 1.0
Effective Date: [Insert Date]

These Terms apply to individuals using the Family Hub provided through a participating care home.

By accessing or using the service, you agree to these Terms.

## 1) Nature of the Service
familyupdates.care provides a platform that enables non-urgent voice messages between residents and their family or friends.

The service operates on a â€œone message in, one message outâ€ structure.
Only the most recent message from you and the most recent reply from the resident are kept.

There is no message history or archive.

The service is not monitored in real time.

The service is provided using reasonable skill and care, but uninterrupted or error-free operation is not guaranteed.

Technical faults, delays, outages, transmission failures, or security incidents may occur despite appropriate technical and organisational safeguards.

## 2) Intended Use
The service is for non-urgent, social communication only.

It must not be used for:
â€¢ Medical or care instructions
â€¢ Safeguarding reports
â€¢ Complaints about care
â€¢ Emergency communication
â€¢ Legal authority document handling
â€¢ Financial account or investment management
â€¢ Storage or management of Carer Pack documents

For urgent matters, contact the care home directly.

The service must not be used for confidential, highly personal, or time-critical communication.

Care homes are communal environments, and during normal operations messages may be heard in shared areas.

## 3) Access
Access is provided and managed by the care home.

You must:
â€¢ Use your own access credentials
â€¢ Not share login details
â€¢ Use the service responsibly

Access may be withdrawn by the care home.

## 4) Content
You are responsible for the content of any message you send.

Messages must not include:
â€¢ Abusive or threatening content
â€¢ Harassment
â€¢ Unlawful material

The care home is responsible for managing the use of the service within its setting.

familyupdates.care does not monitor or moderate message content.

## 5) Privacy
Personal data is processed in accordance with the Privacy Notice.

The care home acts as Data Controller for resident and family data.

familyupdates.care acts as Data Processor.

## 6) Limitation of Liability
familyupdates.care provides the platform on an â€œas isâ€ basis.

We are not responsible for:
â€¢ Care decisions
â€¢ Safeguarding matters
â€¢ Staff conduct
â€¢ Loss arising from misuse of the service

Subject to applicable law, familyupdates.care is liable only for direct loss caused by proven breach of contractual obligations and is not liable for indirect or consequential loss.

Nothing in these Terms excludes liability where it cannot be excluded by law.

## 7) Changes
We may update these Terms from time to time.
The current version will be available within the service.

---

## Data Processing Schedule (contract attachment)
# Data Processing Schedule
Schedule 1 to the Care Home Subscription Agreement
Version 1.0
Effective Date: [Insert Date]

This Schedule forms part of the Care Home Subscription Agreement between:
familyupdates.care (â€œthe Processorâ€) and [Care Home Legal Entity] (â€œthe Controllerâ€).

1) Subject matter: Provision of the platform enabling voice messages between residents and family members within a care home setting.
2) Duration: For the term of the Agreement, plus up to 30 days after termination before deletion.
3) Nature/purpose: Hosting, storage of current voice messages, authentication, transmission, basic usage logging; to provide the service and support.
4) Data subjects: Residents, family/friends, limited staff account data.
5) Data: Names, emails, voice recordings, basic login activity. Not clinical records.
6) Controller obligations: Lawful basis; capacity/consent; safeguarding; content management; rights requests.
7) Processor obligations: Process on instructions; security; confidentiality; assist with rights; breach notification; deletion per agreement; no moderation.
8) Sub-processors: Cloud infrastructure providers for hosting; list available upon request; contractual safeguards in place.
9) Transfers: Stored in UK-based infrastructure; no transfers outside UK without safeguards.
10) Security: Secure hosting, logical separation, access controls, restricted admin access; controller manages local device/security.

---

## Product Design Principles (internal)
# Product Design Principles
familyupdates.care
Version 1.0

1) Calm Over Immediacy â€” avoid features that introduce urgency, response pressure, or performance expectations.
2) Asynchronous by Design â€” no live status, typing, read receipts, delivery confirmations, response time tracking, push/instant reply notifications.
3) Single-Message Structure â€” one message in, one message out; no history/archive.
4) Date-Only Message Display â€” main care communication views show message date only (no clock time); internal audit timestamps allowed.
5) No Performance Metrics â€” do not display analytics that allow response speed or staff performance to be inferred.
6) Clear Role Boundaries â€” care home responsible for safeguarding, consent, content management, staff supervision, regulatory compliance; platform does not monitor/moderate.

Core principle: presence without performance pressure.

