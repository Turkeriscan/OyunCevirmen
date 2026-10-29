"""
Gelismis sayfasi "Okuma bölgeleri" bolumu testleri (3.5): "Bölge çiz"
butonunun orchestrator'u cagirmasi, "Bölgeleri temizle" butonunun
config'i bosaltmasi, ve etiketin bolge sayisini dogru gostermesi.

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
    # Gercek MainWindow'da ctx.config, load()'a verilen cfg ile AYNI nesnedir
    # (bkz. app/ui/mainwindow.py: page.load(self.config)) - test de bunu yansitir.
    page.ctx.config = cfg
    with patch.object(capture_mod, "list_monitors", return_value=[{"label": "Ekran 1", "index": 0}]):
        page.load(cfg)


def test_draw_button_calls_orchestrator_open_selector(qapp):
    page = _make_page()
    page.btn_draw_regions.click()
    page.ctx.orchestrator.request_open_region_selector.assert_called_once()


def test_label_shows_no_regions_when_empty(qapp):
    page = _make_page()
    _load(page, {"exclude_regions": [], "include_regions": []})
    assert page.lbl_regions.text() == "Bölge yok"


def test_label_shows_counts_when_regions_present(qapp):
    page = _make_page()
    cfg = {
        "exclude_regions": [{"left": 0, "top": 0, "width": 10, "height": 10}],
        "include_regions": [{"left": 0, "top": 0, "width": 10, "height": 10},
                             {"left": 20, "top": 20, "width": 10, "height": 10}],
    }
    _load(page, cfg)
    assert page.lbl_regions.text() == "1 dışında, 2 sadece-oku"


def test_clear_button_empties_config_and_flashes(qapp):
    page = _make_page()
    page.ctx.config = {
        "exclude_regions": [{"left": 0, "top": 0, "width": 10, "height": 10}],
        "include_regions": [{"left": 0, "top": 0, "width": 10, "height": 10}],
    }
    page.btn_clear_regions.click()

    assert page.ctx.config["exclude_regions"] == []
    assert page.ctx.config["include_regions"] == []
    page.ctx.schedule_save.assert_called_once()
    page.ctx.flash.assert_called_once()
    assert page.lbl_regions.text() == "Bölge yok"
