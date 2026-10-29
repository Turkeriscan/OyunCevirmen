"""
app/core/glossary.py testleri: oyun sozlugunun yuklenmesi/kaydedilmesi,
Ollama sistem talimati blogu, Google icin terim koruma/geri koyma.

Gercek dosya sistemine (tmp_path ile izole edilmis) ihtiyac duyar,
ekran/Ollama/Google gerekmez.
"""
import json

import pytest

from app.core import glossary as glossary_mod


@pytest.fixture
def isolated_glossary(tmp_path, monkeypatch):
    path = tmp_path / "glossary.json"
    monkeypatch.setattr(glossary_mod, "GLOSSARY_PATH", str(path))
    monkeypatch.setattr(glossary_mod, "_cached", None)
    yield path
    monkeypatch.setattr(glossary_mod, "_cached", None)


# --------------------------------------------------------------- yukleme/kaydetme
def test_missing_file_returns_empty_list(isolated_glossary):
    assert glossary_mod.load_glossary() == []


def test_save_then_load_roundtrip(isolated_glossary):
    entries = [{"source": "Ldhen", "target": "Ldhen", "no_translate": False}]
    glossary_mod.save_glossary(entries)
    glossary_mod.reset_cache()
    assert glossary_mod.load_glossary() == entries


def test_corrupted_json_falls_back_to_empty(isolated_glossary):
    isolated_glossary.write_text("{bozuk json", encoding="utf-8")
    assert glossary_mod.load_glossary() == []


def test_non_list_json_falls_back_to_empty(isolated_glossary):
    isolated_glossary.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert glossary_mod.load_glossary() == []


def test_entries_missing_source_are_dropped(isolated_glossary):
    glossary_mod.save_glossary([{"source": "", "target": "x"}, {"source": "Ldhen", "target": "Ldhen"}])
    result = glossary_mod.load_glossary()
    assert len(result) == 1
    assert result[0]["source"] == "Ldhen"


def test_no_translate_entry_ignores_target(isolated_glossary):
    entries = glossary_mod.save_glossary([{"source": "Ldhen", "target": "gormezden", "no_translate": True}])
    assert entries[0]["target"] == ""
    assert entries[0]["no_translate"] is True


def test_non_dict_items_are_skipped(isolated_glossary):
    isolated_glossary.write_text(json.dumps(["sadece bir metin", 42, None]), encoding="utf-8")
    assert glossary_mod.load_glossary() == []


# ------------------------------------------------------- Ollama sistem blogu
def test_ollama_block_empty_for_no_entries():
    assert glossary_mod.build_ollama_system_block([]) == ""


def test_ollama_block_includes_translation_pairs():
    entries = [{"source": "Ldhen", "target": "Ldhen", "no_translate": False}]
    block = glossary_mod.build_ollama_system_block(entries)
    assert "Ldhen" in block
    assert "GLOSSARY" in block


def test_ollama_block_marks_no_translate_entries():
    entries = [{"source": "Ldhen", "target": "", "no_translate": True}]
    block = glossary_mod.build_ollama_system_block(entries)
    assert "do NOT translate" in block
    assert "Ldhen" in block


# ------------------------------------------------- Google icin koruma/geri koyma
def test_protect_terms_replaces_source_with_placeholder():
    entries = [{"source": "Ldhen", "target": "Ldhen Hazretleri", "no_translate": False}]
    protected, matches = glossary_mod.protect_terms("Badu'dan Ldhen'e selam", entries)
    assert "Ldhen" not in protected
    assert "@@G0@@" in protected
    assert len(matches) == 1


def test_restore_terms_puts_back_target_translation():
    entries = [{"source": "Ldhen", "target": "Ldhen Hazretleri", "no_translate": False}]
    protected, matches = glossary_mod.protect_terms("Hello Ldhen", entries)
    # Google bu metni "cevirip" placeholder'i degistirmeden donduğunu simule et
    restored = glossary_mod.restore_terms(protected, matches)
    assert restored == "Hello Ldhen Hazretleri"


def test_restore_terms_keeps_source_for_no_translate_entries():
    entries = [{"source": "Ldhen", "target": "", "no_translate": True}]
    protected, matches = glossary_mod.protect_terms("Hello Ldhen", entries)
    restored = glossary_mod.restore_terms(protected, matches)
    assert restored == "Hello Ldhen"


def test_protect_terms_is_case_insensitive():
    entries = [{"source": "Ldhen", "target": "Ldhen Hazretleri", "no_translate": False}]
    protected, matches = glossary_mod.protect_terms("hello ldhen", entries)
    assert "@@G0@@" in protected
    assert len(matches) == 1


