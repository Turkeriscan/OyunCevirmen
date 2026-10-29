"""
OCR modulu testleri: guven skoru tahmini, Windows OCR dil esleme/kurulu
dil kontrolu, kucuk yazi buyutme + koordinat geri olcekleme.

Gercek ekran kartina, Windows OCR'a veya internete ihtiyac duymaz;
winsdk/winocr cagrilari sahte (mock) nesnelerle degistirilir.
"""
import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.core import ocr


# ------------------------------------------------------------- guven tahmini
def test_confidence_high_for_clean_text():
    score = ocr.estimate_windows_ocr_confidence("Inventory is full", box_height=24)
    assert score > 0.7


def test_confidence_low_for_garbled_text():
    garbled = ocr.estimate_windows_ocr_confidence("#@%^&*()_+~`", box_height=24)
    clean = ocr.estimate_windows_ocr_confidence("Inventory is full", box_height=24)
    assert garbled < clean


def test_confidence_lower_for_tiny_box():
    tiny = ocr.estimate_windows_ocr_confidence("Press E", box_height=8)
    normal = ocr.estimate_windows_ocr_confidence("Press E", box_height=22)
    assert tiny < normal


def test_confidence_empty_text_is_zero():
    assert ocr.estimate_windows_ocr_confidence("", box_height=20) == 0.0
    assert ocr.estimate_windows_ocr_confidence(None, box_height=20) == 0.0


def test_confidence_bounded():
    assert 0.0 <= ocr.estimate_windows_ocr_confidence("A", box_height=1) <= 1.0
    assert 0.0 <= ocr.estimate_windows_ocr_confidence("Hello World, this is great!", box_height=40) <= 1.0


def test_confidence_threshold_actually_filters():
    """Arayuzdeki 'okuma guveni esigi' ayarinin bu motorda da ise yaradigini
    dogrular: garip/bozuk metin esigin altinda kalmali."""
    from app.core import textfilter
    garbled_conf = ocr.estimate_windows_ocr_confidence("][}{##", box_height=24)
    assert not textfilter.should_translate("][}{##", confidence=garbled_conf, min_confidence=0.45)


# ------------------------------------------------------------- dil esleme
@pytest.mark.parametrize("ui_code, expected_tag", [
    ("auto", "en-US"),
    ("en", "en-US"),
    ("de", "de-DE"),
    ("fr", "fr-FR"),
    ("es", "es-ES"),
    ("it", "it-IT"),
    ("pt", "pt-PT"),
    ("ru", "ru-RU"),
    ("ja", "ja-JP"),
    ("ko", "ko-KR"),
    ("zh-cn", "zh-Hans"),
    ("tr", "tr-TR"),
])
def test_windows_ocr_tag_mapping(ui_code, expected_tag):
    assert ocr.windows_ocr_tag_for(ui_code) == expected_tag


def test_windows_ocr_tag_unknown_code_passthrough():
    assert ocr.windows_ocr_tag_for("xx") == "xx"


def test_windows_ocr_available_languages_handles_failure_gracefully():
    """winsdk/winrt cagrisi herhangi bir sebeple patlarsa (eksik modul,
    COM hatasi vb.) program cokmemeli, sessizce bos kume donmeli."""
    import sys
    with patch.dict(sys.modules, {"winsdk.windows.media.ocr": None}):
        langs = ocr.windows_ocr_available_languages()
    assert langs == set()


def test_windows_ocr_available_languages_lowercases_tags():
    fake_lang = type("L", (), {"language_tag": "en-US"})()
    fake_module = type("M", (), {
        "OcrEngine": type("E", (), {"available_recognizer_languages": [fake_lang]})
    })()
    import sys
    with patch.dict(sys.modules, {"winsdk.windows.media.ocr": fake_module}):
        langs = ocr.windows_ocr_available_languages()
    assert langs == {"en-us"}


def test_is_windows_ocr_language_installed_true_when_tag_present():
    with patch("app.core.ocr.windows_ocr_available_languages", return_value={"en-us"}):
        assert ocr.is_windows_ocr_language_installed("en") is True
        assert ocr.is_windows_ocr_language_installed("de") is False


def test_is_windows_ocr_language_installed_defaults_true_when_list_unknown():
    """Dil listesi hic alinamiyorsa (bos kume) kullaniciyi bosu bosuna
    engellememek icin True donmeli."""
    with patch("app.core.ocr.windows_ocr_available_languages", return_value=set()):
        assert ocr.is_windows_ocr_language_installed("ja") is True


