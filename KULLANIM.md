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

**Belirli bir sürümü kurmak isterseniz:** Hem `Kurulum.bat`/`kurulum.ps1`
hem de `Guncelle.bat`/`guncelle.ps1`, bir `$Surum` parametresi kabul eder.
Boş bırakılırsa (varsayılan) her zaman en güncel `main` dalı kurulur/
güncellenir. Belirli bir etiketi/dalı sabitlemek için PowerShell'den:
```
powershell -ExecutionPolicy Bypass -File kurulum.ps1 -Surum v1.2.0
powershell -ExecutionPolicy Bypass -File guncelle.ps1 -Surum v1.2.0
```

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

## 4. Kontrol Paneli ve Ayarlar

Program açıldığında kendi **kontrol paneli** açılır (kapattıysanız sistem
tepsisindeki simgeye çift tıklayın). İlk açılışta dört adımlık bir
**karşılama rehberi** çıkar: programın ne yaptığını, oyunun neden
kenarlıksız pencere modunda açılması gerektiğini ve kısayolları anlatır,
son adımda Ollama, çeviri modeli, ekran kartı ve yazı okumayı sizin için
kontrol eder. Rehbere istediğiniz zaman **Gelişmiş → Karşılama rehberi**
ile geri dönebilirsiniz.

Pencerenin üst bandında programın o anki durumu (Beklemede / Çeviriler
ekranda / Canlı mod ve süre sayacı), alt bandında çeviri motoru, yazı
okuma, ekran kartı belleği ve hafızadaki çeviri sayısı görünür. Pencere
kenarlarından boyutlandırılabilir, ekran kenarına sürükleyince yapışır;
boyutu ve konumu hatırlanır. Ctrl + 1…6 ile sayfalar arasında geçilir.

- **Sahne:** Oyunda yakalanan son çeviri büyük perdede altyazı gibi
  belirir, orijinali altında görünür. Altındaki iki düğme Anında tara ve
  Canlı modu fareyle açar/kapatır. Sağdaki **Akış**, oturum boyunca
  çevrilen her satırı bir altyazı dosyasındaki gibi numarası ve zaman
  koduyla listeler; satıra sağ tıklayıp kopyalayabilir, üstteki düğmeyle
  tüm akışı `.srt` biçiminde panoya alabilirsiniz.
- **Çeviri:** Yazı okuma (OCR) ve çeviri motoru, Ollama modeli, oyunun
  dili. **Dene** bölümü, yazdığınız cümleyi seçili motorla çevirip süresini
  gösterir. "Oyunun dili" Windows OCR içinse ve o dilin paketi kurulu
  değilse, hemen altında bir uyarı ve kurulum yolu çıkar. **"Ollama
  çalışmazsa Google'a gönder"** ayarı, Ollama kapalıyken ekrandaki
  yazıların yedek olarak internete (Google Translate'e) gönderilip
  gönderilmeyeceğini belirler — ilk ihtiyaç anında bir kez sorulur,
  burada istediğiniz zaman değiştirebilirsiniz. Çeviri motoru olarak
  zaten Google'ı seçtiyseniz bu ayar geçersizdir (zaten açıkça onay
  vermişsinizdir).
- **Görünüm:** Çevirilerin oyunda nasıl duracağı. Üstteki küçük oyun
  sahnesi, oyundaki çizimin birebir aynısıdır; göz simgesine basılı
  tutunca çeviriler kalkar ve orijinal oyun yazısını görürsünüz. Üç stil
  vardır: **Kutu** (yarı saydam kutu), **Altyazı** (kutu yok; film
  altyazısı gibi kenarlı yazı, altındaki orijinali yumuşak bir gölgeyle
  örter) ve **Şerit** (kenardan kenara koyu şerit). Yazı tipi, boyut,
  koyuluk, renkler ve hazır renk takımları da buradadır.
- **Kısayollar:** "Değiştir"e tıklayıp yeni tuşa (veya Ctrl/Alt/Shift
  ile birleşimine) basın; Esc vazgeçer. Kayıt sırasında programın kendi
  kısayolları geçici olarak durur. Aynı tuş iki işe atanırsa uyarır.
- **Gelişmiş:** Canlı mod tarama aralığı ve ekran bölmesi, filtreler,
  **"Küçük yazıları büyüterek oku"** (okumadan önce görüntüyü 2 kat
  büyütür, küçük fontlu yazılarda isabeti artırır; varsayılan açık, çok
  büyük taramalarda otomatik devre dışı kalıp hızı korur), **izlenecek
  ekran** (birden fazla monitörünüz varsa oyunun açık olduğu ekranı isme
  göre seçersiniz; değişiklik anında uygulanır ve çeviriler artık
  monitörün sanal masaüstündeki gerçek konumuna göre doğru yere çizilir),
  çeviri hafızası, rehberi yeniden açma ve varsayılana dönme.
- **Günlük:** Programın kayıtları; uyarılar sarı, hatalar kırmızı.
  Yalnızca uyarıları veya hataları süzebilir, kopyalayabilirsiniz.

**Mini panel:** Üst banttaki küçük ekran simgesi (veya tepsi menüsündeki
"Mini paneli göster") oyun oynarken ekranın köşesinde duran küçük bir
durum göstergesi açar. Sürükleyip istediğiniz yere taşıyın; yeri
hatırlanır. Üzerindeki iki düğme Anında tara ve Canlı modu açar, son
çeviri tek satır olarak görünür. Mini panel ekran yakalamalarına
görünmez, yani program onu okuyup çevirmeye çalışmaz.

