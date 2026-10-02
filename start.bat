@echo off
echo Starting DR. PROMPT...

start "DR.PROMPT Backend" cmd /k "cd /d "%~dp0backend" && uv run uvicorn app.main:app --reload --port 8000"
start "DR.PROMPT Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo Both servers are starting in separate windows.
echo   Backend : http://localhost:8000
echo   Frontend: http://localhost:3000
echo   API Docs: http://localhost:8000/docs
