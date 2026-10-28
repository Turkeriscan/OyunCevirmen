"""
Orchestrator'in paralel ceviri yardimci metodlarinin (main.py) testleri:
ayni metnin iki kez ayni anda cevrilmeye calisilmamasi, ardisik hatada
seri (tek tek) cevirmeye gecis, baglam penceresinin dogru olusturulmasi.

Gercek QApplication/ekran/Ollama gerektirmez: Orchestrator'in agir
__init__'ini calistirmadan, ilgili metodlari hafif bir sahte nesneye
baglayip dogrudan test ederiz.
"""
import collections
import concurrent.futures
import threading
import time
from unittest.mock import MagicMock

from app import main as main_mod


class _FakeOrchestrator:
    """main.Orchestrator'in gercek metodlarini, agir __init__'i hic
    calistirmadan test etmek icin minimal bir host nesnesi."""

    _translate_one = main_mod.Orchestrator._translate_one
    _claim_inflight = main_mod.Orchestrator._claim_inflight
    _release_inflight = main_mod.Orchestrator._release_inflight
    _context_lines = main_mod.Orchestrator._context_lines
    _remember = main_mod.Orchestrator._remember
    _request_google_permission = main_mod.Orchestrator._request_google_permission
    reset_google_permission_prompt = main_mod.Orchestrator.reset_google_permission_prompt

    def __init__(self, translate_fn, context_lines_cfg=4):
        self.translator = MagicMock()
        self.translator.translate = translate_fn
        self._translate_consecutive_failures = 0
        self._translate_fail_lock = threading.Lock()
        self._translate_sequential_lock = threading.Lock()
        self._translate_inflight = set()
        self._translate_inflight_lock = threading.Lock()
        self._translate_executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        self.recent = collections.deque(maxlen=40)
        self.recent_version = 0
        self.config = {"translate_context_lines": context_lines_cfg}
        self._google_prompt_shown = False
        self._pending_google_prompt = False
        self._google_prompt_lock = threading.Lock()
        self.bridge = MagicMock()


# -------------------------------------------------------------- inflight dedup
def test_claim_inflight_prevents_duplicate():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    assert fake._claim_inflight("Hello") is True
    # Ayni metin hala "cevriliyor" sayilir, ikinci istek reddedilir
    assert fake._claim_inflight("Hello") is False
    fake._release_inflight("Hello")
    # Serbest birakildiktan sonra tekrar talep edilebilir
    assert fake._claim_inflight("Hello") is True


def test_claim_inflight_different_texts_independent():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    assert fake._claim_inflight("A") is True
    assert fake._claim_inflight("B") is True


# -------------------------------------------------------- devre kesici (seri mod)
def test_translate_one_resets_failures_on_success():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "Merhaba")
    fake._translate_consecutive_failures = 1
    result = fake._translate_one("Hello", None)
    assert result == "Merhaba"
    assert fake._translate_consecutive_failures == 0


def test_translate_one_increments_failures_on_none_result():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: None)
    fake._translate_one("Hello", None)
    fake._translate_one("Hello2", None)
    assert fake._translate_consecutive_failures == 2


def test_translate_one_degrades_to_sequential_after_repeated_failures():
    """2 ardisik hatadan sonra, Ollama'nin paralel istekleri iyi
    karsilamadigi varsayilir ve seri kilit kullanilmaya baslanir."""
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    fake._translate_sequential_lock = MagicMock()
    fake._translate_sequential_lock.__enter__ = MagicMock(return_value=None)
    fake._translate_sequential_lock.__exit__ = MagicMock(return_value=False)

    fake._translate_consecutive_failures = 0
    fake._translate_one("normal", None)
    fake._translate_sequential_lock.__enter__.assert_not_called()

    fake._translate_consecutive_failures = 2
    fake._translate_one("degraded", None)
    fake._translate_sequential_lock.__enter__.assert_called_once()


def test_translate_one_recovers_after_success():
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        return None if calls["n"] <= 2 else "Merhaba"

    fake = _FakeOrchestrator(translate_fn=flaky)
    fake._translate_one("a", None)
    fake._translate_one("b", None)
    assert fake._translate_consecutive_failures == 2
    fake._translate_one("c", None)  # bu basarili -> sayaç sifirlanir
    assert fake._translate_consecutive_failures == 0


# ------------------------------------------------------------------ baglam
def test_context_lines_returns_recent_pairs_most_recent_first():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    fake._remember("Hello", "Merhaba")
    fake._remember("Bye", "Güle güle")
    ctx = fake._context_lines()
    assert ctx[0] == ("Bye", "Güle güle")
    assert ctx[1] == ("Hello", "Merhaba")


def test_context_lines_respects_configured_limit():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok", context_lines_cfg=2)
    for i in range(5):
        fake._remember(f"orig{i}", f"ceviri{i}")
    ctx = fake._context_lines()
    assert len(ctx) == 2


def test_context_lines_empty_when_disabled():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok", context_lines_cfg=0)
    fake._remember("Hello", "Merhaba")
    assert fake._context_lines() == []


# ----------------------------------------------------- paralellik gercekten var
def test_translations_actually_run_concurrently():
    """En az 2 is parcacigi gercekten AYNI ANDA calisiyor mu (sirayla degil)?
    Her cagri 150ms bekler; 3 metin PARALEL cevrilirse toplam sure tek bir
    cagri suresine yakin olmali, 3 kati OLMAMALI."""
    def slow_translate(text, source_lang=None, target_lang=None, context_lines=None):
        time.sleep(0.15)
        return f"ceviri:{text}"

    fake = _FakeOrchestrator(translate_fn=slow_translate)
    t0 = time.time()
    futures = [
        fake._translate_executor.submit(fake._translate_one, f"text{i}", None)
        for i in range(3)
    ]
    results = [f.result(timeout=2) for f in futures]
    elapsed = time.time() - t0

    assert results == ["ceviri:text0", "ceviri:text1", "ceviri:text2"]
    assert elapsed < 0.4, f"cok yavas ({elapsed:.2f}s) - paralel calismiyor olabilir"


# ----------------------------------------------------- Google izni (bir kez sor)
def test_request_google_permission_fires_signal_once():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    fake._request_google_permission()
    fake._request_google_permission()
    fake._request_google_permission()
    assert fake.bridge.ask_google_permission_signal.emit.call_count == 1


def test_reset_google_permission_prompt_allows_asking_again():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    fake._request_google_permission()
    assert fake.bridge.ask_google_permission_signal.emit.call_count == 1
    fake.reset_google_permission_prompt()
    fake._request_google_permission()
    assert fake.bridge.ask_google_permission_signal.emit.call_count == 2


def test_reset_google_permission_prompt_clears_pending_flag():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    fake._pending_google_prompt = True
    fake.reset_google_permission_prompt()
    assert fake._pending_google_prompt is False
