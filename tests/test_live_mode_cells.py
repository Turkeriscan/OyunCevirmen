"""
Canli mod hucre isleme testleri (main.py):

1) _submit_live_translation: bir hucre, ceviri surerken BASKA bir satira
   degisirse (nesil sayaci degisir), gecikmeli gelen ESKI cevirinin
   ekrana KONMAMASI ama akisa/onbellege YAZILMASININ devam etmesi.
2) _live_process_cell: onbellekten bulunan bir satir, AYNI hucrede
   ONCEDEN de gorulmusse (ayni metin), akisin (_remember) tekrar tekrar
   en uste tasinmamasi; metin o hucrede YENI belirdiginde ise tasinmasi.

Gercek ekran/OCR/Ollama gerektirmez.
"""
import threading
import time
from unittest.mock import MagicMock

from app import main as main_mod


class _FakeOrchestrator:
    _live_process_cell = main_mod.Orchestrator._live_process_cell
    _submit_live_translation = main_mod.Orchestrator._submit_live_translation
    _translate_one = main_mod.Orchestrator._translate_one
    _claim_inflight = main_mod.Orchestrator._claim_inflight
    _release_inflight = main_mod.Orchestrator._release_inflight
    _remember = main_mod.Orchestrator._remember
    _make_box = staticmethod(main_mod.Orchestrator._make_box)

    def __init__(self, translate_fn):
        self.translator = MagicMock()
        self.translator.translate = translate_fn
        self.translator.cache = MagicMock()
        self.translator.cache.get.return_value = None  # varsayilan: onbellekte yok
        self._translate_consecutive_failures = 0
        self._translate_fail_lock = threading.Lock()
        self._translate_sequential_lock = threading.Lock()
        self._translate_inflight = set()
        self._translate_inflight_lock = threading.Lock()
        self._translate_executor = __import__("concurrent.futures", fromlist=["ThreadPoolExecutor"]).ThreadPoolExecutor(max_workers=3)
        self._live_stop_event = threading.Event()
        self.recent = __import__("collections").deque(maxlen=40)
        self.recent_version = 0
        self.overlay = MagicMock()
        self.config = {}


def _wait_until(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def _fake_result(text, bbox=(0, 0, 100, 20)):
    from app.core.ocr import OCRBoxResult
    return OCRBoxResult(text, 0.9, bbox)


# --------------------------------------------- 1.2: nesil (generation) kontrolu
def test_stale_generation_translation_not_shown_but_remembered():
    """Hucre, ceviri surerken baska bir satira degismisse (nesil artmis),
    gec gelen ESKI cevirinin kutusu EKRANA konmamali ama akisa yazilmasi
    devam etmeli."""
    release = threading.Event()

    def slow_translate(*a, **k):
        release.wait(timeout=2.0)  # test, nesli degistirene kadar bekle
        return "Merhaba Dunya"

    fake = _FakeOrchestrator(translate_fn=slow_translate)
    cell_boxes = {}
    cell_lock = threading.Lock()
    cell_generation = {0: 1}  # hucre 0 su an nesil 1'de

    fake._submit_live_translation(
        _fake_result("Hello World"), idx=0, generation=1,
        cell_generation=cell_generation, cell_boxes=cell_boxes,
        cell_lock=cell_lock, context_lines=None,
    )
    # Ceviri HALA SURERKEN hucre YENIDEN degisti (nesil 2'ye cikti)
    cell_generation[0] = 2
    release.set()  # ceviriyi simdi bitirmesine izin ver

    assert _wait_until(lambda: len(fake.recent) == 1)
    # Akisa yazildi
    assert fake.recent[0][1] == "Hello World"
    assert fake.recent[0][2] == "Merhaba Dunya"
    # Ama ekrana (cell_boxes) KONMADI
    time.sleep(0.05)  # kutuya eklenecek bir sey varsa eklenmis olmali
    assert cell_boxes.get(0, []) == []


def test_matching_generation_translation_is_shown():
    """Hucre ceviri surerken DEGISMEDIYSE (nesil ayni), sonuc normal
    sekilde ekrana (cell_boxes) eklenmeli."""
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "Merhaba Dunya")
    cell_boxes = {}
    cell_lock = threading.Lock()
    cell_generation = {0: 1}

    fake._submit_live_translation(
        _fake_result("Hello World"), idx=0, generation=1,
        cell_generation=cell_generation, cell_boxes=cell_boxes,
        cell_lock=cell_lock, context_lines=None,
    )

    assert _wait_until(lambda: cell_boxes.get(0))
    assert cell_boxes[0][0].text == "Merhaba Dunya"


