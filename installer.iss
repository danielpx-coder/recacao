; Inno Setup Script para Danaurium Redação Studio
; Compatível com Windows 10 e Windows 11 (64 bits)

#define MyAppName "Danaurium Redação Studio"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Danaurium Software"
#define MyAppURL "https://danaurium.com.br"
#define MyAppExeName "DanauriumRedacaoStudio.exe"

[Setup]
AppId={{D1A0E0D7-RECA-CAO1-9097-DANAURIUMSTUDIO}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=docs\LICENCA.txt
OutputDir=output_installer
OutputBaseFilename=DanauriumRedacaoStudio_Instalador_v1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\DanauriumRedacaoStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "sample_data\*"; DestDir: "{userappdata}\DanauriumRedacaoStudio\sample_data"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
