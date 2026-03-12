![logo](../../assets/logo.png)

# Service overview

## Purpose

voice-message.com is a simple tool for exchanging non-urgent social voice messages between residents in care homes and their authorised contacts. The care home office may also send non-urgent general updates about daily life in the home to authorised contacts.

Office updates are one-way informational messages and replies cannot be sent through the system.

The service is not intended for care updates, health information, safeguarding communication, or urgent enquiries.

## Where this helps in practice

- Sending one non-urgent office update to reduce repeated routine calls from authorised contacts.
- Supporting residents to send replies during planned care routines rather than arranging live calls.
- Reducing front-desk time spent on repeated non-urgent check-in requests.
- Keeping communication clear by showing only the current message in each direction.
- Sharing day-to-day home updates as one-way information without creating reply pressure.

## System structure

The system has three application interfaces for different groups of people associated with the resident: Care Hub – Mobile, Care Hub – Office, and the Family App (which includes family members, friends, and other authorised contacts).

Each interface is role-based and uses separate controls.
The messaging system uses two types of channels linked to each resident: two-way contact channels and a one-way Office update channel.

## Message playback and control

In each direction, only one current message is kept. A new message replaces the previous message in that same direction.
Messages in a contact channel may only be played by authorised users of that specific channel. Other authorised contacts cannot access those messages. Care home staff using Care Hub – Mobile and Care Hub – Office may also play messages for operational support.

There is no archive, no scrolling thread, and no message history.

## Authorised contact channel structure

Authorised contacts are organised into authorised contact channels for each resident.
An authorised contact channel may contain one authorised contact or multiple authorised contacts where configured by the care home.

Each two-way contact channel supports Family/Friend -> Resident and Resident -> Family/Friend.
The Office update channel is separate and one-way from the care home to authorised contacts.

![Voice message flow diagram](../../assets/voice-message-flow-diagram.png)

The Voice Message Flow Diagram should appear on any page where the messaging system is explained, as it provides the clearest explanation of how the channels operate.
Updates are sent from the care home to keep families informed about day-to-day events. Messages are one-way and replies cannot be sent through this system. These updates are for non-urgent, non-medical information only. For any urgent, medical, or other queries, please contact the care home directly.

## App versions (three distinct experiences)

- Family App: used by authorised contacts only.
- Care Hub – Mobile: used by carers for resident support and playback/recording assistance.
- Care Hub – Office: used by office/senior staff for oversight, governance, and Office-originated updates.

Family and Care Hub are separate role-based experiences.

## Time display

The product uses simple AM/PM timing language in applicable views (for example, Today AM, Today PM, Yesterday AM, Yesterday PM, or a simple older date + AM/PM). Exact clock times are intentionally not shown in the main care communication views.

## Roles

### Care home (operator)

The care home operates the service in practice and is responsible for day-to-day use. This includes:

- controlling access to the service
- supervising how the service is used
- managing devices used for recording and playback
- managing resident and authorised contacts

The care home is responsible for identifying residents, confirming consent or authority, and deciding who can send and receive messages.

### Residents

Residents use the service to receive and send social voice messages with support from the care home as needed. The service is not a channel for care or health updates.

### Authorised contacts

Authorised contacts (family members, friends, and other approved contacts) use the Family App to send and play social messages only. They should not rely on it for care information, health updates, or safeguarding concerns. Those matters should be directed to the care home using its usual channels.

### Service provider (voice-message.com)

The service provider supplies the technical platform that enables the exchange of social voice messages. The platform does not provide care updates or health information and is not intended to be used as a safeguarding channel.

The platform does not verify identity, consent, or authority, and does not review or moderate message content.
