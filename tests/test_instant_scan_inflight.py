"""
_translate_all_blocking() testleri (main.py, F9 "aninda tarama"):

Daha once, bir satir BASKA bir yerden (tipik olarak canli modun arka
plan cevirisinden) ayni anda cevrilmekteyse, aninda tarama bu satiri
SESSIZCE ATLIYORDU - kullanici F9'a bastiginda o satir ekranda hic
gorunmuyordu. Artik bu durumda diger cevirinin SONUCUNU bekleyip
kullaniyor.

Gercek ekran/OCR/Ollama gerektirmez.
"""
import concurrent.futures
import threading
import time
from unittest.mock import MagicMock

from app import main as main_mod
from app.core.ocr import OCRBoxResult


class _FakeOrchestrator:
    _translate_all_blocking = main_mod.Orchestrator._translate_all_blocking
    _translate_one = main_mod.Orchestrator._translate_one
    _claim_inflight = main_mod.Orchestrator._claim_inflight
    _claim_or_join_inflight = main_mod.Orchestrator._claim_or_join_inflight
    _release_inflight = main_mod.Orchestrator._release_inflight
    _context_lines = main_mod.Orchestrator._context_lines
    _remember = main_mod.Orchestrator._remember
    _make_box = staticmethod(main_mod.Orchestrator._make_box)

    def __init__(self, translate_fn):
        self.translator = MagicMock()
        self.translator.translate = translate_fn
        self.translator.cache = MagicMock()
        self.translator.cache.get.return_value = None
        self._translate_consecutive_failures = 0
        self._translate_fail_lock = threading.Lock()
        self._translate_sequential_lock = threading.Lock()
        self._translate_inflight = {}
        self._translate_inflight_lock = threading.Lock()
        self._translate_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        self._ollama_recovery_attempted = False
        self._quitting = False
        self.recent = __import__("collections").deque(maxlen=40)
        self.recent_version = 0
        self.config = {"translate_context_lines": 0, "translate_engine": "ollama"}


def _result(text, bbox=(0, 0, 100, 20)):
    return OCRBoxResult(text, 0.9, bbox)


def test_normal_translation_is_included_in_boxes():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "Merhaba")
    boxes, stats = fake._translate_all_blocking([_result("Hello")])
    assert len(boxes) == 1
    assert boxes[0].text == "Merhaba"
    assert stats["total"] == 1


def test_line_already_inflight_elsewhere_is_waited_for_not_dropped():
    """Bu, bildirilen hatanin dogrudan testi: bir satir BASKA bir yerden
    (orn. canli mod arka plan isi) cevrilmekteyken F9 aninda taramasi o
    satiri ARTIK ATLAMAMALI - sonucu bekleyip kullanmali."""
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")

    # "Baska bir yer" (canli mod gibi) bu metni ONCEDEN claim etmis olsun.
    is_owner, task = fake._claim_or_join_inflight("Hello")
    assert is_owner is True

    def finish_other_translation_later():
        time.sleep(0.1)
        fake._release_inflight("Hello", "Merhaba (baskasindan)")

    threading.Thread(target=finish_other_translation_later, daemon=True).start()

    boxes, stats = fake._translate_all_blocking([_result("Hello")])

    assert len(boxes) == 1
    assert boxes[0].text == "Merhaba (baskasindan)"


def test_inflight_wait_times_out_gracefully_without_crashing():
    """Diger ceviri cok uzun surerse (veya hic bitmezse), aninda tarama
    sonsuza dek kilitlenmemeli - zaman asimiyla devam etmeli."""
    from unittest.mock import patch

    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    is_owner, task = fake._claim_or_join_inflight("Hello")
    assert is_owner is True
    # BILEREK release etmiyoruz - "sonsuza dek suren" bir ceviriyi simule ediyor.

    try:
        with patch.object(main_mod, "INFLIGHT_WAIT_TIMEOUT", 0.05):
            boxes, stats = fake._translate_all_blocking([_result("Hello")])
    finally:
        fake._release_inflight("Hello", "gec kalan sonuc")  # temizlik

    assert boxes == []  # zaman asimi oldu, kutu eklenmedi ama cokmedi de


def test_multiple_lines_mixed_owned_and_joined():
    fake = _FakeOrchestrator(translate_fn=lambda text, **k: f"ceviri:{text}")

    is_owner, _task = fake._claim_or_join_inflight("Busy")
    assert is_owner is True

    def finish_busy_later():
        time.sleep(0.08)
        fake._release_inflight("Busy", "disaridan gelen ceviri")

    threading.Thread(target=finish_busy_later, daemon=True).start()

    boxes, stats = fake._translate_all_blocking([_result("Busy"), _result("Free")])

    texts = sorted(b.text for b in boxes)
    assert texts == ["ceviri:Free", "disaridan gelen ceviri"]
    assert stats["total"] == 2


def test_cache_hit_does_not_touch_inflight_tracking():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    fake.translator.cache.get.return_value = "Zaten onbellekte"
    boxes, stats = fake._translate_all_blocking([_result("Hello")])
    assert boxes[0].text == "Zaten onbellekte"
    assert stats["cache_hits"] == 1
    assert fake._translate_inflight == {}
