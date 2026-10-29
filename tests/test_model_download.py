"""
TranslationPage model onerisi + indirme testleri (2.6): donanima gore
model onerisi gosterilmesi, "Modeli indir" ile ollama pull cikisinin
akis durumuna yansimasi. Gercek Ollama/ag gerekmez; subprocess.Popen
mock'lanir.

Arka plan is parcacigi + Qt sinyali kullanildigi icin sonuclar kisa bir
sure (_wait_until) beklenerek kontrol edilir.
"""
import time
from unittest.mock import MagicMock, patch

from PyQt6 import QtCore

from app.ui.pages.translation import TranslationPage


class _FakeCtx:
    def __init__(self):
        self.config = {
            "ocr_engine": "windows", "translate_engine": "ollama",
            "ollama_model": "aya-expanse:8b", "ollama_host": "http://127.0.0.1:11434",
            "source_lang": "auto", "allow_google_fallback": None,
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


def _wait_until(predicate, timeout=2.0):
    """Arka plan is parcacigindan gelen Qt sinyalleri, ana thread'in olay
    dongusu isletilmeden TESLIM EDILMEZ (QueuedConnection); bu yuzden
    beklerken processEvents() ile dongu kisaca isletilir."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        QtCore.QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_refresh_recommendation_shows_model_and_reason(qapp):
    page = TranslationPage(_FakeCtx())
    with patch("app.core.hardware.recommend_model_for_this_machine", return_value=("gemma2:2b", None)):
        page.refresh_model_recommendation()
        assert _wait_until(lambda: page._recommended_model == "gemma2:2b")
    assert "gemma2:2b" in page.lbl_model_recommend.text()


def test_download_success_updates_label_and_flashes(qapp):
    page = TranslationPage(_FakeCtx())
    page.combo_model.setCurrentText("gemma2:2b")

    fake_proc = MagicMock()
    fake_proc.stdout.read.side_effect = [b"pulling manifest\n", b"success\n", b""]
    fake_proc.wait.return_value = 0

    # Mock'un suresi, arka plan is parcacigi Popen'i GERCEKTEN cagirana
    # kadar AKTIF kalmali (download_recommended_model() sadece bir thread
    # baslatip hemen doner) - bu yuzden _wait_until de "with" icinde.
    # Basari sonrasi _on_download_done() KENDI de refresh_models() ile
    # ayri bir "ollama list" (check_output) cagirir; o da mock'lanir ki
    # ayni Popen mock'unu (bu kez uygunsuz sekilde) kullanmaya calismasin.
    with patch("app.ui.pages.translation.subprocess.Popen", return_value=fake_proc), \
         patch("app.ui.pages.translation.subprocess.check_output", return_value=b"NAME\ngemma2:2b\n"):
        page.download_recommended_model()
        assert _wait_until(lambda: page.btn_model_download.isEnabled())

    assert "indirildi" in page.lbl_model_recommend.text()
    assert any("indirildi" in m for m in page.ctx.flash_messages)


def test_download_failure_shows_error_and_reenables_button(qapp):
    page = TranslationPage(_FakeCtx())
    page.combo_model.setCurrentText("gemma2:2b")

    fake_proc = MagicMock()
    fake_proc.stdout.read.side_effect = [b""]
    fake_proc.wait.return_value = 1

    with patch("app.ui.pages.translation.subprocess.Popen", return_value=fake_proc):
        page.download_recommended_model()
        assert _wait_until(lambda: page.btn_model_download.isEnabled())

    assert "başarısız" in page.lbl_model_recommend.text()
    assert any("indirilemedi" in m for m in page.ctx.flash_messages)


def test_download_disables_button_immediately():
    pass  # ayri bir qapp widget testinde dogrulanir; asagidaki testte


def test_download_disables_button_while_running(qapp):
    page = TranslationPage(_FakeCtx())
    page.combo_model.setCurrentText("gemma2:2b")

    fake_proc = MagicMock()
    # okuma COK yavas olsun ki buton devre disi durumda yakalanabilsin
    release = __import__("threading").Event()

    def slow_read(n):
        release.wait(timeout=2.0)
        return b""

    fake_proc.stdout.read.side_effect = slow_read
    fake_proc.wait.return_value = 0

    with patch("app.ui.pages.translation.subprocess.Popen", return_value=fake_proc):
        page.download_recommended_model()
        assert page.btn_model_download.isEnabled() is False
    release.set()


def test_download_uses_combo_text_when_set(qapp):
    """Basari sonrasi _on_download_done() KENDI de refresh_models()
    uzerinden ayri bir Popen ("ollama list") cagirir; bu test SADECE
    "pull" cagrisinin dogru model adiyla yapildigini dogrular, listedeki
    TUM cagrilari toplayarak (tek bir paylasimli degiskene yazip
    birbirini ezmeleri yerine) yarisi onler."""
    page = TranslationPage(_FakeCtx())
    page.combo_model.setCurrentText("custom-model:latest")

    fake_proc = MagicMock()
    fake_proc.stdout.read.side_effect = [b""]
    fake_proc.wait.return_value = 0
    calls = []

    def fake_popen(args, **kwargs):
        calls.append(list(args))
        return fake_proc

    with patch("app.ui.pages.translation.subprocess.Popen", side_effect=fake_popen), \
         patch("app.ui.pages.translation.subprocess.check_output", return_value=b"NAME\n"):
        page.download_recommended_model()
        assert _wait_until(lambda: ["ollama", "pull", "custom-model:latest"] in calls)
