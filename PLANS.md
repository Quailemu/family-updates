# PLANS.md — Canonical Copy (source of truth)

Reference: `docs/security/SECURITY_MODEL.md` (final security/login model)

## Homepage banner (public)
voicemailcare.com  
One message in. One message out.  
(Optional small line) No threads. No pressure.

Homepage buttons (only):
- Family
- Care Hub – Mobile
- Care Hub – Office

Canonical interface sentence:
The platform has three app interfaces: Family Hub, Care Hub – Mobile, and Care Hub – Office.

User-facing help rule:
Use short, plain-language, outcome-led explanations. Do not show system diagrams, walkthrough videos, or screen recordings in the app. Diagrams and recordings may be kept as internal product/design references only.

Homepage public info copy (before feedback section):
## Familiar voices
A simple communication tool for care homes, residents, and their families.

Family members may each send an individual message to a resident at any time, as it is not a live service. Carers may play messages for the resident when convenient. Carers may also help residents record one reply to the family group.

The care home may also send non-urgent or practical updates, and families may respond with structured text to simple requests.

There is no message history, no long threads, and it is not live. It fits around normal care routines and helps keep communication manageable.

## A simple way to explore the idea
Voicemail Care can be introduced through a one-to-one, activity-based session in the care home.

The session uses printed artwork and conversation as a starting point. A short voice message can be played as part of the interaction, introducing the idea in a natural way.

There is no obligation to adopt anything, simply an opportunity to see how this might help communication for you.

Non-real-time reinforcement (homepage or family entry page, short):
This is non-urgent and not live messaging. Messages are played when staff are available, to fit around care routines.

Family security session statement (family-facing, short):
For security, Family sessions sign out after 30 minutes of inactivity. If signed out, request a new secure email link.

Family preparation statement (family-facing, short):
Plan your message before recording. Most messages only need a few seconds.

No notifications / date-only statement (family-facing, short):
The service does not send live notifications. Main care communication views show message date only (no clock time).

Transcript assist statement (all interfaces, short):
Transcripts can be requested when recording in Family Hub, Care Hub – Mobile, and Care Hub – Office.
When available, the transcript appears under “Transcript assist”.
Transcripts may contain errors, and voice remains the source of truth.
If transcript is unavailable or not requested, voice playback still operates (unless a care-home precheck policy is enabled).

Role-based access (Family vs Care Hub):
Family and Care Hub are separate, role-based experiences.

Playback and control statement:
All current messages for that resident may be played by users designated by the care home across Mobile, Office, and Family, but no group can alter another group's message. Each message may only be replaced by the interface that created it.

Office update statement:
General updates are sent from the care home to keep families informed about day-to-day events. General updates are one-way and are for non-urgent, non-medical information only.

Office practical messages are optional structured requests linked to a specific resident (for example visits, attendance, reminders, or item requests). Family members, friends, or other individuals designated by the care home can reply with a minimal structured response (Yes / No / Maybe), optional fixed tick-box options, and an optional short context note. This is still non-urgent and not live messaging.

For urgent, medical, safeguarding, or other time-sensitive matters, families must contact the care home directly through normal channels.

Service overview purpose statement:
voicemailcare.com is a simple tool for exchanging non-urgent social voice messages between residents in care homes and their family members, friends, or other individuals designated by the care home. The care home office may also send non-urgent general updates about daily life in the home to family members, friends, or other individuals designated by the care home.

Office general updates are one-way informational messages.

The care home may also publish an Office practical message that allows each registered Family Member to send a structured non-urgent reply (Yes / No / Maybe, optional fixed tick-boxes, and an optional short context note).

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

## How VoicemailCare Works

VoicemailCare uses voice messages for personal connection and simple text updates or structured requests for coordination.

Core rules:
- Personal messages can be voice messages, with transcription available where enabled.
- Coordination updates and practical requests can be simple text.
- Each new item replaces the previous one in that channel.
- There is always one current item at a time.
- No threads.
- No live chat.
- No ongoing conversations.
- Updates are shared with all relevant Family Members.
- Requests use fixed structured replies only.

This keeps communication calm, current, and easy to manage. People can use as much or as little of the system as they choose.

Whole-system definition:
VoicemailCare helps families share calm updates, reduce repeated calls, and coordinate practical support without live chat or message history.

## Transparency

VoicemailCare is designed to support clear and shared understanding between family members.

