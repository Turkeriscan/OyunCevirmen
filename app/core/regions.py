"""
"Burayi okuma" / "sadece burayi oku" bolgeleri (3.5). Bolgeler masaustu
MUTLAK piksel koordinatinda saklanir ({"left","top","width","height"}) -
boylece OCR sonuclarinin bbox'u (zaten mutlak ekran koordinatinda, bkz.
Orchestrator._ocr_and_filter) ile dogrudan karsilastirilabilir.

Karar, bir OCR sonucunun bbox'unun MERKEZ noktasina gore verilir - kismi
(kenardan biraz tasan) ortusmeler yuzunden kafa karistirici "yari
disarida" durumlar olmasin diye.
"""


def region_to_rect(region):
    left = region["left"]
    top = region["top"]
    return (left, top, left + region["width"], top + region["height"])


def _rect_contains_point(rect, x, y):
    l, t, r, b = rect
    return l <= x <= r and t <= y <= b


def is_bbox_excluded(bbox, exclude_regions, include_regions):
    """Bir OCR sonucunun bu taramada GORMEZDEN GELINIP gelinmeyecegine
    karar verir.

    include_regions BOS DEGILSE: bbox'un merkezi bu bolgelerden HICBIRINE
    denk gelmiyorsa disarida tutulur (beyaz liste modu).
    Ayrica (include modunda da) exclude_regions icine denk gelen bbox'lar
    her zaman disarida tutulur."""
    if not exclude_regions and not include_regions:
        return False

    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0

    if include_regions:
        inside_include = any(
            _rect_contains_point(region_to_rect(r), cx, cy) for r in include_regions
        )
        if not inside_include:
            return True

    return any(_rect_contains_point(region_to_rect(r), cx, cy) for r in exclude_regions)
