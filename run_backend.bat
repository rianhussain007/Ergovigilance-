@echo off
cd /d "%~dp0"
echo Starting Ergonomic Posture Analysis API...
echo.
"%~dp0venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