Where responsibilities are shared - especially care, communication, practical help, or finances - arrangements should be as transparent as possible.

This is particularly important where one family member is managing money or making financial arrangements on behalf of someone else.

Where appropriate, relevant family members should be able to see financial statements or summaries, so that responsibility does not sit invisibly with one person.

Families may also consider using a suitable professional to manage investments or provide independent financial oversight.

VoicemailCare does not define legal authority or decide who should manage finances. It helps make responsibilities visible and supports families in agreeing transparent arrangements.

## Stages of Use

Stage 0 preparation:
The external filing system should be organised first, before starting updates. VoicemailCare does not store those files.

## Outcomes for Users

VoicemailCare can be used in levels, so you do not have to use the whole system at once. You can use the full system, or start with simple updates and add more when needed.

The table below gives a quick overview of what becomes available at each stage. It is not a full description of every detail.

| Level | Outcome / capability                                     | Stage 1: Person/Couple | Stage 2: + Family coordinator | Stage 3: + Carer | Stage 4: Care home + Family coordinator |
| ----- | -------------------------------------------------------- | ---------------------- | ----------------------------- | ---------------- | --------------------------------------- |
| 1     | Single update to family group                            | ✓                      | ✓                             | ✓                | ✓ Care home system                      |
| 2     | Individual voice messages from family members            | ✓                      | ✓                             | ✓                | ✓ Care home system                      |
| 3     | Voice message request (+ structured replies from family) | ✓                      | ✓                             | ✓                | ✓ Care home system                      |
| 4     | Option: Mobile additional channel*                       | ✓                      | ✓                             | ✓                | ✓ Care home system                      |
| 5     | Family coordinator system**                              | —                      | —                             | —                | ✓                                       |

### Stage explanations

* **Stage 1: Person/Couple** — An individual person or a couple living at home and managing their own day-to-day communication.
* **Stage 2: + Family coordinator** — The person/couple plus a family coordinator. A family coordinator is a family member who helps organise communication and practical requests.
* **Stage 3: + Carer** — The person/couple plus a family coordinator and a paid carer.
* **Stage 4: Care home + Family coordinator** — The person/couple moves into a care home. The care home has its own system, and the family coordinator has a separate family coordinator system.

### Notes

*Additional mobile channel: a separate mobile channel that can send a single voice message to the family group, receive family voice messages, and send requests with structured replies.*

**Family coordinator system: used separately from the care home system. It allows the family coordinator to send a single voice message to the family group, receive individual family voice messages to the office, and use requests with structured replies.**

## How the levels work

Each level includes everything from the previous levels, with additional features added.

You can start at Level 1 and move up through the levels as more support is needed.

Important:

* Keep this section in Markdown.
* Do not use an image for the table.
* Do not change the wording inside the table unless specifically requested.
* Keep the table as a quick overview.
* Keep detail in the stage explanations and notes.

Targeted request boundary:
Requests and structured replies are for non-urgent, non-essential coordination only. Family requests remain visible to all linked Family Members and may name an intended responder, such as Sarah, Tom, or Coordinator. Office-to-Mobile/carer requests are a separate working channel where enabled. Replies use fixed structured choices, optional fixed tick-boxes, and an optional short context note only: no private chat, no threads, and no back-and-forth conversation. Essential, urgent, sensitive, or time-critical matters should use normal direct communication outside VoicemailCare, such as phone, text, WhatsApp, email, or existing care-home channels.

Lifecycle model:
The app uses four active lifecycle stages to describe the real-life situation. Stage policy controls capabilities; it must not assign fixed role ownership.
The user should choose the lifecycle stage, not a separate organisation mode. Stage 0 is preparation of documents and information outside the app. It is not an active app communication stage. Planning & Organisation guidance belongs in the Life File Guide and other help areas only.

- Stage 0 - Preparation of documents: this is not an active app communication stage. It is the external filing system step: Life Log, Contacts, Admin and Key Documents, Private Finance, Private Health Notes, and Carer and Housekeeping Notes. The files remain outside VoicemailCare.

Stages 1-3 use the same at-home principles: one current message, no threads, no live chat, and practical structured replies where helpful. Stage 1 uses [Surname] Family Office, Mobile, and Family Hub. Mobile lets the person or couple hear family voice messages and send one shared voice message to family. From Stage 2, Mobile also gives the person or couple and the family member separate ways to send messages and keep independence. In Stage 3, Mobile helps a carer or supporter work separately from the family member.

