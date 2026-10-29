"""
Dil tespiti testleri: Turkce olmayan (Almanca/Fransizca/Ispanyolca/
Portekizce) metinlerin yanlislikla "zaten Turkce" sanilip atlanmadigini,
gercek Turkce cumlelerin dogru tanindigini dogrular.

Gercek ekran/OCR/ag gerektirmez; sadece metin uzerinde calisan saf
fonksiyonlar test edilir.
"""
import csv
import os

from app.core import textfilter

_CORPUS_PATH = os.path.join(os.path.dirname(__file__), "data", "filter_corpus.csv")


def _load_corpus():
    with open(_CORPUS_PATH, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------- ASCII "I" ile Turkce ı/İ karismasi
# Bu dogrudan bildirilen hatanin kendisi: Turkce'de "I" (ASCII U+0049) hem
# noktasiz buyuk harf, hem de Ingilizce'nin kendi "I" zamiri/harfidir. Bu
# yuzden sadece BUYUK HARFLE yazilmis veya "I" harfi iceren gayet sIradan
# Ingilizce oyun metinleri yanlislikla "zaten Turkce" sayilip atlanmamali.
ENGLISH_WITH_ASCII_I = [
    "Inventory is full",
    "I need help",
    "It is dangerous",
    "Items",
    "I",
    "Press I to open inventory",
    "This is important",
    "I am ready",
]

ALL_CAPS_ENGLISH_MENUS = [
    "OPTIONS", "SETTINGS", "INVENTORY", "EXIT", "CONTINUE", "NEW GAME",
    "PAUSE MENU", "MAIN MENU", "LOAD GAME", "CONTROLS", "RESUME GAME",
]


def test_english_sentences_with_ascii_i_are_not_treated_as_turkish():
    for text in ENGLISH_WITH_ASCII_I:
        assert not textfilter.is_probably_turkish(text), (
            f"{text!r} ASCII 'I' harfi yuzunden yanlislikla Turkce sayildi"
        )


def test_all_caps_english_menus_should_translate():
    for text in ALL_CAPS_ENGLISH_MENUS:
        assert textfilter.should_translate(text, confidence=0.9), (
            f"{text!r} (BUYUK HARFLI Ingilizce menu) cevrilmek uzere isaretlenmedi"
        )


def test_ascii_i_is_not_in_strong_turkish_chars():
    """Bu hatanin kok sebebi: ASCII "I" (U+0049) kumede OLMAMALI - Turkce'nin
    kendi noktasiz/noktali harfleri (ı/İ/ğ/Ğ/ş/Ş) ile ayni kod noktasini
    paylasmiyor, bu yuzden ayri kalmalilar."""
    assert "I" not in textfilter._TURKISH_STRONG_CHARS
    assert ord("I") == 0x49
    for ch in textfilter._TURKISH_STRONG_CHARS:
        assert ord(ch) != 0x49


# --------------------------------------------------- yabanci diller cevrilmeli
FOREIGN_EXAMPLES = [
    ("Über die Brücke", "de"),
    ("Größe", "de"),
    ("Ça va, garçon", "fr"),
    ("Abre la puerta de la casa", "es"),
    ("O jogo começa", "pt"),
]


def test_foreign_language_examples_should_translate_with_specific_source_lang():
    for text, lang in FOREIGN_EXAMPLES:
        assert textfilter.should_translate(text, confidence=0.9, source_lang=lang), (
            f"{text!r} ({lang}) yanlislikla Turkce sayilip atlandi"
        )


def test_foreign_language_examples_should_translate_with_auto_source_lang():
    """Kaynak dil 'auto' iken de (dil bilinmiyor varsayimi) ayni ornekler
    Turkce sanilip atlanmamali."""
    for text, lang in FOREIGN_EXAMPLES:
        assert textfilter.should_translate(text, confidence=0.9, source_lang="auto"), (
            f"{text!r} ({lang}, auto) yanlislikla Turkce sayilip atlandi"
        )


def test_accented_chars_alone_are_not_enough():
    """ç/ö/ü tek basina Turkce isareti SAYILMAMALI (Almanca/Fransizca/
    Portekizce de kullanir)."""
    assert not textfilter.is_probably_turkish("Größe")
    assert not textfilter.is_probably_turkish("garçon")
    assert not textfilter.is_probably_turkish("Brücke")


# ------------------------------------------------------- gercek turkce atlanmali
TURKISH_EXAMPLES = [
    "Kapıyı açmak için E'ye bas",
    "Envanter dolu",
]


def test_real_turkish_sentences_are_skipped():
    for text in TURKISH_EXAMPLES:
        assert not textfilter.should_translate(text, confidence=0.9, source_lang="auto"), (
            f"{text!r} gercekten Turkce oldugu halde cevrilmek uzere isaretlendi"
        )


def test_turkish_specific_letters_are_strong_signal():
    """ğ/ı/ş iceren kisa bir ifade tek basina yeterli olmali."""
    assert textfilter.is_probably_turkish("Kapıyı aç")  # ı
    assert textfilter.is_probably_turkish("Üşüdüm")  # ş + ü (strong + weak)
    assert textfilter.is_probably_turkish("Değiştir")  # ğ


def test_source_lang_specific_is_more_cautious():
    """source_lang belirli bir yabanci dil oldugunda, zayif isaretler
    (kelime listesi, langdetect) devre disi kalmali; sadece guclu Turkce
    harfleri karar verdirmeli."""
    # Guclu harf yoksa, source_lang='de' iken kelime-listesi tetiklenmemeli.
    assert not textfilter.is_probably_turkish("Envanter dolu", source_lang="de")
    # Guclu harf varsa (ı), source_lang ne olursa olsun yine de Turkce sayilir
    # (gercekten Turkce metin baska dildeki bir oyunda da cikabilir, orn. menude).
    assert textfilter.is_probably_turkish("Kapıyı aç", source_lang="de")


def test_short_ambiguous_strings_default_to_translate():
    """Cok kisa, belirsiz metinlerde (langdetect devreye girmeden) varsayilan
    'Turkce degil' (yani cevrilsin) olmali - cevrilmemesi daha riskli olurdu."""
    assert not textfilter.is_probably_turkish("Größe")
    assert not textfilter.is_probably_turkish("OK")


def test_should_translate_still_respects_other_filters():
    # Cok kisa
    assert not textfilter.should_translate("A", confidence=0.9)
    # Sadece sayi/sembol
    assert not textfilter.should_translate("99%", confidence=0.9)
    # Dusuk guven
    assert not textfilter.should_translate("Hello world", confidence=0.1)
    # Normal Ingilizce -> cevrilmeli
    assert textfilter.should_translate("Hello world", confidence=0.9)


# ------------------------------------------------------- 150+ satirlik korpus
def test_filter_corpus_has_at_least_150_lines():
    rows = _load_corpus()
    assert len(rows) >= 150


def test_filter_corpus_covers_turkish_and_multiple_foreign_languages():
    rows = _load_corpus()
    langs = {r["lang"] for r in rows}
    assert "tr" in langs
    foreign_langs = langs - {"tr"}
    assert len(foreign_langs) >= 5, (
        "Korpus en az 5 farkli yabanci dil icermeli (EN/DE/FR/ES/PT/IT/RU)"
    )


def test_filter_catches_at_least_98_percent_of_foreign_lines():
    """Korpustaki yabanci dil (EN/DE/FR/ES/PT/IT/RU) satirlarinin en az
    %98'i, "auto" kaynak dille (gercek kullanimdaki en zorlu/belirsiz
    durum) dogru sekilde CEVRILMEYE DEGER bulunmali."""
    rows = [r for r in _load_corpus() if r["lang"] != "tr"]
    assert rows, "Korpusta yabanci dil satiri yok"
    failed = [
        r["text"] for r in rows
        if not textfilter.should_translate(r["text"], confidence=0.9, source_lang="auto")
    ]
    success_ratio = (len(rows) - len(failed)) / len(rows)
    assert success_ratio >= 0.98, (
        f"Yabanci dil basari orani %{success_ratio * 100:.1f} "
        f"(en az %98 gerekli). Atlanan satirlar: {failed}"
    )


def test_filter_skips_at_least_90_percent_of_turkish_lines():
    """Korpustaki gercek Turkce satirlarin en az %90'i "zaten Turkce"
    sayilip cevrilmeden atlanmali."""
    rows = [r for r in _load_corpus() if r["lang"] == "tr"]
    assert rows, "Korpusta Turkce satir yok"
    wrongly_translated = [
        r["text"] for r in rows
        if textfilter.should_translate(r["text"], confidence=0.9, source_lang="auto")
    ]
    skip_ratio = (len(rows) - len(wrongly_translated)) / len(rows)
    assert skip_ratio >= 0.90, (
        f"Turkce atlama orani %{skip_ratio * 100:.1f} (en az %90 gerekli). "
        f"Yanlislikla cevrilmek istenen satirlar: {wrongly_translated}"
    )
