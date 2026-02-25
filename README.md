baseline before cleanup

# voice-message.com

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

## Documentation

- `docs/SYSTEM_OVERVIEW.md`
- `docs/VOICE_MESSAGE_MASTER_PLAN.md`
- `docs/security/SECURITY_MODEL.md`
- `docs/registration/FAMILY_REGISTRATION.md`
