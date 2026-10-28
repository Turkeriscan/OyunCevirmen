#Requires -Version 5.1
<#
    Oyun Cevirmen - Sifirdan Kurulum Betigi
    =========================================
    Bu betik, uzerinde HICBIR SEY kurulu olmayan bir Windows bilgisayarda
    Oyun Cevirmen'i calisir hale getirmek icin gereken her seyi indirip
    kurar:
        - winget kontrolu
        - Git
        - Python 3.12
        - Ollama + ceviri modeli (aya-expanse:8b)
        - Proje (GitHub'dan klonlanir / guncellenir)
        - Python sanal ortami + bagimliliklar
        - (varsa NVIDIA ekran karti) GPU'lu EasyOCR icin PyTorch
        - Windows OCR Ingilizce dil paketi
        - Masaustu kisayolu

    Kullanim: Kurulum.bat dosyasina cift tiklayin (bu betigi o cagirir).
#>
param(
    # Belirli bir surumu (git etiketi veya dali, orn. "v1.2.0") kurmak
    # icin bu satiri "v1.2.0" gibi doldurun. BOS birakilirsa (varsayilan)
    # en guncel "main" dali kurulur/guncellenir - mevcut davranis budur.
    [string]$Surum = ""
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

# ----------------------------------------------------------------- yardimcilar
function Write-Step($text) {
    Write-Host ""
    Write-Host "==> $text" -ForegroundColor Cyan
}
function Write-Ok($text) {
    Write-Host "    [OK] $text" -ForegroundColor Green
}
function Write-Skip($text) {
    Write-Host "    [--] $text" -ForegroundColor DarkGray
}
function Write-Warn2($text) {
    Write-Host "    [!!] $text" -ForegroundColor Yellow
}
function Write-Err2($text) {
    Write-Host "    [HATA] $text" -ForegroundColor Red
}

function Update-SessionPath {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

$Report = [ordered]@{}

# ----------------------------------------------------------------- 0) yonetici
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "Yonetici izni gerekiyor, yeniden baslatiliyor..." -ForegroundColor Yellow
    $psi = @{
        FilePath     = "powershell.exe"
        ArgumentList = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$PSCommandPath`"")
        Verb         = "RunAs"
    }
    Start-Process @psi
    exit
}

Write-Host "===========================================================" -ForegroundColor DarkCyan
Write-Host "   OYUN CEVIRMEN - SIFIRDAN KURULUM"                          -ForegroundColor DarkCyan
Write-Host "===========================================================" -ForegroundColor DarkCyan
Write-Host "Bu islem bilgisayariniza su programlari kurabilir: Git, Python," -ForegroundColor White
Write-Host "Ollama. Ayrica internetten bir ceviri modeli (yaklasik 5 GB) ve" -ForegroundColor White
Write-Host "Python kutuphaneleri indirilecek. Internet hizinize gore 10-40" -ForegroundColor White
Write-Host "dakika surebilir. Lutfen bilgisayari kapatmayin." -ForegroundColor White

$RepoUrl   = "https://github.com/Turkeriscan/OyunCevirmen.git"
$TargetDir = "C:\OyunCevirmen"
$ScriptDir = Split-Path -Parent $PSCommandPath

# ----------------------------------------------------------------- 1) winget
Write-Step "winget (Windows Paket Yoneticisi) kontrol ediliyor"
if (-not (Test-Command "winget")) {
    Write-Err2 "winget bulunamadi."
    Write-Host "    Microsoft Store'u acip 'App Installer' uygulamasini guncelleyin," -ForegroundColor Yellow
    Write-Host "    ardindan bu betigi tekrar calistirin." -ForegroundColor Yellow
    Read-Host "`nCikmak icin Enter'a basin"
    exit 1
}
Write-Ok "winget hazir."

# ----------------------------------------------------------------- 2) Git
Write-Step "Git kontrol ediliyor"
if (Test-Command "git") {
    Write-Skip "Git zaten kurulu."
    $Report["Git"] = "zaten kuruluydu"
} else {
    Write-Host "    Git kuruluyor..." -ForegroundColor White
    winget install --id Git.Git -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    Update-SessionPath
    if (Test-Command "git") {
        Write-Ok "Git kuruldu."
        $Report["Git"] = "kuruldu"
    } else {
        Write-Err2 "Git kurulamadi. Elle kurup tekrar deneyin: https://git-scm.com"
        Read-Host "`nCikmak icin Enter'a basin"
        exit 1
    }
}

# ----------------------------------------------------------------- 3) Python
Write-Step "Python kontrol ediliyor"
$pythonOk = $false
if (Test-Command "python") {
    try {
        $verOut = (python --version) 2>&1
        if ($verOut -match "Python 3\.(\d+)") {
            $minor = [int]$Matches[1]
            if ($minor -ge 10) { $pythonOk = $true }
        }
    } catch {}
}
if ($pythonOk) {
    Write-Skip "Python zaten kurulu ($verOut)."
    $Report["Python"] = "zaten kuruluydu"
} else {
    Write-Host "    Python 3.12 kuruluyor..." -ForegroundColor White
    winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    Update-SessionPath
    if (Test-Command "python") {
        Write-Ok "Python kuruldu."
        $Report["Python"] = "kuruldu"
    } else {
        Write-Err2 "Python kurulamadi. Elle kurup tekrar deneyin: https://python.org"
        Read-Host "`nCikmak icin Enter'a basin"
        exit 1
    }
}

# ----------------------------------------------------------------- 4) Ollama
Write-Step "Ollama kontrol ediliyor"
if (Test-Command "ollama") {
    Write-Skip "Ollama zaten kurulu."
    $Report["Ollama"] = "zaten kuruluydu"
} else {
    Write-Host "    Ollama kuruluyor..." -ForegroundColor White
    winget install --id Ollama.Ollama -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    Update-SessionPath
    if (-not (Test-Command "ollama")) {
        $fallback = Join-Path $env:LOCALAPPDATA "Programs\Ollama"
        if (Test-Path $fallback) { $env:Path = "$env:Path;$fallback" }
    }
    if (Test-Command "ollama") {
        Write-Ok "Ollama kuruldu."
        $Report["Ollama"] = "kuruldu"
    } else {
        Write-Warn2 "Ollama otomatik bulunamadi, devam ediliyor (program acilista tekrar dener)."
        $Report["Ollama"] = "kurulamadi - elle kontrol edin"
    }
}

# ----------------------------------------------------------------- 5) Proje
$surumEtiketi = if ($Surum) { " ($Surum)" } else { " (main)" }
Write-Step "Proje dosyalari hazirlaniyor$surumEtiketi ($TargetDir)"
$alreadyHere = (Test-Path (Join-Path $ScriptDir "app\main.py"))
if ($alreadyHere) {
    Write-Skip "Betik zaten proje klasorunun icinde calistirilmis, oldugu yerde devam ediliyor."
    $TargetDir = $ScriptDir
}

if (Test-Path (Join-Path $TargetDir ".git")) {
    # NOT: git (ve pek cok native komut) normal bilgi satirlarini bile
    # stderr'e yazar. $ErrorActionPreference="Stop" altinda PowerShell 5.1
    # bu satirlarin HER BIRINI (nereye yonlendirilirse yonlendirilsin)
    # sonlandirici hataya cevirir. Bu yuzden bu blokta gecici olarak
    # "Continue"ya alinip basari/basarisizlik $LASTEXITCODE ile kontrol
    # edilir.
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        Push-Location $TargetDir
        git fetch origin --tags --quiet 2>$null | Out-Null
        if ($Surum) {
            git checkout $Surum --quiet 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "git checkout '$Surum' basarisiz (kod $LASTEXITCODE)" }
            git show-ref --verify --quiet "refs/remotes/origin/$Surum"
            if ($LASTEXITCODE -eq 0) {
                # Bu bir dalsa (etiket degil), o dalin en guncelini de cek
                git pull --ff-only origin $Surum 2>$null | Out-Null
                if ($LASTEXITCODE -ne 0) { throw "git pull basarisiz (kod $LASTEXITCODE)" }
            }
        } else {
            git pull --ff-only 2>$null | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "git pull basarisiz (kod $LASTEXITCODE)" }
        }
        Pop-Location
        Write-Ok "Proje guncellendi$surumEtiketi."
        $Report["Proje"] = "guncellendi$surumEtiketi"
    } catch {
        Pop-Location -ErrorAction SilentlyContinue
        Write-Warn2 "Proje guncellenemedi, mevcut dosyalarla devam ediliyor: $_"
        $Report["Proje"] = "guncellenemedi, mevcut surum kullanildi"
    } finally {
        $ErrorActionPreference = $prevEAP
    }
} elseif (Test-Path $TargetDir) {
    if ($alreadyHere) {
        $Report["Proje"] = "mevcut klasor kullanildi (git deposu degil)"
    } else {
        Write-Err2 "$TargetDir zaten var ama bir git deposu degil. Lutfen klasoru tasiyin/silin ve tekrar deneyin."
        Read-Host "`nCikmak icin Enter'a basin"
        exit 1
    }
} else {
    Write-Host "    $TargetDir klasorune klonlaniyor..." -ForegroundColor White
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"  # git clone normal ilerlemeyi de stderr'e yazar
    try {
        if ($Surum) {
            git clone --branch $Surum $RepoUrl $TargetDir 2>$null | Out-Null
        } else {
            git clone $RepoUrl $TargetDir 2>$null | Out-Null
        }
        if ($LASTEXITCODE -ne 0) { throw "git clone basarisiz (kod $LASTEXITCODE)" }
        Write-Ok "Proje klonlandi$surumEtiketi."
        $Report["Proje"] = "klonlandi$surumEtiketi"
    } catch {
        Write-Err2 "Proje klonlanamadi: $_"
        Write-Host "    Internet baglantinizi ve '$Surum' adinin dogrulugunu kontrol edin." -ForegroundColor Yellow
        Read-Host "`nCikmak icin Enter'a basin"
        exit 1
    } finally {
        $ErrorActionPreference = $prevEAP
    }
}

