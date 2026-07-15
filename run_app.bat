@echo off
setlocal

cd /d "%~dp0"

echo ========================================
echo NTP Export 실행
echo ========================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo Python을 찾을 수 없습니다.
    echo Python 설치 후 다시 실행하세요.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo 가상환경을 생성합니다...
    python -m venv .venv
    if errorlevel 1 (
        echo 가상환경 생성에 실패했습니다.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"

echo 필요한 패키지를 확인/설치합니다...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo 패키지 설치에 실패했습니다.
    pause
    exit /b 1
)

echo.
echo 앱을 실행합니다. 브라우저가 자동으로 열립니다.
echo 종료하려면 이 창에서 Ctrl+C를 누르세요.
echo.
streamlit run app.py

pause
