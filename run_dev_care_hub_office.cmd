@echo off
set DEV_AUTH_BYPASS=1
set APP_VARIANT=OFFICE
set OFFICE_MFA_REQUIRED=0
if "%FAMILY_INVITE_REDIRECT_URL%"=="" set FAMILY_INVITE_REDIRECT_URL=http://localhost:8501/family/login
if "%PASSWORD_RESET_REDIRECT_URL%"=="" set PASSWORD_RESET_REDIRECT_URL=http://localhost:8501/family/login
if "%SUPABASE_URL%"=="" (
  echo SUPABASE_URL is not set. Set it in this terminal before running this script.
  exit /b 1
)
if "%SUPABASE_SECRET_KEY%"=="" (
  echo SUPABASE_SECRET_KEY is not set. Set it in this terminal before running this script.
  exit /b 1
)
echo Starting Voice Message - CARE HUB OFFICE DEV BYPASS (APP_VARIANT=%APP_VARIANT%)
python -m streamlit run app.py --server.port 8503