- Stage 1 - Individual or Couple at Home: this stage is for an individual or couple still mainly managing at home. Family contact may be increasing, and repeated calls or scattered messages can become tiring. VoicemailCare helps them share one calm family voice update and receive family messages when useful, without creating a live chat or long message thread.
- Stage 2 - Support from a Family Member: this stage is for when one family member starts helping organise things. The family member may help share updates, ask practical questions, and reduce repeated conversations across the family. Mobile gives the person or couple and the family member separate ways to send messages. The aim is to make the coordination role manageable without taking over the person's life.
- Stage 3 - Family Support plus Carer: this stage is for when support from a family member continues and a carer, supporter, or regular helper is involved at home. The same shared system helps the person or couple, family member, and helper keep practical communication clear. It avoids creating separate message streams for everyone.
- Stage 4 - Care Home plus Separate Family Support: this stage is for when the person is living in a care home, with external and separate support from a family member. The care home uses its own separate workspace for updates, family messages, and practical requests. Family support may still happen, but it must stay separate from the care home's responsibilities and systems.

Stage 4 separation rule:
The Care Home Office and Family Coordinator Office are separate workspaces. They may relate to the same real-life person, but they do not connect inside the app.

This means:
- No shared inbox between the two offices.
- No shared requests.
- No shared updates.
- No shared admin tools.
- No cross-access.
- No care-home data visible in the Family Coordinator Office.
- No Family Coordinator Office data visible in the Care Home Office.
- No handover workflow or internal linking between them.

The Care Home Office belongs to the care organisation and its operational responsibilities. The Family Coordinator Office belongs to family-side coordination only.

Stage 4 Care Home Office wording:
The Care Home Office should use care-home wording and the actual care home name. Do not label the care home workspace as the person's home.

The Family Coordinator Office should use its own separate coordinator/family workspace name, for example "Hill family coordination" or "David's family coordination". It should not use the care home name, and it should not use the person's home name. It is for the coordinator and family, not for the care home, and it must not connect to the Care Home Office.

Stage 4 mobile separation:
- Care Home Mobile stays operational. It supports care-home/resident voice workflows and does not create structured requests.
- Family Coordinator Mobile may exist later. It belongs to the family-side workspace, not the care-home workspace.
- Family Coordinator Mobile may support quick family updates, visit updates, and simple family coordination requests.
- Family Coordinator Mobile must not connect to Care Home Mobile, Care Home Office, or care-home operational data.
- Care-home tools and family-coordinator tools may use similar UI patterns, but they are separate products/workspaces in Stage 4.

Stage 4 family-side purpose:
The Family Coordinator Office and future Family Coordinator Mobile exist to help the wider family help out. They should make it easy to share one update with everyone, coordinate visits or practical help, and reduce pressure on one overloaded coordinator. They must not duplicate care-home operations.

Stage 4 Family Coordinator workspace planned architecture:
This is planned separately and should not be built by extending the Care Home Office tables/workflow unless there is a deliberate separation layer.

Purpose:
The Family Coordinator workspace helps the family coordinate around someone now living in a care home. It is not a care-home tool and is not connected to the Care Home Office.

Planned interfaces:
- Family Coordinator Office: used by the main coordinator or family admin person. It may send family updates, create simple family coordination requests, review structured replies, and manage family-side contacts.
- Family Coordinator Mobile: may exist later for quick family-side updates during visits, errands, or conversations. It may help a visiting family member record an update or help the person record a family-side message.
- Family Hub: family members receive/listen/respond using the same calm, non-live, latest-message-only model.

Possible family-side channels:
- Coordinator/family update to all family.
- Visiting family/mobile update to all family.
- Person/family-side voice message to all family.
- Simple family coordination request.
- Structured replies visible to the coordinator/family workspace.

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
Use separate family workspace tables where practical, for example family_workspaces, family_workspace_members, family_workspace_people, family_workspace_messages, family_workspace_requests, and family_workspace_request_responses. Avoid reusing care-home operational tables for family-side Stage 4 coordination unless a clear separation layer prevents cross-access and conceptual confusion.

Mobile channel principle:
Mobile is not the carer app. Mobile is the simple in-the-moment channel. In Stage 1, Mobile lets the person or couple hear family voice messages and send one shared voice message to family. In Stages 2-3, Mobile may be used by the person, a family member, a supporter, or a carer depending on how the household works.
In Stages 2-3, Mobile may send shared updates and structured practical requests where enabled. This is useful when the person present in the home can ask the wider family for practical help without routing every request through the coordinator.
In Stage 4 care-home mode, Care Home Mobile remains voice playback/recording only. Structured requests stay with Care Home Office.