Set-Location $TargetDir

# ----------------------------------------------------------------- 6) venv
Write-Step "Python sanal ortami hazirlaniyor"
if (-not (Test-Path "venv\Scripts\python.exe")) {
    python -m venv venv
    Write-Ok "Sanal ortam olusturuldu."
} else {
    Write-Skip "Sanal ortam zaten var."
}
$venvPy = Join-Path $TargetDir "venv\Scripts\python.exe"
& $venvPy -m pip install --upgrade pip --quiet

# ----------------------------------------------------------------- 7) bagimliliklar
Write-Step "Python kutuphaneleri kuruluyor (birkaç dakika surebilir)"
& $venvPy -m pip install --quiet -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Err2 "Temel kutuphaneler kurulamadi."
    $Report["Temel kutuphaneler"] = "HATA"
} else {
    Write-Ok "Temel kutuphaneler kuruldu."
    $Report["Temel kutuphaneler"] = "kuruldu"
}

# ----------------------------------------------------------------- 8) GPU / EasyOCR
Write-Step "Ekran karti kontrol ediliyor (GPU'lu OCR icin)"
$hasNvidia = Test-Command "nvidia-smi"
if ($hasNvidia) {
    Write-Host "    NVIDIA ekran karti bulundu, GPU'lu EasyOCR kuruluyor..." -ForegroundColor White
    Write-Host "    (Bu adim buyuk dosyalar indirir, biraz uzun surebilir)" -ForegroundColor DarkGray
    & $venvPy -m pip install --quiet torch torchvision --index-url https://download.pytorch.org/whl/cu128
    & $venvPy -m pip install --quiet easyocr
    if ($LASTEXITCODE -ne 0) {
        Write-Warn2 "EasyOCR/GPU kurulumu tam tamamlanamadi. Program yine de Windows OCR ile calisir."
        $Report["GPU'lu OCR (EasyOCR)"] = "kurulamadi - Windows OCR kullanilacak"
    } else {
        Write-Ok "GPU'lu EasyOCR kuruldu."
        $Report["GPU'lu OCR (EasyOCR)"] = "kuruldu"
    }
} else {
    Write-Skip "NVIDIA ekran karti bulunamadi, GPU'lu EasyOCR atlandi (Windows OCR kullanilacak)."
    $Report["GPU'lu OCR (EasyOCR)"] = "atlandi (NVIDIA karti yok)"
}

