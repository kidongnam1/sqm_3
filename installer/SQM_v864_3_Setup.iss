; ═══════════════════════════════════════════════════════════════════
; SQM Inventory v864.3 — Inno Setup 스크립트
; 작성: Ruby, Tier 3 S2, 2026-04-21
;
; 빌드:
;   1. Inno Setup 6 이상 설치 (https://jrsoftware.org/isdl.php)
;   2. PyInstaller 먼저: pyinstaller build\SQM_v864_3.spec --noconfirm
;   3. ISCC.exe installer\SQM_v864_3_Setup.iss
;   4. 산출물: installer\dist\SQM_v864_3_Setup.exe
; ═══════════════════════════════════════════════════════════════════

#define MyAppName "SQM Inventory"
#define MyAppVersion "8.6.4.3"
#define MyAppPublisher "GY Logis / Nam Ki-dong"
#define MyAppExeName "SQM_v864_3.exe"

[Setup]
AppId={{8F6D7C5A-9B3E-4F2D-B1A7-C4E6D8A2B5F9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\SQM\v864.3
DefaultGroupName=SQM Inventory
AllowNoIcons=yes
OutputDir=dist
OutputBaseFilename=SQM_v864_3_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면 아이콘 생성"; GroupDescription: "추가 작업:"; Flags: unchecked

[Files]
; PyInstaller 산출물 전체
Source: "..\build\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; 설정 파일
Source: "..\settings.ini"; DestDir: "{app}"; Flags: onlyifdoesntexist

; 프로그램 데이터 (DB, 로그 폴더 초기화)
Source: "..\REPORTS\*"; DestDir: "{userappdata}\SQM\reports"; Flags: onlyifdoesntexist recursesubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "지금 실행"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 사용자 설정은 유지하되 로그는 제거
Type: filesandordirs; Name: "{userappdata}\SQM\logs"
