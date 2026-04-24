@echo off
set DEV_AUTH_BYPASS=1
set APP_VARIANT=MOBILE
set OFFICE_MFA_REQUIRED=0
if "%SUPABASE_URL%"=="" (
  echo SUPABASE_URL is not set. Set it in this terminal before running this script.
  exit /b 1
)
if "%SUPABASE_SECRET_KEY%"=="" (
  echo SUPABASE_SECRET_KEY is not set. Set it in this terminal before running this script.
  exit /b 1
)
echo Starting Voice Message - CARE HUB MOBILE DEV BYPASS (APP_VARIANT=%APP_VARIANT%)
python -m streamlit run app.py --server.port 8502
