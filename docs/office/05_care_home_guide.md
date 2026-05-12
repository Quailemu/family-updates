![logo](../../assets/logo.png)

## Purpose

This guide is for care home managers and staff.
It explains how familyupdates.care is used day to day for structured family communication around care.

There are three roles for the family to fill:

1. Family Organiser.
2. Person available for urgent/emergency phone contact and emergency protocol.
3. Care support.

familyupdates.care is for non-urgent communication only.

## System structure

If a care home later runs its own completely separate system, the Care Home system provides three app interfaces for that care-home setup:

- Care Home Mobile: the operational interface used by carers to support the resident and manage voice messaging
- Care Home Office: the office/administration interface used by care-home staff
- Care Home Family Hub: used by Family Members registered by the care home

Each interface has its own controls for creating and managing the messages it sends.

In this guide, **Family Member** means a person the care home has decided may access a resident in the service.

The Care Home system is separate from any Family system used by a Family Organiser. The two systems may relate to the same real-life person, but they do not connect inside familyupdates.care, and there is no planned direct connection at this stage.

In the family-facing version, the app does not communicate directly with the care home. Care home updates usually go to the Family Organiser by the care home's normal method, such as email. The Family Organiser may then post an organiser update or request in the app if appropriate.

The messaging system uses four channel types linked to each resident:

- Family Member channels for Family/Friend -> Resident messages
- A shared Resident -> Family message channel to the family group, plus a direct Resident -> Family message channel to a selected Family Member
- A one-way Office update channel used by the care home to send updates to Family Members
- An Office practical text message channel used by the care home to request structured family replies

Carers may send their own professional care updates using their own system. They may also use the app directly for family communication where enabled. If they do not use the app, they can text the Family Organiser, who may post an organiser update or request if appropriate.

## Message playback and control

Each channel keeps only the latest message.
When a new message is recorded, it replaces the previous message in that channel.

Optional transcript assist may be requested when recording in Family, Mobile, and Office.
When available, transcript text appears under "Transcript assist" for the current message.
Transcript text may contain errors; voice remains the source of truth.

Messages within a Family Member channel can only be played by users of that specific channel. Other Family Members cannot access those messages.

Care-home staff using Care Home Mobile or Care Home Office may also play messages when required for operational support.

Messages stay in the channel where they were created. A Family Member can replace their own latest Family -> Resident message, Mobile can replace the latest Resident -> Family message, and Office can replace the latest Office update. One channel cannot directly replace another channel's message.

Playback status is tracked separately for each resident and each Family Member channel.
When a new family message arrives, only that Family Member channel is marked as unplayed.
If all other current family messages have already been played, that new message appears as the next unplayed item for that resident.

## Voice Message Flow Example

Example resident flow

Each Family Member has their own channel for Family/Friend -> Resident messages. Care Home Mobile plays these family messages in a fair rotating order, with unplayed messages first.

Resident -> Family channels keep the latest shared resident message to the family group, and the latest direct resident message to a selected Family Member. The care home can also send a one-way Office update to all Family Members. Office can additionally send a practical text message to gather structured family responses (for example yes/no/maybe, fixed tick-box options, and an optional short context note). Each Family Member channel keeps only the latest Family/Friend -> Resident message. A new message replaces only the previous message in that channel.

## Family member channel structure

For each resident, communication with family and friends is organised through Family Member channels.

Each Family Member channel contains one Family Member only (no shared multi-user channels).

Only the latest Family/Friend -> Resident message is kept per Family Member channel.
Resident -> Family channels keep the latest shared resident message to the family group, and the latest direct resident message to a selected Family Member.
The Office update channel is separate and one-way from the care home to Family Members.
Office practical text messages are separate from voice channels and support structured family replies.

## Day-to-day use

### Where this helps in practice

- Sending one office update for routine home news instead of multiple separate calls.
- Supporting resident playback and recording within existing care rounds.
- Reducing repeated non-urgent inbound enquiries to office staff.
- Keeping message handling simple by retaining only the latest message in each channel.
- Giving Family Members clear one-way office information without response workflows.
- Sending practical Office text messages when a quick structured family response is needed (for example Yes/No/Maybe, fixed tick-box options, and an optional short context note).
- Reviewing structured family replies in Office to support practical planning and follow-up.

### Access model

Family users sign in with secure email links (email only).

Care Home Mobile is intended for individual staff access with an individual Mobile PIN per staff member.

Care Home Office is a separate care home staff/admin login path using two-factor authentication.

Carers use Care Home Mobile only.
Office staff use Care Home Office only.

### Setting up residents and contacts

