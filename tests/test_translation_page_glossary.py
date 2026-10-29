"""
TranslationPage'teki "Sözlük" tablosu testleri (2.2): satir ekleme/silme,
hucre duzenleme sonucu glossary.json'a yazilmasi, CSV ice/disa aktarma.

glossary.GLOSSARY_PATH bir tmp_path'e yonlendirilir ki testler GERCEK
glossary.json dosyasina dokunmasin. Gercek ekran gerekmez (qapp fixture).
"""
from unittest.mock import MagicMock, patch

import pytest
from PyQt6 import QtCore, QtWidgets

from app.core import glossary as glossary_mod
from app.ui.pages.translation import TranslationPage


class _FakeCtx:
    def __init__(self):
        self.config = {
            "ocr_engine": "windows", "translate_engine": "ollama",
            "ollama_model": "aya-expanse:8b", "ollama_host": "http://127.0.0.1:11434",
            "source_lang": "auto", "allow_google_fallback": None,
        }
        self._loading = 0
        self.orchestrator = MagicMock()
        self.flash_messages = []

    def is_loading(self):
        return self._loading > 0

    def schedule_save(self, *_):
        pass

    def flash(self, text):
        self.flash_messages.append(text)


@pytest.fixture
def isolated_glossary(tmp_path, monkeypatch):
    path = tmp_path / "glossary.json"
    monkeypatch.setattr(glossary_mod, "GLOSSARY_PATH", str(path))
    monkeypatch.setattr(glossary_mod, "_cached", None)
    yield path
    monkeypatch.setattr(glossary_mod, "_cached", None)


def test_table_starts_empty_when_no_glossary_file(qapp, isolated_glossary):
    page = TranslationPage(_FakeCtx())
    assert page.table_glossary.rowCount() == 0


def test_table_loads_existing_entries(qapp, isolated_glossary):
    glossary_mod.save_glossary([{"source": "Ldhen", "target": "Ldhen Hazretleri", "no_translate": False}])
    page = TranslationPage(_FakeCtx())
    assert page.table_glossary.rowCount() == 1
    assert page.table_glossary.item(0, 0).text() == "Ldhen"
    assert page.table_glossary.item(0, 1).text() == "Ldhen Hazretleri"
    assert page.table_glossary.item(0, 2).checkState() == QtCore.Qt.CheckState.Unchecked


def test_add_row_then_edit_saves_to_glossary(qapp, isolated_glossary):
    page = TranslationPage(_FakeCtx())
    page._glossary_add_row()
    page.table_glossary.item(0, 0).setText("Ldhen")
    page.table_glossary.item(0, 1).setText("Ldhen Hazretleri")

    saved = glossary_mod.load_glossary()
    assert saved == [{"source": "Ldhen", "target": "Ldhen Hazretleri", "no_translate": False}]


def test_checking_no_translate_clears_target_on_save(qapp, isolated_glossary):
    page = TranslationPage(_FakeCtx())
    page._glossary_add_row()
    page.table_glossary.item(0, 0).setText("Ldhen")
    page.table_glossary.item(0, 1).setText("gormezden gelinecek")
    page.table_glossary.item(0, 2).setCheckState(QtCore.Qt.CheckState.Checked)

    saved = glossary_mod.load_glossary()
    assert saved == [{"source": "Ldhen", "target": "", "no_translate": True}]


def test_rows_without_source_are_not_saved(qapp, isolated_glossary):
    page = TranslationPage(_FakeCtx())
    page._glossary_add_row()  # kaynak bos birakildi
    assert glossary_mod.load_glossary() == []


def test_remove_selected_row_deletes_entry(qapp, isolated_glossary):
    glossary_mod.save_glossary([{"source": "Ldhen", "target": "x", "no_translate": False}])
    page = TranslationPage(_FakeCtx())
    page.table_glossary.setCurrentCell(0, 0)
    page._glossary_remove_selected()

    assert page.table_glossary.rowCount() == 0
    assert glossary_mod.load_glossary() == []


def test_export_csv_writes_expected_rows(qapp, isolated_glossary, tmp_path):
    glossary_mod.save_glossary([
        {"source": "Ldhen", "target": "Ldhen Hazretleri", "no_translate": False},
        {"source": "Gurme", "target": "", "no_translate": True},
    ])
    page = TranslationPage(_FakeCtx())
    out_path = tmp_path / "export.csv"

    with patch.object(QtWidgets.QFileDialog, "getSaveFileName", return_value=(str(out_path), "")):
        page._glossary_export_csv()

    content = out_path.read_text(encoding="utf-8-sig")
    assert "Ldhen" in content and "Ldhen Hazretleri" in content
    assert "Gurme" in content and ",1" in content


def test_import_csv_adds_entries_and_reloads_table(qapp, isolated_glossary, tmp_path):
    import csv
    csv_path = tmp_path / "import.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "target", "no_translate"])
        writer.writeheader()
        writer.writerow({"source": "Ldhen", "target": "Ldhen Hazretleri", "no_translate": "0"})

    page = TranslationPage(_FakeCtx())
    with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(str(csv_path), "")):
        page._glossary_import_csv()

    assert page.table_glossary.rowCount() == 1
    assert glossary_mod.load_glossary() == [
        {"source": "Ldhen", "target": "Ldhen Hazretleri", "no_translate": False}
    ]


def test_import_csv_merges_with_existing_entries_by_source(qapp, isolated_glossary, tmp_path):
    glossary_mod.save_glossary([{"source": "Ldhen", "target": "eski", "no_translate": False}])
    import csv
    csv_path = tmp_path / "import2.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source", "target", "no_translate"])
        writer.writeheader()
        writer.writerow({"source": "Ldhen", "target": "yeni", "no_translate": "0"})

    page = TranslationPage(_FakeCtx())
    with patch.object(QtWidgets.QFileDialog, "getOpenFileName", return_value=(str(csv_path), "")):
        page._glossary_import_csv()

    saved = glossary_mod.load_glossary()
    assert len(saved) == 1
    assert saved[0]["target"] == "yeni"
