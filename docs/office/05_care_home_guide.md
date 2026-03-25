![logo](../../assets/logo.png)

## Purpose

This guide is for care home managers and staff.
It explains how the Care Hub is used day to day across the Care Hub – Mobile and Care Hub – Office, in line with the agreed scope for non-urgent, social voice messages, and not for safeguarding matters.

## System structure

The service provides three user interfaces connected to a resident's care circle:

- Care Hub – Mobile: the operational interface used by carers to support the resident and manage voice messaging
- Care Hub – Office: the office/administration interface used by care-home staff
- Family App: used by family members, friends, and other authorised contacts

Each interface has its own controls for creating and managing the messages it sends.

The messaging system uses four channel types linked to each resident:

- Authorised contact channels for Family/Friend -> Resident messages
- A shared Resident -> Family message channel to all authorised contacts
- A one-way Office update channel used by the care home to send updates to authorised contacts
- An Office practical text message channel used by the care home to request structured family replies

## Message playback and control

Each channel keeps only the latest message.
When a new message is recorded, it replaces the previous message in that channel.

Messages within a contact channel can only be played by authorised users of that specific channel. Other authorised contacts cannot access those messages.

Care-home staff using Care Hub – Mobile or Care Hub – Office may also play messages when required for operational support.

Messages are controlled by the group that created them. One group cannot directly replace another group's message.

Unread queue state is tracked per resident and per authorised contact channel.
If all current family messages have been played, then one new family message from a single contact appears as the next unread item for that resident.

## Voice Message Flow Example

![Voice message flow diagram](../../assets/voice-message-flow-diagram.png)

Example resident flow

This diagram shows how voice messages and updates are organised for a single resident. Each authorised contact has their own contact channel for Family/Friend -> Resident messages. Care Hub – Mobile plays these family messages in a fair rotating order, with unplayed messages first.

Resident -> Family channel keeps the latest resident message shared to all authorised contacts. The care home can also send a one-way Office update to all authorised contacts. Office can additionally send a practical text message to gather structured family responses (for example yes/no/maybe, tick-box options, and an optional short note). Each authorised contact channel keeps only the latest Family/Friend -> Resident message. A new message replaces only the previous message in that channel.

## Authorised contact channel structure

For each resident, communication with family and friends is organised through authorised contact channels.

Each authorised contact channel contains one authorised contact only (no shared multi-contact channels).

Family/Friend -> Resident messages are kept per authorised contact channel.
Resident -> Family channel keeps the latest shared resident message to all authorised contacts.
The Office update channel is separate and one-way from the care home to authorised contacts.
Office practical text messages are separate from voice channels and support structured family replies.

## Day-to-day use

### Where this helps in practice

- Sending one office update for routine home news instead of multiple separate calls.
- Supporting resident playback and recording within existing care rounds.
- Reducing repeated non-urgent inbound enquiries to office staff.
- Keeping message handling simple by retaining only the latest message in each channel.
- Giving authorised contacts clear one-way office information without response workflows.

### Access model

Family users sign in with secure email links (email only).

Care Hub – Mobile is intended for individual staff access with an individual Mobile PIN per staff member.

Care Hub – Office is a separate staff/admin login path using two-factor authentication.

Carers use Care Hub – Mobile only.  
Office staff use Care Hub – Office only.

### Setting up residents and contacts

Managers and staff may add residents and their approved family members, friends, or other authorised contacts to the service. The care home decides how residents are identified and which contacts are included.

These admin tasks are handled in Care Hub – Office, not on Care Hub – Mobile.

### Registering a Family Member

Purpose

Care Hub staff can securely invite authorised family contacts to access the Family app.

Steps

1. Open Care Hub – Office.
2. Go to "Register a Family Member".
3. Enter contact details, including relationship to the resident where known (for example: daughter, son, spouse, friend).
4. Select resident.
5. Confirm authorisation.
6. Click "Send invitation".

What Happens Next

The family contact receives an email invitation. They click a secure email login link to sign in. No password is required. They log into the Family app. Access is restricted to the selected resident.

Important notes

This service is for non-urgent social communication only. Only authorised contacts should be registered. Duplicate registrations are prevented automatically. Relationship labels help staff identify the right contact in daily workflows.

### Resident list and cards (Care Hub)

Care Hub users see a scrollable list of residents. Each resident has one communication area showing the latest messages relevant to that role.

### Mobile send section

Staff can record an outgoing message for that resident from the Send section. The card includes a single recorder/player and an "I have listened to this message." checkbox before sending. The resident message is then sent to all authorised contacts as the latest shared resident message.

### Office update message

Office can record a current Office -> Family/Friend update for that resident.
This update is playable in Office, Mobile, and Family.
Mobile users can play this Office message but cannot replace it.

### Assisting residents to record messages

Staff may help residents record short social messages. This assistance is part of normal day-to-day support and is carried out on behalf of the care home.

### Managing access

The care home controls who has access. Staff may add or remove contacts as directed by the care home and in line with its usual processes.

### Managing devices

Homes typically use a desk device for admin tasks (Care Hub – Office) and a Care Hub – Mobile device for recording and listening. The care home decides how devices are used and supervised.

### Care Hub – Mobile and Care Hub – Office devices

Care Hub – Office is typically used for admin tasks on a fixed device. Care Hub – Mobile is typically used on shared devices for recording and listening around the home.

Care Hub – Mobile devices typically use an inactivity warning and lock after a short period. Care Hub – Office devices typically remain signed in, with a clear way to lock the session when leaving the desk.

### Locking sessions and device security

When a device is left unattended, staff may lock the session so that access is limited until the device is in use again.

The care home typically uses the device's own lock (PIN, password, or similar) and supervises devices in line with its usual procedures.

If a quick lock option is used, it is typically a single shared code per care home rather than staff-specific accounts.

### Operational settings

Operational security settings (such as lock timeouts) are managed per care home to support the shared operator login model.

## Responsibility and governance

Staff act on behalf of the care home when using the service. The care home decides how the service is used and supervised in practice.

### Responsibilities / staff use

Care homes support staff, through normal training and supervision, to follow in-app guidance, such as listening to messages before they are sent.

For consent, authority, and safeguarding governance, refer to the Safeguarding and Consent section.

## Time display

Where timing labels are shown in care communication views, the system uses simple AM/PM language (for example: Today AM, Today PM, Yesterday AM, Yesterday PM, or a simple older date + AM/PM). Exact clock times are intentionally not shown in these views.
