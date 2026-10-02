# DR. PROMPT — start both servers
# Usage: ./start.ps1

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Free ports if already occupied from a previous run
foreach ($port in @(8000, 3000)) {
    try {
        $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop
        Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
        Write-Host "Freed port $port (was occupied)" -ForegroundColor Yellow
    } catch {
        # Port was already free
    }
}

# Start backend
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$root\backend'; Write-Host 'Backend starting...' -ForegroundColor Cyan; uv run uvicorn app.main:app --reload --port 8000"
)

# Start frontend
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$root\frontend'; Write-Host 'Frontend starting...' -ForegroundColor Cyan; npm run dev"
)

Write-Host ""
Write-Host "DR. PROMPT is starting up:" -ForegroundColor Green
Write-Host "  Frontend : http://localhost:3000" -ForegroundColor White
Write-Host "  Backend  : http://localhost:8000" -ForegroundColor White
Write-Host "  API Docs : http://localhost:8000/docs" -ForegroundColor White
Write-Host ""
Write-Host "Close the two terminal windows to stop the servers." -ForegroundColor DarkGray
