# Kurulum paketi (.exe) nasıl derlenir

Bu klasördeki dosyalar, Oyun Çevirmen'i ayrı bir Python kurulumu
gerektirmeyen tek bir `.exe` kurulum paketine dönüştürür:

- `oyuncevirmen.spec` — PyInstaller tarifi (programı + gerekli her şeyi
  `dist/OyunCevirmen/` klasörüne paketler, "onedir" modunda).
- `setup.iss` — Inno Setup betiği (`dist/OyunCevirmen/`'i gerçek bir
  kurulum `.exe`'sine sarar: Başlat Menüsü/Masaüstü kısayolları,
  Denetim Masası'ndan kaldırılabilme, Yönetici GEREKTİRMEZ).

## Gereksinimler

- Bu depo, normal şekilde kurulmuş bir `venv` ile (bkz. ana `KULLANIM.md`).
- `pip install -r installer/requirements-build.txt` (sadece PyInstaller).
- [Inno Setup](https://jrsoftware.org/isinfo.php) (ücretsiz) kurulu olmalı
  (`iscc.exe` komut satırında erişilebilir olmalı).

## Adımlar

```powershell
cd installer
..\venv\Scripts\pip install -r requirements-build.txt
..\venv\Scripts\pyinstaller oyuncevirmen.spec --noconfirm
iscc setup.iss
```

Sonuç: `installer/output/OyunCevirmenKur.exe` — çift tıklayınca kurulur,
Yönetici izni İSTEMEZ (kullanıcının kendi profiline, `%LocalAppData%\
Programs\OyunCevirmen` altına kurulur), Başlat Menüsü ve (isteğe bağlı)
Masaüstü kısayolu oluşturur, Denetim Masası → "Program Ekle/Kaldır"dan
kaldırılabilir. Ollama ve çeviri modelinin kurulumu, kurulumdan SONRA
isteğe bağlı bir görev olarak sunulur (atlanabilir) — büyük model
indirmesi (~5 GB) kurulum `.exe`'sinin içine gömülmez.

## Neden "onedir" (tek .exe değil)?

Program, ayarlarını (`config.json`), önbelleğini ve loglarını KENDİ
klasörünün içine yazar. PyInstaller'ın "onefile" modu programı her
açılışta GEÇİCİ bir klasöre açıp kapanışta SİLER — bu da her açılışta
ayarların sıfırlanmasına yol açardı. "onedir" modunda bu klasör KALICI
(kurulum klasörünün kendisi) olduğu için ayarlar doğru şekilde kalıcı
olur.

## Gerçek makinede doğrulandı

Bu `.spec` dosyasıyla derlenen bağımsız `.exe`, bu makinede gerçekten
çalıştırılıp doğrulandı: program eksiksiz açıldı (OCR, kısayollar —
hem `keyboard` hem Win32 RegisterHotKey kanalı —, sistem tepsisi dahil),
ayarlarını kendi klasörüne kalıcı olarak yazdı. `setup.iss`'in kendisi
bu oturumda GERÇEKTEN derlenip test EDİLEMEDİ (bu makinede Inno Setup
kurulu değil) — bu betiğin elle veya GitHub Actions'taki `release.yml`
iş akışıyla (bkz. `.github/workflows/release.yml`) derlenip denenmesi
gerekir.
