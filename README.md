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

## Single-service multi-domain (Render)

Use one web service with multiple custom domains and set:

- `APP_VARIANT_BY_HOST` for domain-to-variant mapping
- keep `APP_VARIANT` as fallback for unmapped hosts or local/dev

Example:

`APP_VARIANT_BY_HOST=public.voicemailcare.com=public,family.voicemailcare.com=family,care-hub-mobile.voicemailcare.com=mobile,care-hub-office.voicemailcare.com=office`

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
