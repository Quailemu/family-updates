![logo](../../assets/logo.png)

# Service overview

## Purpose

voice-message.com is a simple tool for exchanging non-urgent, social voice messages between residents in care homes and their authorised contacts. It supports staying in touch and is not intended for care updates, health information, or safeguarding communication.

## System structure

The system has three application interfaces for different groups of people associated with the resident: Care Hub – Mobile, Care Hub – Office, and the Family App (which includes family members, friends, and other authorised contacts).

Each interface is role-based and uses separate controls.

## Message playback and control

The service uses separate message lanes linked to each resident.  
Each lane follows a one-message-only rule: a new message replaces the previous message in that same lane.

| Message lane | Created by | Playable by | Replaceable by |
| --- | --- | --- | --- |
| Family/Friend -> Resident | Family App | Family App, Care Hub – Mobile, Care Hub – Office | Family App |
| Resident -> Family/Friend | Care Hub – Mobile | Family App, Care Hub – Mobile, Care Hub – Office | Care Hub – Mobile |
| Office -> Family/Friend | Care Hub – Office | Family App, Care Hub – Mobile, Care Hub – Office | Care Hub – Office |

All current messages for that resident may be played by authorised users across these groups, but no group can alter another group's message. Each message lane may only be replaced by the interface that created it.

This means, for example:

- Office messages are playable in Mobile and Family.
- Mobile/resident messages are playable in Office and Family.
- Office cannot replace Mobile/resident messages.
- Mobile cannot replace Office messages.
- Family cannot replace Office or Mobile/resident messages, except by replacing its own Family lane message.

There is no archive, no scrolling thread, and no message history.

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
