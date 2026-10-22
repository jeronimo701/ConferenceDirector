#ifndef Payload
  #error Payload must point to the clean portable folder
#endif
#ifndef SetupOut
  #error SetupOut must point to the installer output directory
#endif
[Setup]
AppId={{B3E69098-997C-4B94-A59C-B9C11E4F5FE9}
AppName=ConferenceDirector
AppVersion=Snapshot 2026-10-22
VersionInfoVersion=0.0.0.0
AppPublisher=Jeronimo701
DefaultDirName={src}\ConferenceDirector
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
Uninstallable=no
CreateUninstallRegKey=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#SetupOut}
OutputBaseFilename=ConferenceDirectorSetup-snapshot-2026-10-22-clean
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
LicenseFile={#Payload}\LICENSE.txt
[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
[Files]
Source: "{#Payload}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
