# Oyun Çevirmen

Türkçe dil desteği olmayan oyunlarda ekrandaki yabancı yazıları otomatik
bulan ve Türkçeye çevirip orijinal yazının tam üstünde gösteren bir
Windows masaüstü uygulaması.

## Özellikler

- **Ekran yakalama:** `dxcam` (DXGI Desktop Duplication), `mss` yedekli. Borderless Windowed oyunları destekler.
- **OCR:** Windows OCR (varsayılan, kurulum gerektirmez) veya EasyOCR (GPU/CUDA hızlandırmalı).
- **Çeviri:** Ollama ile yerel, GPU hızlandırmalı çeviri (varsayılan model: `aya-expanse:8b`) + Google Translate yedek motoru.
- **Overlay:** PyQt6 ile şeffaf, tıklamaları geçiren, her zaman üstte kalan ve `WDA_EXCLUDEFROMCAPTURE` ile ekran yakalamalardan gizlenen pencere.
- **Kontrol paneli:** Sinema altyazısı temalı, özel çerçeveli pencere. Son çeviriyi büyük perdede gösteren Sahne sayfası ve SRT tarzı akış, oyundaki çizimin birebir önizlemesi (Kutu / Altyazı / Şerit stilleri), tıklayıp tuşa basarak kısayol atama, ilk açılış rehberi ve sistem kontrolü, oyun sırasında köşede duran mini panel.
- **Modlar:** F9 anlık tarama, F10 canlı (sadece değişen bölgeleri izleyen) mod, F11 çıkış.
- **Akıllı filtreleme + önbellek:** Kısa/anlamsız/zaten Türkçe metinleri atlar; çevirileri bellek + SQLite'ta önbellekler.

## Kurulum ve Kullanım

Ayrıntılı kurulum, kısayollar, ayarlar ve sorun giderme için
[`KULLANIM.md`](KULLANIM.md) dosyasına bakın.

Hızlı başlangıç:

```powershell
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python -m app.main
```

Ollama'nın kurulu olması ve bir çeviri modelinin (`ollama pull aya-expanse:8b`) indirilmiş olması gerekir.

## Proje Yapısı

```
app/
├── main.py            Ana orkestrasyon, kısayollar, modlar
├── config.py           Ayarlar (config.json okuma/yazma)
└── core/
    ├── capture.py       Ekran yakalama
    ├── ocr.py           Windows OCR / EasyOCR / PaddleOCR
    ├── translate.py      Ollama + Google Translate
    ├── overlay.py         Şeffaf overlay penceresi
    ├── cache.py            Çeviri önbelleği
    ├── textfilter.py        Akıllı filtreleme kuralları
    ├── hotkeys.py           Global kısayollar
    └── tray.py              Sistem tepsisi simgesi
app/ui/                      Kontrol paneli, rehber, mini panel, tema
app/assets/fonts/            IBM Plex ve Newsreader (SIL OFL)
```

## Lisans

Bu proje kişisel kullanım amacıyla geliştirilmiştir.
