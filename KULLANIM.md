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
bir şey varsa tamamlar, projeyi GitHub'daki son **yayınlanmış sürüme**
(aşağıya bakın) günceller, zaten kurulu olanları atlar.

**Varsayılan sürüm:** `kurulum.ps1` (ve dolayısıyla `Kurulum.bat`), hiçbir
parametre verilmezse GitHub'da yayınlanmış **en son sürümü** (release
etiketini) otomatik bulup onu kurar — `main` dalındaki henüz test
edilmemiş değişiklikleri değil. GitHub'a ulaşılamazsa (internet yok,
henüz hiç sürüm yayınlanmamış) sessizce `main` dalına döner.
`guncelle.ps1` ise (rutin güncelleme) hâlâ üzerinde bulunduğunuz dalı/
etiketi takip eder.

**Belirli bir sürümü kurmak isterseniz:** Hem `Kurulum.bat`/`kurulum.ps1`
hem de `Guncelle.bat`/`guncelle.ps1`, bir `$Surum` parametresi kabul eder.
Belirli bir etiketi/dalı sabitlemek için PowerShell'den:
```
powershell -ExecutionPolicy Bypass -File kurulum.ps1 -Surum v1.2.0
powershell -ExecutionPolicy Bypass -File guncelle.ps1 -Surum v1.2.0
```

**Alternatif: hazır kurulum paketi (.exe).** Python/Git bilmeyen veya
hiçbir şey kurmak istemeyen kullanıcılar için, GitHub'ın
[Releases](https://github.com/Turkeriscan/OyunCevirmen/releases)
sayfasında (varsa) ayrı bir Python kurulumu GEREKTİRMEYEN, Yönetici izni
İSTEMEYEN, Başlat Menüsü/Masaüstü kısayolu oluşturan ve Denetim
Masası'ndan kaldırılabilen bir `OyunCevirmenKur.exe` bulunabilir. Bu
paketi kendiniz derlemek isterseniz bkz. [`installer/README.md`](installer/README.md).

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
| **F8**  | Tam ekranı kaplayan bölge seçim katmanını açar: "dışında bırak" veya "sadece burayı oku" bölgeleri çizebilirsiniz (bkz. Bölüm 4.1). |
| **F6**  | Basılı **tutulduğu sürece** çeviri kutularını gizler, orijinal oyun yazısını gösterir; bırakınca aynı çeviriler anında geri gelir (yeniden tarama yapılmaz). |
| **F11** | Programı tamamen kapatır. |

Tüm bu kısayollar `config.json`'dan (veya Kısayollar sayfasından)
değiştirilebilir (bkz. Bölüm 4). **Global**'dirler, yani oyun pencerede/
odakta olsa da çalışır — biri değil, **iki ayrı kanaldan birden** dinlenir:
`keyboard` kütüphanesinin düşük seviye klavye kancası VE Windows'un kendi
`RegisterHotKey` API'si. Biri (örn. başka bir programın kancayla
çakışması yüzünden) çalışmazsa diğeri bir şans daha sağlar.

**Oyun Yönetici olarak çalışıyorsa kısayollar çalışmayabilir.** Bu,
Windows'un "Kullanıcı Arayüzü Ayrıcalık Yalıtımı" (UIPI) kuralından
kaynaklanır: daha düşük yetkili bir program (bu program), daha yüksek
yetkili bir pencereden (Yönetici olarak çalışan oyun) klavye olaylarını
güvenilir şekilde alamaz. Çözüm: Gelişmiş sayfasındaki **"Yönetici
olarak yeniden başlat"** düğmesiyle programı da aynı yetkiyle açın.

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
  Canlı modu fareyle açar/kapatır. Üstteki **profil çubuğu**, o an ön
  planda hangi oyunun olduğunu gösterir ve o oyun için ayrı bir ayar
  profili kaydedip yönetmenizi sağlar (bkz. Bölüm 4.1). Sağdaki **Akış**,
  oturum boyunca çevrilen her satırı bir altyazı dosyasındaki gibi
  numarası ve zaman koduyla listeler; satıra sağ tıklayıp kopyalayabilir
  veya **"Çeviriyi düzelt…"** ile o satırın çevirisini kalıcı olarak
  (motorlar tarafından bir daha asla ezilmeyecek şekilde) değiştirebilir,
  üstteki düğmeyle tüm akışı `.srt` biçiminde panoya alabilirsiniz.
