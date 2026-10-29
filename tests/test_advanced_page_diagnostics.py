"""
Gelismis sayfasi "Sorun bildirimi için paket oluştur" testleri (4.5):
arka plan is parcacigi + Qt sinyali kullanildigi icin sonuclar kisa bir
sure (_wait_until) beklenerek kontrol edilir (bkz. test_model_download.py'deki
ayni desen).

Gercek dosya sistemi/ekran goruntusu gerektirmez.
"""
import time
from unittest.mock import MagicMock, patch

from PyQt6 import QtCore

from app.core import capture as capture_mod
from app.core import diagnostics as diagnostics_mod
from app.ui.pages.advanced import AdvancedPage


class _FakeCtx(MagicMock):
    def is_loading(self):
        return False


def _make_page():
    with patch.object(capture_mod, "list_monitors", return_value=[{"label": "Ekran 1", "index": 0}]):
        return AdvancedPage(_FakeCtx())


def _wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        QtCore.QCoreApplication.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_build_diagnostics_success_flashes_filename(qapp):
    page = _make_page()
    page.ctx.config = {"deepl_api_key": "", "ocr_engine": "windows"}

    with patch.object(diagnostics_mod, "default_output_path", return_value=r"C:\Desktop\out.zip"), \
         patch.object(diagnostics_mod, "build_diagnostics_zip", return_value=r"C:\Desktop\out.zip"):
        page.btn_diagnostics.click()
        assert _wait_until(lambda: page.btn_diagnostics.isEnabled())

    assert any("out.zip" in m for m in [c.args[0] for c in page.ctx.flash.call_args_list])


def test_build_diagnostics_disables_button_while_running(qapp):
    page = _make_page()
    page.ctx.config = {}
    release = __import__("threading").Event()

    def slow_build(*a, **k):
        release.wait(timeout=2.0)
        return "out.zip"

    with patch.object(diagnostics_mod, "build_diagnostics_zip", side_effect=slow_build):
        page.btn_diagnostics.click()
        assert page.btn_diagnostics.isEnabled() is False
    release.set()
    assert _wait_until(lambda: page.btn_diagnostics.isEnabled())


def test_build_diagnostics_failure_flashes_error(qapp):
    page = _make_page()
    page.ctx.config = {}

    with patch.object(diagnostics_mod, "build_diagnostics_zip", side_effect=RuntimeError("patlat")):
        page.btn_diagnostics.click()
        assert _wait_until(lambda: page.btn_diagnostics.isEnabled())

    assert any("oluşturulamadı" in m for m in [c.args[0] for c in page.ctx.flash.call_args_list])


def test_build_diagnostics_captures_screenshot_only_when_combo_enabled(qapp):
    page = _make_page()
    page.ctx.config = {}
    i = page.combo_diag_screenshot.findData(True)
    page.combo_diag_screenshot.setCurrentIndex(i)

    with patch.object(diagnostics_mod, "capture_screenshot_png_bytes", return_value=b"PNG") as cap, \
         patch.object(diagnostics_mod, "build_diagnostics_zip", return_value="out.zip"):
        page.btn_diagnostics.click()
        assert _wait_until(lambda: page.btn_diagnostics.isEnabled())

    cap.assert_called_once()


def test_build_diagnostics_skips_screenshot_by_default(qapp):
    page = _make_page()
    page.ctx.config = {}
    assert page.combo_diag_screenshot.currentData() is False

    with patch.object(diagnostics_mod, "capture_screenshot_png_bytes") as cap, \
         patch.object(diagnostics_mod, "build_diagnostics_zip", return_value="out.zip"):
        page.btn_diagnostics.click()
        assert _wait_until(lambda: page.btn_diagnostics.isEnabled())

    cap.assert_not_called()
