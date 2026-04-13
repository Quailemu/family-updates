@echo off
setlocal

for %%I in ("%~dp0..\.venv\Scripts\python.exe") do set "PYEXE=%%~fI"

if exist "%PYEXE%" (
  set "PY_CMD=%PYEXE%"
) else (
  set "PY_CMD=python"
)

if "%~1"=="" goto :usage

if /I "%~1"=="check" (
  %PY_CMD% scripts\transcript_guard.py --check
  exit /b %ERRORLEVEL%
)

if /I "%~1"=="fix" (
  %PY_CMD% scripts\transcript_guard.py --write
  if errorlevel 1 exit /b %ERRORLEVEL%
  %PY_CMD% scripts\transcript_guard.py --check
  exit /b %ERRORLEVEL%
)

if /I "%~1"=="full" (
  %PY_CMD% scripts\transcript_guard.py --check
  if errorlevel 1 exit /b %ERRORLEVEL%
  %PY_CMD% -m pre_commit run --all-files
  exit /b %ERRORLEVEL%
)

:usage
echo Usage:
echo   scripts\transcript_guard.cmd check
echo   scripts\transcript_guard.cmd fix
echo   scripts\transcript_guard.cmd full
echo.
echo check = transcript mojibake check only
echo fix   = auto-fix known transcript mojibake + re-check
echo full  = transcript check + full pre-commit checks
exit /b 1
