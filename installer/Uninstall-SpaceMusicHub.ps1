$ErrorActionPreference = "Stop"
$AppName     = "Space Music Hub"
$AppFolder   = "SpaceMusicHub"
$InstallRoot = Join-Path $env:LOCALAPPDATA $AppFolder
$Desktop     = [Environment]::GetFolderPath("Desktop")
$StartMenu   = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"

Write-Host ""
Write-Host "  Uninstalling Space Music Hub  " -ForegroundColor Black -BackgroundColor Yellow
Write-Host ""

# Kill any running instance
Get-Process -Name "SpaceMusicHub" -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "  Stopping running instance ..." -ForegroundColor Cyan
    $_ | Stop-Process -Force
}

# Remove install dir
if (Test-Path $InstallRoot) {
    Remove-Item $InstallRoot -Recurse -Force
    Write-Host "  Removed: $InstallRoot" -ForegroundColor Green
}

# Remove shortcuts
foreach ($lnk in @("$Desktop\$AppName.lnk", "$StartMenu\$AppName.lnk")) {
    if (Test-Path $lnk) { Remove-Item $lnk -Force; Write-Host "  Removed: $lnk" -ForegroundColor Green }
}

# Remove auto-start
$RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
if ((Get-ItemProperty -Path $RunKey -ErrorAction SilentlyContinue).$AppName) {
    Remove-ItemProperty -Path $RunKey -Name $AppName -Force
    Write-Host "  Removed auto-start entry." -ForegroundColor Green
}

Write-Host ""
Write-Host "  Done.  " -ForegroundColor Black -BackgroundColor Green
Write-Host ""
Read-Host "Press Enter to exit"
