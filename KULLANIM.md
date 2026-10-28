# Oyun Çevirmen - Kullanım Kılavuzu

Türkçe dil desteği olmayan oyunlarda ekrandaki yabancı yazıları otomatik
bulup Türkçeye çeviren ve çeviriyi orijinal yazının tam üstünde gösteren
masaüstü programı.

## 0. Sıfırdan Kurulum (Yeni/Boş Bir Bilgisayarda)

Üzerinde hiçbir şey (Python, Git, Ollama vb.) kurulu olmayan bir
bilgisayarda programı ilk kez kuracaksanız:

1. Bu depoyu indirin (yeşil **Code → Download ZIP** veya `git clone
   https://github.com/Turkeriscan/OyunCevirmen.git`) ve klasörü
   `C:\OyunCevirmen` olarak açın.
2. **`Kurulum.bat`** dosyasına çift tıklayın.
3. Yönetici izni isteyecektir, **Evet**'e tıklayın.
4. Betik sizin için şunları otomatik yapar: Git/Python/Ollama'yı kurar
   (eksikse), projeyi hazırlar, Python kütüphanelerini kurar, ekran
   kartınız varsa GPU'lu OCR'ı kurar, çeviri modelini indirir (~5 GB),
   Windows OCR dil paketini ekler ve masaüstüne kısayol oluşturur.
   İnternet hızınıza göre **10-40 dakika** sürebilir; bilgisayarı
   kapatmayın.
5. Sonunda "Şimdi başlatmak ister misiniz?" diye sorar — Enter'a basmanız
   yeterli.

Bu betiği zaten kurulu bir sistemde de çalıştırabilirsiniz; eksik/bozuk
bir şey varsa tamamlar, projeyi GitHub'daki son sürüme günceller,
zaten kurulu olanları atlar.

## 1. Nasıl Başlatılır

Kurulum tamamlandıktan sonra, en kolay yol: **Masaüstündeki "Oyun
Çevirmen" kısayoluna çift tıklamak.**

Alternatif olarak:
- `C:\OyunCevirmen\OyunCevirmenBaslat.bat` dosyasına çift tıklayın.
- Veya bir terminalden:
  ```
  cd C:\OyunCevirmen
  venv\Scripts\python.exe -m app.main
  ```
  (Hata ayıklamak istiyorsanız bu yöntemi kullanın; `python.exe` konsollu
  olduğu için hataları ekranda görürsünüz. `.bat` dosyası ise konsolsuz
  `pythonw.exe` kullanır, bir sorun olursa otomatik olarak konsollu moda
  geçip hata mesajını gösterir.)

Program açıldığında:
- Ollama servisi çalışmıyorsa otomatik olarak başlatılır (bu nedenle ilk
  açılış birkaç saniye sürebilir).
- Sistem tepsisinde (saat yanında, gerekirse "gizli simgeler" oku ile
  açılan alanda) bir simge belirir. Bu simgeye sağ tıklayarak ayarları
  açabilir, anlık/canlı modu tetikleyebilir veya programı kapatabilirsiniz.

## 2. Kısayollar

| Tuş | İşlev |
|-----|-------|
| **F9**  | Anlık mod: O anki ekranı bir kez tarar, bulduğu tüm yazıların Türkçe çevirisini üstlerine yazar. Tekrar F9'a basınca kapanır. |
| **F10** | Canlı mod aç/kapat: Ekran sürekli izlenir, sadece *değişen* bölgeler yeniden okunup çevrilir. Diyalog kutuları, alt yazılar gibi değişen metinler için idealdir. |
| **F11** | Programı tamamen kapatır. |

Bu kısayollar **global**'dir, yani oyun pencerede/odakta olsa da çalışır
(düşük seviye klavye kancası kullanılır). Bazı anti-cheat sistemi agresif
oyunlarda (örn. bazı rekabetçi oyunlar) bu tür global kancalar engellenebilir;
bu durumda programı oyundan önce başlatmanız veya oyunu Borderless Windowed
modda çalıştırmanız önerilir (bkz. aşağıdaki bölüm).

Kısayollar `config.json` dosyasından değiştirilebilir (bkz. Bölüm 4).

## 3. Neden Borderless Windowed Mod Gerekli?

Ekran yakalama (`dxcam` / DXGI Desktop Duplication) ve global kısayollar,
**Tam Ekran Özel (Exclusive Fullscreen)** modda çalışan oyunlarda genellikle
sorun çıkarır:

