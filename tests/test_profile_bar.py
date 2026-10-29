"""
Sahne sayfasindaki ProfileBar (4.1) testleri: su an tespit edilen oyunun
gosterilmesi, "Profili kaydet/güncelle/sil" butonlarinin orchestrator'u
dogru cagirmasi, "Profiller açık/kapalı" acma/kapamanin calismasi.

Gercek ekran/Windows API gerektirmez (orchestrator mock'lanir).
"""
from unittest.mock import MagicMock

from app.ui.pages.scene import ProfileBar


class _FakeCtx:
    def __init__(self):
        self.orchestrator = MagicMock()
        self.orchestrator.config = {"game_profiles_enabled": True, "game_profiles": {}}
        self.orchestrator._current_foreground_exe = None
        self.orchestrator._active_profile_exe = None
        self.flash_messages = []

    def is_loading(self):
        return False

    def flash(self, text):
        self.flash_messages.append(text)


def test_label_shows_no_game_detected_when_no_foreground(qapp):
    ctx = _FakeCtx()
    bar = ProfileBar(ctx)
    bar.refresh()
    assert bar.lbl.text() == "Oyun tespit edilemedi"
    assert bar.btn_save.isEnabled() is False
    assert bar.btn_delete.isEnabled() is False


def test_label_shows_no_profile_for_detected_game(qapp):
    ctx = _FakeCtx()
    ctx.orchestrator._current_foreground_exe = "game.exe"
    bar = ProfileBar(ctx)
    bar.refresh()
    assert "profil yok" in bar.lbl.text()
    assert bar.btn_save.text() == "Profili kaydet"
    assert bar.btn_delete.isEnabled() is False


def test_label_shows_profile_applied_when_active(qapp):
    ctx = _FakeCtx()
    ctx.orchestrator._current_foreground_exe = "game.exe"
    ctx.orchestrator._active_profile_exe = "game.exe"
    ctx.orchestrator.config["game_profiles"] = {"game.exe": {}}
    bar = ProfileBar(ctx)
    bar.refresh()
    assert "uygulanıyor" in bar.lbl.text()
    assert bar.btn_save.text() == "Profili güncelle"
    assert bar.btn_delete.isEnabled() is True


def test_save_button_calls_orchestrator_with_current_exe(qapp):
    ctx = _FakeCtx()
    ctx.orchestrator._current_foreground_exe = "game.exe"
    bar = ProfileBar(ctx)

    bar.btn_save.click()

    ctx.orchestrator.save_current_as_profile.assert_called_once_with("game.exe")
    assert any("game.exe" in m for m in ctx.flash_messages)


def test_save_button_does_nothing_without_detected_game(qapp):
    ctx = _FakeCtx()
    bar = ProfileBar(ctx)

    bar.btn_save.click()

    ctx.orchestrator.save_current_as_profile.assert_not_called()
    assert ctx.flash_messages  # kullaniciya aciklama gosterildi


def test_delete_button_calls_orchestrator(qapp):
    ctx = _FakeCtx()
    ctx.orchestrator._current_foreground_exe = "game.exe"
    ctx.orchestrator.delete_profile.return_value = True
    bar = ProfileBar(ctx)

    bar.btn_delete.click()

    ctx.orchestrator.delete_profile.assert_called_once_with("game.exe")


def test_toggle_combo_calls_set_game_profiles_enabled(qapp):
    ctx = _FakeCtx()
    bar = ProfileBar(ctx)

    i = bar.combo_enabled.findData(False)
    bar.combo_enabled.setCurrentIndex(i)

    ctx.orchestrator.set_game_profiles_enabled.assert_called_once_with(False)


def test_toggle_combo_does_nothing_while_loading(qapp):
    ctx = _FakeCtx()
    ctx.is_loading = lambda: True
    bar = ProfileBar(ctx)

    i = bar.combo_enabled.findData(False)
    bar.combo_enabled.setCurrentIndex(i)

    ctx.orchestrator.set_game_profiles_enabled.assert_not_called()
