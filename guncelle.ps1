#Requires -Version 5.1
<#
    Oyun Cevirmen - Guncelleme Betigi
    ===================================
    Kurulum.bat'in aksine, Python/Git/Ollama'yi tekrar kurmaya veya
    ceviri modelini yeniden indirmeye CALISMAZ. Sadece:
        1) GitHub'daki en son kodu ceker (git pull)
        2) Yeni/degisen Python kutuphanesi varsa kurar
        3) Ne degistigini kisaca gosterir
        4) Isterseniz programi yeniden baslatir

    Tasarimda degisiklik yapip GitHub'a yukledikten sonra, bilgisayarinizda
    bu dosyaya (Guncelle.bat ile) cift tiklamaniz yeterlidir.
#>

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

function Write-Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }
function Write-Ok($text)   { Write-Host "    [OK] $text" -ForegroundColor Green }
function Write-Skip($text) { Write-Host "    [--] $text" -ForegroundColor DarkGray }
function Write-Warn2($text){ Write-Host "    [!!] $text" -ForegroundColor Yellow }
function Write-Err2($text) { Write-Host "    [HATA] $text" -ForegroundColor Red }

$TargetDir = Split-Path -Parent $PSCommandPath

Write-Host "===========================================================" -ForegroundColor DarkCyan
Write-Host "   OYUN CEVIRMEN - GUNCELLEME"                                 -ForegroundColor DarkCyan
Write-Host "===========================================================" -ForegroundColor DarkCyan

if (-not (Test-Path (Join-Path $TargetDir ".git"))) {
    Write-Err2 "Bu klasor bir git deposu degil ($TargetDir)."
    Write-Host "    Ilk kurulum icin Kurulum.bat dosyasini kullanin." -ForegroundColor Yellow
    Read-Host "`nCikmak icin Enter'a basin"
    exit 1
}
if (-not (Test-Path (Join-Path $TargetDir "venv\Scripts\python.exe"))) {
    Write-Err2 "Python sanal ortami bulunamadi."
    Write-Host "    Ilk kurulum icin Kurulum.bat dosyasini kullanin." -ForegroundColor Yellow
    Read-Host "`nCikmak icin Enter'a basin"
    exit 1
}

Set-Location $TargetDir

# ----------------------------------------------------------------- calisan programi kapat
$running = Get-Process -Name "python", "pythonw" -ErrorAction SilentlyContinue |
    Where-Object {
        try { (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine -match "app\.main" }
        catch { $false }
    }
if ($running) {
    Write-Step "Program su an calisiyor, kapatiliyor"
    foreach ($p in $running) {
        try { Stop-Process -Id $p.Id -Force; Write-Ok "Kapatildi (PID $($p.Id))." }
        catch { Write-Warn2 "Kapatilamadi (PID $($p.Id)), elle kapatmaniz gerekebilir." }
    }
    Start-Sleep -Seconds 1
}

# ----------------------------------------------------------------- git pull
Write-Step "GitHub'daki en son surum kontrol ediliyor"
$oldHash = (git rev-parse HEAD).Trim()

$localChanges = git status --porcelain
if ($localChanges) {
    Write-Warn2 "Klasorde yerel degisiklikler var, bunlar GUNCELLENMEYECEK:"
    $localChanges | ForEach-Object { Write-Host "        $_" -ForegroundColor DarkYellow }
}

try {
    git fetch origin --quiet
    git pull --ff-only 2>&1 | Out-Null
} catch {
    Write-Err2 "Guncelleme alinamadi. Internet baglantinizi kontrol edin veya yerel degisiklikler"
    Write-Err2 "catisma yaratiyor olabilir."
    Write-Host "    Teknik ayrinti: $_" -ForegroundColor DarkGray
    Read-Host "`nCikmak icin Enter'a basin"
    exit 1
}

$newHash = (git rev-parse HEAD).Trim()

if ($oldHash -eq $newHash) {
    Write-Ok "Zaten en son surumdesiniz, yeni bir sey yok."
} else {
    Write-Ok "Guncellendi: $($oldHash.Substring(0,7)) -> $($newHash.Substring(0,7))"
    Write-Host ""
    Write-Host "    Neler degisti:" -ForegroundColor White
    git log --oneline "$oldHash..$newHash" | ForEach-Object { Write-Host "      - $_" }

    $changedFiles = git diff --name-only $oldHash $newHash

    # ----------------------------------------------------- bagimliliklar
    if ($changedFiles -contains "requirements.txt") {
        Write-Step "Kutuphane listesi degismis, guncelleniyor"
        & ".\venv\Scripts\python.exe" -m pip install --quiet -r requirements.txt
        if ($LASTEXITCODE -eq 0) { Write-Ok "Kutuphaneler guncellendi." }
        else { Write-Warn2 "Bazi kutuphaneler guncellenemedi, programi yine de baslatmayi deneyin." }
    } else {
        Write-Skip "Kutuphane listesi degismemis, atlandi."
    }
}

# ----------------------------------------------------------------- yeniden baslat
Write-Host ""
$answer = Read-Host "Programi simdi baslatmak ister misiniz? (E/h)"
if ($answer -eq "" -or $answer -match "^[EeYy]") {
    Start-Process -FilePath (Join-Path $TargetDir "OyunCevirmenBaslat.bat") -WorkingDirectory $TargetDir
}

Read-Host "`nPencereyi kapatmak icin Enter'a basin"