- **Çeviri:** Yazı okuma (OCR — Windows OCR / EasyOCR / PaddleOCR /
  RapidOCR) ve çeviri motoru (Ollama / Argos Translate / DeepL / Google
  Translate, sıralamasıyla birlikte), Ollama modeli (ekran kartınıza göre
  bir model önerilir, **"Modeli indir"** ile indirme ilerlemesi gösterilir),
  oyunun dili. **Sözlük** bölümünde oyuna özgü karakter/yer/eşya adlarını
  ekleyip (CSV olarak içe/dışa aktarabilirsiniz) motorların bu isimleri
  her zaman aynı şekilde çevirmesini sağlayabilirsiniz. **Dene** bölümü,
  yazdığınız cümleyi seçili motorla çevirip süresini gösterir. **"Ollama
  çalışmazsa Google'a gönder"** ayarı üç durumludur (hiç sorulmadı / izin
  verildi / izin verilmedi) ve yalnızca Google bir **yedek** motor olarak
  devreye girecekse sorulur; motor olarak zaten Google'ı seçtiyseniz bu
  ayar geçersizdir.
- **Görünüm:** Çevirilerin oyunda nasıl duracağı. Üstteki küçük oyun
  sahnesi, oyundaki çizimin birebir aynısıdır; göz simgesine basılı
  tutunca çeviriler kalkar ve orijinal oyun yazısını görürsünüz. Dört
  stil vardır: **Kutu** (yarı saydam kutu), **Altyazı** (kutu yok; film
  altyazısı gibi kenarlı yazı, altındaki orijinali yumuşak bir gölgeyle
  örter), **Şerit** (kenardan kenara koyu şerit) ve **Altyazı şeridi**
  (tüm çeviriler orijinal yazının üzerine değil, ekranın EN ALTINDA
  birleşik tek bir satırda gösterilir — sinematik sahnelerde dağılmış
  kutular yerine tek, okunaklı bir altyazı ister iseniz). Yazı tipi,
  boyut, koyuluk, renkler ve hazır renk takımları da buradadır.
- **Kısayollar:** "Değiştir"e tıklayıp yeni tuşa (veya Ctrl/Alt/Shift
  ile birleşimine) basın; Esc vazgeçer. Kayıt sırasında programın kendi
  kısayolları geçici olarak durur. Aynı tuş iki işe atanırsa uyarır.
