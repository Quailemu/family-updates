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

## 2) Cloudflare media audit (walkthrough videos)

- Verify all public walkthrough video URLs load directly in browser.
- Confirm these app walkthrough env vars point to `media.voicemessagecare.com`:
  - `PUBLIC_VIDEO_FAMILY_APP_WALKTHROUGH_URL`
  - `PUBLIC_VIDEO_MOBILE_APP_WALKTHROUGH_URL`
  - `PUBLIC_VIDEO_OFFICE_APP_WALKTHROUGH_URL`
- Confirm service-flow walkthrough URLs are still correct and working.
- Remove duplicate or obsolete large video uploads when safe.

## 3) Render audit (runtime + config)

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
- Public docs:
  - walkthrough pages load for Family/Mobile/Office without placeholder errors.

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
- Walkthrough/document routes regress to wrong variant pages.

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

