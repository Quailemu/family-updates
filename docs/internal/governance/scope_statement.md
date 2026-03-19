![logo](../../assets/logo.png)

# Scope Statement (Authoritative - Non-Negotiable)

Project: voice-message.com

Purpose:
- Non-urgent, social voice messages only between residents and their family/friends.
- Audio-only. No text, no video, no live calls.

Out of scope:
- Care updates, health information, safeguarding alerts, monitoring, assessment, or care planning.
- Text messages, media uploads, or video.
- Message history, feeds, or timelines.
- Moderation, review queues, or content analysis.

Data minimisation:
- Each channel keeps only the latest audio message.
- One message to the resident and one from the resident per contact.
- New messages overwrite the previous message.
- No archive or historical access.

Roles & responsibility:
- Care home is the operator and Data Controller.
- Care home manages identity, consent/LPA, supervision, access, devices, and disputes.
- The platform provides technical tooling only and does not verify identity, consent, authority, or content.

Security posture:
- Access controlled via authentication, server-side authorization, and database-level enforcement (RLS).
- Storage is non-browsable; audio access is via short-lived signed URLs only.
- Conservative rate limiting and documented incident response procedures are in place.

This document defines the maximum scope of the service. Features or behaviours not explicitly included here are out of scope by design.
