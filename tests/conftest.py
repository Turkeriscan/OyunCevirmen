"""
Ortak pytest fixture'lari. PyQt6 widget'lari test edebilmek icin tek bir
QApplication ornegi (offscreen - ekranda pencere acip yanip sonmesin).
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6 import QtWidgets


@pytest.fixture(scope="session")
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    yield app
