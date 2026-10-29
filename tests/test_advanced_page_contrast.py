"""
Gelismis sayfasi "Kontrasti güçlendir" secenegi testleri (3.3): config'teki
ocr_contrast_enhance ayarinin arayuze yuklenip kaydedildigini dogrular.

Gercek ekran/monitor listesi gerektirmez (capture_mod.list_monitors mock'lanir).
"""
from unittest.mock import MagicMock, patch

from app.core import capture as capture_mod
from app.ui.pages.advanced import AdvancedPage


class _FakeCtx(MagicMock):
    def is_loading(self):
        return False


def _make_page(qapp):
    with patch.object(capture_mod, "list_monitors", return_value=[{"label": "Ekran 1", "index": 0}]):
        return AdvancedPage(_FakeCtx())


def test_combo_contrast_defaults_to_closed(qapp):
    page = _make_page(qapp)
    cfg = {"ocr_contrast_enhance": False}
    with patch.object(capture_mod, "list_monitors", return_value=[{"label": "Ekran 1", "index": 0}]):
        page.load(cfg)
    assert page.combo_contrast.currentData() is False


def test_combo_contrast_loads_enabled_value(qapp):
    page = _make_page(qapp)
    cfg = {"ocr_contrast_enhance": True}
    with patch.object(capture_mod, "list_monitors", return_value=[{"label": "Ekran 1", "index": 0}]):
        page.load(cfg)
    assert page.combo_contrast.currentData() is True


def test_combo_contrast_save_writes_config(qapp):
    page = _make_page(qapp)
    cfg = {"ocr_contrast_enhance": False}
    with patch.object(capture_mod, "list_monitors", return_value=[{"label": "Ekran 1", "index": 0}]):
        page.load(cfg)
    i = page.combo_contrast.findData(True)
    page.combo_contrast.setCurrentIndex(i)

    out_cfg = {}
    page.save(out_cfg)
    assert out_cfg["ocr_contrast_enhance"] is True
