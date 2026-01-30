 ; ============================================
; Sky Wave ERP - Inno Setup Script
; ============================================
; Ù„ØªØ´ØºÙŠÙ„ Ù‡Ø°Ø§ Ø§Ù„Ù…Ù„Ù:
; 1. Ø­Ù…Ù‘Ù„ Inno Setup Ù…Ù†: https://jrsoftware.org/isdl.php
; 2. Ø§ÙØªØ­ Ù‡Ø°Ø§ Ø§Ù„Ù…Ù„Ù ÙÙŠ Inno Setup
; 3. Ø§Ø¶ØºØ· Compile (Ctrl+F9)
; ============================================

#define MyAppName "Sky Wave ERP"
#define MyAppVersion "2.0.5"
#define MyAppPublisher "Sky Wave Team"
#define MyAppURL "https://github.com/ireda8041-lab/SkyWaveERB"
#define MyAppExeName "SkyWaveERP.exe"
#define MyAppIcon "icon.ico"

[Setup]
; Ù…Ø¹Ù„ÙˆÙ…Ø§Øª Ø§Ù„ØªØ·Ø¨ÙŠÙ‚
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Ù…Ø³Ø§Ø±Ø§Øª Ø§Ù„ØªØ«Ø¨ÙŠØª - Ø§ÙØªØ±Ø§Ø¶ÙŠØ§Ù‹ ÙÙŠ D: Ù„ØªØ¬Ù†Ø¨ Ù…Ø´Ø§ÙƒÙ„ Ø§Ù„ØµÙ„Ø§Ø­ÙŠØ§Øª
DefaultDirName=D:\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Ø§Ù„Ø³Ù…Ø§Ø­ Ù„Ù„Ù…Ø³ØªØ®Ø¯Ù… Ø¨ØªØºÙŠÙŠØ± Ù…Ø³Ø§Ø± Ø§Ù„ØªØ«Ø¨ÙŠØª
DisableDirPage=no

