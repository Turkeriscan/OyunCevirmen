"""
Gelismis sayfasi "Kaynak tasarrufu" bolumu testleri (3.4): config'teki
live_auto_pause_enabled / live_cutscene_skip_enabled ayarlarinin arayuze
yuklenip kaydedildigini dogrular.

Gercek ekran/monitor listesi gerektirmez (capture_mod.list_monitors mock'lanir).
"""
from unittest.mock import MagicMock, patch

from app.core import capture as capture_mod
from app.ui.pages.advanced import AdvancedPage


class _FakeCtx(MagicMock):
    def is_loading(self):
        return False


def _make_page():
    with patch.object(capture_mod, "list_monitors", return_value=[{"label": "Ekran 1", "index": 0}]):
        return AdvancedPage(_FakeCtx())


def _load(page, cfg):
    with patch.object(capture_mod, "list_monitors", return_value=[{"label": "Ekran 1", "index": 0}]):
        page.load(cfg)


def test_combo_auto_pause_loads_true(qapp):
    page = _make_page()
    _load(page, {"live_auto_pause_enabled": True})
    assert page.combo_auto_pause.currentData() is True


def test_combo_auto_pause_loads_false(qapp):
    page = _make_page()
    _load(page, {"live_auto_pause_enabled": False})
    assert page.combo_auto_pause.currentData() is False


def test_combo_auto_pause_save_writes_config(qapp):
    page = _make_page()
    _load(page, {"live_auto_pause_enabled": True})
    i = page.combo_auto_pause.findData(False)
    page.combo_auto_pause.setCurrentIndex(i)

    out_cfg = {}
    page.save(out_cfg)
    assert out_cfg["live_auto_pause_enabled"] is False


def test_combo_cutscene_skip_loads_true(qapp):
    page = _make_page()
    _load(page, {"live_cutscene_skip_enabled": True})
    assert page.combo_cutscene_skip.currentData() is True


def test_combo_cutscene_skip_save_writes_config(qapp):
    page = _make_page()
    _load(page, {"live_cutscene_skip_enabled": True})
    i = page.combo_cutscene_skip.findData(False)
    page.combo_cutscene_skip.setCurrentIndex(i)

    out_cfg = {}
    page.save(out_cfg)
    assert out_cfg["live_cutscene_skip_enabled"] is False
