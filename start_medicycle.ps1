$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
if (-not (Test-Path '.env')) {
    Copy-Item '.env.example' '.env'
    Write-Host 'Created .env. Edit DB_PASSWORD and JWT_SECRET, then run this script again.' -ForegroundColor Yellow
    notepad '.env'
    exit
}
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    Write-Host 'Python environment not found. Run the setup commands in README_PYTHON_APP.md first.' -ForegroundColor Red
    exit 1
}
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$BackendCommand = "Set-Location '$ProjectRoot'; & '$Python' -m uvicorn api.main:app --host 127.0.0.1 --port 8000"
Start-Process powershell -ArgumentList '-NoExit','-ExecutionPolicy','Bypass','-Command',$BackendCommand -WindowStyle Normal
Start-Sleep -Seconds 3
$env:MEDICYCLE_API_URL = 'http://127.0.0.1:8000'
& $Python -m streamlit run (Join-Path $ProjectRoot 'streamlit_app\app.py') --server.address 127.0.0.1 --server.port 8501
