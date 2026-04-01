baseline before cleanup

# voicemailcare.com

Calm, non-urgent voice messaging between residents and authorised contacts. One message in, one message out.

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
