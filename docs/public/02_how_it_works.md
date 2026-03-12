![logo](../../assets/logo.png)

# Voice messages — how it works

## System structure

The system has three application interfaces for different groups of people associated with the resident: Care Hub – Mobile, Care Hub – Office, and the Family App (which includes family members, friends, and other authorised contacts).

Each interface has its own role in the resident's care circle. The product is role-based and non-urgent.

## One-message-only model

The service uses a one-message-only principle in each message lane.  
When a new message is sent in a lane, the previous message in that lane is automatically deleted.

Only the latest message remains in each lane.

## Message lanes

| Message lane | Created by | Playable by | Replaceable by |
| --- | --- | --- | --- |
| Family/Friend -> Resident | Family App | Family App, Care Hub – Mobile, Care Hub – Office | Family App |
| Resident -> Family/Friend | Care Hub – Mobile | Family App, Care Hub – Mobile, Care Hub – Office | Care Hub – Mobile |
| Office -> Family/Friend | Care Hub – Office | Family App, Care Hub – Mobile, Care Hub – Office | Care Hub – Office |

All current messages for that resident may be played by authorised users across these groups, but no group can alter another group's message. Each message lane may only be replaced by the interface that created it.

## Family/friend channels and sub-groups

Family and friends are organised into authorised channels (sub-groups) around the resident.
A sub-group is often one person (for example one daughter, one son, or one close friend), but can include more than one authorised contact where the care home chooses.

Each sub-group channel has one current message each way at any one time:

- Family/Friend -> Resident (current message only)
- Resident -> Family/Friend (current message only)

When a new message is recorded in either direction for that same channel, the previous message in that direction is replaced.

## Flow diagram (channel model)

![Voice message flow diagram](../../assets/voice-message-flow-diagram.png)

The diagram shows the three-interface model:

- Care Hub – Office provides one-way informational Office updates.
- Family/friend sub-groups each have their own channel to the resident (often one person per sub-group).
- Care Hub – Mobile supports resident playback and resident replies.

```text
Care Hub – Office
    |  Office -> Family/Friend (one current update per resident/family group)
    v
Family/Friend sub-group 1 <-> Resident (one current message each way)
Family/Friend sub-group 2 <-> Resident (one current message each way)
Family/Friend sub-group 3 <-> Resident (one current message each way)
    ^
    |  Resident support and playback
Care Hub – Mobile
```

## Playback and care setting

Playback access is limited to authorised users in the resident's care circle.  
Messages may be played in normal care environments where staff are supporting residents.

This is non-urgent and not live messaging. Messages are played and replies are recorded when staff are available.

## Time display

The interface uses simple timing language rather than exact clock times, for example:

- Today AM / Today PM
- Yesterday AM / Yesterday PM
- A simple older date with AM/PM

Exact times are intentionally not shown in the main care communication views.

## Interface roles

### Family App

Used by authorised contacts (family members, friends, and other approved contacts) to send and play social voice messages linked to the resident.

### Care Hub – Mobile

Used by carers to play messages to residents and support residents in recording replies.

### Care Hub – Office

Used by office and senior staff for oversight, governance documents, and Office-originated updates for each resident.

## Safeguarding boundary

Safeguarding duties remain with the care home.  
This service is not a safeguarding alert system and is not monitored in real time.
