"""
Canli modun F9 (anlik tarama) gibi davranmasi icin: bir hucrenin PIKSELLERI
degisse bile (orn. yakinindaki hafif bir animasyon/isik titremesi yuzunden),
OKUNAN METIN gercekte AYNIYSA cevirmeye/onbellege/overlay'e HIC dokunulmaz -
kullanicinin bildirdigi "canli mod surekli titriyor/yeniden ceviriyor"
sorununun duzeltmesi.

Gercek ekran/OCR/Ollama gerektirmez.
"""
import collections
import concurrent.futures
import threading
import time
from unittest.mock import MagicMock

import numpy as np

from app import main as main_mod
from app.core.ocr import OCRBoxResult


class _FakeOrchestrator:
    _live_loop = main_mod.Orchestrator._live_loop
    _live_process_cell = main_mod.Orchestrator._live_process_cell
    _submit_live_translation = main_mod.Orchestrator._submit_live_translation
    _translate_one = main_mod.Orchestrator._translate_one
    _claim_inflight = main_mod.Orchestrator._claim_inflight
    _claim_or_join_inflight = main_mod.Orchestrator._claim_or_join_inflight
    _release_inflight = main_mod.Orchestrator._release_inflight
    _remember = main_mod.Orchestrator._remember
    _make_box = staticmethod(main_mod.Orchestrator._make_box)
    _context_lines = main_mod.Orchestrator._context_lines

    def __init__(self):
        self.translator = MagicMock()
        self.translator.translate.return_value = "Merhaba"
        self.translator.cache = MagicMock()
        self.translator.cache.get.return_value = None  # varsayilan: onbellekte yok
        self._translate_consecutive_failures = 0
        self._translate_fail_lock = threading.Lock()
        self._translate_sequential_lock = threading.Lock()
        self._translate_inflight = {}
        self._translate_inflight_lock = threading.Lock()
        self._translate_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        self._live_stop_event = threading.Event()
        self.recent = collections.deque(maxlen=40)
        self.recent_version = 0
        self.overlay = MagicMock()
        self.capturer = MagicMock()
        self.capturer.get_origin.return_value = (0, 0)
        self.config = {
            "live_scan_interval": 0.01,
            "live_grid_cols": 2,
            "live_grid_rows": 2,
            "live_cell_padding": 0,
            "live_auto_pause_enabled": False,
            "live_cutscene_skip_enabled": False,
            "live_typewriter_debounce_ms": 0,
            "translate_context_lines": 0,
            "source_lang": "en",
            "target_lang": "tr",
            "translate_engine": "ollama",
        }
        self._ocr_and_filter = MagicMock()


def _stop_after_n_sleeps(fake, n):
    calls = {"i": 0}

    def fake_sleep_remaining(t0, interval):
        calls["i"] += 1
        if calls["i"] >= n:
            fake._live_stop_event.set()

    fake._sleep_remaining = fake_sleep_remaining


def _two_frames():
    frame1 = np.zeros((100, 100, 3), dtype=np.uint8)
    frame2 = frame1.copy()
    frame2[:, :] = 50  # TUM pikseller degisti - hucrelerin hepsi "degismis" sayilir
    return frame1, frame2


def test_unchanged_text_is_not_reprocessed_despite_pixel_change():
    """2x2 izgarada (4 hucre): tick1 hepsi ilk kez okunur (bootstrap),
    tick2'de piksel YINE degisti ama OCR AYNI metni okudu - hicbir hucre
    yeniden islenmemeli (cache.get tekrar cagrilmamali)."""
    fake = _FakeOrchestrator()
    fake._ocr_and_filter.return_value = [OCRBoxResult("Hello", 0.9, (0, 0, 50, 20))]
    frame1, frame2 = _two_frames()
    fake.capturer.grab_full.side_effect = [frame1, frame2]
    _stop_after_n_sleeps(fake, 2)

    fake._live_loop()

    # tick1: 4 hucre ilk kez okunuyor -> 4 cache.get cagrisi.
    # tick2: metin AYNI -> HICBIR ek cagri olmamali.
    assert fake.translator.cache.get.call_count == 4


def test_changed_text_is_reprocessed_normally():
    """Ayni senaryoda, tick2'de OCR GERCEKTEN farkli bir metin okursa,
    normal sekilde yeniden islenmeli."""
    fake = _FakeOrchestrator()
    fake._ocr_and_filter.side_effect = (
        [[OCRBoxResult("Hello", 0.9, (0, 0, 50, 20))]] * 4
        + [[OCRBoxResult("World", 0.9, (0, 0, 50, 20))]] * 4
    )
    frame1, frame2 = _two_frames()
    fake.capturer.grab_full.side_effect = [frame1, frame2]
    _stop_after_n_sleeps(fake, 2)

    fake._live_loop()

    assert fake.translator.cache.get.call_count == 8


def test_empty_survivors_repeated_does_not_keep_reprocessing():
    """Bos bir hucre (OCR hicbir sey bulamadi) piksel titremesi yuzunden
    surekli 'degisti' sayilsa bile, bos sonuc tekrar tekrar islenmemeli."""
    fake = _FakeOrchestrator()
    fake._ocr_and_filter.return_value = []
    frame1, frame2 = _two_frames()
    fake.capturer.grab_full.side_effect = [frame1, frame2]
    _stop_after_n_sleeps(fake, 2)

    fake._live_loop()

    assert fake.translator.cache.get.call_count == 0
    # tick1'de "bos da olsa ilk kez goruluyor" sayilip islenir (4 hucre),
    # tick2'de metin (bos kume) AYNI oldugu icin atlanir.
    assert fake._ocr_and_filter.call_count == 8  # OCR cagrisinin kendisi hep yapilir