At-home setup model:
For Stage 1, Stage 2, and Stage 3, the visible setup should be a home/person setup, not a care-home setup. Reuse existing backend tables where practical, but label the UI as Setup name, Person 1, Person 2 optional, and Main supporter / coordinator.

Stage 1/2/3 wording:
When Stage 1, Stage 2, or Stage 3 is active, avoid visible "Care organisation", "Care Home", and "Resident" framing where the context is at-home coordination. Prefer "shared at-home coordination" and "person/people" wording while keeping the existing backend routing intact.
Prefer "shared update", "shared request", "shared coordination", and "[Surname] Family Office" wording over care-home Office wording where the user is doing routine at-home coordination.

At-home How it works copy:
VoicemailCare helps families share calm updates, reduce repeated calls, and coordinate practical support without live chat or message history.

The external filing system should be organised first, before starting updates. VoicemailCare does not store those files.

Once the external filing system is in place, users can start with one calm voice update to registered Family Members. There are no replies in that update channel, no thread, and the next update replaces the previous one.

Add only the communication tools that are useful: family voice messages, practical requests, and structured replies. Mobile is added only where useful from Stage 2 onward. One voice message replaces the last voice message in that channel.

Stage 1 uses [Surname] Family Office, Mobile, and Family Hub. Mobile lets the person or couple hear family voice messages and send one shared voice message to family. From Stage 2, Mobile also gives the person or couple and the family member separate ways to send messages and keep independence. In Stage 3, Mobile helps a carer or supporter work separately from the family member. What changes is who is involved, not a new technical system.

Private notes and records stay outside VoicemailCare, in the person's or family coordinator's own filing system.

Use "[Surname] Family Office" for the main at-home message area when a surname is available, for example "Hill Family Office". Use "Family Office" as the fallback. Use "Care Hub - Office" for the Stage 4 care-home workspace.

Documentation boundary:
The original care-home documentation remains the Stage 4 Care Home documentation set. Do not dilute it into at-home wording. Stage 4 Care Home Office/Mobile/Family should continue to use the full care-home governance, resident, room/reference, staff, safeguarding, consent, and responsibility wording.

Stage 1, Stage 2, and Stage 3 need a smaller separate at-home help set. Do not show the full care-home Office documentation pack in at-home stages unless a page has been rewritten for at-home use. At-home guidance should focus on simple messages, shared coordination, registering family/contact access, Life File Guide, and practical requests where enabled.

Office model shorthand:
Single -> Shared -> Split.

Life File Guide (in-app help):
The Life File Guide explains a simple external notes/files approach. It should help users organise important information outside the app, using paper, computer files, or phone notes.

Canonical Life File Guide copy:
Use this guide to organise important information outside the app. Paper, computer files, and phone notes are all fine.

The important point is that information is organised, accessible to the right person when needed, and separated so private information is not shared by accident.

This is Stage 0: preparation before family coordination becomes difficult. This external filing system helps the person stay independent for longer, reduces family friction, and avoids important information being sorted out in a rush.

The app may suggest the file structure, but the files themselves remain in the person's or family coordinator's own external system.

VoicemailCare does not store the contents of notebooks, documents, medical records, financial records, legal documents, care logs, passwords, or private long-form notes.

Keep private information separate from practical information that a carer, helper, or family member may need.

Do not put medical records, financial records, legal documents, passwords, care logs, or private long-form notes into VoicemailCare.

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
VoicemailCare may suggest that users organise authority contact details and consider whether formal authority, such as financial or health/welfare LPA, LPOA, or similar arrangements, is relevant. It must not give legal or financial advice. Use wording such as "you may want to", "where relevant", and "seek professional advice where needed." Do not say the app requires any authority document.

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
- Private Health Notes: health summary and key conditions; current medication list; allergies and important risks; appointments, questions, and observations; GP, pharmacy, hospital, and clinic contacts; who has health and welfare LPA/LPOA or similar authority, where relevant; keep formal medical records outside VoicemailCare.
- Carer and Housekeeping Notes: first page with important information for helpers; emergency contacts; house access instructions; allergies; medication schedule summary; daily routine; mobility / falls risk notes; food and drink preferences; housekeeping notes, deliveries, bins, pets, or keys; what to do if something changes.
- Authority and professional advice: you may want to consider whether formal authority, such as financial or health/welfare LPA, LPOA, or similar arrangements, is relevant; people coordinating care or paid support may need to know who has authority to make decisions or arrange costs; keep authority documents outside VoicemailCare and share only with people who need them; this is not legal or financial advice; seek professional advice where needed.
- If a care home becomes involved: care home contact details; family coordinator contact; preferences and routines; financial / admin contacts; visiting arrangements; important family updates; notes of care home meetings; questions for care home staff.

