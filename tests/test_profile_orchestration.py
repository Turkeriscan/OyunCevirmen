"""
Orchestrator'daki oyun profili (4.1) baglama testleri (main.py):
_sync_active_profile'in config'i gercekten degistirmesi, save/delete/
enable-disable islemlerinin config.json'a yazilip translator'un aktif
sozlugunu guncellemesi.

Gercek ekran/Windows API/Ollama gerektirmez.
"""
from unittest.mock import MagicMock, patch

from app import main as main_mod


class _FakeOrchestrator:
    _sync_active_profile = main_mod.Orchestrator._sync_active_profile
    save_current_as_profile = main_mod.Orchestrator.save_current_as_profile
    delete_profile = main_mod.Orchestrator.delete_profile
    set_game_profiles_enabled = main_mod.Orchestrator.set_game_profiles_enabled

    def __init__(self, config):
        self.config = config
        self.translator = MagicMock()
        self.translator.active_profile_glossary = None
        self._active_profile_exe = None
        self._profile_base_snapshot = None
        self._current_foreground_exe = None


def _base_config(**overrides):
    cfg = {
        "ocr_engine": "windows", "source_lang": "auto", "overlay_style": "box",
        "exclude_regions": [], "include_regions": [],
        "game_profiles_enabled": True, "game_profiles": {},
    }
    cfg.update(overrides)
    return cfg


def test_sync_applies_profile_when_game_detected():
    cfg = _base_config(game_profiles={"game.exe": {"ocr_engine": "easyocr", "source_lang": "ja"}})
    fake = _FakeOrchestrator(cfg)

    with patch.object(main_mod.activity_mod, "get_foreground_exe_name", return_value="game.exe"):
        fake._sync_active_profile("game.exe")

    assert fake.config["ocr_engine"] == "easyocr"
    assert fake.config["source_lang"] == "ja"
    assert fake._active_profile_exe == "game.exe"


def test_sync_restores_global_settings_when_game_loses_focus():
    cfg = _base_config(game_profiles={"game.exe": {"ocr_engine": "easyocr"}})
    fake = _FakeOrchestrator(cfg)
    fake._sync_active_profile("game.exe")
    assert fake.config["ocr_engine"] == "easyocr"

    fake._sync_active_profile(None)  # oyun artik on planda degil

    assert fake.config["ocr_engine"] == "windows"  # genel ayara dondu
    assert fake._active_profile_exe is None


def test_sync_sets_translator_glossary_from_profile():
    glossary = [{"source": "Ldhen", "target": "", "no_translate": True}]
    cfg = _base_config(game_profiles={"game.exe": {"glossary": glossary}})
    fake = _FakeOrchestrator(cfg)

    fake._sync_active_profile("game.exe")

    assert fake.translator.active_profile_glossary == glossary


def test_sync_clears_translator_glossary_when_leaving_profile():
    cfg = _base_config(game_profiles={"game.exe": {"glossary": [{"source": "X", "target": "Y",
                                                                  "no_translate": False}]}})
    fake = _FakeOrchestrator(cfg)
    fake._sync_active_profile("game.exe")
    assert fake.translator.active_profile_glossary

    fake._sync_active_profile(None)

    assert fake.translator.active_profile_glossary is None


def test_sync_disabled_never_applies_profile():
    cfg = _base_config(game_profiles_enabled=False,
                        game_profiles={"game.exe": {"ocr_engine": "easyocr"}})
    fake = _FakeOrchestrator(cfg)

    fake._sync_active_profile("game.exe")

    assert fake.config["ocr_engine"] == "windows"
    assert fake._active_profile_exe is None


def test_malformed_glossary_entry_is_sanitized_not_crashed():
    """Elle bozulmus (orn. 'source' alani eksik) bir profil sozlugu
    translate() cagrisinda KeyError firlatmasin diye sessizce temizlenmeli."""
    cfg = _base_config(game_profiles={"game.exe": {"glossary": [{"bad": "entry"}]}})
    fake = _FakeOrchestrator(cfg)

    fake._sync_active_profile("game.exe")

    assert not fake.translator.active_profile_glossary  # temizlenince bos kaldi


# --------------------------------------------------------- save/delete/enable
def test_save_current_as_profile_snapshots_live_config():
    cfg = _base_config(ocr_engine="easyocr", source_lang="ja")
    fake = _FakeOrchestrator(cfg)

    with patch.object(main_mod.glossary_mod, "load_glossary", return_value=[]), \
         patch.object(main_mod.config_mod, "save_config") as save:
        ok = fake.save_current_as_profile("game.exe")

    assert ok is True
    assert fake.config["game_profiles"]["game.exe"]["ocr_engine"] == "easyocr"
    assert fake.config["game_profiles"]["game.exe"]["source_lang"] == "ja"
    save.assert_called_once_with(fake.config)


def test_save_current_as_profile_rejects_empty_exe():
    fake = _FakeOrchestrator(_base_config())
    assert fake.save_current_as_profile("") is False
    assert fake.save_current_as_profile(None) is False


def test_delete_profile_removes_entry_and_restores_if_active():
    cfg = _base_config(game_profiles={"game.exe": {"ocr_engine": "easyocr"}})
    fake = _FakeOrchestrator(cfg)
    fake._sync_active_profile("game.exe")
    assert fake.config["ocr_engine"] == "easyocr"

    with patch.object(main_mod.config_mod, "save_config"):
        ok = fake.delete_profile("game.exe")

    assert ok is True
    assert "game.exe" not in fake.config["game_profiles"]
    assert fake.config["ocr_engine"] == "windows"  # genel ayara donuldu
    assert fake._active_profile_exe is None


def test_delete_profile_returns_false_when_missing():
    fake = _FakeOrchestrator(_base_config())
    assert fake.delete_profile("yok.exe") is False


def test_set_game_profiles_enabled_persists_and_resyncs():
    cfg = _base_config(game_profiles={"game.exe": {"ocr_engine": "easyocr"}})
    fake = _FakeOrchestrator(cfg)
    fake._current_foreground_exe = "game.exe"

    with patch.object(main_mod.config_mod, "save_config") as save:
        fake.set_game_profiles_enabled(True)

    assert fake.config["game_profiles_enabled"] is True
    assert fake.config["ocr_engine"] == "easyocr"  # hemen uygulandi
    save.assert_called_once_with(fake.config)
