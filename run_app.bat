@echo off
setlocal

cd /d "%~dp0"

echo.
streamlit run app.py --server.port 8503

pause
