# Oyun Çevirmen

Türkçe dil desteği olmayan oyunlarda ekrandaki yabancı yazıları otomatik
bulan ve Türkçeye çevirip orijinal yazının tam üstünde gösteren bir
Windows masaüstü uygulaması.

## Özellikler

- **Ekran yakalama:** `dxcam` (DXGI Desktop Duplication), `mss` yedekli. Borderless Windowed oyunları destekler. İzlenecek monitör, ekran dizilimi değişse bile konum+çözünürlük kimliğiyle doğru bulunur.
- **OCR:** Windows OCR (varsayılan, kurulum gerektirmez), EasyOCR/PaddleOCR (GPU/CUDA) veya RapidOCR (DirectML, GPU üreticisinden bağımsız). Küçük yazılar otomatik büyütülerek okunur (anlık taramada da).
- **Çeviri:** Ollama ile yerel, GPU hızlandırmalı çeviri (varsayılan model: `aya-expanse:8b`) + yapılandırılabilir yedek sırası (Argos Translate çevrimdışı, DeepL, Google Translate). Oyuna özgü sözlük (karakter/yer/eşya adları), elle çeviri düzeltme, harf-harf-beliren diyalog için debounce.
- **Oyun profilleri:** Ön plandaki `.exe`'ye göre OCR motoru/dili, overlay stili, okuma bölgeleri ve sözlük otomatik değişir.
- **Overlay:** PyQt6 ile şeffaf, tıklamaları geçiren, her zaman üstte kalan ve `WDA_EXCLUDEFROMCAPTURE` ile ekran yakalamalardan gizlenen pencere. Kutu / Altyazı / Şerit / Altyazı şeridi (ekranın en altında birleşik tek satır) stilleri. Exclusive fullscreen oyunlar için ikinci monitörde büyük bir altyazı penceresi açılabilir.
- **Okuma bölgeleri:** Tam ekranı kaplayan bir seçim katmanıyla "burayı hiç okuma" / "sadece burayı oku" bölgeleri çizilebilir.
- **Kaynak tasarrufu:** Oyun arka plandayken/bilgisayar boştayken canlı mod otomatik duraklar; sinematik sahne geçişleri OCR'a hiç gönderilmez; taramalar yavaşlarsa aralık otomatik büyür.
- **Kontrol paneli:** Sinema altyazısı temalı, özel çerçeveli pencere. Son çeviriyi büyük perdede gösteren Sahne sayfası ve SRT tarzı akış, oyundaki çizimin birebir önizlemesi, tıklayıp tuşa basarak kısayol atama, ilk açılış rehberi ve sistem kontrolü, oyun sırasında köşede duran mini panel.
- **Kısayollar:** F9 anlık tarama, F10 canlı (sadece değişen bölgeleri izleyen) mod, F11 çıkış, F8 bölge seçimi, F6 basılı tutunca orijinali göster. Hem `keyboard` kancası hem Win32 `RegisterHotKey` ile (çift kanal) çalışır; oyun Yönetici olarak çalışıyorsa programı da Yönetici olarak yeniden başlatma seçeneği vardır.
- **Akıllı filtreleme + önbellek:** Kısa/anlamsız/zaten Türkçe metinleri atlar; çevirileri bellek + SQLite'ta önbellekler.
- **Sorun giderme:** Gelişmiş sayfasından tek tıkla, son günlükler + (gizlenmiş) ayarlar + sistem bilgisini içeren bir tanı paketi (`.zip`) oluşturulabilir. Program açılışında GitHub Releases'e bakıp yeni sürüm varsa haber verir.

## Kurulum ve Kullanım

Ayrıntılı kurulum, kısayollar, ayarlar ve sorun giderme için
[`KULLANIM.md`](KULLANIM.md) dosyasına bakın. Sıfırdan bir bilgisayarda
en kolay yol `Kurulum.bat`'a çift tıklamak (bkz. KULLANIM.md §0); hazır
bir kurulum `.exe`'si üretmek isteyen geliştiriciler için bkz.
[`installer/README.md`](installer/README.md).

Hızlı başlangıç (geliştirici/elle kurulum):

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m app.main
```

Ollama'nın kurulu olması ve bir çeviri modelinin (`ollama pull aya-expanse:8b`) indirilmiş olması gerekir.

## Proje Yapısı

```
app/
├── __init__.py          __version__ (bkz. uygulama içi sürüm kontrolü)
├── main.py               Ana orkestrasyon, kısayollar, modlar
├── config.py              Ayarlar (config.json okuma/yazma)
└── core/
    ├── capture.py          Ekran yakalama + monitör kimliği
    ├── ocr.py              Windows OCR / EasyOCR / PaddleOCR / RapidOCR
    ├── translate.py         Ollama / Argos / DeepL / Google Translate
    ├── glossary.py           Oyun sözlüğü (karakter/yer/eşya adları)
    ├── overlay.py             Şeffaf overlay penceresi (4 stil)
    ├── cache.py                Çeviri önbelleği (SQLite)
    ├── textfilter.py            Akıllı filtreleme kuralları
    ├── hotkeys.py                Global kısayollar (keyboard + Win32)
    ├── winhotkey.py               Win32 RegisterHotKey + Yönetici yeniden başlatma
    ├── activity.py                 Ön plan pencere/boşta kalma tespiti
    ├── profiles.py                  Oyun bazlı profiller
    ├── regions.py                    Okuma bölgesi (dışında bırak/sadece oku) kararı
    ├── diagnostics.py                 Sorun bildirimi paketi (.zip)
    ├── update.py                      GitHub Releases sürüm kontrolü
    └── tray.py                        Sistem tepsisi simgesi
app/ui/                       Kontrol paneli, rehber, mini panel, büyük
                               altyazı penceresi, bölge seçici, tema
app/assets/fonts/              IBM Plex ve Newsreader (SIL OFL)
installer/                     PyInstaller + Inno Setup kurulum paketi tarifi
```

## Lisans

Bu proje kişisel kullanım amacıyla geliştirilmiştir.
