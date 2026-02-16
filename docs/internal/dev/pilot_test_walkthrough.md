![logo](../../assets/logo.png)

# Test walkthrough (minimal, scope-aligned)

Scope reference: `docs/support/scope_statement.md`

Format: Step-by-step actions with expected outcomes.

---

## A) Family -> Resident (send + overwrite)

1. Action: On the landing page, select "Family & friends".
   - PASS: You are taken to Login.
   - FAIL: You see "Please choose a role to continue."

2. Action: Use "Sign in" to log in as a family contact.
   - PASS: Login succeeds and you land on the Family resident page.
   - FAIL: You see "We could not sign you in. Please try again."

3. Action: Confirm the page heading shows "Current messages".
   - PASS: "Current messages" is visible.
   - FAIL: A different heading is shown.

4. Action: Select "Play current resident message" (if any).
   - PASS: Audio plays; no history or list is visible.
   - FAIL: Any timeline/feed/history is visible.

5. Action: Use "Start recording" -> "Stop recording" -> "Play" -> "Send message".
   - PASS: Message sends successfully; no other messages are shown.
   - FAIL: You see any history or a non-generic error.

6. Action: Send another message using "Start recording" -> "Stop recording" -> "Play" -> "Send message".
   - PASS: The new message replaces the previous one; no history is visible.
   - FAIL: You can access or view earlier messages.

7. Action: Confirm no history is visible.
   - PASS: There is no timeline/feed/history anywhere.
   - FAIL: Any history or message list is visible.

---

## B) Care Hub – Mobile (carers) -> Resident -> Family

1. Action: On the landing page, select "Care Hub – Mobile".
   - PASS: You are taken to Login.
   - FAIL: You see "Please choose a role to continue."

2. Action: Use "Sign in" to log in as care home staff (shared account).
   - PASS: Login succeeds and you land on the Care Hub – Mobile resident list.
   - FAIL: You see "We could not sign you in. Please try again."

3. Action: Select a resident row (e.g., "Margaret — Room 25").
   - PASS: You enter "Carers' Hub" for that resident.
   - FAIL: You can access a resident without selection, or see a global search.

4. Action: Select "Play current family message".
   - PASS: Audio plays; no history is visible.
   - FAIL: Any timeline/feed/history appears.

5. Action: Select a contact using "Select contact" (e.g., "Kate — daughter").
   - PASS: A contact is required before sending.
   - FAIL: You can send without selecting a contact.

6. Action: Use "Start recording" -> "Stop recording" -> "Play" -> "Send message".
   - PASS: Message sends successfully and replaces the current message for that contact.
   - FAIL: Multiple messages appear or history is visible.

7. Action: Send another message with the same contact selected.
   - PASS: The new message replaces the previous one.
   - FAIL: Older messages remain accessible.

---

## C) Care Hub – Office (admin)

1. Action: Sign in on Care Hub – Office.
   - PASS: You see Documents and admin-only tools.
   - FAIL: Documents are visible on Care Hub – Mobile.

2. Action: Confirm "Documents" is only in the Office menu.
   - PASS: Documents appears in Office only.
   - FAIL: Documents appears in Family or Care Hub – Mobile.

---

## D) Access control checks

1. Action: As family, attempt to access another resident.
   - PASS: "Access denied" screen; no details about other residents.
   - FAIL: Any resident data is visible.

2. Action: As family, attempt to access "Carers' Hub".
   - PASS: "Access denied" screen.
   - FAIL: "Carers' Hub" loads.

3. Action: As staff, attempt to access the Family resident page directly.
   - PASS: "Access denied" screen.
   - FAIL: Family resident page loads.

4. Action: Observe denial copy.
   - PASS: "Access denied" only; no existence leaks.
   - FAIL: Error reveals whether a resident/message exists.

---

## E) Rate-limit / error behaviour (light)

1. Action: Rapidly press Play multiple times.
   - PASS: You eventually see "Please slow down".
   - FAIL: No rate limit response after sustained rapid requests.

2. Action: Observe the rate limit message.
   - PASS: "Please slow down" and "Too many requests. Try again shortly."
   - FAIL: Error shows internal or diagnostic details.

---

## Acceptance criteria

- Audio-only and current-message-only behaviour is enforced.
- No history, timeline, or feed is visible anywhere.
- Access is restricted by role and resident link only.
- Denial messages are generic and do not leak existence.
- Overwrite semantics are confirmed for family and staff flows.
