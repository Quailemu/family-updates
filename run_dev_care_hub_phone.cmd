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
echo Starting Mobile DEV BYPASS (APP_VARIANT=%APP_VARIANT%)
echo Mobile URL: http://localhost:8502/?route=/care-hub/mobile/login
start "" powershell -WindowStyle Hidden -NoProfile -Command "Start-Sleep -Seconds 5; Start-Process 'http://localhost:8502/?route=/care-hub/mobile/login'"
python -m streamlit run app.py --server.port 8502 --server.headless true
