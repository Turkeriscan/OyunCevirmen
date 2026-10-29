"""
app/core/overlay.py testleri (4.2): "tutma-ile-goster" kisayolu sirasinda
kutular SILINMEDEN aninda gizlenip, birakinca AYNI kutularla aninda geri
gelmesi (yeniden tarama gerekmeden).

Gercek ekran gerektirmez (qapp fixture offscreen platformda calisir).
"""
from PyQt6 import QtCore

from app.core.overlay import OverlayController, OverlayWindow, TranslationBox


def _box(text="Merhaba"):
    return TranslationBox(QtCore.QRect(10, 10, 100, 20), text)


# ---------------------------------------------------------------- OverlayWindow
def test_temporarily_hide_keeps_boxes_but_hides_window(qapp):
    window = OverlayWindow({})
    window.set_boxes([_box()])
    window.show()

    window.temporarily_hide()

    assert window.isVisible() is False
    assert window._boxes  # kutular SILINMEDI


def test_restore_after_reveal_shows_window_again(qapp):
    window = OverlayWindow({})
    window.set_boxes([_box()])
    window.show()
    window.temporarily_hide()

    window.restore_after_reveal()

    assert window.isVisible() is True
    assert window._boxes


def test_restore_after_reveal_does_nothing_without_boxes(qapp):
    """Hic kutu yoksa (orn. taramadan once tutulup birakildiysa), bos bir
    pencere gostermek yerine gizli kalmali."""
    window = OverlayWindow({})
    window.restore_after_reveal()
    assert window.isVisible() is False


# ------------------------------------------------------------- OverlayController
def test_controller_temp_hide_and_restore_threadsafe(qapp):
    controller = OverlayController(qapp, {})
    controller.show_boxes_threadsafe([_box()])
    QtCore.QCoreApplication.processEvents()
    assert controller.window.isVisible() is True

    controller.temporarily_hide_threadsafe()
    QtCore.QCoreApplication.processEvents()
    assert controller.window.isVisible() is False
    assert controller.window._boxes

    controller.restore_after_reveal_threadsafe()
    QtCore.QCoreApplication.processEvents()
    assert controller.window.isVisible() is True
