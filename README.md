baseline before cleanup

# voicemailcare.com

Calm, non-urgent voice messaging between residents and authorised contacts. One message in, one message out.

Optional transcript assist is supported across Family, Care Hub – Mobile, and Care Hub – Office.
When requested, transcript text can be shown for the current message, but voice remains the source of truth.

## Install

```bat
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Run (single app)

```bat
streamlit run app.py
```

## Single-service variant routing

Runtime resolves app variant from request path first:

- `/` -> public
- `/family` -> family
- `/mobile` -> mobile
- `/office` -> office

`APP_VARIANT` remains as fallback for local/dev or unmapped paths.

## Deployment topology (current live)

- Live Render service: `voicemailcare-main`
- Primary domain (indexed): `https://voicemailcare.com`
- Media domain: `https://media.voicemailcare.com`

### Legacy infrastructure status

- Any previous Render project names and auth-cookie env groups that now use an `old-` prefix are legacy.
- Legacy `old-*` Render resources are not part of active runtime documentation for this service.
- Legacy preview/host URLs are redirected to the canonical domain where configured.

## Run by variant

```bat
.\run_family.cmd
.\run_care_hub_phone.cmd
.\run_care_hub_office.cmd
```

Ports:
- Family: http://localhost:8501
- Care Hub – Mobile: http://localhost:8502
- Care Hub – Office: http://localhost:8503

## Local backend development without login

For local backend work only, set the service-role key in the same terminal, then
use a dev launcher.

PowerShell:

```powershell
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_SECRET_KEY="your_secret_key"
.\run_dev_care_hub_office.cmd
```

Command Prompt:

```bat
set SUPABASE_URL=https://your-project.supabase.co
set SUPABASE_SECRET_KEY=your_secret_key
.\run_dev_care_hub_office.cmd
```

Optional selectors:

```powershell
$env:DEV_AUTH_BYPASS_CARE_HOME_ID="care_home_uuid"
$env:DEV_AUTH_BYPASS_AUTH_UID="auth_user_uuid"
```

The shortcut only activates on localhost/127.0.0.1/::1, keeps the selected
Family/Mobile/Office variant locked, and uses the first active mapping row when
no selector is provided.

## Supabase auth setup (role-based)

- Family: email magic-link auth (email only). Set `FAMILY_MAGIC_LINK_REDIRECT_URL`.
- Care Hub – Mobile: individual staff PIN for day-to-day access, with email secure link only for first sign-in / recovery (`CARE_MOBILE_MAGIC_LINK_REDIRECT_URL`).
- Care Hub – Office: separate staff/admin login path (email + password), with Office MFA available if enabled.
- In Supabase Dashboard, add Family/Mobile magic-link redirect URLs to Auth -> URL Configuration -> Redirect URLs.

## Documentation

- `docs/SYSTEM_OVERVIEW.md`
- `docs/VOICE_MESSAGE_MASTER_PLAN.md`
- `docs/security/SECURITY_MODEL.md`
- `docs/registration/FAMILY_REGISTRATION.md`

## Cloudflare media (R2)

- Media base URL: `https://media.familyupdates.care`
- Media bucket name (ops reference): `voicemailcare-media`
- App uses Supabase Storage for message audio playback.
- Keep public walkthrough videos out of the app.
