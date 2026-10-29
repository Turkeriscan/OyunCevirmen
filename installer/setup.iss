; Oyun Çevirmen - Inno Setup kurulum betiği (5.1)
;
; Kullanıcı kapsamında (Yönetici GEREKMEZ) kurar: PyInstaller'ın "onedir"
; çıktısını (installer/dist/OyunCevirmen/) paketler, Başlat Menüsü ve
; (isteğe bağlı) Masaüstü kısayolları oluşturur, Denetim Masası'ndan
; ("Program Ekle/Kaldır") kaldırılabilir.
;
; Derleme sırası:
;   1) installer/ klasöründe:  pyinstaller oyuncevirmen.spec --noconfirm
;   2) installer/ klasöründe:  iscc setup.iss
; Çıktı: installer/output/OyunCevirmenKur.exe
;
; Ollama + çeviri modeli kurulumu, BU betiğin dışında, kurulumdan SONRA
; açılan kurulum.ps1 ile yapılır (opsiyonel, atlanabilir görev olarak
; sunulur) - böylece büyük model indirmesi (~5 GB) kurulum .exe'sinin
; içine gömülmez.

#define MyAppName "Oyun Çevirmen"
#define MyAppVersion "2.1.0"
#define MyAppPublisher "Turkeriscan"
#define MyAppURL "https://github.com/Turkeriscan/OyunCevirmen"
#define MyAppExeName "OyunCevirmen.exe"

[Setup]
AppId={{B6A6E1D0-6C9C-4B6E-9B7B-3C7B0D7C9A41}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Yönetici GEREKMEZ - kullanıcının KENDİ profiline kurulur.
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\OyunCevirmen
DefaultGroupName=Oyun Çevirmen
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=OyunCevirmenKur
SetupIconFile=..\app\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Program Ekle/Kaldır'da (Denetim Masası) görünür - PrivilegesRequired=lowest
; ile bu bilgi HKCU altına (kullanıcıya özel) yazılır, sistem genelini
; ETKİLEMEZ, ayrıca Yönetici gerektirmeden kaldırılabilir.
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstüne kısayol oluştur"; GroupDescription: "Ek kısayollar:"
Name: "ollamasetup"; Description: "Kurulumdan sonra Ollama ve çeviri modelini kur (önerilir, ~5 GB indirir)"; GroupDescription: "Çeviri motoru:"; Flags: unchecked

[Files]
Source: "dist\OyunCevirmen\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\kurulum.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\Kurulum.bat"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\Oyun Çevirmen"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,Oyun Çevirmen}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Oyun Çevirmen"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; Ollama/model kurulumu İSTEĞE BAĞLIDIR (yukarıdaki görev işaretliyse):
; PyInstaller paketine GÖMÜLMEZ, ayrı bir adımda (PowerShell) çalışır -
; böylece kurulum .exe'si küçük kalır ve kullanıcı büyük model indirmesini
; isterse atlayabilir.
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\kurulum.ps1"""; \
    WorkingDir: "{app}"; Tasks: ollamasetup; Flags: postinstall runascurrentuser shellexec skipifsilent; \
    Description: "Ollama ve çeviri modelini kur"
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,Oyun Çevirmen}"; \
    Flags: nowait postinstall skipifsilent runascurrentuser

[UninstallDelete]
; Program KENDİ çalışırken oluşturduğu dosyalar (config.json, önbellek,
; loglar) kaldırma sırasında da TEMİZLENİR - kullanıcı "Program Ekle/
; Kaldır"dan kaldırdığında tertemiz bir sistem kalsın diye.
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\cache"
Type: filesandordirs; Name: "{app}\_internal\logs"
Type: filesandordirs; Name: "{app}\_internal\cache"
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\_internal\config.json"
Type: files; Name: "{app}\glossary.json"
Type: files; Name: "{app}\_internal\glossary.json"
