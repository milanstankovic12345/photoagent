[Setup]
AppId=PhotoAgent.Desktop
AppName=PhotoAgent
AppVersion={#ReleaseVersion}
DefaultDirName={localappdata}\Programs\PhotoAgent
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0
OutputBaseFilename=PhotoAgent-Setup
Compression=lzma2/fast
SolidCompression=no
AppMutex=PhotoAgent.Installed.Running
UninstallDisplayName=PhotoAgent
SetupLogging=yes

[Files]
Source: "{#Payload}\*"; Excludes: "\manifest.json"; DestDir: "{app}\{code:ReleaseDir}"; Flags: recursesubdirs ignoreversion
Source: "{#Payload}\manifest.json"; DestDir: "{app}\{code:ReleaseDir}"; Flags: ignoreversion; AfterInstall: VerifyRelease

[Icons]
Name: "{userprograms}\PhotoAgent"; Filename: "{app}\{code:ReleaseDir}\.runtime\pythonw.exe"; Parameters: "-B ""{app}\{code:ReleaseDir}\windows_entry.py"""; WorkingDir: "{app}\{code:ReleaseDir}"

[Code]
var
  Folder: String;

function ReleaseDir(Param: String): String;
begin
  Result := Folder;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var I: Integer;
begin
  I := 0;
  repeat
    Folder := 'versions\{#ReleaseVersion}-' + IntToStr(I);
    I := I + 1;
  until not DirExists(ExpandConstant('{app}\') + Folder);
  Result := '';
end;

procedure VerifyRelease;
var Dir: String; Status: Integer;
begin
  Dir := ExpandConstant('{app}\') + Folder;
  if not Exec(Dir + '\.runtime\python.exe', '-B "' + Dir + '\check_install.py"', Dir,
              SW_HIDE, ewWaitUntilTerminated, Status) or (Status <> 0) then
    RaiseException('PhotoAgent installation verification failed.');
end;
