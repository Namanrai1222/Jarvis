$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Virtual environment not found. Run the setup steps from README.md first."
    exit 1
}

& ".venv\Scripts\python.exe" -m jarvis_app.main serve