Internal diagram/video reference rule:
System diagrams and recordings are internal product/design references only. Keep reference assets in `assets/` when useful for coding and product thinking, but do not expose them in normal user-facing app help.

---

## Pricing page (public)
# Pricing
Simple, transparent pricing per care home.

## Pilot Programme
We offer a structured 30-day pilot to allow care homes to evaluate the service within their setting.

**£75 + VAT one-time pilot fee**

• Formal agreement required  
• 30-day duration  
• Credited against the first month’s subscription if continuing  
• Access activated once payment is received  

## Monthly Subscription
A flat monthly subscription per care home.  
No per-message fees. No hidden charges.

### Up to 50 residents  
**£195 + VAT per month**

### 51+ residents  
**£295 + VAT per month**

• Minimum commitment: 3 months following pilot  
• 30 days’ written notice thereafter  
• Invoiced monthly in advance  
• Access activated once payment is received  

## What’s Included
• Family access  
• Care Hub – Mobile access  
• Care Hub – Office access  
• Secure hosting  
• Ongoing platform availability  
• Technical support for platform-related issues  

## Important
voicemailcare.com provides a communication platform.  
Each participating care home remains responsible for care delivery, safeguarding, and regulatory compliance.

---

## Complaints & Concerns page (public)
# Complaints & Concerns
We take concerns seriously and aim to respond promptly and fairly.

## 1) Concerns relating to care or platform use within a care home
voicemailcare.com provides a communication platform to care homes under a subscription agreement.

Each participating care home is responsible for:
• Care delivery and safeguarding  
• How the platform is used within their service  
• Staff access, supervision, and training  
• Responding to families through the platform  
• Local governance and regulatory compliance  

If your concern relates to care, staff conduct, safeguarding, or how the platform is being used within a specific care home, please contact the care home directly in the first instance.

The care home remains responsible for operational decisions and oversight.

## 2) Concerns relating to the voicemailcare.com service
If your concern relates to:
• Access or login issues  
• Technical faults  
• System errors  
• Data protection queries  
• Contract or subscription matters  

You may contact voicemailcare.com directly.

Email: hello@voicemailcare.com

## 3) What happens next
For platform-related complaints, we will:
• Acknowledge your complaint within 2 working days  
• Review the matter promptly  
• Provide a response within 10 working days where possible  

If more time is required, we will explain why.

Where appropriate, we may liaise with the relevant care home.

## 4) Important clarification
voicemailcare.com does not:
• Provide care services  
• Supervise care home staff  
• Make care decisions  
• Replace a care home’s own complaints process  

The care home remains responsible under its own regulatory framework.

---

## Care Hub – Office page (public info path)
# Care Hub – Office
Oversight and administrative control for participating care homes.

## Purpose
Care Hub – Office provides management-level access to the voicemailcare.com platform within your service.

It supports oversight of how the platform is used, while maintaining the care home’s existing governance framework.

## How the Platform Operates
The messaging system uses two types of channels linked to each resident: two-way contact channels and a one-way Office update channel.

Channel directions:
- Family/Friend -> Resident (created/replaced in Family Hub)
- Resident -> Family/Friend (created/replaced in Care Hub – Mobile)
- Office -> Family/Friend (created/replaced in Care Hub – Office)

Each channel keeps only the latest message.  
When a new message is sent in a channel, the previous message in that channel is replaced.

Messages in a contact channel may only be played by users designated by the care home for that specific channel. Other family members, friends, or other individuals designated by the care home cannot access those messages. Care home staff using Care Hub – Mobile and Care Hub – Office may also play messages for operational support.

This structure helps keep communication simple and manageable within care settings.

## Management Functions
Care Hub – Office allows personnel designated by the care home to:
• Manage staff access  
• Enable or disable resident participation  
• Monitor platform usage  
• Maintain oversight of subscription status  