- Tam ekran özel modda GPU, ekranı doğrudan oyuna "kiralar"; Windows'un
  masaüstü penceresi (overlay'imiz dahil) o anda ekranda GÖRÜNMEZ ve
  bazı ekran yakalama API'leri siyah/boş görüntü döndürür.
- Global klavye kısayolları ve üstte kalan pencereler tam ekran özel modda
  güvenilmez çalışabilir.

**Borderless Windowed** (veya "Pencereli Tam Ekran") modda oyun, aslında
kenarlıksız bir **pencere** olarak çalışır ve masaüstü kompozisyonunun bir
parçasıdır. Bu sayede:
- Ekran yakalama düzgün çalışır,
- Overlay'imiz oyunun üstünde doğru şekilde görünür,
- Kısayollar güvenilir şekilde tetiklenir.

Oyununuzun grafik ayarlarından "Pencere Modu" / "Display Mode" seçeneğini
**Borderless / Windowed Fullscreen / Pencereli Tam Ekran** olarak ayarlayın.

## 4. Ayarları Değiştirme

Program açıldığında kendi **kontrol paneli** penceresi açılır (yoksa
sistem tepsisindeki simgeye çift tıklayın). Soldaki menüden sayfalar
arasında geçin:

- **Ana sayfa:** F9/F10'u fareyle tetikleyin, anlık durum (Ollama, GPU,
  OCR motoru, önbellekteki çeviri sayısı) ve son çevirilerin listesi.
- **Çeviri:** OCR/çeviri motoru, Ollama modeli, kaynak dil; "Çeviriyi
  dene" kutusuyla ayarı oyuna girmeden test edebilirsiniz.
- **Görünüm:** Font boyutu, saydamlık, renkler — yandaki mini önizleme
  değişikliği anında gösterir. Hazır stiller (Altyazı sarısı, Yüksek
  kontrast, Kâğıt...) tek tıkla uygulanır.
- **Kısayollar:** F9/F10/F11 tuşlarını değiştirin.
- **Performans:** Canlı mod tarama sıklığı/ızgarası, filtre eşikleri,
  **izlenecek ekran** (birden fazla monitörünüz varsa, oyunun açık
  olduğu ekranı isme göre seçersiniz — değişiklik anında uygulanır,
  yeniden başlatmaya gerek yoktur) ve **"Çeviri hafızasını sil"**
  butonu (modeli değiştirdiyseniz veya eski/bozuk çevirilerden
  kurtulmak isterseniz).
- **Günlük:** Programın yaptığı her şeyin canlı akışı; bir sorun olursa
  buraya bakın.

Değişikliklerin neredeyse tamamı **anında** uygulanır ve otomatik olarak
`config.json` dosyasına kaydedilir — ayrıca kaydetmeniz gerekmez.
Dosyayı elle düzenlemek isterseniz de `C:\OyunCevirmen\config.json`
içinde aynı ayarları bulabilirsiniz, ama bunun için programı kapatmanız
gerekir.

## 5. OCR ve Çeviri Motorları Hakkında

- **Windows OCR** (varsayılan): Kurulum gerektirmez, hızlıdır. Sistem
  dilinizde ilgili OCR dil paketi kurulu olmalıdır (İngilizce metinler için
  "English (US)" OCR paketi). Eksikse Windows Ayarlar > Saat ve Dil >
  Dil ve Bölge > "Tercih ettiğim dilleri ekleyin" üzerinden İngilizce dil
  paketini (OCR bileşeniyle birlikte) ekleyebilirsiniz, veya yönetici
  olarak şu komutu çalıştırabilirsiniz:
  ```
  DISM /Online /Add-Capability /CapabilityName:Language.OCR~~~en-US~0.0.1.0
  ```
- **EasyOCR** (GPU): PyTorch/CUDA tabanlıdır, bu bilgisayardaki
  NVIDIA RTX 5070 ile GPU hızlandırmalı çalışır. İlk kullanımda modelleri
  internetten indirir (~100 MB), bu nedenle ilk açılış biraz sürebilir.
- **PaddleOCR**: Kod içinde desteklenir ancak bu bilgisayardaki RTX 5070
  (Blackwell mimarisi, "compute capability 12.0") için PaddlePaddle'ın GPU
  derlemesi şu anda **resmi olarak desteklenmiyor** (test edildi, GPU'da
  yanlış sonuç üretti). Bu yüzden GPU alternatifi olarak **EasyOCR**
  kullanılmaktadır. Paddle'ın Blackwell desteği ileride gelirse,
  `pip install paddlepaddle-gpu paddleocr` ile yeniden kurup
  `config.json`'da `ocr_engine` alanını güncelleyebilirsiniz.

- **Ollama** (`aya-expanse:8b`): Cohere'in çok dilli (23+ dil, Türkçe dahil)
  olarak özel eğitilmiş modelidir. Oyun metinleri için kısa ve doğal Türkçe
  üretmesi amacıyla özel bir sistem talimatı (`app/core/translate.py`
  içindeki `SYSTEM_PROMPT_TR`) kullanılır. Model RTX 5070'te **tamamen
  GPU üzerinde** çalışır (test edildi: `ollama ps` çıktısında "100% GPU").
- **Google Translate** (`deep-translator`): Ollama kullanılamazsa (servis
  kapalıysa, model bozuksa vb.) otomatik olarak devreye girer. İnternet
  bağlantısı gerektirir.