- **Gelişmiş:** Canlı mod tarama aralığı ve ekran bölmesi, harf-harf
  beliren diyalog bekleme süresi, filtreler, **"Küçük yazıları büyüterek
  oku"**, **"Kontrastı güçlendir"** (açık renk üzerine açık renk yazılar
  için CLAHE ile kontrast artırma), **Kaynak tasarrufu** (oyun arka
  plandayken/bilgisayar boştayken canlı modu duraklatma, büyük sahne
  geçişlerini OCR'a göndermeme), **izlenecek ekran**, **okuma bölgeleri**
  (bkz. Bölüm 4.2), çeviri hafızası, **Sorun giderme** (Yönetici olarak
  yeniden başlatma, sorun bildirimi paketi — bkz. Bölüm 4.4), sürüm
  numarası, rehberi yeniden açma ve varsayılana dönme.
- **Günlük:** Programın kayıtları; uyarılar sarı, hatalar kırmızı.
  Yalnızca uyarıları veya hataları süzebilir, kopyalayabilirsiniz.

**Mini panel:** Üst banttaki küçük ekran simgesi (veya tepsi menüsündeki
"Mini paneli göster") oyun oynarken ekranın köşesinde duran küçük bir
durum göstergesi açar. Sürükleyip istediğiniz yere taşıyın; yeri
hatırlanır. Üzerindeki iki düğme Anında tara ve Canlı modu açar, son
çeviri tek satır olarak görünür. Mini panel ekran yakalamalarına
görünmez, yani program onu okuyup çevirmeye çalışmaz.

### 4.1 Oyun Profilleri

Program, o an **ön planda olan pencerenin `.exe` adına** göre otomatik
olarak ayrı bir profil uygulayabilir: OCR motoru/dili, overlay stili,
okuma bölgeleri ve sözlük oyundan oyuna değişebilir. Sahne sayfasındaki
profil çubuğundan:
- O an tespit edilen oyunu görürsünüz ("Oyun tespit edilemedi" ise
  program/pencere öne alınamamış demektir).
- **"Profili kaydet"** ile o oyun için SU ANKI ayarlarınızı bir profil
  olarak kaydedersiniz; aynı oyuna her dönüşünüzde bu ayarlar otomatik
  uygulanır (genel ayarlarınız etkilenmez, siz başka bir oyuna veya
  masaüstüne geçtiğinizde genel ayarlarınıza geri dönülür).
- Profil varken **"Profili güncelle"**ye dönüşür — o oyundayken yaptığınız
  yeni ayar değişikliklerini profile kaydetmek için tekrar tıklayın.
- **"Profili sil"** o oyun için profili kaldırır, genel ayarlara döner.
- **"Profiller açık/kapalı"** tüm profil özelliğini (profilleri SİLMEDEN)
  geçici olarak devre dışı bırakır.

### 4.2 Okuma Bölgeleri ("Dışında Bırak" / "Sadece Burayı Oku")

Gelişmiş sayfasındaki **"Bölge çiz"** düğmesi veya **F8** kısayolu, tam
ekranı kaplayan yarı saydam bir seçim katmanı açar. Fare ile sürükleyerek
dikdörtgenler çizebilir, her birini **"Dışında bırak"** (o bölge hiç
okunmaz — örn. sabit bir HUD/sohbet kutusu) veya **"Sadece burayı oku"**
(işaretlenmişse SADECE o bölge(ler) okunur, geri kalanı yok sayılır)
olarak işaretleyebilirsiniz. **Enter** ile kaydedip kapatır, **Esc** ile
vazgeçersiniz (hiçbir şey kaydedilmez). Bu bölgeler oyun profilleriyle
birlikte de kaydedilebilir (Bölüm 4.1).

### 4.3 Büyük Altyazı Penceresi (İkinci Monitör)

Bazı oyunlar **Tam Ekran Özel (Exclusive Fullscreen)** modda çalışır ve
bu durumda normal overlay penceresi oyunun ÜSTÜNE ÇIKAMAZ (Windows'un
kendi sınırlamasıdır, Bölüm 3'e bakın). Çözüm: üst banttaki ikinci monitör
simgesi (veya tepsi menüsündeki "Büyük altyazı penceresini göster") ile
büyük, okunaklı bir altyazı penceresi açılır — varsayılan olarak ikinci
bir monitörünüz varsa oraya, yoksa birincil ekranın alt kısmına konur.
Sürükleyip istediğiniz yere taşıyabilirsiniz; yeri hatırlanır. Oyunu
birinci monitörde tam ekran oynarken göz ucuyla ikinci monitöre
bakarak çeviriyi takip edebilirsiniz.

### 4.4 Sorun Giderme ve Sorun Bildirimi

Gelişmiş sayfasındaki **"Sorun giderme"** bölümünde iki araç bulunur:
- **"Yönetici olarak yeniden başlat":** Kısayollar oyunda çalışmıyorsa
  (bkz. Bölüm 2), programı Yönetici izniyle yeniden başlatır.
- **"Paket oluştur (Masaüstüne)":** Son günlükleri, ayarlarınızı (API
  anahtarları gizlenmiş hâliyle) ve sistem bilgisini (Windows sürümü,
  ekran kartı, ekran düzeni, kurulu OCR dilleri, Ollama modelleri) tek
  bir `.zip` dosyasında Masaüstüne kaydeder — bir sorunu bildirirken bu
  dosyayı paylaşmanız yeterlidir. İsteğe bağlı olarak bir ekran görüntüsü
  de eklenebilir (varsayılan kapalı).

### 4.5 Sürüm Kontrolü

Program her açılışta (en fazla **günde bir kez**) GitHub'da yayınlanmış
en son sürüme bakar. Daha yeni bir sürüm varsa kontrol panelinin alt
bandındaki **"Sürüm"** alanında ve sistem tepsisi bildirimiyle haber
verilir. İnternet yoksa veya henüz hiç sürüm yayınlanmamışsa sessizce
hiçbir şey göstermez (hataya yol açmaz).

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
- **RapidOCR** (`onnxruntime-directml`): GPU üreticisinden bağımsız
  (NVIDIA/AMD/Intel fark etmez) bir GPU hızlandırmalı alternatiftir;
  isteğe bağlı kurulur (`pip install rapidocr-onnxruntime`), kurulu
  değilse program sessizce Windows OCR'a döner.

Küçük yazılar (örn. "Press E" gibi kısa etkileşim ipuçları), hangi
motoru kullanırsanız kullanın, okunmadan önce otomatik olarak büyütülüp
yeniden okunur — bu, hem canlı modda hem de F9 anlık taramasında
(ekranın yalnızca küçük yazılı bölgeleri tek tek kırpılıp büyütülerek)
çalışır.

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
- **Argos Translate** (çevrimdışı, isteğe bağlı): İnternet olmadan da
  çalışan ikinci bir yedek motordur; kurulu değilse sessizce atlanır.
- **DeepL** (bulut, isteğe bağlı): Ücretsiz bir API anahtarı
  (deepl.com/pro-api) girerseniz kullanılabilir hale gelir.

Hangi motorların, hangi SIRAYLA denenceği (örn. Ollama → Argos →
Google) Çeviri sayfasından yapılandırılabilir; kurulu/yapılandırılmamış
bir motor (örn. API anahtarı boşsa DeepL) otomatik atlanır.

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

**Oyun Yönetici olarak çalışıyor ve hiçbir kısayol (F9/F10/F8/F6)
çalışmıyor**
- Bu, Windows'un kendi güvenlik kuralından (UIPI) kaynaklanır: daha
  düşük yetkili bir program, daha yüksek yetkili bir pencereden klavye
  olaylarını güvenilir şekilde alamaz. Gelişmiş sayfasındaki **"Yönetici
  olarak yeniden başlat"** düğmesiyle programı da aynı yetkiyle açın.

**Canlı mod aniden duruyor/hiç tepki vermiyor gibi görünüyor**
- Bu BEKLENEN bir davranış olabilir: "Kaynak tasarrufu" özelliği, oyun
  penceresi arka plana alındığında veya bilgisayar bir süre boşta
  kaldığında canlı modu GEÇİCİ olarak duraklatır (ekranı hiç
  yakalamaz); oyuna/pencereye geri dönünce otomatik devam eder. Bu
  davranışı Gelişmiş sayfasından kapatabilirsiniz.

**Bir sinematik/sahne geçişi sırasında çeviriler kısa süreliğine kayboluyor**
- Ekranın büyük bölümü (%60 ve üzeri) birden değişirse, program bunu
  muhtemelen bir sinematik/sahne geçişi sayıp o kareyi hiç çevirmeye
  göndermez (anlamsız/yarım çevirilerin yanıp sönmesini önlemek için).
  Bu davranış Gelişmiş sayfasından kapatılabilir.

## 7. Klasör Yapısı (bilgi amaçlı)

```
C:\OyunCevirmen\
├── app\
│   ├── __init__.py          (__version__ - surum numarasi)
│   ├── main.py               (ana orkestrasyon, kisayollar, modlar)
│   ├── config.py              (ayarlar: config.json okuma/yazma)
│   ├── core\
│   │   ├── capture.py          (dxcam/mss ekran yakalama + monitor kimligi)
│   │   ├── ocr.py               (Windows OCR / EasyOCR / PaddleOCR / RapidOCR)
│   │   ├── translate.py          (Ollama / Argos / DeepL / Google Translate)
│   │   ├── glossary.py            (oyun sozlugu)
│   │   ├── overlay.py              (PyQt6 seffaf/clickthrough pencere, 4 stil)
│   │   ├── cache.py                 (bellek + SQLite ceviri onbellegi)
│   │   ├── textfilter.py             (akilli filtreleme kurallari)
│   │   ├── hotkeys.py                 (global kisayollar: keyboard + Win32)
│   │   ├── winhotkey.py                (Win32 RegisterHotKey + Yonetici yeniden baslatma)
│   │   ├── activity.py                  (on plan penceresi/bosta kalma tespiti)
│   │   ├── profiles.py                   (oyun bazli profiller)
│   │   ├── regions.py                     (okuma bolgesi karari)
│   │   ├── hardware.py                     (GPU'ya gore model onerisi)
│   │   ├── diagnostics.py                   (sorun bildirimi paketi)
│   │   ├── update.py                        (GitHub Releases surum kontrolu)
│   │   └── tray.py                           (sistem tepsisi simgesi/menusu)
│   ├── ui\
│   │   ├── theme.py          (renkler, yazi tipleri, stil sayfasi)
│   │   ├── frame.py          (ozel pencere cercevesi)
│   │   ├── mainwindow.py     (kontrol paneli)
│   │   ├── onboarding.py     (ilk acilis rehberi)
│   │   ├── minipanel.py      (oyun ici mini panel)
│   │   ├── bigsubtitle.py    (ikinci monitorde buyuk altyazi penceresi)
│   │   ├── regionoverlay.py  (F8 bolge secici tam ekran katmani)
│   │   ├── widgets.py, icons.py, logo.py
│   │   └── pages\           (Sahne, Ceviri, Gorunum, Kisayollar, Gelismis, Gunluk)
│   └── assets\icon.png, icon.ico, fonts\
├── installer\                 (PyInstaller + Inno Setup kurulum paketi tarifi)
├── .github\workflows\          (pytest + surum yayinlama is akislari)
├── venv\                     (Python sanal ortami)
├── cache\translations.sqlite3
├── logs\oyuncevirmen.log
├── config.json               (ilk calistirmada otomatik olusur)
├── glossary.json              (oyun sozlugu, ilk kullanimda olusur)
├── OyunCevirmenBaslat.bat     (programi baslatir)
├── Kurulum.bat                (sifirdan kurulum - bkz. Bolum 0)
├── kurulum.ps1
├── Guncelle.bat                (GitHub'daki guncellemeyi ceker)
├── guncelle.ps1
├── tools\test_pencere.py       (elle hotkey/overlay testi - pytest DEGIL)
├── tests\                      (pytest testleri - gercek ekran/Ollama gerektirmez)
├── pytest.ini
└── KULLANIM.md                (bu dosya)
```

Testleri çalıştırmak için (geliştirme ortamında):
```
venv\Scripts\python.exe -m pytest
```
