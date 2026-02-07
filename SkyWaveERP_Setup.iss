 ; ============================================
; Sky Wave ERP - Inno Setup Script
; ============================================
; لتشغيل هذا الملف:
; 1. حمّل Inno Setup من: https://jrsoftware.org/isdl.php
; 2. افتح هذا الملف في Inno Setup
; 3. اضغط Compile (Ctrl+F9)
; ============================================

#define MyAppName "Sky Wave ERP"
#define MyAppVersion "2.1.5"
#define MyAppPublisher "Sky Wave Team"
#define MyAppURL "https://github.com/ireda8041-lab/SkyWaveERB"
#define MyAppExeName "SkyWaveERP.exe"
#define MyAppIcon "icon.ico"

[Setup]
; معلومات التطبيق
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; مسارات التثبيت - افتراضياً في D: لتجنب مشاكل الصلاحيات
DefaultDirName=D:\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; السماح للمستخدم بتغيير مسار التثبيت
DisableDirPage=no

; ملفات الإخراج
OutputDir=installer_output
OutputBaseFilename=SkyWaveERP-Setup-{#MyAppVersion}
SetupIconFile=icon.ico

; الضغط (أفضل ضغط)
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; متطلبات Windows
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; واجهة التثبيت
WizardStyle=modern
WizardSizePercent=120
DisableWelcomePage=no

; ⚡ إغلاق التطبيقات تلقائياً
CloseApplications=force
CloseApplicationsFilter=*.exe
RestartApplications=yes

; صلاحيات - lowest لأن التثبيت في D: مش محتاج Admin
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; إلغاء التثبيت
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}

[Languages]
Name: "arabic"; MessagesFile: "compiler:Languages\Arabic.isl"

[Tasks]
Name: "desktopicon"; Description: "إنشاء اختصار على سطح المكتب"; GroupDescription: "اختصارات إضافية:"
Name: "quicklaunchicon"; Description: "إنشاء اختصار في شريط المهام"; GroupDescription: "اختصارات إضافية:"; Flags: unchecked

[Files]
; نسخ كل محتويات مجلد dist\SkyWaveERP (قاعدة البيانات موجودة في _internal)
Source: "dist\SkyWaveERP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.db-shm,*.db-wal,*.log"

; نسخ قاعدة البيانات الأولية من المجلد الجذري كاحتياطي (لو مش موجودة في _internal)
Source: "skywave_local.db"; DestDir: "{app}"; Flags: onlyifdoesntexist skipifsourcedoesntexist

; ✅ نسخ ملف الإعدادات البيئية (اختياري للاتصال بـ MongoDB)
Source: ".env"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

; نسخ الأيقونة
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

; نسخ المحدث (إذا كان موجوداً)
Source: "updater.exe"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
; اختصار في قائمة Start
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\إلغاء تثبيت {#MyAppName}"; Filename: "{uninstallexe}"

; اختصار على سطح المكتب
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

; اختصار في شريط المهام
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; تشغيل البرنامج بعد التثبيت (حتى في الوضع الصامت)
Filename: "{app}\{#MyAppExeName}"; Description: "تشغيل {#MyAppName}"; Flags: nowait postinstall runasoriginaluser
; ⚡ تشغيل البرنامج في الوضع الصامت (بدون سؤال المستخدم)
Filename: "{app}\{#MyAppExeName}"; Flags: nowait skipifnotsilent runasoriginaluser shellexec

[UninstallDelete]
; حذف ملفات إضافية عند إلغاء التثبيت
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\exports"
Type: files; Name: "{app}\*.db"
Type: files; Name: "{app}\*.db-shm"
Type: files; Name: "{app}\*.db-wal"

[Code]
// ⚡ إغلاق التطبيقات قبل التثبيت
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  
  // إغلاق SkyWaveERP.exe
  Exec('taskkill', '/F /IM SkyWaveERP.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // إغلاق updater.exe
  Exec('taskkill', '/F /IM updater.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // انتظار قليلاً للتأكد من إغلاق العمليات
  Sleep(1000);
end;

// التحقق من وجود إصدار سابق
function InitializeSetup(): Boolean;
var
  UninstallKey: String;
  UninstallString: String;
  ResultCode: Integer;
begin
  Result := True;
  
  // البحث عن إصدار سابق
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1';
  
  if RegQueryStringValue(HKLM, UninstallKey, 'UninstallString', UninstallString) or
     RegQueryStringValue(HKCU, UninstallKey, 'UninstallString', UninstallString) then
  begin
    if MsgBox('تم العثور على إصدار سابق من Sky Wave ERP.' + #13#10 +
              'هل تريد إلغاء تثبيته أولاً؟', mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec(RemoveQuotes(UninstallString), '/SILENT', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
    end;
  end;
end;

// رسالة بعد التثبيت
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // يمكن إضافة أي إجراءات بعد التثبيت هنا
  end;
end;
