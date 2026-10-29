"""
3.5 "disinda birak / sadece burayi oku" bolgeleri testleri:

1) app/core/regions.py: saf is_bbox_excluded() karar fonksiyonu.
2) Orchestrator._ocr_and_filter (main.py): config'teki exclude_regions/
   include_regions'in OCR sonuclarini gercekten elemesi.

Gercek ekran/OCR/Ollama gerektirmez.
"""
from unittest.mock import MagicMock

from app import main as main_mod
from app.core import regions
from app.core.ocr import OCRBoxResult


# ------------------------------------------------------------- is_bbox_excluded
def test_no_regions_means_nothing_excluded():
    assert regions.is_bbox_excluded((0, 0, 10, 10), [], []) is False


def test_excluded_when_center_inside_exclude_region():
    bbox = (10, 10, 30, 30)  # merkez (20,20)
    exclude = [{"left": 0, "top": 0, "width": 100, "height": 100}]
    assert regions.is_bbox_excluded(bbox, exclude, []) is True


def test_not_excluded_when_center_outside_exclude_region():
    bbox = (200, 200, 220, 220)  # merkez (210,210)
    exclude = [{"left": 0, "top": 0, "width": 100, "height": 100}]
    assert regions.is_bbox_excluded(bbox, exclude, []) is False


def test_include_mode_excludes_everything_outside_whitelist():
    bbox = (200, 200, 220, 220)
    include = [{"left": 0, "top": 0, "width": 100, "height": 100}]
    assert regions.is_bbox_excluded(bbox, [], include) is True


def test_include_mode_keeps_boxes_inside_whitelist():
    bbox = (10, 10, 30, 30)
    include = [{"left": 0, "top": 0, "width": 100, "height": 100}]
    assert regions.is_bbox_excluded(bbox, [], include) is False


def test_exclude_wins_even_inside_include_region():
    """Bir bolge AYNI ANDA hem 'sadece burayi oku' alaninin icinde hem de
    'disinda birak' alaninin icinde kaliyorsa, DISLAMA kazanmali (orn.
    buyuk bir 'sadece oku' alani icinde kucuk bir 'okunmasin' kosesi)."""
    bbox = (10, 10, 20, 20)  # merkez (15,15)
    include = [{"left": 0, "top": 0, "width": 100, "height": 100}]
    exclude = [{"left": 0, "top": 0, "width": 50, "height": 50}]
    assert regions.is_bbox_excluded(bbox, exclude, include) is True


# ------------------------------------------------ Orchestrator._ocr_and_filter
class _FakeOrchestrator:
    _ocr_and_filter = main_mod.Orchestrator._ocr_and_filter

    def __init__(self, config):
        self.config = config
        self.ocr_manager = MagicMock()


def test_ocr_and_filter_drops_results_inside_exclude_region():
    results = [
        OCRBoxResult("Hello there friend", 0.9, (10, 10, 200, 40)),   # disarida tutulan bolgede
        OCRBoxResult("Good morning everyone", 0.9, (500, 500, 700, 540)),  # serbest alanda
    ]
    fake = _FakeOrchestrator({
        "source_lang": "en", "min_text_length": 2, "min_ocr_confidence": 0.0,
        "exclude_regions": [{"left": 0, "top": 0, "width": 300, "height": 300}],
        "include_regions": [],
    })
    fake.ocr_manager.recognize.return_value = results

    survivors = fake._ocr_and_filter(MagicMock(), offset=(0, 0))

    assert [r.text for r in survivors] == ["Good morning everyone"]


def test_ocr_and_filter_include_region_keeps_only_whitelisted():
    results = [
        OCRBoxResult("Hello there friend", 0.9, (10, 10, 200, 40)),
        OCRBoxResult("Good morning everyone", 0.9, (500, 500, 700, 540)),
    ]
    fake = _FakeOrchestrator({
        "source_lang": "en", "min_text_length": 2, "min_ocr_confidence": 0.0,
        "exclude_regions": [],
        "include_regions": [{"left": 0, "top": 0, "width": 300, "height": 300}],
    })
    fake.ocr_manager.recognize.return_value = results

    survivors = fake._ocr_and_filter(MagicMock(), offset=(0, 0))

    assert [r.text for r in survivors] == ["Hello there friend"]


def test_ocr_and_filter_no_regions_configured_keeps_everything():
    results = [OCRBoxResult("Hello there friend", 0.9, (10, 10, 200, 40))]
    fake = _FakeOrchestrator({
        "source_lang": "en", "min_text_length": 2, "min_ocr_confidence": 0.0,
        "exclude_regions": [], "include_regions": [],
    })
    fake.ocr_manager.recognize.return_value = results

    survivors = fake._ocr_and_filter(MagicMock(), offset=(0, 0))

    assert [r.text for r in survivors] == ["Hello there friend"]
