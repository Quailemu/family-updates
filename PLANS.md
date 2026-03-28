# PLANS.md — Canonical Copy (source of truth)

Reference: `docs/security/SECURITY_MODEL.md` (final security/login model)

## Homepage banner (public)
voice-message.com  
One message in. One message out.  
(Optional small line) No threads. No pressure.

Homepage buttons (only):
- Family
- Care Hub – Mobile
- Care Hub – Office

Short Explanation (homepage section):
The system has three application interfaces for groups associated with the resident: Care Hub – Mobile, Care Hub – Office, and the Family App (which includes family members, friends, or other individuals designated by the care home).  
Messages are organised into channels. Each channel keeps only the latest message.  
When a new message is recorded in a channel, the previous message in that channel is replaced.  
No archive. No message history. No scrolling thread.

Non-real-time reinforcement (homepage or family entry page, short):
This is non-urgent and not live messaging. Messages are played when staff are available, to fit around care routines.

Family security session statement (family-facing, short):
For security, Family sessions sign out after 30 minutes of inactivity. If signed out, request a new secure email link.

Family preparation statement (family-facing, short):
Plan your message before recording. Most messages only need a few seconds.

No notifications / date-only statement (family-facing, short):
The service does not send live notifications. Main care communication views show message date only (no clock time).

Role-based access (Family vs Care Hub):
Family and Care Hub are separate, role-based experiences.

Playback and control statement:
All current messages for that resident may be played by users designated by the care home across Mobile, Office, and Family, but no group can alter another group's message. Each message may only be replaced by the interface that created it.

Office update statement:
General updates are sent from the care home to keep families informed about day-to-day events. General updates are one-way and are for non-urgent, non-medical information only.

Office practical messages are optional structured requests linked to a specific resident (for example visits, attendance, reminders, or item requests). Family members, friends, or other individuals designated by the care home can reply with a minimal structured response (Yes / No / Maybe), optional tick-box options, and an optional short note. This is still non-urgent and not live messaging.

For urgent, medical, safeguarding, or other time-sensitive matters, families must contact the care home directly through normal channels.

Service overview purpose statement:
voice-message.com is a simple tool for exchanging non-urgent social voice messages between residents in care homes and their family members, friends, or other individuals designated by the care home. The care home office may also send non-urgent general updates about daily life in the home to family members, friends, or other individuals designated by the care home.

Office general updates are one-way informational messages.

The care home may also publish an Office practical message that allows each registered Family Member to send a structured non-urgent reply (Yes / No / Maybe, optional tick-boxes, optional short note).

The service is not intended for care updates, health information, safeguarding communication, or urgent enquiries.

Video naming and env key spec (locked):
- Core labels everywhere: `Record video` and `Diagram video`.
- Only two video types are allowed: `Record` and `Diagram`.
- Do not use: `walkthrough`, `explainer`, or `flow video` in UI naming.
- Optional helper text only when needed:
- `Record video` -> `Send a voice message`
- `Diagram video` -> `How the system works`
- If `Diagram video` is unclear in a specific UI context, use `How it works`.

Env key format (locked):
- `PUBLIC_<AUDIENCE>_<TYPE>_VIDEO_URL`
- `<AUDIENCE>` = `MOBILE | FAMILY | OFFICE | UNIVERSAL`
- `<TYPE>` = `RECORD | DIAGRAM`

Final public video env keys:
- `PUBLIC_MOBILE_RECORD_VIDEO_URL`
- `PUBLIC_FAMILY_RECORD_VIDEO_URL`
- `PUBLIC_OFFICE_RECORD_VIDEO_URL`
- `PUBLIC_MOBILE_DIAGRAM_VIDEO_URL`
- `PUBLIC_FAMILY_DIAGRAM_VIDEO_URL`
- `PUBLIC_OFFICE_DIAGRAM_VIDEO_URL`
- `PUBLIC_UNIVERSAL_DIAGRAM_VIDEO_URL`

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
voice-message.com provides a communication platform.  
Each participating care home remains responsible for care delivery, safeguarding, and regulatory compliance.

---

## Complaints & Concerns page (public)
# Complaints & Concerns
We take concerns seriously and aim to respond promptly and fairly.

## 1) Concerns relating to care or platform use within a care home
voice-message.com provides a communication platform to care homes under a subscription agreement.

Each participating care home is responsible for:
• Care delivery and safeguarding  
• How the platform is used within their service  
• Staff access, supervision, and training  
• Responding to families through the platform  
• Local governance and regulatory compliance  