Çeviriler hem bellekte hem de `cache\translations.sqlite3` dosyasında
önbelleğe alınır; aynı metin tekrar görüldüğünde yeniden çeviri
yapılmadan anında gösterilir.

## 6. Sık Karşılaşılan Sorunlar

**Overlay hiçbir şey göstermiyor / F9 tepki vermiyor**
- `logs\oyuncevirmen.log` dosyasını kontrol edin.
- Programı normal `python.exe -m app.main` ile (konsollu) başlatıp
  hata mesajlarını doğrudan görün.
- Bazı oyunlar klavye kancalarını engeller; oyunu Borderless Windowed
  moda alın (Bölüm 3) ve programı **oyundan önce** başlatmayı deneyin.

**Çeviriler çok yavaş geliyor**
- `translate_engine` olarak `"ollama"` kullanıldığından ve modelin
  GPU'da çalıştığından emin olun: `ollama ps` komutunu çalıştırıp
  `PROCESSOR` sütununda `100% GPU` yazdığını doğrulayın.
- Canlı moddaysanız `live_scan_interval` değerini artırarak (örn. `0.7`)
  tarama sıklığını azaltabilirsiniz.
- `live_grid_cols` / `live_grid_rows` değerlerini küçültmek (daha büyük
  ama daha az hücre) de yükü azaltabilir.

**Windows OCR "dil paketi kurulu değil" hatası veriyor**
- Bölüm 5'teki DISM komutunu **yönetici olarak açılmış** PowerShell'de
  çalıştırın, ardından bilgisayarı yeniden başlatmanız gerekebilir.
- Alternatif olarak `config.json`'da `"ocr_engine": "easyocr"` yapın;
  EasyOCR herhangi bir Windows dil paketine ihtiyaç duymaz.

**Ollama modeli hiç yanıt vermiyor**
- `ollama list` ile modelin kurulu olduğunu doğrulayın
  (`aya-expanse:8b` görünmeli).
- Ollama servisi elle başlatmak için: `ollama serve` (ayrı bir
  terminalde açık bırakın) ya da sadece programı yeniden başlatın,
  kendisi otomatik başlatmayı dener.

**Overlay'in kendi yazdığı çeviri tekrar okunup tekrar "çevriliyor"**
- Bu olmaması gerekir: overlay penceresine `SetWindowDisplayAffinity`
  ile `WDA_EXCLUDEFROMCAPTURE` uygulanmıştır, yani hem ekran
  kayıt/yayın yazılımları hem de programın kendi ekran taraması bu
  pencereyi görmez. Eğer yine de bir sorun fark ederseniz
  (örn. çok eski bir Windows sürümünde bu API yoksa), `logs` klasöründeki
  günlükte "WDA_EXCLUDEFROMCAPTURE" ile ilgili bir uyarı olup olmadığına
  bakın.

**Çok fazla yanlış/anlamsız çeviri kutusu çıkıyor**
- `min_ocr_confidence` değerini artırın (örn. `0.6`).
- `min_text_length` değerini artırın.

**Oyun ikinci bir monitörde ama çeviri hiç çıkmıyor**
- Ekran yakalama tek seferde tek bir monitörü tarar (oyunlarda performans
  için gereklidir). Kontrol paneli → **Performans** → **"İzlenecek
  ekran"** menüsünden oyunun açık olduğu ekranı seçin; değişiklik anında
  uygulanır, programı yeniden başlatmanıza gerek yoktur.

## 7. Klasör Yapısı (bilgi amaçlı)

```
C:\OyunCevirmen\
├── app\
│   ├── main.py            (ana orkestrasyon, kısayollar, modlar)
│   ├── config.py           (ayarlar: config.json okuma/yazma)
│   ├── core\
│   │   ├── capture.py       (dxcam/mss ekran yakalama)
│   │   ├── ocr.py           (Windows OCR / EasyOCR / PaddleOCR)
│   │   ├── translate.py     (Ollama + Google Translate, sistem talimatı)
│   │   ├── overlay.py        (PyQt6 seffaf/clickthrough pencere)
│   │   ├── cache.py          (bellek + SQLite ceviri onbellegi)
│   │   ├── textfilter.py     (akilli filtreleme kurallari)
│   │   ├── hotkeys.py        (F9/F10/F11 global kisayollar)
│   │   ├── tray.py           (sistem tepsisi simgesi/menusu)
│   │   └── mainwindow.py      (kontrol paneli / ayarlar arayuzu)
│   └── assets\icon.png, icon.ico
├── venv\                     (Python sanal ortami)
├── cache\translations.sqlite3
├── logs\oyuncevirmen.log
├── config.json               (ilk calistirmada otomatik olusur)
├── OyunCevirmenBaslat.bat     (programi baslatir)
├── Kurulum.bat                (sifirdan kurulum - bkz. Bolum 0)
├── kurulum.ps1
└── KULLANIM.md                (bu dosya)
```
