; Inno Setup 6 script of the HakiAI Windows installer (D34). scripts/build_desktop.ps1 runs it after PyInstaller:
;   iscc /DAppVersion=2.0.0 desktop\windows\hakiai.iss   ->  dist\HakiAI-Setup-x64.exe
; Per-user install (no administrator rights), Start-menu entry, optional desktop icon, optional Ollama download
; (Ollama's own installer, run silently), and an uninstaller that asks before deleting accounts and history.
#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif
#define OllamaSetupUrl "https://ollama.com/download/OllamaSetup.exe"

[Setup]
AppId={{8C3B6E3A-4F0D-4C6B-9E5B-2A7D1F0C9B41}
AppName=HakiAI
AppVersion={#AppVersion}
AppPublisher=Lukorito Ray Khayota
AppPublisherURL=https://github.com/raykl640/ICS-PROJECT
DefaultDirName={localappdata}\Programs\HakiAI
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\..\dist
OutputBaseFilename=HakiAI-Setup-x64
SetupIconFile=..\icons\hakiai.ico
UninstallDisplayIcon={app}\HakiAI.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "ollama"; Description: "Download and install Ollama, the local AI engine HakiAI writes answers with (about 1 GB, needs internet)"; Check: not OllamaInstalled

[Files]
Source: "..\..\dist\HakiAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\HakiAI"; Filename: "{app}\HakiAI.exe"
Name: "{autodesktop}\HakiAI"; Filename: "{app}\HakiAI.exe"; Tasks: desktopicon

[Run]
Filename: "{tmp}\OllamaSetup.exe"; Parameters: "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES"; StatusMsg: "Installing Ollama..."; Tasks: ollama; Check: OllamaDownloaded
Filename: "{app}\HakiAI.exe"; Description: "{cm:LaunchProgram,HakiAI}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  DownloadPage: TDownloadWizardPage;

function OllamaInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'));
end;

function OllamaDownloaded: Boolean;
begin
  Result := FileExists(ExpandConstant('{tmp}\OllamaSetup.exe'));
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and WizardIsTaskSelected('ollama') then begin
    DownloadPage.Clear;
    DownloadPage.Add('{#OllamaSetupUrl}', 'OllamaSetup.exe', '');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
      except
        if not DownloadPage.AbortedByUser then
          SuppressibleMsgBox('Ollama could not be downloaded (' + GetExceptionMessage + ').' + #13#10 +
            'HakiAI is still installed; get Ollama later from https://ollama.com/download', mbError, MB_OK, IDOK);
      end;
    finally
      DownloadPage.Hide;
    end;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  DataDir := ExpandConstant('{localappdata}\HakiAI');
  if (CurUninstallStep = usPostUninstall) and DirExists(DataDir) then
    if SuppressibleMsgBox('Also delete your HakiAI accounts and saved history?' + #13#10 + DataDir,
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
      DelTree(DataDir, True, True, True);
end;
