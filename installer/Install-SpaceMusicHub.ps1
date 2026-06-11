# =====================================================================
#  Space Music Hub — Installer
# =====================================================================
#  Right-click → Run with PowerShell, or:
#      powershell -ExecutionPolicy Bypass -File .\Install-SpaceMusicHub.ps1
#
#  What it does:
#    1. Copies the SpaceMusicHub folder into %LOCALAPPDATA%\SpaceMusicHub
#    2. Creates a Desktop shortcut with the neon logo
#    3. Creates a Start-Menu shortcut
#    4. (Optional) Registers an auto-start entry so the app runs hidden
#       in the system tray every time Windows boots
#
#  No admin rights required. Uninstall: just delete the AppData folder
#  + the two shortcuts + the Run registry entry (see Uninstall.ps1).
# =====================================================================
$ErrorActionPreference = "Stop"

$AppName      = "Space Music Hub"
$AppFolder    = "SpaceMusicHub"
$ExeName      = "SpaceMusicHub.exe"
$IconName     = "logo.ico"

$SourceDir    = Join-Path $PSScriptRoot $AppFolder
$InstallRoot  = Join-Path $env:LOCALAPPDATA $AppFolder
$ExePath      = Join-Path $InstallRoot $ExeName
$IconPath     = Join-Path $InstallRoot $IconName

# ── 0. Sanity check ───────────────────────────────────────────────────
if (-not (Test-Path (Join-Path $SourceDir $ExeName))) {
    Write-Host ""
    Write-Host "  ERROR  " -ForegroundColor Black -BackgroundColor Red -NoNewline
    Write-Host "  Could not find $ExeName inside $SourceDir." -ForegroundColor Red
    Write-Host "  Make sure you extracted the whole ZIP and re-run this script." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "  Space Music Hub Installer  " -ForegroundColor Black -BackgroundColor Cyan
Write-Host ""

# ── 1. Copy files ─────────────────────────────────────────────────────
Write-Host "  [1/4]  Installing to $InstallRoot ..." -ForegroundColor Cyan
if (Test-Path $InstallRoot) {
    Write-Host "         Existing install found — overwriting." -ForegroundColor DarkGray
    Remove-Item $InstallRoot -Recurse -Force
}
Copy-Item $SourceDir $InstallRoot -Recurse -Force
Write-Host "         Done." -ForegroundColor Green

# ── 2. Desktop shortcut ───────────────────────────────────────────────
Write-Host "  [2/4]  Creating Desktop shortcut ..." -ForegroundColor Cyan
$Desktop  = [Environment]::GetFolderPath("Desktop")
$LnkDesk  = Join-Path $Desktop "$AppName.lnk"

$WSH = New-Object -ComObject WScript.Shell
$sc = $WSH.CreateShortcut($LnkDesk)
$sc.TargetPath       = $ExePath
$sc.WorkingDirectory = $InstallRoot
$sc.IconLocation     = "$IconPath,0"
$sc.Description      = "Mirror your YouTube playlists to Telegram as MP3"
$sc.Save()
Write-Host "         $LnkDesk" -ForegroundColor Green

# ── 3. Start Menu shortcut ────────────────────────────────────────────
Write-Host "  [3/4]  Creating Start Menu entry ..." -ForegroundColor Cyan
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
$LnkStart  = Join-Path $StartMenu "$AppName.lnk"

$sc = $WSH.CreateShortcut($LnkStart)
$sc.TargetPath       = $ExePath
$sc.WorkingDirectory = $InstallRoot
$sc.IconLocation     = "$IconPath,0"
$sc.Description      = "Mirror your YouTube playlists to Telegram as MP3"
$sc.Save()
Write-Host "         $LnkStart" -ForegroundColor Green

# ── 4. Auto-start (optional) ──────────────────────────────────────────
Write-Host ""
Write-Host "  [4/4]  Background auto-start" -ForegroundColor Cyan
Write-Host "         If enabled, the app will silently launch into the system tray"
Write-Host "         every time you sign in to Windows, and resume Watch mode if a"
Write-Host "         playlist is configured."
$ans = Read-Host "         Enable auto-start with Windows? [Y/n]"
if (-not $ans -or $ans -match "^[Yy]") {
    $RunKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
    Set-ItemProperty -Path $RunKey -Name $AppName `
        -Value "`"$ExePath`" --tray" -Force
    Write-Host "         Auto-start enabled." -ForegroundColor Green
} else {
    Write-Host "         Skipped." -ForegroundColor DarkGray
}

# ── done ──────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Installed successfully.  " -ForegroundColor Black -BackgroundColor Green
Write-Host ""
Write-Host "  Launch it from:" -ForegroundColor White
Write-Host "    * the Desktop icon"
Write-Host "    * Start Menu  ->  $AppName"
Write-Host ""
$ans = Read-Host "  Launch Space Music Hub now? [Y/n]"
if (-not $ans -or $ans -match "^[Yy]") {
    Start-Process -FilePath $ExePath -WorkingDirectory $InstallRoot
}
