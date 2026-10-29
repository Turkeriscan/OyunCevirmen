"""
HotkeyManager testleri: config.json'da bir kisayol gecersiz bir dizgeye
donusmus olsa bile DIGER kisayollarin kayit olmaya devam ettigini
dogrular (daha once tek bir hata TUM kayitlari iptal ediyordu).

Gercek klavye kancasi kurmaz: 'keyboard' modulu sahte (mock) ile
degistirilir.
"""
from unittest.mock import MagicMock, patch

from app.core import hotkeys as hotkeys_mod


def test_all_hotkeys_register_when_all_valid():
    config = {"hotkey_instant": "f9", "hotkey_live_toggle": "f10", "hotkey_quit": "f11"}
    mgr = hotkeys_mod.HotkeyManager(config, lambda: None, lambda: None, lambda: None)

    with patch.object(hotkeys_mod.keyboard, "add_hotkey", return_value="hook") as add:
        mgr.start()

    assert add.call_count == 3
    assert len(mgr._hooks) == 3


def test_one_invalid_hotkey_does_not_block_others():
    """Ortadaki (canli) kisayol kaydi patlarsa, aninda VE cikis kisayollari
    yine de kaydolmali - ozellikle F11 (cikis) her zaman denenmeli."""
    config = {"hotkey_instant": "f9", "hotkey_live_toggle": "!!!gecersiz!!!", "hotkey_quit": "f11"}
    mgr = hotkeys_mod.HotkeyManager(config, lambda: None, lambda: None, lambda: None)

    def fake_add(key, handler):
        if key == "!!!gecersiz!!!":
            raise ValueError("bilinmeyen tus")
        return f"hook-{key}"

    with patch.object(hotkeys_mod.keyboard, "add_hotkey", side_effect=fake_add):
        mgr.start()  # ValueError disariya sizmamali

    assert len(mgr._hooks) == 2
    assert "hook-f9" in mgr._hooks
    assert "hook-f11" in mgr._hooks


def test_quit_hotkey_registers_even_if_instant_fails():
    config = {"hotkey_instant": "gecersiz", "hotkey_live_toggle": "f10", "hotkey_quit": "f11"}
    mgr = hotkeys_mod.HotkeyManager(config, lambda: None, lambda: None, lambda: None)

    def fake_add(key, handler):
        if key == "gecersiz":
            raise RuntimeError("patlat")
        return f"hook-{key}"

    with patch.object(hotkeys_mod.keyboard, "add_hotkey", side_effect=fake_add):
        mgr.start()

    assert "hook-f11" in mgr._hooks


def test_all_hotkeys_invalid_does_not_raise():
    """En kotu durumda (uc kisayol da gecersiz) program yine de cokmemeli."""
    config = {"hotkey_instant": "a", "hotkey_live_toggle": "b", "hotkey_quit": "c"}
    mgr = hotkeys_mod.HotkeyManager(config, lambda: None, lambda: None, lambda: None)

    with patch.object(hotkeys_mod.keyboard, "add_hotkey", side_effect=RuntimeError("patlat")):
        mgr.start()  # istisna firlatmamali

    assert mgr._hooks == []


def test_region_select_hotkey_registers_when_handler_provided():
    config = {"hotkey_instant": "f9", "hotkey_live_toggle": "f10", "hotkey_quit": "f11",
              "hotkey_region_select": "f8"}
    mgr = hotkeys_mod.HotkeyManager(config, lambda: None, lambda: None, lambda: None,
                                     on_region_select=lambda: None)

    with patch.object(hotkeys_mod.keyboard, "add_hotkey", return_value="hook") as add:
        mgr.start()

    assert add.call_count == 4
    assert len(mgr._hooks) == 4


def test_region_select_hotkey_not_registered_when_handler_omitted():
    """Eski (3.5 oncesi) cagiranlarla uyumluluk: on_region_select
    verilmezse SADECE 3 kisayol kaydolmali, hata verilmemeli."""
    config = {"hotkey_instant": "f9", "hotkey_live_toggle": "f10", "hotkey_quit": "f11"}
    mgr = hotkeys_mod.HotkeyManager(config, lambda: None, lambda: None, lambda: None)

    with patch.object(hotkeys_mod.keyboard, "add_hotkey", return_value="hook") as add:
        mgr.start()

    assert add.call_count == 3


def test_safe_wrapper_catches_handler_exceptions():
    """Bir kisayolun ISLEVI (orn. toggle_instant) hata verirse, klavye
    kancasinin kendisi cokmemeli (keyboard kutuphanesi sessizce patlardi)."""
    config = {"hotkey_instant": "f9", "hotkey_live_toggle": "f10", "hotkey_quit": "f11"}
    boom = MagicMock(side_effect=RuntimeError("patlat"))
    mgr = hotkeys_mod.HotkeyManager(config, boom, lambda: None, lambda: None)

    wrapped = mgr._safe(boom)
    wrapped()  # istisna disariya sizmamali
    boom.assert_called_once()
