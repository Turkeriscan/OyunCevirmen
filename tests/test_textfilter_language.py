"""
Dil tespiti testleri: Turkce olmayan (Almanca/Fransizca/Ispanyolca/
Portekizce) metinlerin yanlislikla "zaten Turkce" sanilip atlanmadigini,
gercek Turkce cumlelerin dogru tanindigini dogrular.

Gercek ekran/OCR/ag gerektirmez; sadece metin uzerinde calisan saf
fonksiyonlar test edilir.
"""
from app.core import textfilter


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