; Ù…Ù„ÙØ§Øª Ø§Ù„Ø¥Ø®Ø±Ø§Ø¬
OutputDir=C:\Users\HREDA~1\AppData\Local\Temp\SkyWaveSetup
OutputBaseFilename=SkyWaveERP-Setup-{#MyAppVersion}
SetupIconFile=icon.ico

; Ø§Ù„Ø¶ØºØ· (Ø£ÙØ¶Ù„ Ø¶ØºØ·)
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Ù…ØªØ·Ù„Ø¨Ø§Øª Windows
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; ÙˆØ§Ø¬Ù‡Ø© Ø§Ù„ØªØ«Ø¨ÙŠØª
WizardStyle=modern
WizardSizePercent=120
DisableWelcomePage=no

; ØµÙ„Ø§Ø­ÙŠØ§Øª - lowest Ù„Ø£Ù† Ø§Ù„ØªØ«Ø¨ÙŠØª ÙÙŠ D: Ù…Ø´ Ù…Ø­ØªØ§Ø¬ Admin
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Ø¥Ù„ØºØ§Ø¡ Ø§Ù„ØªØ«Ø¨ÙŠØª
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"

[Tasks]
Name: "desktopicon"; Description: "Ø¥Ù†Ø´Ø§Ø¡ Ø§Ø®ØªØµØ§Ø± Ø¹Ù„Ù‰ Ø³Ø·Ø­ Ø§Ù„Ù…ÙƒØªØ¨"; GroupDescription: "Ø§Ø®ØªØµØ§Ø±Ø§Øª Ø¥Ø¶Ø§ÙÙŠØ©:"
Name: "quicklaunchicon"; Description: "Ø¥Ù†Ø´Ø§Ø¡ Ø§Ø®ØªØµØ§Ø± ÙÙŠ Ø´Ø±ÙŠØ· Ø§Ù„Ù…Ù‡Ø§Ù…"; GroupDescription: "Ø§Ø®ØªØµØ§Ø±Ø§Øª Ø¥Ø¶Ø§ÙÙŠØ©:"; Flags: unchecked

[Files]
; Ù†Ø³Ø® ÙƒÙ„ Ù…Ø­ØªÙˆÙŠØ§Øª Ù…Ø¬Ù„Ø¯ dist\SkyWaveERP (Ù‚Ø§Ø¹Ø¯Ø© Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ù…ÙˆØ¬ÙˆØ¯Ø© ÙÙŠ _internal)
Source: "dist\SkyWaveERP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.db-shm,*.db-wal,*.log"

; Ù†Ø³Ø® Ù‚Ø§Ø¹Ø¯Ø© Ø§Ù„Ø¨ÙŠØ§Ù†Ø§Øª Ø§Ù„Ø£ÙˆÙ„ÙŠØ© Ù…Ù† Ø§Ù„Ù…Ø¬Ù„Ø¯ Ø§Ù„Ø¬Ø°Ø±ÙŠ ÙƒØ§Ø­ØªÙŠØ§Ø·ÙŠ (Ù„Ùˆ Ù…Ø´ Ù…ÙˆØ¬ÙˆØ¯Ø© ÙÙŠ _internal)
Source: "skywave_local.db"; DestDir: "{app}"; Flags: onlyifdoesntexist skipifsourcedoesntexist

; âœ… Ù†Ø³Ø® Ù…Ù„Ù Ø§Ù„Ø¥Ø¹Ø¯Ø§Ø¯Ø§Øª Ø§Ù„Ø¨ÙŠØ¦ÙŠØ© (Ù…Ù‡Ù… Ù„Ù„Ø§ØªØµØ§Ù„ Ø¨Ù€ MongoDB)
Source: ".env"; DestDir: "{app}"; Flags: ignoreversion

; Ù†Ø³Ø® Ø§Ù„Ø£ÙŠÙ‚ÙˆÙ†Ø©
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; Ù†Ø³Ø® Ø§Ù„Ù…Ø­Ø¯Ø« (Ø¥Ø°Ø§ ÙƒØ§Ù† Ù…ÙˆØ¬ÙˆØ¯Ø§Ù‹)
Source: "updater.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; Ø§Ø®ØªØµØ§Ø± ÙÙŠ Ù‚Ø§Ø¦Ù…Ø© Start
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\Ø¥Ù„ØºØ§Ø¡ ØªØ«Ø¨ÙŠØª {#MyAppName}"; Filename: "{uninstallexe}"

; Ø§Ø®ØªØµØ§Ø± Ø¹Ù„Ù‰ Ø³Ø·Ø­ Ø§Ù„Ù…ÙƒØªØ¨
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

; Ø§Ø®ØªØµØ§Ø± ÙÙŠ Ø´Ø±ÙŠØ· Ø§Ù„Ù…Ù‡Ø§Ù…
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; ØªØ´ØºÙŠÙ„ Ø§Ù„Ø¨Ø±Ù†Ø§Ù…Ø¬ Ø¨Ø¹Ø¯ Ø§Ù„ØªØ«Ø¨ÙŠØª
Filename: "{app}\{#MyAppExeName}"; Description: "ØªØ´ØºÙŠÙ„ {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Ø­Ø°Ù Ù…Ù„ÙØ§Øª Ø¥Ø¶Ø§ÙÙŠØ© Ø¹Ù†Ø¯ Ø¥Ù„ØºØ§Ø¡ Ø§Ù„ØªØ«Ø¨ÙŠØª
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\exports"
Type: files; Name: "{app}\*.db"
Type: files; Name: "{app}\*.db-shm"
Type: files; Name: "{app}\*.db-wal"

[Code]
// Ø§Ù„ØªØ­Ù‚Ù‚ Ù…Ù† ÙˆØ¬ÙˆØ¯ Ø¥ØµØ¯Ø§Ø± Ø³Ø§Ø¨Ù‚
function InitializeSetup(): Boolean;
var
  UninstallKey: String;
  UninstallString: String;
  ResultCode: Integer;
begin
  Result := True;
  
  // Ø§Ù„Ø¨Ø­Ø« Ø¹Ù† Ø¥ØµØ¯Ø§Ø± Ø³Ø§Ø¨Ù‚
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1';
  
  if RegQueryStringValue(HKLM, UninstallKey, 'UninstallString', UninstallString) or
     RegQueryStringValue(HKCU, UninstallKey, 'UninstallString', UninstallString) then
  begin
    if MsgBox('ØªÙ… Ø§Ù„Ø¹Ø«ÙˆØ± Ø¹Ù„Ù‰ Ø¥ØµØ¯Ø§Ø± Ø³Ø§Ø¨Ù‚ Ù…Ù† Sky Wave ERP.' + #13#10 +
              'Ù‡Ù„ ØªØ±ÙŠØ¯ Ø¥Ù„ØºØ§Ø¡ ØªØ«Ø¨ÙŠØªÙ‡ Ø£ÙˆÙ„Ø§Ù‹ØŸ', mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec(RemoveQuotes(UninstallString), '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;

// Ø±Ø³Ø§Ù„Ø© Ø¨Ø¹Ø¯ Ø§Ù„ØªØ«Ø¨ÙŠØª
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // ÙŠÙ…ÙƒÙ† Ø¥Ø¶Ø§ÙØ© Ø£ÙŠ Ø¥Ø¬Ø±Ø§Ø¡Ø§Øª Ø¨Ø¹Ø¯ Ø§Ù„ØªØ«Ø¨ÙŠØª Ù‡Ù†Ø§
  end;
end;

