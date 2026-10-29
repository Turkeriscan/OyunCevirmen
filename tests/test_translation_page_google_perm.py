"""
TranslationPage'teki "Ollama çalışmazsa Google'a gönder" ayarinin UC
DURUMLU oldugunu dogrular: Sorulmadi (None) | Acik (True) | Kapali
(False). Eskiden None durumu gorsel olarak "Kapali" ile ayni gosterilip
kullaniciyi "zaten kapatmisim" sanabilirdi.

Gercek ekran gerekmez (qapp fixture 'offscreen' platformda calisir).
"""
from unittest.mock import MagicMock

from app.ui.pages.translation import TranslationPage


class _FakeCtx:
    def __init__(self, allow_google_fallback=None):
        self.config = {
            "ocr_engine": "windows", "translate_engine": "ollama",
            "ollama_model": "aya-expanse:8b", "ollama_host": "http://127.0.0.1:11434",
            "source_lang": "auto", "allow_google_fallback": allow_google_fallback,
        }
        self._loading = 0
        self.orchestrator = MagicMock()
        self.flash_messages = []

    def is_loading(self):
        return self._loading > 0

    def schedule_save(self, *_):
        pass

    def flash(self, text):
        self.flash_messages.append(text)


def test_load_shows_unset_state_distinctly(qapp):
    ctx = _FakeCtx(allow_google_fallback=None)
    page = TranslationPage(ctx)
    page.load(ctx.config)
    assert page.combo_google_perm.currentData() is None
    assert "sorulmadı" in page.combo_google_perm.currentText().lower()


def test_load_shows_granted_state(qapp):
    ctx = _FakeCtx(allow_google_fallback=True)
    page = TranslationPage(ctx)
    page.load(ctx.config)
    assert page.combo_google_perm.currentData() is True


def test_load_shows_denied_state(qapp):
    ctx = _FakeCtx(allow_google_fallback=False)
    page = TranslationPage(ctx)
    page.load(ctx.config)
    assert page.combo_google_perm.currentData() is False


def test_selecting_granted_writes_true_and_flashes(qapp):
    ctx = _FakeCtx(allow_google_fallback=None)
    page = TranslationPage(ctx)
    page.load(ctx.config)

    i = page.combo_google_perm.findData(True)
    page.combo_google_perm.setCurrentIndex(i)

    assert ctx.config["allow_google_fallback"] is True
    assert any("açıldı" in m for m in ctx.flash_messages)


def test_selecting_denied_writes_false_and_flashes(qapp):
    ctx = _FakeCtx(allow_google_fallback=None)
    page = TranslationPage(ctx)
    page.load(ctx.config)

    i = page.combo_google_perm.findData(False)
    page.combo_google_perm.setCurrentIndex(i)

    assert ctx.config["allow_google_fallback"] is False
    assert any("kapatıldı" in m for m in ctx.flash_messages)


def test_selecting_unset_resets_prompt_flag(qapp):
    """Kullanici bilerek 'Sorulmadi' durumuna geri donerse, Orchestrator'a
    izin sorusunun bu oturumda TEKRAR sorulabilmesi icin sinyal
    verilmeli (reset_google_permission_prompt)."""
    ctx = _FakeCtx(allow_google_fallback=True)
    page = TranslationPage(ctx)
    page.load(ctx.config)

    i = page.combo_google_perm.findData(None)
    page.combo_google_perm.setCurrentIndex(i)

    assert ctx.config["allow_google_fallback"] is None
    ctx.orchestrator.reset_google_permission_prompt.assert_called_once()
    assert any("sıfırlandı" in m for m in ctx.flash_messages)


def test_changing_perm_during_load_is_ignored(qapp):
    """Sayfa load() ile doldurulurken (program ayarlari ekrana yazarken)
    combo'nun degismesi KULLANICI SECIMI SAYILMAMALI - config'e yazmamali."""
    ctx = _FakeCtx(allow_google_fallback=None)
    page = TranslationPage(ctx)
    ctx._loading = 1  # "yukleniyor" durumunu simule et
    page.load(ctx.config)

    i = page.combo_google_perm.findData(True)
    page.combo_google_perm.setCurrentIndex(i)

    assert ctx.config["allow_google_fallback"] is None  # degismedi


def test_deepl_key_loads_and_saves(qapp):
    ctx = _FakeCtx(allow_google_fallback=None)
    ctx.config["deepl_api_key"] = "my-secret-key"
    page = TranslationPage(ctx)
    page.load(ctx.config)
    assert page.edit_deepl_key.text() == "my-secret-key"

    page.edit_deepl_key.setText("new-key")
    cfg = dict(ctx.config)
    page.save(cfg)
    assert cfg["deepl_api_key"] == "new-key"


def test_translate_engine_combo_includes_argos_and_deepl(qapp):
    ctx = _FakeCtx()
    page = TranslationPage(ctx)
    values = [page.combo_translate.itemData(i) for i in range(page.combo_translate.count())]
    assert "argos" in values
    assert "deepl" in values
