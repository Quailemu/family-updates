# System Diagram Walkthrough Transcript

> Transcript style requirement: This script is written for a screen recording narrated in a calm, clear, spoken style for viewers to watch and listen to. Keep wording simple, practical, and walkthrough-focused, matching the existing transcript tone and structure.

"This is the systems diagram for voicemailcare.com.

It shows how Family Hub, Care Hub - Mobile, and Care Hub - Office fit together."

---

"Each family contact has a separate Family -> Resident message channel.

Only the latest message is kept in each channel.

A new message replaces the previous one in that same channel."

---

"Resident -> Family is a shared latest-message channel for all family members.

Office can send one-way updates to family and practical structured messages.

The service is non-live and non-urgent."

---

"In Care Hub - Mobile, queue order is fixed.

Unplayed messages are first, in family order.

After unplayed messages, playback continues in the same fixed family order.

Order changes only when staff confirm listened and select 'Mark listened and move to next.'"

---

"In Care Hub - Office, playback is review-only.

Reviewing a message in Office does not change queue order."