Access is restricted to management users designated by the care home.

## Governance Position
voicemailcare.com provides a communication platform.

The care home remains responsible for:
• Care delivery and safeguarding  
• Regulatory compliance  
• Staff conduct and supervision  
• Decisions regarding resident participation  
• Responding appropriately to family messages  

The platform does not replace the care home’s own policies, safeguarding systems, or complaints procedures.

## Subscription & Agreement
The service is provided under a formal Subscription Agreement.

The current version of the Care Home Subscription Agreement is available here:
**Care Home Subscription Agreement – Version 1.0**
(Download link)

## Support
Platform-related support is available via email.  
Care-related concerns should be addressed through the care home’s own procedures.

---

## Family and Friends Guide (public info path)
# Family and Friends Guide

## Purpose
This guide explains how voicemailcare.com is used for simple, non-urgent social messages between residents and their family or friends.

It sets out how the service works and its intended use.

## App Version
Families and friends use the **Family Hub only**.
The Family Hub does not include Care Hub features.

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
The service operates on a channel-based “one message in, one message out” structure.

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

## Care Hub – Mobile Guide (public info path)
# Care Hub – Mobile Guide

## Purpose
This guide explains how Care Hub – Mobile is used within the care home to support residents in sending and receiving simple, non-urgent voice messages.

## App Version
Care Hub – Mobile is used by staff designated by the care home on care home devices.
It does not include Office-level administrative features.

## How the Service Works

### Listening to a family message
When a family member sends a voice message, the most recent message becomes available for the resident to hear.
Staff may assist the resident with playback where appropriate.

### Recording a resident reply
Staff may assist a resident in recording a reply.
Once recorded, that reply replaces the previous reply from the resident.

### Message replacement
The service operates on a channel-based “one message in, one message out” structure.
Each channel keeps only the latest message (Family/Friend -> Resident, Resident -> Family/Friend, and Office -> Family/Friend).
There is no message history or archive within the service.

## Intended Use
The service is for non-urgent, social messages.
It is not designed for:
• Care updates  
• Clinical communication  
• Safeguarding reporting  
• Complaints handling  

Care-related matters must be handled through the care home’s existing procedures.

## Staff Responsibilities
Staff are responsible for:
• Supporting residents appropriately  
• Using devices designated by the care home only  
• Logging out where required  
• Following the care home’s internal policies  

The platform does not replace existing safeguarding or communication procedures.

## Privacy in a Care Setting
Messages may be played in shared areas.
Staff may assist residents with listening or recording.
Messages are not guaranteed to be private.

---

## Safeguarding and Consent (public)
# Safeguarding and Consent

## Purpose
This section explains how safeguarding and consent responsibilities operate when using voicemailcare.com within a care setting.

## Safeguarding Responsibility
voicemailcare.com provides a communication platform only.

Each participating care home remains fully responsible for:
• Safeguarding residents  
• Assessing risk  
• Monitoring staff conduct  
• Responding to safeguarding concerns  
• Compliance with regulatory obligations  

The platform is not monitored in real time and is not reviewed for safeguarding purposes.

The service does not replace the care home’s existing safeguarding procedures.

Any safeguarding concern must be handled through the care home’s established processes.

## Managing Inappropriate Messages
The care home is responsible for managing the use of the platform within its service. This includes:
• Determining whether messages are appropriate  
• Addressing inappropriate, distressing, or unsuitable content  
• Managing or restricting family access where necessary  
• Taking action in accordance with internal policies  

voicemailcare.com does not moderate, screen, or approve message content.

## Consent to Participate
The care home is responsible for determining whether a resident is suitable to participate in the service.
This includes:
• Assessing capacity where required  
• Obtaining appropriate consent  
• Involving family or representatives where applicable  
• Reviewing participation where circumstances change  

voicemailcare.com does not assess resident capacity or consent.

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
Platform-related issues may be directed to voicemailcare.com.

---

## Privacy Notice (public)
# Privacy Notice
Version 1.0  
Effective Date: [Insert Date]

voicemailcare.com provides a communication platform to care homes under a Subscription Agreement.

We are committed to protecting personal data and complying with applicable UK data protection law.

## 1) Our Role
When a care home subscribes to the service:
• The care home acts as the Data Controller for resident and family data entered into the platform.  
• voicemailcare.com acts as the Data Processor, processing data on behalf of the care home.

