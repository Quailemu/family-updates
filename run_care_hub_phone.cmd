@echo off
set APP_VARIANT=MOBILE
echo Starting Voice Message - CARE HUB MOBILE (APP_VARIANT=%APP_VARIANT%)
python -m streamlit run app.py --server.port 8502