# ----------------------------------------------------------------- 9) Ollama servisi + model
Write-Step "Ollama servisi ve ceviri modeli hazirlaniyor"
if (Test-Command "ollama") {
    $ollamaUp = $false
    try {
        Invoke-WebRequest -Uri "http://127.0.0.1:11434" -UseBasicParsing -TimeoutSec 3 | Out-Null
        $ollamaUp = $true
    } catch {
        Write-Host "    Ollama servisi baslatiliyor..." -ForegroundColor White
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        for ($i = 0; $i -lt 20; $i++) {
            Start-Sleep -Seconds 1
            try {
                Invoke-WebRequest -Uri "http://127.0.0.1:11434" -UseBasicParsing -TimeoutSec 2 | Out-Null
                $ollamaUp = $true
                break
            } catch {}
        }
    }

    if ($ollamaUp) {
        Write-Ok "Ollama servisi calisiyor."
        $existing = (ollama list) 2>&1 | Select-String "aya-expanse"
        if ($existing) {
            Write-Skip "Ceviri modeli (aya-expanse:8b) zaten kurulu."
            $Report["Ceviri modeli"] = "zaten kuruluydu"
        } else {
            Write-Host "    Ceviri modeli indiriliyor (aya-expanse:8b, ~5 GB)..." -ForegroundColor White
            ollama pull aya-expanse:8b
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "Ceviri modeli indirildi."
                $Report["Ceviri modeli"] = "indirildi"
            } else {
                Write-Warn2 "Model indirilemedi. Program acilista Google Translate'e dusecek."
                $Report["Ceviri modeli"] = "indirilemedi"
            }
        }
    } else {
        Write-Warn2 "Ollama servisi baslatilamadi. Program acilista tekrar dener."
        $Report["Ceviri modeli"] = "Ollama baslamadigi icin indirilemedi"
    }
} else {
    Write-Skip "Ollama kurulu olmadigi icin bu adim atlandi."
    $Report["Ceviri modeli"] = "atlandi (Ollama yok)"
}