def test_failed_translation_does_not_remember_or_show():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: None)
    cell_boxes = {}
    cell_lock = threading.Lock()
    cell_generation = {0: 1}

    fake._submit_live_translation(
        _fake_result("Hello"), idx=0, generation=1,
        cell_generation=cell_generation, cell_boxes=cell_boxes,
        cell_lock=cell_lock, context_lines=None,
    )
    time.sleep(0.1)
    assert len(fake.recent) == 0
    assert cell_boxes.get(0, []) == []


# --------------------------------------------- 1.3: akisin tekrar siralanmamasi
def test_cache_hit_remembers_new_text_in_cell():
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    fake.translator.cache.get.return_value = "Merhaba"
    cell_boxes = {}
    cell_last_texts = {}
    cell_lock = threading.Lock()
    cell_generation = {0: 1}

    cached_boxes, hits, pending = fake._live_process_cell(
        0, [_fake_result("Hello")], "auto", "tr", "ollama", None,
        1, cell_generation, cell_boxes, cell_last_texts, cell_lock,
    )

    assert hits == 1 and pending == 0
    assert len(fake.recent) == 1
    assert fake.recent[0][1] == "Hello"


def test_cache_hit_does_not_reremember_unchanged_text_in_same_cell():
    """Ayni hucre, ayni metni (orn. komsu bir HUD titreyip sinyali
    degistirdigi icin) tekrar bulursa, akis tekrar en uste TASINMAMALI."""
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    fake.translator.cache.get.return_value = "Merhaba"
    cell_boxes = {}
    cell_last_texts = {}
    cell_lock = threading.Lock()
    cell_generation = {0: 1}

    # Birinci tarama: "Hello" bu hucrede YENI -> hatirlanir
    fake._live_process_cell(
        0, [_fake_result("Hello")], "auto", "tr", "ollama", None,
        1, cell_generation, cell_boxes, cell_last_texts, cell_lock,
    )
    assert len(fake.recent) == 1
    first_entry_time = fake.recent[0][0]

    # Ikinci tarama: AYNI hucre, AYNI metin tekrar geldi (sinyal titremesi)
    fake._live_process_cell(
        0, [_fake_result("Hello")], "auto", "tr", "ollama", None,
        2, cell_generation, cell_boxes, cell_last_texts, cell_lock,
    )
    # Akista hala TEK kayit olmali, zaman damgasi degismemeli
    assert len(fake.recent) == 1
    assert fake.recent[0][0] == first_entry_time


def test_cache_hit_remembers_when_text_changes_in_same_cell():
    """Hucredeki metin GERCEKTEN degisirse (yeni bir satir), akis
    guncellenmeli (yeni zaman damgasiyla en uste eklenmeli)."""
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    cell_boxes = {}
    cell_last_texts = {}
    cell_lock = threading.Lock()
    cell_generation = {0: 1}

    fake.translator.cache.get.return_value = "Merhaba"
    fake._live_process_cell(
        0, [_fake_result("Hello")], "auto", "tr", "ollama", None,
        1, cell_generation, cell_boxes, cell_last_texts, cell_lock,
    )
    fake.translator.cache.get.return_value = "Gule gule"
    fake._live_process_cell(
        0, [_fake_result("Bye")], "auto", "tr", "ollama", None,
        2, cell_generation, cell_boxes, cell_last_texts, cell_lock,
    )

    assert len(fake.recent) == 2
    assert fake.recent[0][1] == "Bye"  # en yenisi en uste


def test_cache_hit_remembers_same_text_reappearing_in_different_cell():
    """Ayni metin FARKLI bir hucrede cikarsa (orn. oyun ekranin farkli
    yerine kaydirdi), bu YENI bir goruntu sayilir ve hatirlanir."""
    fake = _FakeOrchestrator(translate_fn=lambda *a, **k: "ok")
    fake.translator.cache.get.return_value = "Merhaba"
    cell_boxes = {}
    cell_last_texts = {}
    cell_lock = threading.Lock()
    cell_generation = {0: 1, 1: 1}

    fake._live_process_cell(
        0, [_fake_result("Hello")], "auto", "tr", "ollama", None,
        1, cell_generation, cell_boxes, cell_last_texts, cell_lock,
    )
    fake._live_process_cell(
        1, [_fake_result("Hello")], "auto", "tr", "ollama", None,
        1, cell_generation, cell_boxes, cell_last_texts, cell_lock,
    )

    # _remember kendi ici tekillestirir (ayni metin tek kayit olarak kalir)
    # ama IKI KEZ cagirildigi icin zaman damgasi yenilenmis olmali.
    assert len(fake.recent) == 1