## 2) What Data Is Processed
The platform may process:
• Resident name  
• Family member name  
• Email address  
• Voice messages uploaded through the platform  
• Basic usage data (such as login activity)

Only the most recent message from each sender is retained.
The platform is not designed to store long-term communication histories.

The platform is not intended to process or store legal authority documents, clinical records, finance/investment records, identity document data, safeguarding case files, or Carer Pack documents.

## 3) Where Data Is Stored
Data is stored within secure UK-based cloud infrastructure operated by voicemailcare.com.
Logical separation is maintained between participating care homes.

## 4) Purpose of Processing
Data is processed solely to:
• Enable voice message exchange  
• Maintain platform functionality  
• Provide technical support  
• Meet contractual obligations  

The platform is intended for non-urgent social communication.

## 5) Data Retention
The system operates on a “one message in, one message out” structure.
When a new message is sent, the previous message from that sender is replaced.

Upon termination of the Subscription Agreement, personal data will be retained for up to 30 days to allow for administrative processing and potential reactivation.
After this period, personal data will be permanently deleted from active systems.

## 6) Security
We implement reasonable technical and organisational measures to protect data, including:
• Secure hosting  
• Access controls  
• Restricted administrative access  

Care homes remain responsible for managing local device security and staff access.

## 7) Individual Rights
Requests relating to resident or family data should be directed to the relevant care home as Data Controller.

Platform-related data enquiries may be directed to:
hello@voicemailcare.com

---

## Family Terms of Use (public)
# Family Terms of Use
Version 1.0  
Effective Date: [Insert Date]

These Terms apply to individuals using the Family Hub provided through a participating care home.

By accessing or using the service, you agree to these Terms.

## 1) Nature of the Service
voicemailcare.com provides a platform that enables non-urgent voice messages between residents and their family or friends.

The service operates on a “one message in, one message out” structure.  
Only the most recent message from you and the most recent reply from the resident are kept.

There is no message history or archive.

The service is not monitored in real time.

The service is provided using reasonable skill and care, but uninterrupted or error-free operation is not guaranteed.

Technical faults, delays, outages, transmission failures, or security incidents may occur despite appropriate technical and organisational safeguards.

## 2) Intended Use
The service is for non-urgent, social communication only.

It must not be used for:
• Medical or care instructions  
• Safeguarding reports  
• Complaints about care  
• Emergency communication  
• Legal authority document handling  
• Financial account or investment management  
• Storage or management of Carer Pack documents  

For urgent matters, contact the care home directly.

The service must not be used for confidential, highly personal, or time-critical communication.

Care homes are communal environments, and during normal operations messages may be heard in shared areas.

## 3) Access
Access is provided and managed by the care home.

You must:
• Use your own access credentials  
• Not share login details  
• Use the service responsibly  

Access may be withdrawn by the care home.

## 4) Content
You are responsible for the content of any message you send.

Messages must not include:
• Abusive or threatening content  
• Harassment  
• Unlawful material  

The care home is responsible for managing the use of the service within its setting.

voicemailcare.com does not monitor or moderate message content.

## 5) Privacy
Personal data is processed in accordance with the Privacy Notice.

The care home acts as Data Controller for resident and family data.

voicemailcare.com acts as Data Processor.

## 6) Limitation of Liability
voicemailcare.com provides the platform on an “as is” basis.

We are not responsible for:
• Care decisions  
• Safeguarding matters  
• Staff conduct  
• Loss arising from misuse of the service  

Subject to applicable law, voicemailcare.com is liable only for direct loss caused by proven breach of contractual obligations and is not liable for indirect or consequential loss.

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
voicemailcare.com (“the Processor”) and [Care Home Legal Entity] (“the Controller”).

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
voicemailcare.com  
Version 1.0

1) Calm Over Immediacy — avoid features that introduce urgency, response pressure, or performance expectations.  
2) Asynchronous by Design — no live status, typing, read receipts, delivery confirmations, response time tracking, push/instant reply notifications.  
3) Single-Message Structure — one message in, one message out; no history/archive.  
4) Date-Only Message Display — main care communication views show message date only (no clock time); internal audit timestamps allowed.  
5) No Performance Metrics — do not display analytics that allow response speed or staff performance to be inferred.  
6) Clear Role Boundaries — care home responsible for safeguarding, consent, content management, staff supervision, regulatory compliance; platform does not monitor/moderate.

Core principle: presence without performance pressure.

