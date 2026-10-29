"""
3.4 kaynak tasarrufu testleri: canli modun (main.py)

1) _is_cutscene_like / _compute_next_interval saf fonksiyonlari,
2) _live_loop'un (a) oyun arka plandayken/sistem bostayken ekrani HIC
   yakalamadan duraklamasi, (b) hucrelerin cogu birden degisince
   (sinematik) OCR'a hic gondermemesi - AMA bunun canli mod ACILDIGINDA
   (ilk kare, henuz referans imza yokken) YANLISLIKLA tetiklenmemesi.

Gercek ekran/OCR/Ollama/Windows API'si gerektirmez.
"""
import collections
import threading
from unittest.mock import MagicMock, patch

import numpy as np

from app import main as main_mod


# ------------------------------------------------------------- _is_cutscene_like
def test_is_cutscene_like_false_for_empty_grid():
    assert main_mod._is_cutscene_like(0, 0) is False


def test_is_cutscene_like_false_below_ratio():
    assert main_mod._is_cutscene_like(1, 4) is False  # %25


def test_is_cutscene_like_true_at_or_above_ratio():
    assert main_mod._is_cutscene_like(3, 4) is True  # %75
    assert main_mod._is_cutscene_like(3, 5) is True  # tam esik: %60


# -------------------------------------------------------- _compute_next_interval
def test_compute_next_interval_no_change_when_fast_enough():
    new_interval, streak, grew = main_mod._compute_next_interval(
        0.45, elapsed=0.2, max_interval=3.0, overrun_streak=0)
    assert new_interval == 0.45
    assert streak == 0
    assert grew is False


def test_compute_next_interval_increments_streak_below_threshold():
    new_interval, streak, grew = main_mod._compute_next_interval(
        0.45, elapsed=0.9, max_interval=3.0, overrun_streak=0, streak_needed=3)
    assert new_interval == 0.45
    assert streak == 1
    assert grew is False


def test_compute_next_interval_grows_after_streak_reached():
    new_interval, streak, grew = main_mod._compute_next_interval(
        0.45, elapsed=0.9, max_interval=3.0, overrun_streak=2, streak_needed=3,
        growth_factor=1.5)
    assert grew is True
    assert new_interval == 0.45 * 1.5
    assert streak == 0


def test_compute_next_interval_capped_at_max():
    new_interval, streak, grew = main_mod._compute_next_interval(
        2.5, elapsed=3.0, max_interval=3.0, overrun_streak=2, streak_needed=3,
        growth_factor=1.5)
    assert new_interval == 3.0
    assert grew is True


def test_compute_next_interval_no_growth_when_already_at_max():
    new_interval, streak, grew = main_mod._compute_next_interval(
        3.0, elapsed=5.0, max_interval=3.0, overrun_streak=2, streak_needed=3)
    assert new_interval == 3.0
    assert grew is False


# ------------------------------------------------------------------- _live_loop
class _FakeOrchestrator:
    _live_loop = main_mod.Orchestrator._live_loop

    def __init__(self):
        self.config = {
            "live_scan_interval": 0.01,
            "live_grid_cols": 2,
            "live_grid_rows": 2,
            "live_cell_padding": 0,
            "live_auto_pause_enabled": False,
            "live_cutscene_skip_enabled": True,
        }
        self.capturer = MagicMock()
        self.capturer.get_origin.return_value = (0, 0)
        self.overlay = MagicMock()
        self._live_stop_event = threading.Event()
        self.recent = collections.deque(maxlen=40)
        self._ocr_and_filter = MagicMock(return_value=[])
        self._live_process_cell = MagicMock(return_value=([], 0, 0))
        self._context_lines = MagicMock(return_value=[])


def _stop_after_n_sleeps(fake, n):
    calls = {"i": 0}

    def fake_sleep_remaining(t0, interval):
        calls["i"] += 1
        if calls["i"] >= n:
            fake._live_stop_event.set()

    fake._sleep_remaining = fake_sleep_remaining


