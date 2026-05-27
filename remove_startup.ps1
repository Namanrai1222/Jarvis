$taskName = "JarvisLocalAgent"
$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$startupLauncher = Join-Path $startupDir "JarvisLocalAgent.cmd"

schtasks /Delete /TN $taskName /F *> $null
if (Test-Path $startupLauncher) {
    Remove-Item -LiteralPath $startupLauncher -Force
}

if ($LASTEXITCODE -eq 0 -or -not (Test-Path $startupLauncher)) {
    Write-Host "Jarvis startup task removed."
} else {
    Write-Host "Jarvis startup task was not removed."
    exit 1
}