If your concern relates to care, staff conduct, safeguarding, or how the platform is being used within a specific care home, please contact the care home directly in the first instance.

The care home remains responsible for operational decisions and oversight.

## 2) Concerns relating to the voice-message.com service
If your concern relates to:
• Access or login issues  
• Technical faults  
• System errors  
• Data protection queries  
• Contract or subscription matters  

You may contact voice-message.com directly.

Email: complaints@voicemessagecare.com

## 3) What happens next
For platform-related complaints, we will:
• Acknowledge your complaint within 2 working days  
• Review the matter promptly  
• Provide a response within 10 working days where possible  

If more time is required, we will explain why.

Where appropriate, we may liaise with the relevant care home.

## 4) Important clarification
voice-message.com does not:
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
Care Hub – Office provides management-level access to the voice-message.com platform within your service.

It supports oversight of how the platform is used, while maintaining the care home’s existing governance framework.

## How the Platform Operates
The messaging system uses two types of channels linked to each resident: two-way contact channels and a one-way Office update channel.

Channel directions:
- Family/Friend -> Resident (created/replaced in Family App)
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
voice-message.com provides a communication platform.

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
This guide explains how voice-message.com is used for simple, non-urgent social messages between residents and their family or friends.

It sets out how the service works and its intended use.

## App Version
Families and friends use the **Family app only**.
The Family app does not include Care Hub features.

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
This section explains how safeguarding and consent responsibilities operate when using voice-message.com within a care setting.

## Safeguarding Responsibility
voice-message.com provides a communication platform only.

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

voice-message.com does not moderate, screen, or approve message content.

## Consent to Participate
The care home is responsible for determining whether a resident is suitable to participate in the service.
This includes:
• Assessing capacity where required  
• Obtaining appropriate consent  
• Involving family or representatives where applicable  
• Reviewing participation where circumstances change  

voice-message.com does not assess resident capacity or consent.

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
Platform-related issues may be directed to voice-message.com.

---

## Privacy Notice (public)
# Privacy Notice
Version 1.0  
Effective Date: [Insert Date]

voice-message.com provides a communication platform to care homes under a Subscription Agreement.

We are committed to protecting personal data and complying with applicable UK data protection law.

## 1) Our Role
When a care home subscribes to the service:
• The care home acts as the Data Controller for resident and family data entered into the platform.  
• voice-message.com acts as the Data Processor, processing data on behalf of the care home.

## 2) What Data Is Processed
The platform may process:
• Resident name  
• Family member name  
• Email address  
• Voice messages uploaded through the platform  
• Basic usage data (such as login activity)

Only the most recent message from each sender is retained.
The platform is not designed to store long-term communication histories.

## 3) Where Data Is Stored
Data is stored within secure UK-based cloud infrastructure operated by voice-message.com.
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
privacy@voicemessagecare.com

---

## Family Terms of Use (public)
# Family Terms of Use
Version 1.0  
Effective Date: [Insert Date]

These Terms apply to individuals using the Family app provided through a participating care home.

By accessing or using the service, you agree to these Terms.

## 1) Nature of the Service
voice-message.com provides a platform that enables non-urgent voice messages between residents and their family or friends.

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

voice-message.com does not monitor or moderate message content.

## 5) Privacy
Personal data is processed in accordance with the Privacy Notice.

The care home acts as Data Controller for resident and family data.

voice-message.com acts as Data Processor.

## 6) Limitation of Liability
voice-message.com provides the platform on an “as is” basis.

We are not responsible for:
• Care decisions  
• Safeguarding matters  
• Staff conduct  
• Loss arising from misuse of the service  

Subject to applicable law, voice-message.com is liable only for direct loss caused by proven breach of contractual obligations and is not liable for indirect or consequential loss.

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
voice-message.com (“the Processor”) and [Care Home Legal Entity] (“the Controller”).

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
voice-message.com  
Version 1.0

1) Calm Over Immediacy — avoid features that introduce urgency, response pressure, or performance expectations.  
2) Asynchronous by Design — no live status, typing, read receipts, delivery confirmations, response time tracking, push/instant reply notifications.  
3) Single-Message Structure — one message in, one message out; no history/archive.  
4) Date-Only Message Display — main care communication views show message date only (no clock time); internal audit timestamps allowed.  
5) No Performance Metrics — do not display analytics that allow response speed or staff performance to be inferred.  
6) Clear Role Boundaries — care home responsible for safeguarding, consent, content management, staff supervision, regulatory compliance; platform does not monitor/moderate.

Core principle: presence without performance pressure.
