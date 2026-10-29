"""
Orchestrator.change_monitor() testleri (main.py): monitor degistirilince
sadece sira numarasinin degil, monitorun KIMLIGININ (konum+cozunurluk) de
kaydedildigini dogrular - ekran dizilimi sonradan degisirse (bkz.
capture_mod.resolve_monitor_index) dogru fiziksel ekran bulunabilsin diye.

Gercek ekran/ekran karti gerektirmez.
"""
import threading
from unittest.mock import MagicMock, patch

from app import main as main_mod


class _FakeOrchestrator:
    MODE_NONE = main_mod.Orchestrator.MODE_NONE
    MODE_LIVE = main_mod.Orchestrator.MODE_LIVE
    MODE_INSTANT = main_mod.Orchestrator.MODE_INSTANT

    change_monitor = main_mod.Orchestrator.change_monitor
    _stop_live_locked = main_mod.Orchestrator._stop_live_locked

    def __init__(self):
        self.mode = self.MODE_NONE
        self.live_started_at = None
        self._mode_lock = threading.Lock()
        self._live_stop_event = threading.Event()
        self.capturer = MagicMock()
        self.overlay = MagicMock()
        self.config = {"capture_monitor_index": 0, "capture_monitor_identity": None}


def test_change_monitor_saves_index_and_identity():
    fake = _FakeOrchestrator()
    new_capturer = MagicMock()
    identity = {"left": 1920, "top": 0, "width": 1920, "height": 1080}

    with patch.object(main_mod.capture_mod, "ScreenCapturer", return_value=new_capturer), \
         patch.object(main_mod.capture_mod, "get_monitor_identity", return_value=identity), \
         patch.object(main_mod.config_mod, "save_config") as save:
        ok = fake.change_monitor(1)

    assert ok is True
    assert fake.capturer is new_capturer
    assert fake.config["capture_monitor_index"] == 1
    assert fake.config["capture_monitor_identity"] == identity
    save.assert_called_once_with(fake.config)


def test_change_monitor_closes_old_capturer():
    fake = _FakeOrchestrator()
    old_capturer = fake.capturer
    new_capturer = MagicMock()

    with patch.object(main_mod.capture_mod, "ScreenCapturer", return_value=new_capturer), \
         patch.object(main_mod.capture_mod, "get_monitor_identity", return_value=None), \
         patch.object(main_mod.config_mod, "save_config"):
        fake.change_monitor(1)

    old_capturer.close.assert_called_once()


def test_change_monitor_returns_false_on_failure_without_touching_config():
    fake = _FakeOrchestrator()

    with patch.object(main_mod.capture_mod, "ScreenCapturer", side_effect=RuntimeError("yok")), \
         patch.object(main_mod.config_mod, "save_config") as save:
        ok = fake.change_monitor(5)

    assert ok is False
    assert fake.config["capture_monitor_index"] == 0  # degismedi
    save.assert_not_called()


def test_change_monitor_stops_live_mode_first():
    fake = _FakeOrchestrator()
    fake.mode = fake.MODE_LIVE

    with patch.object(main_mod.capture_mod, "ScreenCapturer", return_value=MagicMock()), \
         patch.object(main_mod.capture_mod, "get_monitor_identity", return_value=None), \
         patch.object(main_mod.config_mod, "save_config"):
        fake.change_monitor(1)

    assert fake._live_stop_event.is_set()
    assert fake.mode == fake.MODE_NONE
    fake.overlay.hide_threadsafe.assert_called_once()
