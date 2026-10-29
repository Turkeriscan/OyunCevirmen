"""
Akilli filtreleme: OCR'dan gelen metin parcalarindan hangilerinin
cevrilmeye deger oldugunu belirler.

Kurallar:
 - 2 karakterden kisa metinler atlanir (tekil harf, nokta, vb.)
 - Sadece sayi/sembol iceren metinler atlanir (skor, HP bari, vb.)
 - OCR guven skoru esigin altindaysa atlanir (yanlis okunan curuk metin)
 - Metin zaten Turkce ise atlanir (ceviriye gerek yok)
"""
import re

try:
    from langdetect import detect, DetectorFactory, LangDetectException
    DetectorFactory.seed = 0
    _LANGDETECT_OK = True
except Exception:
    _LANGDETECT_OK = False

# Sadece Turkceye OZGU harfler (Almanca/Fransizca/Portekizce de ç/ö/ü kullanir,
# bu yuzden onlar ayri ve daha zayif bir sinyal sayilir - bkz. _TURKISH_WEAK_CHARS).
#
# ONEMLI: Buraya ASCII "I" (U+0049) KESINLIKLE EKLENMEMELI. Turkce'de buyuk
# noktasiz I ile Ingilizce "I" harfi AYNI Unicode kod noktasini (U+0049)
# paylasir - bu yuzden "I" harfini "kesin Turkce sinyali" saymak "Inventory
# is full", "I need help", "Items", "OPTIONS" gibi gayet sIradan Ingilizce
# metinleri (ve tum BUYUK HARFLI Ingilizce menuleri) Turkce sanip atlatirdi.
# Harfleri duz metin yerine BILEREK \u kod noktalariyla yaziyoruz; bu hata
# ("ğıİşĞIŞ" gibi duz bir dizgi icine yanlislikla ASCII I sizdirmak) boylece
# ileride tekrarlanamaz - her karakter acikca ne oldugunu soyler.
_TURKISH_STRONG_CHARS = {
    "ğ",  # g-breve kucuk harf (lowercase g-breve)
    "Ğ",  # G-breve buyuk harf (uppercase G-breve)
    "ı",  # noktasiz kucuk i - ASCII "I" (U+0049) ILE KARISTIRILMAMALI
    "İ",  # noktali buyuk I
    "ş",  # s-cedilla kucuk harf
    "Ş",  # S-cedilla buyuk harf
}
_TURKISH_WEAK_CHARS = {
    "ç",  # c-cedilla kucuk harf
    "ö",  # o-umlaut kucuk harf
    "ü",  # u-umlaut kucuk harf
    "Ç",  # c-cedilla buyuk harf
    "Ö",  # o-umlaut buyuk harf
    "Ü",  # u-umlaut buyuk harf
}

# Kisa fonksiyon kelimeleri: digerdillerle (Ispanyolca/Portekizce/Italyanca/
# Fransizca) carpisanlar ("de", "da", "o", "ne", "ya", "su", "mi", "la"...)
# BILEREK listede degil.
_TURKISH_STOPWORDS = {
    "ve", "bir", "bu", "için", "icin", "ile", "çok", "cok", "ama", "gibi",
    "ben", "sen", "biz", "siz", "var", "yok", "evet", "hayır", "hayir",
    "mı", "mu", "mü", "şu", "kadar", "daha", "sonra",
    "merhaba", "selam", "naber", "nasılsın", "nasilsin", "tamam", "lütfen", "lutfen",
    "teşekkür", "tesekkur", "dünya", "dunya", "gün", "gun", "iyi", "kötü",
}

# Oyun arayuzunde sik gecen, Turkceye OZGU harf icermeyen (ğ/ı/ş yok) ama
# baska dillerle kolay karismayan yaygin Turkce kelimeler. "Envanter dolu"
# gibi aksansiz kisa cumleleri yakalamak icin (langdetect bu tur kisa
# metinlerde guvenilmez - bkz. is_probably_turkish).
_TURKISH_COMMON_WORDS = {
    "dolu", "boş", "bos", "tam", "yeni", "eski", "oyun", "oyuna", "can", "envanter",
    "devam", "zaman", "harita", "seviye", "puan", "aktif", "durum", "silah",
    "zırh", "zirh", "altın", "altin", "para", "ekip", "görev", "gorev",
    "başarı", "basari", "menü", "menu", "ayarlar", "kaydet", "yükle", "yukle",
    "bitti", "yükleniyor", "yukleniyor", "duraklatma", "duraklat",
    "takip", "dikkat", "kontrol", "tuzak", "tuzaklar",
}

