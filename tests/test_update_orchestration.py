"""
Orchestrator'daki surum kontrolu (5.2) baglama testleri (main.py):
_check_for_update'in config'e yazmasi, tepsi bildirimi gondermesi, GUI
thread'ine sinyal gondermesi; MainWindow.show_update_available'in
durum cubugunu guncellemesi.

Gercek internet/GitHub API'sine ihtiyac duymaz.
"""
from unittest.mock import MagicMock, patch

from app import main as main_mod
from app.ui import mainwindow as mainwindow_mod


class _FakeOrchestrator:
    _check_for_update = main_mod.Orchestrator._check_for_update
    _on_update_available_on_gui_thread = main_mod.Orchestrator._on_update_available_on_gui_thread

    def __init__(self, config):
        self.config = config
        self.bridge = MagicMock()
        self.tray = MagicMock()
        self.main_window = None
        self.available_update = None


def test_check_for_update_persists_timestamp_even_without_new_release():
    cfg = {"last_update_check_at": None}
    fake = _FakeOrchestrator(cfg)

    with patch.object(main_mod.update_mod, "check_for_update", return_value=(None, 12345.0)), \
         patch.object(main_mod.config_mod, "save_config") as save:
        fake._check_for_update()

    assert cfg["last_update_check_at"] == 12345.0
    save.assert_called_once_with(cfg)
    fake.bridge.update_available_signal.emit.assert_not_called()
    fake.tray.notify.assert_not_called()


def test_check_for_update_emits_signal_and_notifies_tray_when_newer():
    cfg = {"last_update_check_at": None}
    fake = _FakeOrchestrator(cfg)
    release = {"tag_name": "v2.2.0", "html_url": "https://example.com"}

    with patch.object(main_mod.update_mod, "check_for_update", return_value=(release, 999.0)), \
         patch.object(main_mod.config_mod, "save_config"):
        fake._check_for_update()

    assert fake.available_update == release
    fake.bridge.update_available_signal.emit.assert_called_once_with("v2.2.0", "https://example.com")
    fake.tray.notify.assert_called_once()


def test_check_for_update_does_not_save_when_timestamp_unchanged():
    cfg = {"last_update_check_at": 500.0}
    fake = _FakeOrchestrator(cfg)

    with patch.object(main_mod.update_mod, "check_for_update", return_value=(None, 500.0)), \
         patch.object(main_mod.config_mod, "save_config") as save:
        fake._check_for_update()

    save.assert_not_called()


def test_check_for_update_swallows_exceptions():
    cfg = {"last_update_check_at": None}
    fake = _FakeOrchestrator(cfg)

    with patch.object(main_mod.update_mod, "check_for_update", side_effect=RuntimeError("patlat")):
        fake._check_for_update()  # istisna firlatmamali


def test_on_update_available_updates_main_window_when_open():
    fake = _FakeOrchestrator({})
    fake.main_window = MagicMock()

    fake._on_update_available_on_gui_thread("v2.2.0", "https://example.com")

    fake.main_window.show_update_available.assert_called_once_with("v2.2.0", "https://example.com")


def test_on_update_available_safe_when_window_not_open():
    fake = _FakeOrchestrator({})
    fake._on_update_available_on_gui_thread("v2.2.0", "https://example.com")  # istisna firlatmamali


# ------------------------------------------------------------ MainWindow
class _FakeWindow:
    show_update_available = mainwindow_mod.MainWindow.show_update_available

    def __init__(self):
        self.credits = MagicMock()


def test_show_update_available_sets_credits_item_with_tooltip():
    window = _FakeWindow()
    window.show_update_available("v2.2.0", "https://example.com/release")

    window.credits.set_item.assert_called_once()
    args, _ = window.credits.set_item.call_args
    assert args[0] == "update"
    assert "v2.2.0" in args[1]
    assert "https://example.com/release" in args[3]


def test_show_update_available_handles_missing_url():
    window = _FakeWindow()
    window.show_update_available("v2.2.0", "")
    args, _ = window.credits.set_item.call_args
    assert args[3] != ""
