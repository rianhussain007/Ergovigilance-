@echo off
cd /d "%~dp0"
echo Starting Live Posture Analysis Demo...
venv\Scripts\python.exe scripts\live_demo.py
pause
