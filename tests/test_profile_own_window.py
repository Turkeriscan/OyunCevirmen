"""Kontrol paneline gecmek oyun degisimi sayilmamali (profil programa kaydedilmemeli)."""
import threading
import types

from app import main as m


def test_own_window_does_not_replace_current_game(monkeypatch):
    o = types.SimpleNamespace(_current_foreground_exe=None, synced=[])
    o._profile_poll_stop = threading.Event()
    o._sync_active_profile = lambda exe: o.synced.append(exe)
    seq = iter(["game.exe", "pythonw.exe", "pythonw.exe"])

    def fg():
        try:
            return next(seq)
        except StopIteration:
            o._profile_poll_stop.set()
            return None

    monkeypatch.setattr(m.activity_mod, "get_foreground_exe_name", fg)
    monkeypatch.setattr(m.activity_mod, "own_exe_name", lambda: "pythonw.exe")
    monkeypatch.setattr(m.profiles_mod, "POLL_INTERVAL_SECONDS", 0)
    m.Orchestrator._profile_poll_loop(o)
    assert o._current_foreground_exe == "game.exe"
    assert o.synced == ["game.exe"]
