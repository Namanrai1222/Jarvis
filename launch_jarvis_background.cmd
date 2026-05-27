@echo off
setlocal
cd /d "%~dp0"

set "PYTHONW=%~dp0.venv\Scripts\pythonw.exe"
if exist "%PYTHONW%" (
	start "" /min "%PYTHONW%" -m jarvis_app.main serve
) else (
	start "" /min pythonw -m jarvis_app.main serve
)
endlocal

