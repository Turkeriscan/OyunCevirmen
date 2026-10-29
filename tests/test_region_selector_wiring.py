"""
Orchestrator'daki bolge secici (3.5) baglama testleri (main.py):
kisayol/butonun GUI thread'ine guvenli gecisi, var olan pencerenin
yeniden olusturulmadan on plana alinmasi, ve secilen bolgelerin
config'e yazilip kaydedilmesi.

Gercek ekran/QWidget olusturmaz (RegionSelectorOverlay mock'lanir).
"""
from unittest.mock import MagicMock, patch

from app import main as main_mod


class _FakeOrchestrator:
    request_open_region_selector = main_mod.Orchestrator.request_open_region_selector
    _open_region_selector_on_gui_thread = main_mod.Orchestrator._open_region_selector_on_gui_thread
    _clear_region_selector_ref = main_mod.Orchestrator._clear_region_selector_ref
    _save_regions = main_mod.Orchestrator._save_regions

    def __init__(self):
        self.bridge = MagicMock()
        self.config = {"exclude_regions": [], "include_regions": []}
        self._region_selector = None


def test_request_open_region_selector_emits_signal():
    """Kisayol kancasi ayri bir thread'de calisir; QWidget sadece GUI
    thread'inde olusturulabilecegi icin sinyal uzerinden gecis yapilmali."""
    fake = _FakeOrchestrator()
    fake.request_open_region_selector()
    fake.bridge.open_region_selector_signal.emit.assert_called_once()


def test_open_region_selector_creates_overlay_and_shows_fullscreen():
    fake = _FakeOrchestrator()
    fake.config["exclude_regions"] = [{"left": 0, "top": 0, "width": 10, "height": 10}]

    fake_widget = MagicMock()
    with patch("app.ui.regionoverlay.RegionSelectorOverlay", return_value=fake_widget) as ctor:
        fake._open_region_selector_on_gui_thread()

    ctor.assert_called_once()
    args, kwargs = ctor.call_args
    assert args[0] == fake.config["exclude_regions"]
    assert args[1] == fake.config["include_regions"]
    assert kwargs["on_done"] == fake._save_regions
    fake_widget.showFullScreen.assert_called_once()
    assert fake._region_selector is fake_widget


def test_open_region_selector_reuses_existing_instance_instead_of_recreating():
    """Kisayola/butona TEKRAR basilirsa, ikinci bir pencere ACILMAMALI -
    var olani on plana getirmek yeterli."""
    fake = _FakeOrchestrator()
    existing = MagicMock()
    fake._region_selector = existing

    with patch("app.ui.regionoverlay.RegionSelectorOverlay") as ctor:
        fake._open_region_selector_on_gui_thread()

    ctor.assert_not_called()
    existing.raise_.assert_called_once()
    existing.activateWindow.assert_called_once()


def test_clear_region_selector_ref_resets_to_none():
    fake = _FakeOrchestrator()
    fake._region_selector = MagicMock()
    fake._clear_region_selector_ref()
    assert fake._region_selector is None


def test_save_regions_writes_config_and_persists():
    fake = _FakeOrchestrator()
    exclude = [{"left": 0, "top": 0, "width": 5, "height": 5}]
    include = [{"left": 10, "top": 10, "width": 5, "height": 5}]

    with patch.object(main_mod.config_mod, "save_config") as save:
        fake._save_regions(exclude, include)

    assert fake.config["exclude_regions"] == exclude
    assert fake.config["include_regions"] == include
    save.assert_called_once_with(fake.config)
