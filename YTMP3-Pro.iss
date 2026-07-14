; ============================================================
; YTMP3 Pro Suite — Inno Setup script
; Compiles dist\YTMP3-Pro\ (PyInstaller onedir output) into a
; single installer: YTMP3-Pro-Setup-<version>.exe
;
; Build order:
;   1. pyinstaller YTMP3-Pro.spec        (produces dist\YTMP3-Pro\)
;   2. ISCC.exe YTMP3-Pro.iss            (produces Output\YTMP3-Pro-Setup-*.exe)
; ============================================================

#define MyAppName "YTMP3 Pro"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "getdownloadaid.com"
#define MyAppURL "https://getdownloadaid.com"
#define MyAppExeName "YTMP3-Pro.exe"

[Setup]
AppId={{B4E2F5A1-8C3D-4F9E-9A2B-1D6E7C8F9A0B}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Not code-signed, so let Windows show the standard install prompt
OutputDir=Output
OutputBaseFilename=YTMP3-Pro-Setup
SetupIconFile=app_icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
; Allow both per-user and per-machine installs (avoids needing admin every time)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Auto-close the running app if it's open (so files aren't locked during update).
; Relaunch is handled by the [Run] section below, not here, to avoid
; opening two instances of the app after an update.
CloseApplications=yes
CloseApplicationsFilter={#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Pull in the ENTIRE onedir output folder — exe, _internal, everything
Source: "dist\YTMP3-Pro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up any logs/cache the app writes next to the exe at runtime
Type: filesandordirs; Name: "{app}\youtube_to_mp3.log"
