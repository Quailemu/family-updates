# Weekly Ops Audit Checklist

Purpose: keep deployments predictable, control Supabase egress, and catch regressions early.

Frequency: once per week (and again after any production deployment).

## 1) Supabase audit (cost + reliability)

- Check project usage dashboard:
  - Storage egress trend (week over week).
  - Database egress/API usage trend.
  - Storage size growth.
- Spot-check latest messages:
  - Confirm new audio rows are using `audio_source = storage` where expected.
  - Confirm legacy inline audio is not growing unexpectedly.
- Check for query waste:
  - Repeated large reads.
  - Unexpected spikes after deploys.
- Record findings in a dated note.

## 2) Media audit

- Confirm message audio record/playback still works in each active workspace.
- Confirm no public walkthrough video routes are linked from the app.
- Remove duplicate or obsolete large media uploads when safe.

## 3) Render audit (runtime + config)

- Active live service: `voicemailcare-main`
- Primary domain must be: `voicemailcare.com`
- Media domain must be: `media.voicemailcare.com`
- Treat any Render resources with `old-` prefixes as legacy only (not active runtime).
- Confirm all required env vars are present and correctly named.
- Check logs for:
  - 4xx/5xx spikes
  - media loading errors
  - auth/session errors
- Confirm deployed commit hash matches latest intended GitHub commit.
- Confirm no temporary/test env vars remain.

## 4) App smoke tests (Family, Mobile, Office)

- Family:
  - login works
  - send voice message works
  - latest resident message plays
- Mobile:
  - login + PIN flow works
  - play next message works
  - record/send resident message works
- Office:
  - login + 2FA flow works
  - office update send works
  - practical message send + responses view works
- Public front page:
  - main public page loads and shows the three access buttons (Family, Care Hub – Mobile, Care Hub – Office).
  - How it works loads without video placeholders.

## 5) GitHub/source-control audit

- Confirm `main` contains all production fixes.
- Confirm no local-only hotfixes are missing from Git.
- Tag noteworthy releases (optional) for rollback clarity.

## 6) Rollback readiness check

- Keep the previous known-good commit hash noted.
- Confirm you can redeploy a prior commit quickly in Render.
- If a deployment degrades behavior:
  - roll back to last known-good commit
  - verify core smoke tests
  - log incident summary and root cause.

## 7) Pilot risk flags (must escalate immediately)

- Egress rises sharply without matching user activity.
- Messages fail to send or playback fails in any variant.
- Auth/login loops or repeated temporary unavailable states.
- Public document routes regress to wrong variant pages.

## Quick weekly record template

- Date:
- Auditor:
- Deployed commit:
- Supabase egress status:
- Cloudflare media status:
- Render/log status:
- Smoke test result:
- Issues found:
- Actions taken:
- Follow-up due date:

