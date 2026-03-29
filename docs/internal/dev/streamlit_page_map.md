![logo](../../assets/logo.png)

# Streamlit page map and wireframes (strict scope)

Scope reminders:
- Audio-only.
- Current message only (no history/feed/timeline).
- No text updates, care notes, requests, or assessments.

## Shared (all apps)

### Front page descriptor (exact text)

- "voicemailcare.com — for non-urgent social voice messages."
- "One message kept at a time in each direction, with no threads."
- "Only one message is kept between each family member and each resident, in each direction."
- "Each new message deletes the previous message, to keep communication simple and up to date."

### Login

Purpose: authenticate with email + password.

Components:
- Email field
- Password field
- "Sign in" button
- "Forgot password" link
- Short privacy + acceptable use note (non-urgent, social audio only)

Empty/error states:
- Invalid credentials -> generic error
- Rate limited -> "Too many attempts, try later"

### Access denied / Rate limited / Error

Purpose: generic failure screens without existence leaks.

Components:
- Friendly message: "You don’t have access to that."
- "Return to login"
- "Contact support" (role-based contact hint)

## Hamburger menu (all apps)

The first item in the hamburger menu is always:
- "How it works"

Documents are Office-only. Families see Privacy & data, Terms & conditions, and Contact care home.

## Family app

Purpose: families and friends send and listen to social messages.

Pages:
- Family login
- Family send/listen page
- How it works (selection)
- How it works — Family app
- Privacy & data
- Terms & conditions
- Contact the care home

Menu items:
- How it works
- Privacy & data
- Terms & conditions
- Contact the care home

Notes:
- Families use the Family app only.
- No care hub features are visible.

## Care Hub – Mobile

Purpose: carers use a shared lanyard device for recording and playback only.

Pages:
- Care Hub – Mobile login
- Resident list / inbox
- Record + play (per resident)
- How it works (selection)
- How it works — Care Hub – Mobile

Menu items:
- How it works

Notes:
- Restricted operational view used by carers.
- Carers using Care Hub – Mobile cannot access Office/admin functions.
- No documents or admin tools.
- Shared device, supervised use.

## Care Hub – Office

Purpose: senior staff/admin use a desk device for admin and compliance tasks.

Pages:
- Care Hub – Office login
- Resident list / inbox
- Documents pack
- How it works (selection)
- How it works — Care Hub – Office

Menu items:
- How it works
- Documents

Notes:
- Provides full access and includes Care Hub – Mobile functionality.
- Office users may carry out Mobile tasks as part of supervision or care delivery.
- Office oversight requires visibility of messages coming in and going out.
- Admin access only; carers do not use this app.

## Non-negotiable UI rules

- Never show IDs (resident_id, care_home_id, message_id).
- No global search across residents or users.
- Just-in-time signed URLs only (generate on play/upload).
- No user-visible history or timeline.
- Generic denial messaging (no existence leaks).
- Keep session state minimal; avoid caching sensitive data.