# --------------------------------------------------------- kucuk yazi buyutme
def test_maybe_upscale_disabled_returns_same_frame():
    frame = np.zeros((50, 50, 3), dtype=np.uint8)
    out, factor = ocr.maybe_upscale(frame, enabled=False)
    assert factor == 1.0
    assert out is frame


def test_maybe_upscale_enabled_doubles_small_frame():
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    out, factor = ocr.maybe_upscale(frame, enabled=True)
    assert factor == 2.0
    assert out.shape[0] == 200
    assert out.shape[1] == 400


def test_maybe_upscale_skips_large_frame_for_performance():
    """Tam ekran gibi buyuk kareler 4 kat islem yuku bindirmesin diye
    buyutulmemeli."""
    frame = np.zeros((1200, 1900, 3), dtype=np.uint8)  # > 1_000_000 piksel
    out, factor = ocr.maybe_upscale(frame, enabled=True)
    assert factor == 1.0
    assert out is frame


def test_rescale_results_converts_bbox_back_to_original_scale():
    results = [ocr.OCRBoxResult("Merhaba", 0.9, (20, 40, 220, 80))]
    rescaled = ocr.rescale_results(results, 2.0)
    assert rescaled[0].bbox == (10.0, 20.0, 110.0, 40.0)
    assert rescaled[0].text == "Merhaba"
    assert rescaled[0].confidence == 0.9


def test_rescale_results_noop_for_factor_one():
    results = [ocr.OCRBoxResult("Merhaba", 0.9, (20, 40, 220, 80))]
    assert ocr.rescale_results(results, 1.0) is results


def test_ocr_manager_recognize_applies_offset_after_rescale():
    """OCRManager.recognize: buyutulmus karedeki koordinatlar once gercek
    olcege donsun, asil offset SADECE ondan sonra eklensin (aksi halde
    offset de yanlislikla 2 kat buyurdu)."""
    class _FakeEngine:
        def recognize(self, frame_bgr, offset=(0, 0)):
            assert offset == (0, 0)  # OCRManager motoru hep (0,0) ile cagirmali
            return [ocr.OCRBoxResult("Test", 0.9, (20, 40, 220, 80))]

    class _FakeConfig(dict):
        pass

    cfg = _FakeConfig(ocr_engine="windows", ocr_upscale_small_text=True)
    manager = ocr.OCRManager(cfg)
    manager._engine = _FakeEngine()
    manager._engine_name = "windows"
    manager._engine_lang = "auto"

    frame = np.zeros((100, 200, 3), dtype=np.uint8)  # buyutulecek kadar kucuk
    results = manager.recognize(frame, offset=(500, 300))

    # Buyutulmus karedeki (20,40,220,80) -> 2'ye bolunur (10,20,110,40) -> +offset
    assert results[0].bbox == (510.0, 320.0, 610.0, 340.0)


# ------------------------------------------------- motor degisince GPU temizligi
def test_release_engine_noop_for_non_easyocr():
    """windows/paddle motoru birakilirken torch'a hic dokunulmamali."""
    fake_engine = type("E", (), {"name": "windows"})()
    with patch("builtins.__import__") as fake_import:
        ocr.OCRManager._release_engine(fake_engine)
        # torch import edilmeye CALISILMAMALI (easyocr degil)
        torch_calls = [c for c in fake_import.call_args_list if c.args and c.args[0] == "torch"]
        assert not torch_calls


def test_release_engine_empties_cuda_cache_for_easyocr():
    fake_reader = MagicMock()
    fake_engine = type("E", (), {"name": "easyocr", "reader": fake_reader})()

    fake_torch = MagicMock()
    fake_torch.cuda.is_available.return_value = True

    with patch.dict("sys.modules", {"torch": fake_torch}):
        ocr.OCRManager._release_engine(fake_engine)

    fake_torch.cuda.empty_cache.assert_called_once()


def test_release_engine_handles_none_gracefully():
    ocr.OCRManager._release_engine(None)  # istisna firlatmamali


def test_get_engine_releases_old_engine_on_switch():
    """OCR motoru degistiginde eski motor (GPU bellegi serbest birakilsin
    diye) release edilmeli."""
    cfg = {"ocr_engine": "windows", "source_lang": "auto"}
    manager = ocr.OCRManager(cfg)

    fake_old = MagicMock()
    fake_old.name = "easyocr"
    manager._engine = fake_old
    manager._engine_name = "easyocr"

    with patch.object(ocr.OCRManager, "_build_engine", return_value=MagicMock(name="windows_engine")), \
         patch.object(ocr.OCRManager, "_release_engine") as release:
        manager.get_engine()

    release.assert_called_once_with(fake_old)


