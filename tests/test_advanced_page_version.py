"""
Gelismis sayfasindaki surum etiketi testi (5.2): mevcut surumun
(app.__version__) sayfada gosterilmesi.

Gercek ekran/monitor listesi gerektirmez (capture_mod.list_monitors mock'lanir).
"""
from unittest.mock import MagicMock, patch

from app import __version__ as APP_VERSION
from app.core import capture as capture_mod
from app.ui.pages.advanced import AdvancedPage


class _FakeCtx(MagicMock):
    def is_loading(self):
        return False


def test_version_label_shows_current_version(qapp):
    with patch.object(capture_mod, "list_monitors", return_value=[{"label": "Ekran 1", "index": 0}]):
        page = AdvancedPage(_FakeCtx())
    assert APP_VERSION in page.lbl_version.text()
