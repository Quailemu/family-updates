@echo off
set APP_VARIANT=OFFICE
echo Starting Voice Message - CARE HUB OFFICE (APP_VARIANT=%APP_VARIANT%)
python -m streamlit run app.py --server.port 8503
