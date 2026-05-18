@echo off
cd /d "%~dp0frontend"

if not exist "dist\index.html" (
  echo Frontend build was not found.
  echo Please run npm install and npm run build from the frontend folder first.
  pause
  exit /b 1
)

"..\backend\.venv\Scripts\python.exe" -m http.server 5173 --bind 127.0.0.1 --directory dist
pause
