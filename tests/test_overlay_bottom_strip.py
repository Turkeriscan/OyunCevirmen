"""
"Altyazı şeridi" (bottom_strip) overlay stili testleri (4.3): tum
cevirilerin orijinal konumlari ustune degil, TEK bir alt-ekran seridinde
birlesik gosterilmesi.

Gercek ekran gerektirmez (qapp fixture offscreen platformda calisir).
"""
from PyQt6 import QtCore, QtGui

from app.core.overlay import (OverlayWindow, TranslationBox, build_bottom_strip_text,
                               compute_bottom_strip_rect)


def _box(text, x, y):
    return TranslationBox(QtCore.QRect(x, y, 100, 20), text)


# ------------------------------------------------------------- build_bottom_strip_text
def test_build_bottom_strip_text_joins_in_reading_order():
    boxes = [_box("İkinci", 0, 100), _box("Birinci", 0, 10), _box("Üçüncü", 50, 100)]
    text = build_bottom_strip_text(boxes)
    assert text.split("/")[0].strip() == "Birinci"
    assert "İkinci" in text and "Üçüncü" in text
    assert text.index("İkinci") < text.index("Üçüncü")


def test_build_bottom_strip_text_empty_for_no_boxes():
    assert build_bottom_strip_text([]) == ""


def test_build_bottom_strip_text_skips_empty_text_boxes():
    boxes = [_box("", 0, 0), _box("Merhaba", 0, 10)]
    assert build_bottom_strip_text(boxes) == "Merhaba"


# ---------------------------------------------------------- compute_bottom_strip_rect
def test_compute_bottom_strip_rect_anchored_near_bottom():
    screen = QtCore.QRect(0, 0, 1920, 1080)
    rect = compute_bottom_strip_rect(screen)
    assert rect.bottom() < screen.bottom()
    assert rect.bottom() > screen.bottom() - int(screen.height() * 0.2)
    assert rect.width() < screen.width()
    assert rect.left() > 0


def test_compute_bottom_strip_rect_handles_tiny_screen_without_crashing():
    screen = QtCore.QRect(0, 0, 10, 10)
    rect = compute_bottom_strip_rect(screen)
    assert rect.width() >= 1
    assert rect.height() >= 1


# --------------------------------------------------------------- OverlayWindow
def test_paint_event_uses_bottom_strip_when_style_selected(qapp):
    """paintEvent patlamiyor ve bottom_strip secildiginde dogru yardimciya
    gidiyor mu - gercek QPainter cizimini dogrudan test etmek yerine,
    _paint_bottom_strip'in cagrildigini dogrulariz."""
    window = OverlayWindow({"overlay_style": "bottom_strip"})
    window.set_boxes([_box("Merhaba Dünya", 10, 10)])

    called = {}

    def fake_paint_bottom_strip(painter, now, out):
        called["yes"] = True

    window._paint_bottom_strip = fake_paint_bottom_strip
    window.paintEvent(QtGui.QPaintEvent(window.rect()))

    assert called.get("yes") is True


def test_paint_event_uses_normal_loop_for_other_styles(qapp):
    window = OverlayWindow({"overlay_style": "box"})
    window.set_boxes([_box("Merhaba Dünya", 10, 10)])

    called = {}
    window._paint_bottom_strip = lambda *a: called.setdefault("yes", True)
    window.paintEvent(QtGui.QPaintEvent(window.rect()))

    assert "yes" not in called
