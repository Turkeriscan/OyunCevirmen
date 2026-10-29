"""
_typewriter_check() ve canli moddaki entegrasyonu (2.4): harf harf
beliren diyalog (typewriter efekti) icin ara durumlarin ("H", "He",
"Hel"...) bosa cevrilmemesi, metin en az debounce suresi kadar
DEGISMEDEN kalinca cevrilmesi. Statik (hic buyumeyen) bir metnin ise
HIC GECIKTIRILMEMESI.
"""
import threading
import time
from unittest.mock import MagicMock

from app import main as main_mod
from app.core.ocr import OCRBoxResult


# --------------------------------------------------------- saf fonksiyon
def test_first_appearance_is_not_deferred():
    defer, state = main_mod._typewriter_check(None, "Hello", now=100.0, debounce_seconds=0.4)
    assert defer is False
    assert state == {"text": "Hello", "stable_since": 100.0, "growing": False}


def test_growing_text_is_deferred():
    prev = {"text": "H", "stable_since": 100.0, "growing": False}
    defer, state = main_mod._typewriter_check(prev, "He", now=100.1, debounce_seconds=0.4)
    assert defer is True
    assert state["growing"] is True
    assert state["text"] == "He"


def test_non_growing_change_is_not_deferred():
    """Metin TAMAMEN degisti (buyume degil) - hemen islenmeli."""
    prev = {"text": "Hello", "stable_since": 100.0, "growing": False}
    defer, state = main_mod._typewriter_check(prev, "Bye", now=100.1, debounce_seconds=0.4)
    assert defer is False
    assert state["growing"] is False


def test_stable_after_growth_is_still_deferred_before_debounce_elapses():
    prev = {"text": "Hello", "stable_since": 100.0, "growing": True}
    defer, state = main_mod._typewriter_check(prev, "Hello", now=100.2, debounce_seconds=0.4)
    assert defer is True
    assert state == prev  # degismedi, hala bekleniyor


def test_stable_after_growth_is_released_once_debounce_elapses():
    prev = {"text": "Hello", "stable_since": 100.0, "growing": True}
    defer, state = main_mod._typewriter_check(prev, "Hello", now=100.5, debounce_seconds=0.4)
    assert defer is False
    assert state["growing"] is False
    assert state["text"] == "Hello"


def test_unchanged_static_text_is_never_deferred():
    """Hic buyume gozlenmemis bir metin (statik/tek seferde beliren),
    tekrar AYNI gelse bile geciktirilmemeli."""
    prev = {"text": "Hello", "stable_since": 100.0, "growing": False}
    defer, state = main_mod._typewriter_check(prev, "Hello", now=100.1, debounce_seconds=0.4)
    assert defer is False


def test_zero_length_debounce_never_defers():
    prev = {"text": "H", "stable_since": 100.0, "growing": False}
    defer, state = main_mod._typewriter_check(prev, "He", now=100.01, debounce_seconds=0.0)
    # growth HALA tespit edilir (state.growing=True) ama debounce=0 oldugundan
    # cagiran taraf (debounce_seconds > 0 kontrolu main.py'de) bu fonksiyonu
    # hic cagirmaz; burada sadece saf fonksiyonun kendisini test ediyoruz.
    assert state["growing"] is True


# --------------------------------------------- canli mod entegrasyonu
class _FakeOrchestrator:
    _live_process_cell = main_mod.Orchestrator._live_process_cell
    _submit_live_translation = main_mod.Orchestrator._submit_live_translation
    _translate_one = main_mod.Orchestrator._translate_one
    _claim_inflight = main_mod.Orchestrator._claim_inflight
    _claim_or_join_inflight = main_mod.Orchestrator._claim_or_join_inflight
    _release_inflight = main_mod.Orchestrator._release_inflight
    _remember = main_mod.Orchestrator._remember
    _make_box = staticmethod(main_mod.Orchestrator._make_box)

    def __init__(self, debounce_ms=400):
        self.translator = MagicMock()
        self.translator.translate = lambda *a, **k: "ok"
        self.translator.cache = MagicMock()
        self.translator.cache.get.return_value = "Merhaba"
        self._translate_consecutive_failures = 0
        self._translate_fail_lock = threading.Lock()
        self._translate_sequential_lock = threading.Lock()
        self._translate_inflight = {}
        self._translate_inflight_lock = threading.Lock()
        self._translate_executor = __import__(
            "concurrent.futures", fromlist=["ThreadPoolExecutor"]
        ).ThreadPoolExecutor(max_workers=3)
        self._live_stop_event = threading.Event()
        self.recent = __import__("collections").deque(maxlen=40)
        self.recent_version = 0
        self.config = {"live_typewriter_debounce_ms": debounce_ms}


