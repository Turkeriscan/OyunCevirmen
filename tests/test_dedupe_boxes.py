"""
_dedupe_boxes / _rects_overlap testleri (main.py): komsu/ortusen ekran
parcalarinin AYNI yaziyi (bazen farkli uzunlukta kirpilmis, orn.
"HELLO WORLD" / "O WORLD") birden fazla kez cevirip ustuste iki kutu
cizmesini onler. Gercek QApplication gerekmez: QRect, QApplication
olmadan da kullanilabilir.
"""
from PyQt6 import QtCore

from app.core.overlay import TranslationBox
from app.main import _dedupe_boxes, _rects_overlap


def _box(x, y, w, h, text):
    return TranslationBox(QtCore.QRect(x, y, w, h), text)


# ------------------------------------------------------------- _rects_overlap
def test_rects_overlap_disjoint_rects_false():
    a = QtCore.QRect(0, 0, 10, 10)
    b = QtCore.QRect(100, 100, 10, 10)
    assert _rects_overlap(a, b) is False


def test_rects_overlap_identical_rects_true():
    a = QtCore.QRect(0, 0, 10, 10)
    b = QtCore.QRect(0, 0, 10, 10)
    assert _rects_overlap(a, b) is True


def test_rects_overlap_below_threshold_false():
    """Kucuk bir kesisim (esigin altinda) ortusme sayilmamali."""
    a = QtCore.QRect(0, 0, 100, 100)
    b = QtCore.QRect(95, 95, 100, 100)  # sadece 5x5 kesisim, min alanin %0.25'i
    assert _rects_overlap(a, b, threshold=0.4) is False


def test_rects_overlap_above_threshold_true():
    a = QtCore.QRect(0, 0, 100, 100)
    b = QtCore.QRect(0, 0, 50, 100)  # b'nin tamami a'nin icinde -> oran 1.0
    assert _rects_overlap(a, b, threshold=0.4) is True


def test_rects_overlap_zero_area_rect_false():
    """Sifir genislik/yukseklikli bir dikdortgen sifira bolme hatasi
    yaratmamali."""
    a = QtCore.QRect(0, 0, 0, 0)
    b = QtCore.QRect(0, 0, 10, 10)
    assert _rects_overlap(a, b) is False


# -------------------------------------------------------------- _dedupe_boxes
def test_dedupe_boxes_no_overlap_keeps_both():
    boxes = [_box(0, 0, 50, 20, "Hello"), _box(200, 200, 50, 20, "World")]
    result = _dedupe_boxes(boxes)
    assert len(result) == 2


def test_dedupe_boxes_full_overlap_keeps_longer_text():
    """Iki komsu hucre AYNI yaziyi farkli tamlıkta okumus olabilir
    (orn. kirpilmis 'O WORLD' vs tam 'HELLO WORLD'); fiziksel olarak
    ortusen kutulardan en UZUN metinli olan tutulmali."""
    short = _box(0, 0, 100, 20, "O WORLD")
    long_ = _box(0, 0, 100, 20, "HELLO WORLD")
    result = _dedupe_boxes([short, long_])
    assert len(result) == 1
    assert result[0].text == "HELLO WORLD"


def test_dedupe_boxes_partial_overlap_above_threshold_removes_shorter():
    a = _box(0, 0, 100, 100, "Kisa")
    b = _box(0, 0, 100, 100, "Daha uzun bir metin burada")
    result = _dedupe_boxes([a, b])
    assert len(result) == 1
    assert result[0].text == "Daha uzun bir metin burada"


def test_dedupe_boxes_disjoint_cells_all_kept():
    boxes = [
        _box(0, 0, 50, 20, "Inventory full"),
        _box(300, 0, 50, 20, "Press E to open"),
        _box(0, 300, 50, 20, "Game Over"),
    ]
    result = _dedupe_boxes(boxes)
    assert len(result) == 3


def test_dedupe_boxes_three_overlapping_keeps_only_longest():
    a = _box(0, 0, 100, 20, "A")
    b = _box(0, 0, 100, 20, "AB")
    c = _box(0, 0, 100, 20, "ABC")
    result = _dedupe_boxes([a, b, c])
    assert len(result) == 1
    assert result[0].text == "ABC"


def test_dedupe_boxes_empty_list_returns_empty():
    assert _dedupe_boxes([]) == []
