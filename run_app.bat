@echo off
setlocal

cd /d "%~dp0"

echo.
streamlit run app.py

pause
