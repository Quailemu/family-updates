@echo off
rem ARCHIVED: use run_family.cmd, run_care_hub_phone.cmd, or run_care_hub_office.cmd.
cd /d "%~dp0"
python -m streamlit run app.py
