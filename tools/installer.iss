; FE Maker's Windows installer (Inno Setup 6), compiled by tools/make_installer.py: the package's files with their own
; Python (python\), for the user alone (no administrator rights), shortcuts in the Start menu and on the desktop.
; Projects and settings are not in the install folder: uninstalling leaves them.

#ifndef AppVersion
  #error Compile through tools/make_installer.py
#endif

[Setup]
AppId={{6F3E2C1A-8B4D-4E7A-9C51-FE0A1B2C3D4E}
AppName=FE Maker
AppVersion={#AppVersion}
AppVerName=FE Maker {#AppVersion}
AppPublisher=FE Maker
AppPublisherURL=https://github.com/cdrom93/fe-maker
AppSupportURL=https://github.com/cdrom93/fe-maker/issues
VersionInfoVersion={#NumericVersion}
DefaultDirName={localappdata}\Programs\FE Maker
DefaultGroupName=FE Maker
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=fe-maker-setup-{#AppVersion}
SetupIconFile={#Stage}\server\fe_maker\fe-maker.ico
UninstallDisplayIcon={app}\server\fe_maker\fe-maker.ico
LicenseFile={#Stage}\LICENSE
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#Stage}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\FE Maker"; Filename: "{app}\lancer-fe-maker.bat"; WorkingDir: "{app}"; IconFilename: "{app}\server\fe_maker\fe-maker.ico"; Flags: runminimized
Name: "{group}\{cm:UninstallProgram,FE Maker}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\FE Maker"; Filename: "{app}\lancer-fe-maker.bat"; WorkingDir: "{app}"; IconFilename: "{app}\server\fe_maker\fe-maker.ico"; Flags: runminimized; Tasks: desktopicon

[Run]
Filename: "{app}\lancer-fe-maker.bat"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,FE Maker}"; Flags: nowait postinstall skipifsilent runminimized

[UninstallDelete]
; what FE Maker writes beside itself: compiled Python files, an update's leftovers
Type: filesandordirs; Name: "{app}\server"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\ui"
Type: filesandordirs; Name: "{app}\.update-old"
Type: filesandordirs; Name: "{app}\.update-new"
