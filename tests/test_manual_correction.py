"""
Orchestrator.correct_translation()/undo_correction()/is_manually_corrected()
testleri (main.py, 2.1): Sahne sayfasindaki akistan "Çeviriyi düzelt" ile
girilen elle duzeltmelerin onbellege kalici yazilip, oyunda hemen
kullanilabildigini ve geri alinabildigini dogrular.

Gercek ekran/OCR/Ollama gerektirmez; gercek TranslationCache (gecici
SQLite dosyasiyla) kullanilir, sadece Orchestrator'in agir __init__'i
calistirilmaz.
"""
import collections
import threading

from app import main as main_mod
from app.core import cache as cache_mod


class _FakeOrchestrator:
    correct_translation = main_mod.Orchestrator.correct_translation
    undo_correction = main_mod.Orchestrator.undo_correction
    is_manually_corrected = main_mod.Orchestrator.is_manually_corrected
    _cache_identity = main_mod.Orchestrator._cache_identity
    _remember = main_mod.Orchestrator._remember

    def __init__(self, tmp_path):
        self.config = {"source_lang": "auto", "target_lang": "tr", "translate_engine": "ollama"}
        self.recent = collections.deque(maxlen=40)
        self.recent_version = 0
        self.translator = type("T", (), {})()
        self.translator.cache = cache_mod.TranslationCache(
            max_memory_items=100, db_path=str(tmp_path / "manual.sqlite3")
        )


def test_correct_translation_writes_to_cache(tmp_path):
    fake = _FakeOrchestrator(tmp_path)
    ok = fake.correct_translation("Hello", "Merhaba (elle)")
    assert ok is True
    assert fake.translator.cache.get("Hello", "auto", "tr", "ollama") == "Merhaba (elle)"


def test_correct_translation_updates_transcript_immediately(tmp_path):
    fake = _FakeOrchestrator(tmp_path)
    fake.correct_translation("Hello", "Merhaba (elle)")
    assert len(fake.recent) == 1
    assert fake.recent[0][1] == "Hello"
    assert fake.recent[0][2] == "Merhaba (elle)"


def test_correct_translation_rejects_empty_text(tmp_path):
    fake = _FakeOrchestrator(tmp_path)
    ok = fake.correct_translation("Hello", "   ")
    assert ok is False
    assert fake.translator.cache.get("Hello", "auto", "tr", "ollama") is None


def test_correction_survives_engine_rewrite_attempt(tmp_path):
    """Duzeltmeden sonra normal bir motor yazisi gelirse (orn. canli mod
    ayni satiri yeniden cevirip onbellege yazmaya calisirsa), duzeltme
    EZILMEMELI."""
    fake = _FakeOrchestrator(tmp_path)
    fake.correct_translation("Hello", "Merhaba (elle)")
    fake.translator.cache.set("Hello", "auto", "tr", "ollama", "Motorun cevirisi")
    assert fake.translator.cache.get("Hello", "auto", "tr", "ollama") == "Merhaba (elle)"


def test_is_manually_corrected_reflects_state(tmp_path):
    fake = _FakeOrchestrator(tmp_path)
    assert fake.is_manually_corrected("Hello") is False
    fake.correct_translation("Hello", "Merhaba (elle)")
    assert fake.is_manually_corrected("Hello") is True


def test_undo_correction_allows_engine_to_rewrite_again(tmp_path):
    fake = _FakeOrchestrator(tmp_path)
    fake.correct_translation("Hello", "Merhaba (elle)")
    fake.undo_correction("Hello")

    assert fake.is_manually_corrected("Hello") is False
    assert fake.translator.cache.get("Hello", "auto", "tr", "ollama") == "Merhaba (elle)"  # metin kaldi

    fake.translator.cache.set("Hello", "auto", "tr", "ollama", "Yeni motor cevirisi")
    assert fake.translator.cache.get("Hello", "auto", "tr", "ollama") == "Yeni motor cevirisi"


def test_cache_identity_uses_current_config():
    fake = _FakeOrchestrator.__new__(_FakeOrchestrator)
    fake.config = {"source_lang": "de", "target_lang": "tr", "translate_engine": "google"}
    assert fake._cache_identity() == ("de", "tr", "google")
