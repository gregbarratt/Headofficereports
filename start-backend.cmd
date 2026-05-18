@echo off
cd /d "%~dp0backend"

if not exist ".venv\Scripts\python.exe" (
  echo Backend Python environment was not found.
  echo Please run the backend setup steps in README.md first.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
