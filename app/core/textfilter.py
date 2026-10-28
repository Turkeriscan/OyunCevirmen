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
import string

try:
    from langdetect import detect, DetectorFactory, LangDetectException
    DetectorFactory.seed = 0
    _LANGDETECT_OK = True
except Exception:
    _LANGDETECT_OK = False

_TURKISH_CHARS = set("çğıöşüÇĞİÖŞÜ")

_TURKISH_STOPWORDS = {
    "ve", "bir", "bu", "da", "de", "için", "icin", "ile", "çok", "cok", "ama", "gibi",
    "ben", "sen", "biz", "siz", "var", "yok", "ne", "evet", "hayır", "hayir",
    "mı", "mi", "mu", "mü", "şu", "su", "o", "ya", "kadar", "daha", "sonra",
    "merhaba", "selam", "naber", "nasılsın", "nasilsin", "tamam", "lütfen", "lutfen",
    "teşekkür", "tesekkur", "dünya", "dunya", "gün", "gun", "iyi", "kötü", "koty",
}

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


def is_probably_turkish(text):
    """Metin buyuk olasilikla zaten Turkce ise True doner (cevrilmesine gerek yok)."""
    cleaned = text.strip()
    if not cleaned:
        return False

    # Turkce'ye ozgu harfler varsa guclu sinyal
    if any(ch in _TURKISH_CHARS for ch in cleaned):
        return True

    words = re.findall(r"[^\W\d_]+", cleaned.lower(), re.UNICODE)
    if words:
        stop_hits = sum(1 for w in words if w in _TURKISH_STOPWORDS)
        if stop_hits >= 1 and stop_hits / max(len(words), 1) >= 0.3:
            return True

    if _LANGDETECT_OK and len(cleaned) >= 6:
        try:
            lang = detect(cleaned)
            return lang == "tr"
        except LangDetectException:
            return False
        except Exception:
            return False

    return False


def should_translate(text, confidence=None, min_length=2, min_confidence=0.45):
    """Tum filtreleri uygular; True ise metin cevrilmeli."""
    if text is None:
        return False
    if is_too_short(text, min_length):
        return False
    if is_only_symbols_or_numbers(text):
        return False
    if is_low_confidence(confidence, min_confidence):
        return False
    if is_probably_turkish(text):
        return False
    return True
