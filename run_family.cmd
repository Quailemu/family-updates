@echo off
set APP_VARIANT=FAMILY
echo Starting Voice Message - FAMILY (APP_VARIANT=%APP_VARIANT%)
python -m streamlit run app.py --server.port 8501