# ------------------------------------- dil degisince motor yeniden kurulmali
def test_get_engine_rebuilds_when_source_lang_changes():
    """Motor turu (ocr_engine) AYNI kalsa bile, "Oyunun dili" ayari
    degisince motor yeniden kurulmali - aksi halde WindowsOCREngine/
    EasyOCREngine kurulurkenki ESKI dili sessizce kullanmaya devam ederdi."""
    cfg = {"ocr_engine": "windows", "source_lang": "en"}
    manager = ocr.OCRManager(cfg)

    with patch.object(ocr.OCRManager, "_build_engine",
                       side_effect=lambda wanted: MagicMock(name=f"engine-{wanted}")) as build:
        first = manager.get_engine()
        cfg["source_lang"] = "de"
        second = manager.get_engine()

    assert build.call_count == 2
    assert first is not second


def test_get_engine_does_not_rebuild_when_nothing_changed():
    cfg = {"ocr_engine": "windows", "source_lang": "en"}
    manager = ocr.OCRManager(cfg)

    with patch.object(ocr.OCRManager, "_build_engine",
                       return_value=MagicMock(name="engine")) as build:
        first = manager.get_engine()
        second = manager.get_engine()

    assert build.call_count == 1
    assert first is second


def test_get_engine_releases_old_engine_when_only_lang_changes():
    fake_old = MagicMock()
    fake_old.name = "easyocr"
    cfg = {"ocr_engine": "easyocr", "source_lang": "en"}
    manager = ocr.OCRManager(cfg)
    manager._engine = fake_old
    manager._engine_name = "easyocr"
    manager._engine_lang = "en"

    with patch.object(ocr.OCRManager, "_build_engine", return_value=MagicMock(name="new_engine")), \
         patch.object(ocr.OCRManager, "_release_engine") as release:
        cfg["source_lang"] = "ja"
        manager.get_engine()

    release.assert_called_once_with(fake_old)


# --------------------------------------------------------------- RapidOCR (3.1)
def test_rapidocr_engine_converts_results_to_ocr_box_results():
    fake_rapidocr_instance = MagicMock()
    fake_rapidocr_instance.return_value = (
        [
            ([[10, 10], [110, 10], [110, 40], [10, 40]], "Hello World", 0.95),
            ([[0, 0], [5, 0], [5, 5], [0, 5]], "", 0.2),  # bos metin elenmeli
        ],
        0.123,
    )
    fake_module = type("M", (), {"RapidOCR": MagicMock(return_value=fake_rapidocr_instance)})()

    with patch.dict(sys.modules, {"rapidocr_onnxruntime": fake_module}):
        engine = ocr.RapidOCREngine()
        results = engine.recognize(np.zeros((50, 150, 3), dtype=np.uint8), offset=(100, 200))

    assert len(results) == 1
    assert results[0].text == "Hello World"
    assert results[0].confidence == 0.95
    assert results[0].bbox == (110.0, 210.0, 210.0, 240.0)


def test_rapidocr_engine_handles_recognition_exception_gracefully():
    fake_rapidocr_instance = MagicMock(side_effect=RuntimeError("patlat"))
    fake_module = type("M", (), {"RapidOCR": MagicMock(return_value=fake_rapidocr_instance)})()

    with patch.dict(sys.modules, {"rapidocr_onnxruntime": fake_module}):
        engine = ocr.RapidOCREngine()
        results = engine.recognize(np.zeros((50, 150, 3), dtype=np.uint8))

    assert results == []


def test_rapidocr_engine_handles_empty_results():
    fake_rapidocr_instance = MagicMock(return_value=(None, 0.0))
    fake_module = type("M", (), {"RapidOCR": MagicMock(return_value=fake_rapidocr_instance)})()

    with patch.dict(sys.modules, {"rapidocr_onnxruntime": fake_module}):
        engine = ocr.RapidOCREngine()
        results = engine.recognize(np.zeros((50, 150, 3), dtype=np.uint8))

    assert results == []


def test_build_engine_falls_back_to_windows_when_rapidocr_unavailable():
    """RapidOCR kurulu degilse (gercek ortamda genelde oyle), sessizce
    Windows OCR'a donulmeli - programi cokertmemeli."""
    cfg = {"ocr_engine": "rapidocr", "source_lang": "auto"}
    manager = ocr.OCRManager(cfg)

    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "rapidocr_onnxruntime":
            raise ImportError("kurulu degil")
        return real_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        engine = manager.get_engine()

    assert engine.name == "windows"
