"""
OCR modulu testleri: guven skoru tahmini, Windows OCR dil esleme/kurulu
dil kontrolu, kucuk yazi buyutme + koordinat geri olcekleme.

Gercek ekran kartina, Windows OCR'a veya internete ihtiyac duymaz;
winsdk/winocr cagrilari sahte (mock) nesnelerle degistirilir.
"""
from unittest.mock import patch

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

    frame = np.zeros((100, 200, 3), dtype=np.uint8)  # buyutulecek kadar kucuk
    results = manager.recognize(frame, offset=(500, 300))

    # Buyutulmus karedeki (20,40,220,80) -> 2'ye bolunur (10,20,110,40) -> +offset
    assert results[0].bbox == (510.0, 320.0, 610.0, 340.0)
