; StampZ-III Inno Setup Installer Script
; Requires Inno Setup 6.x: https://jrsoftware.org/isinfo.php
;
; Build with: ISCC.exe stampz_installer.iss
; (ISCC.exe is in the Inno Setup installation directory)

#define MyAppName "StampZ-III"
#define MyAppVersion "3.2.0"
#define MyAppPublisher "Stainless Brown"
#define MyAppURL "https://github.com/stainlessbrown/StampZ-III"
#define MyAppExeName "StampZ-III.exe"

[Setup]
; Unique AppId - used to detect existing installs for upgrades
; DO NOT change this between versions
AppId={{8A3F5B2E-7C41-4D9A-B6E8-1F2A3C4D5E6F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; No license prompt - just install (DisableLicensePage removed in Inno Setup 6.4+; omitting LicenseFile achieves the same)
DisableProgramGroupPage=yes
; Output installer details
OutputDir=dist
OutputBaseFilename=StampZ-III-{#MyAppVersion}-Setup
; Use the StampZ icon for the installer itself
SetupIconFile=resources\StampZ.ico
; Compression
Compression=lzma2/max
SolidCompression=yes
; Require 64-bit Windows
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Allow non-admin install (user's AppData) if they don't have admin rights
PrivilegesRequiredOverridesAllowed=dialog
PrivilegesRequired=lowest
; Uninstall icon
UninstallDisplayIcon={app}\{#MyAppExeName}
; Upgrade behavior - install over previous version without asking
UsePreviousAppDir=yes
UsePreviousGroup=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Install everything from the PyInstaller onedir output
Source: "dist\StampZ-III\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\StampZ-III\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Option to launch StampZ after installation
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Check for VC++ Redistributable and offer to install if missing
function VCRedistInstalled: Boolean;
var
  RegValue: String;
begin
  Result := RegQueryStringValue(HKLM,
    'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64',
    'Version', RegValue);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  VCRedistPath: String;
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if not VCRedistInstalled then
    begin
      VCRedistPath := ExpandConstant('{app}\vcredist\vc_redist.x64.exe');
      if FileExists(VCRedistPath) then
      begin
        if MsgBox('StampZ requires the Visual C++ Runtime.' + #13#10 +
                   'Would you like to install it now?',
                   mbConfirmation, MB_YESNO) = IDYES then
        begin
          Exec(VCRedistPath, '/quiet /norestart', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
        end;
      end;
    end;
  end;
end;