# ----------------------------------------------------------------- 10) Windows OCR dil paketi
Write-Step "Windows OCR Ingilizce dil paketi kontrol ediliyor"
try {
    $dismOut = dism /Online /Add-Capability /CapabilityName:Language.OCR~~~en-US~0.0.1.0 /Quiet /NoRestart 2>&1
    Write-Ok "Windows OCR (Ingilizce) hazir."
    $Report["Windows OCR (Ingilizce)"] = "hazir"
} catch {
    Write-Warn2 "Windows OCR dil paketi otomatik kurulamadi. Ayarlardan 'easyocr' motorunu secebilirsiniz."
    $Report["Windows OCR (Ingilizce)"] = "otomatik kurulamadi"
}

# ----------------------------------------------------------------- 11) Masaustu kisayolu
Write-Step "Masaustu kisayolu olusturuluyor"
try {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $desktop "Oyun Cevirmen.lnk"
    $ws = New-Object -ComObject WScript.Shell
    $sc = $ws.CreateShortcut($shortcutPath)
    $sc.TargetPath = Join-Path $TargetDir "OyunCevirmenBaslat.bat"
    $sc.WorkingDirectory = $TargetDir
    $sc.WindowStyle = 7
    $iconPath = Join-Path $TargetDir "app\assets\icon.ico"
    if (Test-Path $iconPath) { $sc.IconLocation = "$iconPath,0" }
    $sc.Description = "Oyun ici yazilari Turkceye ceviren overlay programi"
    $sc.Save()
    Write-Ok "Masaustune kisayol eklendi."
    $Report["Masaustu kisayolu"] = "olusturuldu"
} catch {
    Write-Warn2 "Kisayol olusturulamadi, programi $TargetDir\OyunCevirmenBaslat.bat ile baslatabilirsiniz."
    $Report["Masaustu kisayolu"] = "olusturulamadi"
}

# ----------------------------------------------------------------- ozet
Write-Host ""
Write-Host "===========================================================" -ForegroundColor DarkCyan
Write-Host "   KURULUM TAMAMLANDI"                                        -ForegroundColor DarkCyan
Write-Host "===========================================================" -ForegroundColor DarkCyan
foreach ($key in $Report.Keys) {
    Write-Host ("    {0,-28} : {1}" -f $key, $Report[$key])
}
Write-Host ""
Write-Host "Masaustundeki 'Oyun Cevirmen' kisayoluyla her zaman baslatabilirsiniz." -ForegroundColor White

$answer = Read-Host "`nSimdi baslatmak ister misiniz? (E/h)"
if ($answer -eq "" -or $answer -match "^[EeYy]") {
    Start-Process -FilePath (Join-Path $TargetDir "OyunCevirmenBaslat.bat") -WorkingDirectory $TargetDir
}

Read-Host "`nPencereyi kapatmak icin Enter'a basin"
