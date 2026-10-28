"""
Ollama'nin oyun sirasinda cokmesi/kapanmasi durumunda otomatik kendini
toparlama (_maybe_recover_ollama) testleri.

Gercek bir Ollama sureci baslatmaz: ensure_ollama_running main.py'de
mock'lanir. Agir Orchestrator.__init__'i hic calistirmadan, ilgili
metodlari hafif bir sahte nesneye baglayip test ederiz (bkz.
test_orchestrator_translate.py'deki ayni desen).
"""
import threading
import time
from unittest.mock import MagicMock, patch

from app import main as main_mod


class _FakeOrchestrator:
    _translate_one = main_mod.Orchestrator._translate_one
    _maybe_recover_ollama = main_mod.Orchestrator._maybe_recover_ollama

    def __init__(self, translate_fn, engine="ollama"):
        self.translator = MagicMock()
        self.translator.translate = translate_fn
        self.translator.ollama.host = "http://127.0.0.1:11434"
        self._translate_consecutive_failures = 0
        self._translate_fail_lock = threading.Lock()
        self._translate_sequential_lock = threading.Lock()
        self._ollama_recovery_attempted = False
        self._quitting = False
        self.config = {"translate_engine": engine}


def _settle():
    """_maybe_recover_ollama arka planda bir thread baslatiyor; o
    thread'in calisip bitmesi icin kisa bir sure bekler."""
    time.sleep(0.05)


def test_recovery_not_triggered_below_threshold():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: None)
    with patch.object(main_mod, "ensure_ollama_running") as recover:
        for _ in range(4):
            fake._translate_one("metin", None)
        _settle()
    recover.assert_not_called()


def test_recovery_triggered_at_threshold():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: None)
    with patch.object(main_mod, "ensure_ollama_running", return_value=True) as recover:
        for _ in range(5):
            fake._translate_one("metin", None)
        _settle()
    recover.assert_called_once_with("http://127.0.0.1:11434")


def test_recovery_only_attempted_once_per_episode():
    """5. hatada bir kez denenir; devam eden hatalarda (6, 7, 8...)
    TEKRAR denenmemeli - her hata Ollama'yi yeniden baslatmaya calismak
    gereksiz subprocess spawn'larina yol acar."""
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: None)
    with patch.object(main_mod, "ensure_ollama_running", return_value=True) as recover:
        for _ in range(9):
            fake._translate_one("metin", None)
        _settle()
    recover.assert_called_once()


def test_recovery_not_triggered_when_engine_is_not_ollama():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: None, engine="google")
    with patch.object(main_mod, "ensure_ollama_running") as recover:
        for _ in range(6):
            fake._translate_one("metin", None)
        _settle()
    recover.assert_not_called()


def test_recovery_flag_resets_after_success_allowing_a_new_attempt():
    """Kurtarma denendikten sonra ceviri tekrar basarili olursa sayac
    sifirlanir; servis sonra TEKRAR cokerse yeni bir kurtarma denenebilmeli."""
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        # 1-5: basarisiz (ilk kurtarma tetiklenir), 6: basarili (sayac
        # sifirlanir), 7-11: tekrar basarisiz (ikinci kurtarma tetiklenir)
        return None if calls["n"] != 6 else "Merhaba"

    fake = _FakeOrchestrator(translate_fn=flaky)
    with patch.object(main_mod, "ensure_ollama_running", return_value=True) as recover:
        for _ in range(5):
            fake._translate_one("metin", None)
        _settle()
        recover.assert_called_once()

        fake._translate_one("metin", None)  # 6. cagri basarili -> sayac/flag sifirlanir
        assert fake._translate_consecutive_failures == 0
        assert fake._ollama_recovery_attempted is False

        for _ in range(5):
            fake._translate_one("metin_2", None)
        _settle()
        assert recover.call_count == 2


def test_recovery_not_triggered_while_quitting():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: None)
    fake._quitting = True
    with patch.object(main_mod, "ensure_ollama_running") as recover:
        for _ in range(6):
            fake._translate_one("metin", None)
        _settle()
    recover.assert_not_called()
