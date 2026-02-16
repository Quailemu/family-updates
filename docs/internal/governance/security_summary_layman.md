# Security summary (plain English)

Scope reference: `docs/support/scope_statement.md`

Think of the system like a building with locked rooms.

## Key ideas

- **JWT = tamper‑proof ID card (expires).** It proves who you are, but only for a short time.
- **Edge Function = security desk.** It checks your ID and whether you’re allowed into a specific room.
- **RLS = locked drawers.** The database itself enforces who can see which rows.
- **Signed URLs = temporary visitor passes.** They grant access to one file for a short time and then expire.

## What this means in practice

- Access control is enforced at the database level, not just in application code.
- Files are never publicly accessible; access is granted only via time‑limited signed URLs generated after server‑side authorization checks.

## Why this is safer

- People can’t browse files or lists, even if they guess a URL.
- Family access is limited to their linked resident and only when all links are active.
- Care homes control access and supervision with a shared operator login.

This approach keeps the system simple, narrow in scope, and easier to defend under scrutiny.