def test_live_loop_does_not_treat_bootstrap_frame_as_cutscene():
    """Canli mod ACILDIGINDA ilk karede HENUZ referans imza yoktur, bu
    yuzden hucrelerin HEPSI 'degismis' sayilir - bu, yanlislikla sinematik
    atlamasini tetiklememeli (aksi halde her acilista ilk kare hic
    OCR'lanmadan kaybolurdu)."""
    fake = _FakeOrchestrator()
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    fake.capturer.grab_full.side_effect = [frame]
    _stop_after_n_sleeps(fake, 1)

    fake._live_loop()

    assert fake._ocr_and_filter.call_count == 4  # 2x2 izgaranin TUM hucreleri
    assert fake._live_process_cell.call_count == 4


def test_live_loop_skips_ocr_on_cutscene_like_change(caplog):
    """Ilk kare normal isleyip referans imzalari olusturduktan SONRA,
    hucrelerin cogu (3/4) birden degisirse - sinematik/sahne gecisi
    sayilip OCR'a hic gonderilmemeli."""
    fake = _FakeOrchestrator()
    frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
    frame2 = frame1.copy()
    frame2[:50, :] = 255   # ust iki hucre (0,1) beyaz
    frame2[50:, :50] = 255  # sol-alt hucre (2) de beyaz -> 3/4 hucre degisti
    fake.capturer.grab_full.side_effect = [frame1, frame2]
    _stop_after_n_sleeps(fake, 2)

    with caplog.at_level("INFO", logger="OyunCevirmen"):
        fake._live_loop()

    # tick1: 4 hucre islendi (bootstrap). tick2: sinematik sayilip HIC
    # ek OCR cagrisi yapilmamali.
    assert fake._ocr_and_filter.call_count == 4
    assert fake._live_process_cell.call_count == 4
    assert any("atlandi" in r.message for r in caplog.records)


def test_live_loop_auto_pause_skips_capture_entirely():
    """should_pause_live True donunce ekran HIC yakalanmamali (kaynak
    tasarrufu) - sadece kisa bir bekleme yapilip bir sonraki tura gecilmeli."""
    fake = _FakeOrchestrator()
    fake.config["live_auto_pause_enabled"] = True

    calls = {"n": 0}

    def fake_time_sleep(_seconds):
        calls["n"] += 1
        if calls["n"] >= 2:
            fake._live_stop_event.set()

    with patch("app.main.time.sleep", side_effect=fake_time_sleep), \
         patch.object(main_mod.activity_mod, "get_foreground_exe_name", return_value="game.exe"), \
         patch.object(main_mod.activity_mod, "own_exe_name", return_value="python.exe"), \
         patch.object(main_mod.activity_mod, "get_idle_seconds", return_value=0.0), \
         patch.object(main_mod.activity_mod, "should_pause_live", return_value=True):
        fake._live_loop()

    fake.capturer.grab_full.assert_not_called()


def test_live_loop_auto_pause_logs_transition_only_once(caplog):
    fake = _FakeOrchestrator()
    fake.config["live_auto_pause_enabled"] = True

    calls = {"n": 0}

    def fake_time_sleep(_seconds):
        calls["n"] += 1
        if calls["n"] >= 3:
            fake._live_stop_event.set()

    with caplog.at_level("INFO", logger="OyunCevirmen"), \
         patch("app.main.time.sleep", side_effect=fake_time_sleep), \
         patch.object(main_mod.activity_mod, "get_foreground_exe_name", return_value="game.exe"), \
         patch.object(main_mod.activity_mod, "own_exe_name", return_value="python.exe"), \
         patch.object(main_mod.activity_mod, "get_idle_seconds", return_value=0.0), \
         patch.object(main_mod.activity_mod, "should_pause_live", return_value=True):
        fake._live_loop()

    pause_logs = [r for r in caplog.records if "duraklatildi" in r.message]
    assert len(pause_logs) == 1
