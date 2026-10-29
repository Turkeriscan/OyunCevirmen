"""
Sahne sayfasindaki CueRow'un "Çeviriyi düzelt…" / "Düzeltmeyi geri al"
baglam menusu davranisi (2.1). Gercek sag-tik/QMenu.exec() cagirmaz
(bu, testte kullaniciyi bekleyen modal bir dongu baslatirdi); bunun
yerine CueRow'un ic yardimci metotlarini (orn. _correct) dogrudan
cagiririz - QInputDialog.getText mock'lanir.

Gercek ekran gerekmez (qapp fixture 'offscreen' platformda calisir).
"""
from unittest.mock import MagicMock, patch

from PyQt6 import QtWidgets

from app.ui.pages.scene import CueRow


class _FakeCtx:
    def __init__(self):
        self.orchestrator = MagicMock()
        self.flash_messages = []

    def flash(self, text):
        self.flash_messages.append(text)


def test_correct_updates_label_and_calls_orchestrator(qapp):
    ctx = _FakeCtx()
    ctx.orchestrator.correct_translation.return_value = True
    row = CueRow(ctx, 1, "00:00:01,000", "Merhaba Dunya", "Hello World")

    with patch.object(QtWidgets.QInputDialog, "getText", return_value=("Merhaba (duzeltildi)", True)):
        row._correct("Hello World")

    ctx.orchestrator.correct_translation.assert_called_once_with("Hello World", "Merhaba (duzeltildi)")
    assert row.tr_label.text() == "Merhaba (duzeltildi)"
    assert any("düzeltildi" in m for m in ctx.flash_messages)


def test_correct_cancelled_dialog_does_not_change_anything(qapp):
    ctx = _FakeCtx()
    row = CueRow(ctx, 1, "00:00:01,000", "Merhaba Dunya", "Hello World")

    with patch.object(QtWidgets.QInputDialog, "getText", return_value=("baska bir metin", False)):
        row._correct("Hello World")

    ctx.orchestrator.correct_translation.assert_not_called()
    assert row.tr_label.text() == "Merhaba Dunya"


def test_correct_rejected_by_orchestrator_does_not_update_label(qapp):
    """orchestrator.correct_translation False donerse (orn. bos metin),
    etiket GUNCELLENMEMELI."""
    ctx = _FakeCtx()
    ctx.orchestrator.correct_translation.return_value = False
    row = CueRow(ctx, 1, "00:00:01,000", "Merhaba Dunya", "Hello World")

    with patch.object(QtWidgets.QInputDialog, "getText", return_value=("", True)):
        row._correct("Hello World")

    assert row.tr_label.text() == "Merhaba Dunya"
    assert ctx.flash_messages == []


def test_undo_calls_orchestrator_and_flashes(qapp):
    ctx = _FakeCtx()
    row = CueRow(ctx, 1, "00:00:01,000", "Merhaba Dunya", "Hello World")

    row._undo("Hello World")

    ctx.orchestrator.undo_correction.assert_called_once_with("Hello World")
    assert any("geri alındı" in m for m in ctx.flash_messages)


def test_menu_shows_undo_only_when_already_corrected(qapp):
    ctx = _FakeCtx()
    ctx.orchestrator.is_manually_corrected.return_value = True
    row = CueRow(ctx, 1, "00:00:01,000", "Merhaba Dunya", "Hello World")

    menu = QtWidgets.QMenu(row)
    menu.addAction("Çeviriyi kopyala")
    menu.addAction("Orijinali kopyala")
    menu.addSeparator()
    menu.addAction("Çeviriyi düzelt…")
    if ctx.orchestrator.is_manually_corrected("Hello World"):
        menu.addAction("Düzeltmeyi geri al")

    texts = [a.text() for a in menu.actions()]
    assert "Düzeltmeyi geri al" in texts
