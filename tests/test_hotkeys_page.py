"""
Kisayollar sayfasi testleri: 3.5/4.2 ile eklenen "Bölge çiz" ve "Orijinali
göster" satirlarinin load/save dongusunde dogru calistigini dogrular -
ACTIONS listesine eklenen her yeni kisayol otomatik olarak bir satir,
yukleme/kaydetme ve cakisma kontrolu kazanir.

Gercek klavye kancasi kurmaz.
"""
from unittest.mock import MagicMock

from app.ui.pages.hotkeys import HotkeysPage


class _FakeCtx:
    def __init__(self):
        self.pause_hotkeys = MagicMock()
        self.resume_hotkeys = MagicMock()
        self.schedule_save = MagicMock()


def test_new_actions_get_a_recorder_row(qapp):
    page = HotkeysPage(_FakeCtx())
    assert "hotkey_region_select" in page.recorders
    assert "hotkey_hold_reveal" in page.recorders


def test_load_sets_recorder_values(qapp):
    page = HotkeysPage(_FakeCtx())
    page.load({"hotkey_region_select": "f7", "hotkey_hold_reveal": "f5"})
    assert page.recorders["hotkey_region_select"].value() == "f7"
    assert page.recorders["hotkey_hold_reveal"].value() == "f5"


def test_load_falls_back_to_default_when_missing(qapp):
    page = HotkeysPage(_FakeCtx())
    page.load({})
    assert page.recorders["hotkey_region_select"].value() == "f8"
    assert page.recorders["hotkey_hold_reveal"].value() == "f6"


def test_save_writes_all_recorder_values(qapp):
    page = HotkeysPage(_FakeCtx())
    page.recorders["hotkey_region_select"].set_value("f7")
    page.recorders["hotkey_hold_reveal"].set_value("f5")
    cfg = {}
    page.save(cfg)
    assert cfg["hotkey_region_select"] == "f7"
    assert cfg["hotkey_hold_reveal"] == "f5"


def test_conflict_detected_between_new_and_existing_hotkey(qapp):
    page = HotkeysPage(_FakeCtx())
    page.recorders["hotkey_hold_reveal"].set_value("f9")  # aninda ile ayni
    page._check_conflicts()
    assert page.warning.text() != ""
