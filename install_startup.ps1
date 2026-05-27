$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$taskName = "JarvisLocalAgent"
$launcher = Join-Path $root "launch_jarvis_background.cmd"
$workingDir = $root
$startupDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$startupLauncher = Join-Path $startupDir "JarvisLocalAgent.cmd"

if (-not (Test-Path $launcher)) {
    Write-Host "Launcher not found: $launcher"
    exit 1
}

$escapedLauncher = '"' + $launcher + '"'
$escapedWorkingDir = '"' + $workingDir + '"'
$taskCommand = "cmd.exe /c cd /d $escapedWorkingDir && $escapedLauncher"

schtasks /Delete /TN $taskName /F *> $null 2>&1
schtasks /Create /TN $taskName /SC ONLOGON /RL LIMITED /TR $taskCommand /F *> $null 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "Jarvis startup task installed."
    Write-Host "It will start automatically after you sign in to Windows."
    exit 0
}

Copy-Item -LiteralPath $launcher -Destination $startupLauncher -Force

if (Test-Path $startupLauncher) {
    Write-Host "Scheduled task install was blocked, so Jarvis was added to your Startup folder instead."
    Write-Host "It will start automatically after you sign in to Windows."
} else {
    Write-Host "Failed to install Jarvis startup."
    exit 1
}
