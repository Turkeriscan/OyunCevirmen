"""
Google Translate izin akisi testleri:
  - izin "sorulmadi" (None) veya "verilmedi" (False) iken Google'a GIDILMEZ
  - izin "verildi" (True) iken eskisi gibi calisir
  - kullanici motor olarak BILEREK "google" sectiyse izin sorulmaz/uygulanmaz
  - izin "sorulmadi" durumunda, bir kez callback tetiklenir (bildirim/soru icin)

Gercek Ollama/Google/internet gerektirmez; HTTP cagrilari mock'lanir.
"""
from unittest.mock import MagicMock, patch

from app.core import translate


def _make_manager(allow_google_fallback, translate_engine="ollama"):
    config = {
        "translate_engine": translate_engine,
        "ollama_host": "http://127.0.0.1:11434",
        "ollama_model": "test-model",
        "source_lang": "auto",
        "target_lang": "tr",
        "max_cache_memory_items": 100,
        "allow_google_fallback": allow_google_fallback,
    }
    manager = translate.TranslationManager(config)
    # Testler arasi gercek SQLite/bellek onbellegini paylasmamak icin
    # her defasinda temiz bir onbellek enjekte ediyoruz.
    from app.core import cache as cache_mod
    import tempfile, os
    tmp = os.path.join(tempfile.mkdtemp(), "t.sqlite3")
    manager.cache = cache_mod.TranslationCache(max_memory_items=100, db_path=tmp)
    return manager


def _ollama_fails(*a, **k):
    return None


def _ollama_hallucinates(*a, **k):
    return "Bu çok uzun ve alakasız, kaynaktan kat kat büyük bir açıklama metni " * 5


# -------------------------------------------------------- izin yok / sorulmadi
def test_no_google_call_when_permission_not_asked():
    manager = _make_manager(allow_google_fallback=None)
    with patch.object(translate.OllamaTranslator, "translate", side_effect=_ollama_fails), \
         patch.object(translate.GoogleFallbackTranslator, "translate") as google_translate:
        result = manager.translate("Hello")
    assert result is None
    google_translate.assert_not_called()


def test_no_google_call_when_permission_denied():
    manager = _make_manager(allow_google_fallback=False)
    with patch.object(translate.OllamaTranslator, "translate", side_effect=_ollama_fails), \
         patch.object(translate.GoogleFallbackTranslator, "translate") as google_translate:
        result = manager.translate("Hello")
    assert result is None
    google_translate.assert_not_called()


def test_google_call_allowed_when_permission_granted():
    manager = _make_manager(allow_google_fallback=True)
    with patch.object(translate.OllamaTranslator, "translate", side_effect=_ollama_fails), \
         patch.object(translate.GoogleFallbackTranslator, "translate", return_value="Merhaba") as google_translate:
        result = manager.translate("Hello")
    assert result == "Merhaba"
    google_translate.assert_called_once()


def test_no_google_call_when_hallucination_and_no_permission():
    manager = _make_manager(allow_google_fallback=None)
    with patch.object(translate.OllamaTranslator, "translate", side_effect=_ollama_hallucinates), \
         patch.object(translate.GoogleFallbackTranslator, "translate") as google_translate:
        result = manager.translate("Hi")
    assert result is None
    google_translate.assert_not_called()


# ---------------------------------------------- bilerek Google secilmisse sorma
def test_permission_not_required_when_google_is_primary_engine():
    """Kullanici ceviri motoru olarak BILEREK 'google' sectiyse, izin
    None/False olsa bile Google dogrudan kullanilir (zaten acik riza var)."""
    manager = _make_manager(allow_google_fallback=None, translate_engine="google")
    with patch.object(translate.GoogleFallbackTranslator, "translate", return_value="Merhaba") as google_translate:
        result = manager.translate("Hello")
    assert result == "Merhaba"
    google_translate.assert_called_once()


# --------------------------------------------------------------- callback
def test_permission_needed_callback_fires_once_when_unset():
    manager = _make_manager(allow_google_fallback=None)
    callback = MagicMock()
    manager.on_google_permission_needed = callback
    with patch.object(translate.OllamaTranslator, "translate", side_effect=_ollama_fails):
        manager.translate("Hello")
        manager.translate("World")
    # Callback'in kac kez cagrilacagina TranslationManager karar vermez
    # (Orchestrator bir kez sinirlar), ama HER basarisiz denemede tetiklenir.
    assert callback.call_count == 2


def test_permission_needed_callback_not_fired_when_granted():
    manager = _make_manager(allow_google_fallback=True)
    callback = MagicMock()
    manager.on_google_permission_needed = callback
    with patch.object(translate.OllamaTranslator, "translate", side_effect=_ollama_fails), \
         patch.object(translate.GoogleFallbackTranslator, "translate", return_value="Merhaba"):
        manager.translate("Hello")
    callback.assert_not_called()


def test_permission_needed_callback_not_fired_when_denied():
    manager = _make_manager(allow_google_fallback=False)
    callback = MagicMock()
    manager.on_google_permission_needed = callback
    with patch.object(translate.OllamaTranslator, "translate", side_effect=_ollama_fails):
        manager.translate("Hello")
    callback.assert_not_called()


def test_callback_exception_does_not_break_translation():
    """Callback (orn. UI thread'e sinyal gonderme) patlarsa bile ceviri
    akisi cokmemeli."""
    manager = _make_manager(allow_google_fallback=None)
    manager.on_google_permission_needed = MagicMock(side_effect=RuntimeError("patlat"))
    with patch.object(translate.OllamaTranslator, "translate", side_effect=_ollama_fails):
        result = manager.translate("Hello")
    assert result is None  # cokmedi, sadece cevrilemedi
