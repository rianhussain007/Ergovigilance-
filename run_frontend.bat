@echo off
cd /d "%~dp0"
echo Starting Ergonomic Posture Analysis frontend...
echo If this window closes or shows an error, copy the last red traceback.
echo.
"%~dp0venv\Scripts\python.exe" -m streamlit run frontend\app.py --server.address 127.0.0.1 --server.port 8501 --server.fileWatcherType none --server.runOnSave false
echo.
echo Streamlit stopped.
pause
