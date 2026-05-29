[Setup]
AppName=WaveText
AppVersion=1.0
AppPublisher=WaveText
DefaultDirName={autopf}\WaveText
DefaultGroupName=WaveText
OutputDir=Output
OutputBaseFilename=WaveText-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icon.ico

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar icone na Area de Trabalho"; GroupDescription: "Icones adicionais:"

[Files]
Source: "dist\WaveText\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\WaveText"; Filename: "{app}\WaveText.exe"
Name: "{autodesktop}\WaveText"; Filename: "{app}\WaveText.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\WaveText.exe"; Description: "Abrir WaveText agora"; Flags: nowait postinstall skipifsilent
