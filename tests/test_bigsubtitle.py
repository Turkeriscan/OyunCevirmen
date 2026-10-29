"""
Buyuk altyazi penceresi (4.3) testleri: konumlama (ikinci monitor
varsayilani, kaydedilmis konum), metin guncelleme, goster/gizle/kaydetme
dongusu.

Gercek ekran/Windows API gerektirmez (qapp fixture offscreen platformda
calisir; coklu ekran QtWidgets.QApplication.screens() ile simule edilir).
"""
from unittest.mock import MagicMock, patch

from app.ui.bigsubtitle import BigSubtitleController, BigSubtitlePanel


# ------------------------------------------------------------------- set_text
def test_set_text_updates_and_defaults_when_empty(qapp):
    panel = BigSubtitlePanel({})
    panel.set_text("Merhaba")
    assert panel._text == "Merhaba"
    panel.set_text("")
    assert "bekleniyor" in panel._text


# ----------------------------------------------------------------- place()
def test_place_uses_saved_position_when_valid(qapp):
    panel = BigSubtitlePanel({"big_subtitle_pos": [50, 60]})
    panel.place()
    assert (panel.x(), panel.y()) == (50, 60)


def test_place_falls_back_when_saved_position_outside_any_screen(qapp):
    panel = BigSubtitlePanel({"big_subtitle_pos": [999999, 999999]})
    panel.place()
    assert (panel.x(), panel.y()) != (999999, 999999)


def test_place_prefers_second_screen_when_available(qapp):
    panel = BigSubtitlePanel({})
    fake_primary = MagicMock()
    fake_secondary = MagicMock()
    fake_secondary.availableGeometry.return_value = __import__(
        "PyQt6.QtCore", fromlist=["QRect"]).QRect(1920, 0, 1920, 1080)

    with patch("app.ui.bigsubtitle.QtWidgets.QApplication.screens",
               return_value=[fake_primary, fake_secondary]):
        panel.place()

    fake_secondary.availableGeometry.assert_called()


def test_place_handles_no_screens_gracefully(qapp):
    panel = BigSubtitlePanel({})
    with patch("app.ui.bigsubtitle.QtWidgets.QApplication.screens", return_value=[]):
        panel.place()  # istisna firlatmamali


# -------------------------------------------------------- BigSubtitleController
class _FakeOrchestrator:
    def __init__(self):
        self.recent = []


def test_controller_show_hide_toggle_updates_config_and_visibility(qapp):
    config = {}
    o = _FakeOrchestrator()
    ctrl = BigSubtitleController(config, o)

    with patch("app.config.save_config"):
        ctrl.show()
    assert ctrl.is_visible() is True
    assert config["big_subtitle_enabled"] is True

    ctrl.hide()
    assert ctrl.is_visible() is False
    assert config["big_subtitle_enabled"] is False

    ctrl.toggle()
    assert ctrl.is_visible() is True
    ctrl.toggle()
    assert ctrl.is_visible() is False


def test_controller_sync_shows_latest_translation():
    config = {}
    o = _FakeOrchestrator()
    o.recent = [(0.0, "Hello", "Merhaba")]
    ctrl = BigSubtitleController(config, o)
    ctrl.panel = MagicMock()

    ctrl._sync()

    ctrl.panel.set_text.assert_called_once_with("Merhaba")


def test_controller_sync_does_nothing_without_panel():
    ctrl = BigSubtitleController({}, _FakeOrchestrator())
    ctrl._sync()  # istisna firlatmamali (panel yok)


def test_controller_moved_persists_position():
    config = {}
    ctrl = BigSubtitleController(config, _FakeOrchestrator())
    with patch("app.config.save_config"):
        ctrl._moved(100, 200)
    assert config["big_subtitle_pos"] == [100, 200]