_TURKISH_WORDS = _TURKISH_STOPWORDS | _TURKISH_COMMON_WORDS

_SYMBOL_OR_DIGIT_RE = re.compile(r"^[\s\d\W]*$", re.UNICODE)


def is_too_short(text, min_length=2):
    cleaned = text.strip()
    return len(cleaned) < min_length


def is_only_symbols_or_numbers(text):
    cleaned = text.strip()
    if not cleaned:
        return True
    return bool(_SYMBOL_OR_DIGIT_RE.match(cleaned))


def is_low_confidence(confidence, threshold=0.45):
    if confidence is None:
        return False
    return confidence < threshold


def is_probably_turkish(text, source_lang="auto"):
    """Metin buyuk olasilikla zaten Turkce ise True doner (cevrilmesine gerek yok).

    source_lang: config'teki OCR kaynak dili. "auto"/"tr"/None disinda belirli
    bir dil secilmisse (orn. "de"), kullanici oyunun o dilde oldugunu zaten
    soylemis demektir; bu durumda SADECE Turkceye kesin ozgu harfler (ğ/ı/ş)
    Turkce sayilir - zayif harfler/kelime listesi/langdetect gibi daha
    belirsiz sinyallere basvurulmaz (yanlislikla o dildeki metni Turkce
    sanip atlamamak icin daha temkinli davranilir).
    """
    cleaned = text.strip()
    if not cleaned:
        return False

    # Turkceye KESIN ozgu harfler (ğ, ı, ş, İ) -> tek basina yeterli, guclu sinyal.
    if any(ch in _TURKISH_STRONG_CHARS for ch in cleaned):
        return True

    specific_other_language = source_lang not in (None, "auto", "tr")
    if specific_other_language:
        # Kullanici kaynak dili acikca baska bir dil olarak secti; sadece
        # guclu harf sinyaline guven (yukarida zaten kontrol edildi).
        return False

    words = re.findall(r"[^\W\d_]+", cleaned.lower(), re.UNICODE)
    word_count = len(words)
    stop_hits = sum(1 for w in words if w in _TURKISH_WORDS) if words else 0
    ratio = stop_hits / word_count if word_count else 0.0
    has_weak_chars = any(ch in _TURKISH_WEAK_CHARS for ch in cleaned)

    # Kisa bir ifadenin TUM kelimeleri bilinen Turkce kelimelerse (orn.
    # "Envanter dolu") aksan isareti olmasa da guvenle Turkce sayilir.
    if word_count >= 1 and stop_hits == word_count and (word_count >= 2 or has_weak_chars):
        return True
    # Daha uzun metinde kelimelerin coguncu Turkce ise yeterli.
    if ratio >= 0.6 and stop_hits >= 2:
        return True
    # ç/ö/ü gibi zayif harfler TEK BASINA yetmez; makul bir kelime
    # eslesmesiyle birlikteyse ek bir sinyal olarak kabul edilir.
    if has_weak_chars and ratio >= 0.3 and stop_hits >= 1:
        return True

    # langdetect kisa metinlerde cok guvenilmez (test: "Ça va, garçon" -> "tr",
    # "Envanter dolu" -> "nl" gibi yanlis sonuclar verebiliyor). Bu yuzden
    # SADECE yeterince uzun metinlerde VE tek basina karar verdirmeden,
    # digerdillerin kelime listesiyle de celismiyorsa kullanilir.
    if _LANGDETECT_OK and len(cleaned) >= 40 and word_count >= 4:
        try:
            lang = detect(cleaned)
            return lang == "tr"
        except LangDetectException:
            return False
        except Exception:
            return False

    return False


def should_translate(text, confidence=None, min_length=2, min_confidence=0.45, source_lang="auto"):
    """Tum filtreleri uygular; True ise metin cevrilmeli."""
    if text is None:
        return False
    if is_too_short(text, min_length):
        return False
    if is_only_symbols_or_numbers(text):
        return False
    if is_low_confidence(confidence, min_confidence):
        return False
    if is_probably_turkish(text, source_lang=source_lang):
        return False
    return True