Değişikliklerin neredeyse tamamı **anında** uygulanır ve otomatik olarak
`config.json` dosyasına kaydedilir — ayrıca kaydetmeniz gerekmez.
Dosyayı elle düzenlemek isterseniz de `C:\OyunCevirmen\config.json`
içinde aynı ayarları bulabilirsiniz, ama bunun için programı kapatmanız
gerekir.

## 5. OCR ve Çeviri Motorları Hakkında

- **Windows OCR** (varsayılan): Kurulum gerektirmez, hızlıdır. Okuyacağı
  dilin Windows OCR paketi kurulu olmalıdır. "Oyunun dili" **Otomatik
  algıla** ise, pratikte sadece **Latin alfabeli diller** (İngilizce,
  Almanca, Fransızca, İspanyolca, İtalyanca, Portekizce) için işe yarar;
  Japonca/Korece/Rusça/Çince bir oyun için o dili Çeviri sayfasından
  doğrudan seçmeniz gerekir. Program her dili doğru Windows dil
  etiketine çevirir (örn. Almanca → `de-DE`, Çince → `zh-Hans`) ve paket
  kurulu değilse Çeviri sayfasında dil seçiminin altında otomatik bir
  uyarı ve kurulum yolu gösterir. Eksikse Windows Ayarlar > Saat ve Dil >
  Dil ve Bölge > "Tercih ettiğim dilleri ekleyin" üzerinden ilgili dil
  paketini (OCR bileşeniyle birlikte) ekleyebilirsiniz, veya yönetici
  olarak (dil etiketini kendi dilinizle değiştirerek) şu komutu
  çalıştırabilirsiniz:
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
  kapalıysa, şüpheli bir çeviri üretirse vb.) yedek olarak devreye girer
  — ama **sessizce değil**: ilk ihtiyaç anında izin ister (kontrol paneli
  açıksa bir soru penceresiyle, kapalıysa sistem tepsisi bildirimiyle).
  İzin vermezseniz o yazı çevrilmez ve alt bantta "Çeviri yapılamıyor"
  olarak net şekilde görünür; Çeviri sayfasından istediğiniz zaman
  açıp kapatabilirsiniz. Çeviri motoru olarak zaten "Google Translate"i
  seçtiyseniz bu soru hiç sorulmaz. İnternet bağlantısı gerektirir.

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

**Oyun ikinci bir monitörde ama çeviri hiç çıkmıyor / yanlış yerde çıkıyor**
- Ekran yakalama tek seferde tek bir monitörü tarar (oyunlarda performans
  için gereklidir). Kontrol paneli → **Gelişmiş** → **"İzlenecek
  ekran"** menüsünden oyunun açık olduğu ekranı seçin; değişiklik anında
  uygulanır, programı yeniden başlatmanıza gerek yoktur.
- Çeviriler artık seçilen monitörün sanal masaüstündeki gerçek konumuna
  göre (ikincil monitör sağda/solda/üstte olsa, hatta negatif koordinatlı
  olsa bile) doğru yere çizilir. Yine de yanlış yerde çıkıyorsa, Windows
  görüntü ölçeklemesini (Ayarlar > Ekran > Ölçek) tüm monitörlerde aynı
  yapmayı deneyin.

**Çeviri motoru olarak Ollama seçili ama hiç çeviri çıkmıyor, Google'a da
geçmiyor**
- Ollama kapalı/çalışmıyor olabilir ve Google Translate'e henüz izin
  verilmemiş olabilir — bu BİLEREK yapılan bir güvenlik seçimidir, izniniz
  olmadan internete hiçbir şey gönderilmez. Alt bantta "Çeviri yapılamıyor"
  yazdığını görürseniz, kontrol panelini açın: ya izin isteyen soru
  penceresi otomatik çıkar, ya da Çeviri sayfasından **"Ollama çalışmazsa
  Google'a gönder"** ayarını kendiniz açabilirsiniz. Ollama'yı tekrar
  çalışır hale getirmek isterseniz `ollama serve` komutunu çalıştırın.

**Oyun İngilizce değil (Almanca/Fransızca/İspanyolca vb.) ama bazı yazılar
"zaten Türkçe" sanılıp atlanıyor**
- Çeviri sayfasından "Oyunun dili"ni **Otomatik algıla** yerine doğrudan
  o dile ayarlayın; program o zaman sadece Türkçeye kesin özgü harfler
  (ğ, ı, ş) görürse metni atlar, aksi halde çevirir.

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
│   │   └── tray.py           (sistem tepsisi simgesi/menusu)
│   ├── ui\
│   │   ├── theme.py          (renkler, yazi tipleri, stil sayfasi)
│   │   ├── frame.py          (ozel pencere cercevesi)
│   │   ├── mainwindow.py     (kontrol paneli)
│   │   ├── onboarding.py     (ilk acilis rehberi)
│   │   ├── minipanel.py      (oyun ici mini panel)
│   │   ├── widgets.py, icons.py, logo.py
│   │   └── pages\           (Sahne, Ceviri, Gorunum, Kisayollar, Gelismis, Gunluk)
│   └── assets\icon.png, icon.ico, fonts\
├── venv\                     (Python sanal ortami)
├── cache\translations.sqlite3
├── logs\oyuncevirmen.log
├── config.json               (ilk calistirmada otomatik olusur)
├── OyunCevirmenBaslat.bat     (programi baslatir)
├── Kurulum.bat                (sifirdan kurulum - bkz. Bolum 0)
├── kurulum.ps1
├── Guncelle.bat                (GitHub'daki guncellemeyi ceker)
├── guncelle.ps1
├── tests\                      (pytest testleri - gercek ekran/Ollama gerektirmez)
├── pytest.ini
└── KULLANIM.md                (bu dosya)
```

Testleri çalıştırmak için (geliştirme ortamında):
```
venv\Scripts\python.exe -m pytest
```