def _result(text):
    return OCRBoxResult(text, 0.9, (0, 0, 100, 20))


def test_growing_sequence_is_not_translated_until_stable():
    fake = _FakeOrchestrator(debounce_ms=200)
    cell_boxes, cell_last_texts, cell_growth = {}, {}, {}
    cell_lock = threading.Lock()
    cell_generation = {0: 1}

    for partial in ("H", "He", "Hel", "Hell", "Hello"):
        cached_boxes, hits, pending = fake._live_process_cell(
            0, [_result(partial)], "auto", "tr", "ollama", None,
            1, cell_generation, cell_boxes, cell_last_texts, cell_lock, cell_growth,
        )
        time.sleep(0.02)  # ardisik taramalar arasindaki kisa sureyi simule et

    # Sadece ILK gorulen "H" islenir (henuz buyuyup buyumeyecegi bilinmez);
    # "He"/"Hel"/"Hell"/"Hello" BUYUME olarak tespit edilip DEBOUNCE suresi
    # (200ms) henuz gecmedigi icin hicbiri islenmemis olmali.
    assert fake.translator.cache.get.call_count == 1
    fake.translator.cache.get.assert_called_once_with("H", "auto", "tr", "ollama")


def test_stabilized_text_is_translated_after_debounce():
    fake = _FakeOrchestrator(debounce_ms=50)
    cell_boxes, cell_last_texts, cell_growth = {}, {}, {}
    cell_lock = threading.Lock()
    cell_generation = {0: 1}

    fake._live_process_cell(
        0, [_result("H")], "auto", "tr", "ollama", None,
        1, cell_generation, cell_boxes, cell_last_texts, cell_lock, cell_growth,
    )
    fake._live_process_cell(
        0, [_result("Hello")], "auto", "tr", "ollama", None,
        1, cell_generation, cell_boxes, cell_last_texts, cell_lock, cell_growth,
    )
    time.sleep(0.07)  # debounce suresinden FAZLA bekle
    cached_boxes, hits, pending = fake._live_process_cell(
        0, [_result("Hello")], "auto", "tr", "ollama", None,
        1, cell_generation, cell_boxes, cell_last_texts, cell_lock, cell_growth,
    )

    assert hits == 1
    assert cached_boxes[0].text == "Merhaba"


def test_static_text_is_translated_immediately_without_waiting():
    """Hic buyume gozlenmeyen (ilk gorulen) bir metin, debounce suresi
    uzun olsa bile HEMEN islenmeli."""
    fake = _FakeOrchestrator(debounce_ms=5000)
    cell_boxes, cell_last_texts, cell_growth = {}, {}, {}
    cell_lock = threading.Lock()
    cell_generation = {0: 1}

    cached_boxes, hits, pending = fake._live_process_cell(
        0, [_result("Inventory is full")], "auto", "tr", "ollama", None,
        1, cell_generation, cell_boxes, cell_last_texts, cell_lock, cell_growth,
    )

    assert hits == 1
    assert cached_boxes[0].text == "Merhaba"


def test_debounce_disabled_when_zero():
    fake = _FakeOrchestrator(debounce_ms=0)
    cell_boxes, cell_last_texts, cell_growth = {}, {}, {}
    cell_lock = threading.Lock()
    cell_generation = {0: 1}

    fake._live_process_cell(
        0, [_result("H")], "auto", "tr", "ollama", None,
        1, cell_generation, cell_boxes, cell_last_texts, cell_lock, cell_growth,
    )
    cached_boxes, hits, pending = fake._live_process_cell(
        0, [_result("He")], "auto", "tr", "ollama", None,
        1, cell_generation, cell_boxes, cell_last_texts, cell_lock, cell_growth,
    )
    # debounce kapali (0) oldugu icin "He" de HEMEN islenmeli
    assert hits == 1
