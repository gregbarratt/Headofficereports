@echo off
cd /d "%~dp0"

start "Head Office Backend" "%~dp0start-backend.cmd"
start "Head Office Frontend" "%~dp0start-frontend.cmd"

echo Starting Head Office Reporting System...
echo.
echo Leave the two server windows open while using the app.
echo Then open http://127.0.0.1:5173 in your browser.
echo.
pause
