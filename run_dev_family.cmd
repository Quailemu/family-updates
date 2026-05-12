@echo off
set DEV_AUTH_BYPASS=1
set APP_VARIANT=FAMILY
set OFFICE_MFA_REQUIRED=0
rem Optional: set DEV_AUTH_BYPASS_FAMILY_EMAIL before running to open a specific family contact.
if "%SUPABASE_URL%"=="" (
  echo SUPABASE_URL is not set. Set it in this terminal before running this script.
  exit /b 1
)
if "%SUPABASE_SECRET_KEY%"=="" (
  echo SUPABASE_SECRET_KEY is not set. Set it in this terminal before running this script.
  exit /b 1
)
echo Starting Family Hub DEV BYPASS (APP_VARIANT=%APP_VARIANT%)
echo Family Hub URL: http://localhost:8501/?route=/family/login
start "" powershell -WindowStyle Hidden -NoProfile -Command "Start-Sleep -Seconds 5; Start-Process 'http://localhost:8501/?route=/family/login'"
python -m streamlit run app.py --server.port 8501 --server.headless true