def test_protect_terms_handles_overlapping_longer_term_first():
    """Kisa bir terim ("Ldhen"), daha UZUN baska bir terimin ("Badu'dan
    Ldhen'e") parcasi olabilir; once uzun terim eslesmeli ki kisa terim
    onu bozmasin."""
    entries = [
        {"source": "Ldhen", "target": "Ldhen Hazretleri", "no_translate": False},
        {"source": "Badu'dan Ldhen'e", "target": "Badu'dan Ldhen'e selamlar", "no_translate": False},
    ]
    protected, matches = glossary_mod.protect_terms("Badu'dan Ldhen'e selam", entries)
    restored = glossary_mod.restore_terms(protected, matches)
    assert restored == "Badu'dan Ldhen'e selamlar selam"


def test_protect_terms_empty_entries_returns_text_unchanged():
    protected, matches = glossary_mod.protect_terms("Hello World", [])
    assert protected == "Hello World"
    assert matches == []


def test_protect_terms_no_match_returns_empty_matches():
    entries = [{"source": "Ldhen", "target": "x", "no_translate": False}]
    protected, matches = glossary_mod.protect_terms("Hello World", entries)
    assert protected == "Hello World"
    assert matches == []


def test_restore_terms_handles_empty_matches():
    assert glossary_mod.restore_terms("Hello World", []) == "Hello World"


def test_restore_falls_back_to_source_when_target_is_empty():
    """no_translate=False ama target bos birakilmis (kullanici henuz
    doldurmamis) - kaynak terime geri donmeli, bos string'e DEGIL."""
    entries = [{"source": "Ldhen", "target": "", "no_translate": False}]
    protected, matches = glossary_mod.protect_terms("Hello Ldhen", entries)
    restored = glossary_mod.restore_terms(protected, matches)
    assert restored == "Hello Ldhen"


# ---------------------------------------- TranslationManager entegrasyonu
def test_ollama_translate_receives_glossary_block(isolated_glossary):
    """TranslationManager, Ollama'yi cagirirken sozluk blogunu sistem
    talimatina eklemeli."""
    from unittest.mock import patch
    from app.core import translate

    glossary_mod.save_glossary([{"source": "Ldhen", "target": "Ldhen Hazretleri", "no_translate": False}])

    config = {
        "translate_engine": "ollama", "ollama_host": "http://127.0.0.1:11434",
        "ollama_model": "m", "source_lang": "auto", "target_lang": "tr",
        "max_cache_memory_items": 100,
    }
    manager = translate.TranslationManager(config)
    from app.core import cache as cache_mod
    import tempfile, os
    manager.cache = cache_mod.TranslationCache(
        max_memory_items=100, db_path=os.path.join(tempfile.mkdtemp(), "t.sqlite3")
    )

    captured = {}

    def fake_translate(self, text, source_lang="auto", target_lang="tr", model=None,
                        context_lines=None, glossary_block=""):
        captured["glossary_block"] = glossary_block
        return "ok"

    with patch.object(translate.OllamaTranslator, "translate", fake_translate):
        manager.translate("Hello Ldhen")

    assert "Ldhen Hazretleri" in captured["glossary_block"]


def test_google_translate_protects_and_restores_glossary_terms(isolated_glossary):
    """TranslationManager, Google'a gonderirken terimi yer tutucuyla
    korumali ve sonucu sozluk terimiyle geri koymali."""
    from unittest.mock import patch
    from app.core import translate

    glossary_mod.save_glossary([{"source": "Ldhen", "target": "Ldhen Hazretleri", "no_translate": False}])

    config = {
        "translate_engine": "google", "source_lang": "auto", "target_lang": "tr",
        "max_cache_memory_items": 100,
    }
    manager = translate.TranslationManager(config)
    from app.core import cache as cache_mod
    import tempfile, os
    manager.cache = cache_mod.TranslationCache(
        max_memory_items=100, db_path=os.path.join(tempfile.mkdtemp(), "t2.sqlite3")
    )

    captured = {}

    def fake_google(self, text, source_lang="auto", target_lang="tr"):
        captured["sent_to_google"] = text
        # Gercekci simulasyon: Google "Hello"yu cevirir, "@@G0@@" gibi bir
        # yer tutucuyu (alfasayisal + @ iceren, cevrilecek bir kelimeye
        # benzemeyen bir dize oldugu icin) OLDUGU GIBI birakir.
        return text.replace("Hello", "Merhaba")

    with patch.object(translate.GoogleFallbackTranslator, "translate", fake_google):
        result = manager.translate("Hello Ldhen")

    assert "@@G0@@" in captured["sent_to_google"]
    assert "Ldhen" not in captured["sent_to_google"]
    assert result == "Merhaba Ldhen Hazretleri"
