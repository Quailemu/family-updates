# familyupdates.care

Calm, non-urgent family coordination around care. One current item replaces the previous item in that channel.

The live direction is the family-side coordination system:

- Family Office for the Family Organiser.
- Family Hub for wider Family Members.
- Mobile access for a carer, helper, supported person, or trusted family member.

Mobile is part of the starting model. If a Family Organiser is needed, the system should also make room for support from a carer/helper/professional where appropriate, rather than pushing caring work onto the organiser.

The active situations are:

- At home with Family Organiser + Mobile Support.
- Care home with Family Organiser + Mobile Support.

There is no active "managing independently" app situation. If ordinary direct communication is enough, the person or couple may not need familyupdates.care.

The earlier care-home/voice-message product code is preserved for possible later use, but it should not drive the current public app or onboarding.

## Install

```bat
python -m venv .venv
.\.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Run

Single app:

```bat
streamlit run app.py
```

Variant launchers:

```bat
.\run_family.cmd
.\run_care_hub_phone.cmd
.\run_care_hub_office.cmd
```

Local ports:

- Family Hub: http://localhost:8501
- Mobile: http://localhost:8502
- Family Office: http://localhost:8503

The launcher names still use some older care-home wording because the stable code and route structure are being reused during the transition.

## Routing

Runtime resolves app variant from request path first:

- `/` -> public
- `/family` -> family
- `/mobile` -> mobile
- `/office` -> office

`APP_VARIANT` remains as fallback for local/dev or unmapped paths.

## Local Backend Development

For local backend work only, set the service-role key in the same terminal, then use a dev launcher.

PowerShell:

```powershell
$env:SUPABASE_URL="https://your-project.supabase.co"
$env:SUPABASE_SECRET_KEY="your_secret_key"
.\run_dev_care_hub_office.cmd
```

Optional selectors:

```powershell
$env:DEV_AUTH_BYPASS_CARE_HOME_ID="care_home_uuid"
$env:DEV_AUTH_BYPASS_AUTH_UID="auth_user_uuid"
```

The shortcut only activates on localhost/127.0.0.1/::1, keeps the selected Family/Mobile/Office variant locked, and uses the first active mapping row when no selector is provided.

## Supabase Auth Setup

- Family Hub: email magic-link auth. Set `FAMILY_MAGIC_LINK_REDIRECT_URL`.
- Mobile: individual PIN for day-to-day access, with email secure link for first sign-in or recovery. Set `CARE_MOBILE_MAGIC_LINK_REDIRECT_URL`.
- Family Office: separate organiser/admin login path with Office MFA available if enabled.

## Documentation

- `AGENTS.md`
- `PLANS.md`
- `docs/internal/product_direction_note.md`
- `docs/internal/documentation_split_plan.md`
- `docs/security/SECURITY_MODEL.md`
- `docs/registration/FAMILY_REGISTRATION.md`

## Media

- Primary domain: `https://familyupdates.care`
- Media domain: `https://media.familyupdates.care`
- App audio/media currently uses Supabase Storage where enabled.
