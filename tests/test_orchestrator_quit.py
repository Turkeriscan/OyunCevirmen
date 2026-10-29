"""
Orchestrator.request_quit() testleri: kapanista yakalama kaynaginin
(dxcam/mss) acikca kapatildigini, ama hata veren alt sistemlerin
(hotkeys/tray/capturer) birbirini BLOKE ETMEDIGINI dogrular - kapanis
sirasinda tek bir alt sistemin patlamasi diger temizlik adimlarini
veya programin kapanmasini engellememeli.

Gercek QApplication/ekran/klavye gerektirmez: agir __init__'i hic
calistirmadan, ilgili metodlari hafif bir sahte nesneye baglayip
dogrudan test ederiz (bkz. test_orchestrator_translate.py'deki ayni desen).
"""
import concurrent.futures
import threading
from unittest.mock import MagicMock

from app import main as main_mod


class _FakeOrchestrator:
    MODE_NONE = main_mod.Orchestrator.MODE_NONE
    MODE_LIVE = main_mod.Orchestrator.MODE_LIVE
    MODE_INSTANT = main_mod.Orchestrator.MODE_INSTANT

    request_quit = main_mod.Orchestrator.request_quit
    _stop_live_locked = main_mod.Orchestrator._stop_live_locked

    def __init__(self):
        self.mode = self.MODE_NONE
        self.live_started_at = None
        self._mode_lock = threading.Lock()
        self._live_stop_event = threading.Event()
        self.hotkeys = MagicMock()
        self.tray = MagicMock()
        self.capturer = MagicMock()
        self._translate_executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.bridge = MagicMock()
        self._quitting = False
        self._profile_poll_stop = threading.Event()


def test_request_quit_closes_capturer():
    fake = _FakeOrchestrator()
    fake.request_quit()
    fake.capturer.close.assert_called_once()


def test_request_quit_stops_hotkeys_and_tray():
    fake = _FakeOrchestrator()
    fake.request_quit()
    fake.hotkeys.stop.assert_called_once()
    fake.tray.stop.assert_called_once()


def test_request_quit_emits_quit_signal():
    fake = _FakeOrchestrator()
    fake.request_quit()
    fake.bridge.quit_signal.emit.assert_called_once()


def test_request_quit_sets_quitting_flag():
    fake = _FakeOrchestrator()
    fake.request_quit()
    assert fake._quitting is True


def test_request_quit_stops_live_mode_if_active():
    fake = _FakeOrchestrator()
    fake.mode = fake.MODE_LIVE
    fake.request_quit()
    assert fake._live_stop_event.is_set()
    assert fake.mode == fake.MODE_NONE


def test_request_quit_continues_despite_hotkeys_failure():
    """hotkeys.stop() patlasa bile tray/capturer temizligi VE kapanis
    sinyali yine de gerceklesmeli."""
    fake = _FakeOrchestrator()
    fake.hotkeys.stop.side_effect = RuntimeError("patlat")
    fake.request_quit()  # istisna firlatmamali
    fake.tray.stop.assert_called_once()
    fake.capturer.close.assert_called_once()
    fake.bridge.quit_signal.emit.assert_called_once()


def test_request_quit_continues_despite_capturer_failure():
    """capturer.close() patlasa bile kapanis sinyali yine de yayinlanmali."""
    fake = _FakeOrchestrator()
    fake.capturer.close.side_effect = RuntimeError("patlat")
    fake.request_quit()  # istisna firlatmamali
    fake.bridge.quit_signal.emit.assert_called_once()


def test_request_quit_continues_despite_tray_failure():
    fake = _FakeOrchestrator()
    fake.tray.stop.side_effect = RuntimeError("patlat")
    fake.request_quit()  # istisna firlatmamali
    fake.capturer.close.assert_called_once()
    fake.bridge.quit_signal.emit.assert_called_once()
