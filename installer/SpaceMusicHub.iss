; =====================================================================
;  Space Music Hub — Inno Setup installer
;  Compile with:  "C:\Program Files (x86)\Inno Setup 6\iscc.exe" SpaceMusicHub.iss
; =====================================================================
#define MyAppName          "Space Music Hub"
#define MyAppVersion       "1.9.1"
#define MyAppPublisher     "Andrejs Avlasins"
#define MyAppURL           "https://github.com/AAvlasins-dev/Music-from-Youtube-playlist-to-telegram"
#define MyAppExeName       "SpaceMusicHub.exe"
#define MyAppIcoName       "logo_round.ico"

[Setup]
; SHA-1 of {#MyAppName + MyAppPublisher} — stable GUID for upgrade tracking.
AppId={{B7C5F2E1-9A4D-4F8E-A6B3-2C7D8E9F1A5B}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases

; Per-user install — no admin required. Goes to %LOCALAPPDATA%\Programs\SpaceMusicHub
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes

; UI polish
WizardStyle=modern
SetupIconFile=..\docs\logo_round.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

; Output
OutputDir=..\dist
OutputBaseFilename=SpaceMusicHub-Setup-v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=2

; Force re-install over older versions (Programs & Features stays clean)
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=no

ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "latvian"; MessagesFile: "Latvian.isl"

[CustomMessages]
; Tasks group header
english.BackgroundMode=Background mode:
russian.BackgroundMode=Фоновый режим:
latvian.BackgroundMode=Fona režīms:
; Autostart checkbox description
english.AutoStartTask=Launch silently when Windows starts (recommended)
russian.AutoStartTask=Запускать в трее при старте Windows (рекомендуется)
latvian.AutoStartTask=Palaist klusi, kad sākas Windows (ieteicams)

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "autostart";   Description: "{cm:AutoStartTask}"; GroupDescription: "{cm:BackgroundMode}"

[Files]
; Whole PyInstaller folder, recursively
Source: "SpaceMusicHub\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\logo_round.ico"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\logo_round.ico"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartmenu}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\logo_round.ico"; WorkingDir: "{app}"

[Registry]
; Auto-start via per-user Run key — only if the user checked the optional task
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#MyAppName}"; \
    ValueData: """{app}\{#MyAppExeName}"" --tray"; \
    Flags: uninsdeletevalue; Tasks: autostart

[Run]
; Offer to launch right after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; \
    Flags: nowait postinstall skipifsilent

[UninstallDelete]
; State files the bot creates at runtime — clean them up too
Type: files; Name: "{app}\bot.lock"
Type: files; Name: "{app}\bot.log"
Type: files; Name: "{app}\sent_videos_*.json"
Type: files; Name: "{app}\pinned_msgs_*.json"
Type: files; Name: "{app}\lang.txt"
; .env carries the bot token — never leave it behind.
Type: files; Name: "{app}\.env"

[Code]
// Both install and uninstall need to stop any running instance first
// (the tray app + the spawned --bot-watch subprocess hold the .exe and
// every DLL in _internal/ open, so Inno's deleter gets ERROR_SHARING_VIOLATION
// and tells the user "some items could not be removed").

procedure KillRunningInstances();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'),
       '/F /T /IM SpaceMusicHub.exe',
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  // Give the OS a moment to release file handles before deletion begins.
  Sleep(800);
end;

function InitializeUninstall(): Boolean;
begin
  KillRunningInstances();
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssInstall then
    KillRunningInstances();
end;
