@echo off
set APP_VARIANT=OFFICE
echo Starting familyupdates.care - OFFICE (APP_VARIANT=%APP_VARIANT%)
python -m streamlit run app.py --server.port 8503