Managers and staff may add residents and Family Members to the service. The care home decides how residents are identified and who is added.

These admin tasks are handled in Care Home Office, not on Care Home Mobile.

### Registering a Family Member

**Purpose**
Care Home Office can invite and register Family Members in the service.

In Stages 1-3, registration is an at-home coordination action. The organiser / family decides who should be added.

In Stage 4, registration is a Care Home Office action between the named care home and the named Family Member.

**Steps**
1. Open Care Home Office.
2. Go to "Register a Family Member".
3. Enter first name, last name, and email.
4. Select the person/resident.
5. Confirm the appropriate access decision:
   - Stages 1-3: the organiser / family has decided the person may be added.
   - Stage 4: the care home has decided the person may be added.
6. Click "Send invitation".

**What happens next**
The family contact receives an email invitation. They click a secure email login link to sign in. No password is required. They log into the Family Hub. Access is restricted to the selected person/resident. The registration record should include the setup or care home name, Family Member name/email, Office account, and date.

**Important notes**
This service is for non-urgent social communication only. Only appropriate Family Members should be registered. Duplicate registrations are prevented automatically.

### Resident list and communication areas (Care Home system)

In Care Home Office and Care Home Mobile, each resident has one communication area showing the latest message in each channel.

### Mobile send section

Staff can record an outgoing message for a resident from the Send section. The communication area includes a single recorder/player and an "I have listened to this message." checkbox before sending. The resident message is then sent to the family group or to the selected Family Member as that current resident message.

### Office update message

Office can record a current Office -> Family Member update for a resident.
This update is playable in Office, Mobile, and Family.
Mobile users can play this Office message but cannot replace it.

### Assisting residents to record messages

Staff may help residents record short social messages as part of normal day-to-day support, carried out on behalf of the care home.

When a resident message is sent, it is saved as one latest Resident -> Family message to the family group or to the selected Family Member for that resident.

This channel is one-way from resident to family (it is not a live conversation thread). A new resident message replaces the previous resident message in that selected channel.

Recording and playback are done when staff are available, to fit normal care routines.

### Managing access

The care home controls who is registered and allowed to participate for each resident. Only Care Home Office staff may add, maintain, or remove Family Members in line with the care home's usual processes.
familyupdates.care provides technical infrastructure only. It does not decide, verify, or validate identity, authority, entitlement, or appropriateness for registration decisions.

### Managing devices

Homes typically use a desk device for Care Home Office admin tasks. Care Home Mobile is used on the dedicated mobile device supplied for this service, with lanyard, for recording and listening.

The care home decides how the supplied Care Home Mobile device is supervised and used during normal care routines.

### Care Home Mobile and Care Home Office devices

Care Home Office is typically used for admin tasks on a fixed device. Care Home Mobile is typically used on shared devices for recording and listening around the home.

Care Home Mobile devices typically use an inactivity warning and lock after a short period. Care Home Office devices typically remain signed in, with a clear way to lock the session when leaving the desk.

### Locking sessions and device security

Care Home system sessions must not be left open on unattended devices.

Care Home Mobile uses individual staff access. Each staff member has their own Mobile PIN. Shared Mobile PINs should not be used.

If a staff member forgets their Mobile PIN, an authorised Office user can reset it in Care Home Office under Security. The staff member then sets a new PIN at next Mobile sign-in.

When stepping away, staff should lock the device screen (or sign out) in line with the care home's normal security procedures.

Care Home Mobile is used on the dedicated mobile device supplied for this service, with lanyard. That device should stay under staff supervision during use and be stored securely when not in use.

Care Home Office is used on office-managed devices. Access should be limited to designated office staff, with desk sessions locked when unattended.

If a device is lost, misplaced, or access is suspected to be compromised, staff should follow the care home's incident process immediately and reset affected access.

### Operational settings

Each care home chooses how quickly sessions lock after inactivity.

In practice, this is the "time before auto-lock" for devices that are left idle.

Choose a short enough time to protect resident information, but long enough that staff can work through normal care tasks without repeated disruption.

Review this setting regularly, especially after incidents, staffing changes, or workflow changes.

## Responsibility and governance

Staff act on behalf of the care home when using the service. The care home decides how the service is used and supervised in practice.

### Responsibilities / staff use

Care homes support staff, through normal training and supervision, to follow in-app guidance, such as listening to messages before they are sent.

For consent, authority, and safeguarding governance, refer to the Safeguarding and Consent section.

## Time display

Where timing labels are shown in care communication views, the app uses date-only labels. Exact clock times and AM/PM markers are not shown.
