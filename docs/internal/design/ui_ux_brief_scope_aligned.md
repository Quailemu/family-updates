![logo](../../assets/logo.png)

# CODEX UI/UX BRIEF (scope-aligned)

Royal Mail-style behaviour with deckchair palette, adapted to the current UI scope.

Scope reference: `docs/support/scope_statement.md`

This brief preserves the Royal Mail behavioural discipline while removing all out-of-scope features (no history, no inbox, no timeline, no triage).

---

## 1) Design intent (calm, trustworthy, awake, human)

- Calm and trustworthy
- Awake (not muted)
- Human, not techy
- Serious without being cold
- High contrast and purposeful restraint

Core rule: only one colour speaks at full volume at a time.

---

## 2) Information architecture (task-first, scope compliant)

App structure (three distinct app versions):
- Landing page: role selection (Family & friends / Care home staff)
- Login (shared pattern)
- Care home dashboard: resident list (alphabetical; preferred name + room/reference)
- Carers' Hub (per resident): play current family message + record/review/send resident message (per contact)
- Family resident page: play current resident message + record/review/send family message
- Access denied / rate limited / generic error

App separation:
- Family app: families and friends only.
- Care Hub – Mobile: carers on a shared lanyard device (restricted operational view; no Office/admin functions).
- Care Hub – Office: senior staff/admin for documents and oversight; includes Care Hub – Mobile functionality.
- Office users may carry out Mobile tasks as part of supervision or care delivery.

No inbox, no timeline, no history, no triage, no message list with timestamps.

Header (always visible):
- Logo + product name + subtitle + two-line subtext (as specified in `docs/support/ui_page_map.md`)

Primary task surfaces:
- One primary CTA per section (e.g., "Play current family message", "Send message")
- Record -> Review -> Send flow is explicit and step-based

---

## 3) Colour tokens (locked palette behaviour)

Primary:
- Cerise: #D80073 (brand + primary actions)

Neutrals:
- Background: #F5F1EC
- Text/structure: #1F1F1F

Secondary:
- Teal: #0F8B8D (secondary actions/links)
- Coral: #E24A2B (secondary warmth)
- Soft pink: #E86A9A (soft surfaces)
- Raspberry: #B1125B (deep warm support)
- Turquoise thin accent: #1FAFB3

High-energy accent:
- Acid yellow: #C7D300 (focus/live only; thin use)

Rule: one loud colour at a time; no competing bright colours in one element.

---

## 4) Page framing (Royal Mail-style orientation)

- Header band or header accents use #D80073
- Main content sits on #F5F1EC
- Sections are white/near-white cards with clear spacing
- The user always knows "where they are" and "what to do next"

---

## 5) Buttons (shape, hierarchy, states)

Shape:
- Rectangular, small radius
- Solid fill, no gradients, no decorative shadows

Primary CTA:
- Fill: #D80073
- Text: white
- Hover: subtle darken
- Disabled: neutral grey

Secondary CTA:
- Fill: #0F8B8D
- Same size/shape as primary

Tertiary CTA:
- Text-only in #0F8B8D
- Underline on hover

Destructive (rare):
- Explicit label (e.g., "Discard")
- Confirmed action, not a shortcut

---

## 6) Tabs / segmented controls (only if needed)

Use only if a page must switch modes without adding screens.
If used:
- Inactive: neutral background, dark text
- Active: underline or bottom border in #D80073
- Focus ring: thin #C7D300

Avoid adding new tabs that imply history or inboxes.

---

## 7) Index pages (dashboard feel without scope drift)

Care home dashboard:
- A clean resident list with clear selection state
- No urgency badges or timestamps

Family resident page:
- Two clear sections: play current message, record/review/send
- No history, no message lists

---

## 8) Cards, lists, selection

Resident list row:
- Format: "Margaret — Room 25"
- Hover: light neutral highlight
- Selected: thin left border in #D80073

No message list rows or timestamp chips (out of scope).

---

## 9) Forms (simple and explicit)

Record/send pattern:
- One primary action per step
- "Start recording" becomes "Stop recording"
- After recording: show playback + "Send message"

Input styling:
- Large tap targets
- Visible labels (not placeholder-only)
- Inline error text (not colour-only)

---

## 10) Feedback & highlights

Success:
- Neutral confirmation; small cerise tick

Error:
- Clear message + recovery action
- No technical detail

Live recording:
- Tiny pulse dot in #C7D300 + label "Recording"
- Background remains calm

---

## 11) Accessibility + keyboard

- Visible focus rings (#C7D300)
- Do not rely on colour alone for status
- Clear headings and landmarks
- Large clickable areas

---

## 12) Royal Mail feel test (scope-aligned)

If any screen fails these, revise:
- Is the main task obvious in 3 seconds?
- Is there only one primary CTA?
- Is selection state unmistakable without colour?
- Is colour always doing a job?
- Does anything imply history or monitoring? (if yes, remove)
