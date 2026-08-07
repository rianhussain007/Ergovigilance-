@echo off
cd /d "%~dp0backend_api"
echo Starting ErgoVigilance API...
echo.
"%~dp0venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
