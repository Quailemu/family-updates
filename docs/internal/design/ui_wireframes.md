![logo](../../assets/logo.png)

# UI wireframes (scope-aligned, no code)

Scope reference: `docs/support/scope_statement.md`

This document lists components and states in order. It confirms just-in-time signed URL usage on Play and on Send.

This service has three distinct app versions:
- Family app
- Care Hub – Mobile
- Care Hub – Office

Documents are Office-only. Care Hub – Mobile is for carers (record/play only).
Care Hub – Mobile is a restricted operational view; carers cannot access Office/admin functions.
Office users may carry out Mobile tasks as part of supervision or care delivery.

## 1) Landing page - role selection

Header:
- Global header (logo + title + subtitle + subtext lines)
- Front-page descriptor text (exact wording as in UI page map)

Body (order):
- Button: "Family & friends"
- Button: "Care Hub – Mobile" or "Care Hub – Office" (deployment-specific)
- Button: "How it works" (opens the selection page)

Privacy note (all screens):
- "Messages may be played in shared care-home spaces; avoid anything you would not want others to hear."

States:
- Idle: buttons enabled
- Error: "Please choose a role to continue."

## 2) Login (shared pattern)

Header:
- Global header

Body (order):
- Input: Email
- Input: Password
- Button: "Sign in"
- Link: "Forgot password"

Copy:
- "If urgent, contact the care home directly."

States:
- Idle
- Submitting: button disabled, spinner
- Error (generic): "We could not sign you in. Please try again."

## 3) Care home dashboard - resident list

Header:
- Global header
- Page title: "Carers' Hub"
- Notice: "This screen is operated by care staff only."

Body (order):
- List label: "Residents"
- Alphabetical list of residents
  - Row format: "Margaret — Room 25"
  - Row action: open Carers' Hub

Copy:
- "Select a resident to continue."
- "If urgent, contact the care home directly."

States:
- Idle (list visible)
- Empty: "No residents are available."
- Error (generic): "We could not load the resident list. Please try again."

## 4) Carers' Hub (per resident)

Header:
- Global header
- Page title: "Carers' Hub"
- Notice: "This screen is operated by care staff only."

Section A: Play current family message (to resident)
- Button: "Play current family message"
- Indicator: "This message may be replaced at any time."
- JIT signed URL: request on Play only

Section B: Record -> Review -> Send resident message
- Mandatory selector: "Select contact"
  - Option format: "Name — relationship" (e.g. "Kate — daughter")
- Copy: "You are responsible for selecting the correct recipient."
- Step indicator: "1. Record  2. Review  3. Send"
- Record controls:
  - Button: "Start recording"
  - Button: "Stop recording" (recording state only)
- Review controls:
  - Button: "Play"
  - Button: "Discard"
- Send controls:
  - Button: "Send message"
- Copy: "Sending replaces the current message for that contact."
- JIT signed URL: request on Send only (upload path)

Copy:
- "If urgent, contact the care home directly."

States:
- Idle: no recording
- Recording: waveform timer visible, Stop button active
- Review: playback controls active
- Sending: button disabled, spinner
- Empty (no recording): "No recording yet. Tap Start recording to begin."
- Error (generic): "We could not save this message. Please try again."
- Access denied: "Access denied. You do not have permission to do that."

## 5) Family resident page

Header:
- Global header
Subheader:
- "Current messages"

Section A: Play current resident message
- Button: "Play current resident message"
- Indicator: "This message may be replaced at any time."
- JIT signed URL: request on Play only

Section B: Record -> Review -> Send family message
- Step indicator: "1. Record  2. Review  3. Send"
- Record controls:
  - Button: "Start recording"
  - Button: "Stop recording" (recording state only)
- Review controls:
  - Button: "Play"
  - Button: "Discard"
- Send controls:
  - Button: "Send message"
- Copy: "Sending replaces your previous message to this resident."
- JIT signed URL: request on Send only (upload path)

Copy:
- "If urgent, contact the care home directly."

States:
- Idle
- Recording
- Review
- Sending
- Empty: "No current message is available."
- Empty: "The message may have been replaced."
- Error (generic): "We could not play the message. Please try again."
- Access denied: "Access denied. You do not have permission to do that."

## 6) Access Denied / Rate Limited / Generic Error

Header:
- Global header

Access Denied:
- Title: "Access denied"
- Body: "You do not have access to this content."
- Button: "Return to login"

Rate Limited (429):
- Title: "Please slow down"
- Body: "Too many requests. Try again shortly."
- Button: "Return to login"

Generic Error:
- Title: "Something went wrong"
- Body: "Please try again."
- Button: "Return to login"

## Scope guard reminders

- No urgency cues (no badges, timestamps, "new" labels).
- No history, timeline, or feed.
- No text inputs beyond login.
- No IDs shown in UI.
