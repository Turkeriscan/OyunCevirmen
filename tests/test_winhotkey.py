"""
app/core/winhotkey.py testleri (4.4): "ctrl+f9" gibi dizgelerin Win32
VK kodlarina cevrilmesi (parse_hotkey, saf fonksiyon) ve Win32HotkeyBridge'in
RegisterHotKey/UnregisterHotKey cagrilarini dogru yapmasi.

Gercek sistem capinda kisayol KAYDETMEZ: ctypes.windll.user32 mock'lanir.
"""
from unittest.mock import MagicMock, patch

from app.core import winhotkey


# ------------------------------------------------------------------- parse_hotkey
def test_parse_hotkey_simple_function_key():
    assert winhotkey.parse_hotkey("f9") == (0, winhotkey.VK_BY_NAME["f9"])


def test_parse_hotkey_with_single_modifier():
    mods, vk = winhotkey.parse_hotkey("ctrl+f9")
    assert mods == winhotkey.MOD_CONTROL
    assert vk == winhotkey.VK_BY_NAME["f9"]


def test_parse_hotkey_with_multiple_modifiers():
    mods, vk = winhotkey.parse_hotkey("ctrl+shift+a")
    assert mods == winhotkey.MOD_CONTROL | winhotkey.MOD_SHIFT
    assert vk == ord("A")


def test_parse_hotkey_case_insensitive():
    assert winhotkey.parse_hotkey("CTRL+F9") == winhotkey.parse_hotkey("ctrl+f9")


def test_parse_hotkey_rejects_empty_or_none():
    assert winhotkey.parse_hotkey("") is None
    assert winhotkey.parse_hotkey(None) is None


def test_parse_hotkey_rejects_unknown_key():
    assert winhotkey.parse_hotkey("ctrl+doesnotexist") is None


def test_parse_hotkey_rejects_unknown_modifier():
    assert winhotkey.parse_hotkey("super+f9") is None


def test_parse_hotkey_digits_and_letters():
    assert winhotkey.parse_hotkey("5") == (0, ord("5"))
    assert winhotkey.parse_hotkey("z") == (0, ord("Z"))


# -------------------------------------------------------------- Win32HotkeyBridge
def test_register_returns_empty_on_non_windows():
    bridge = winhotkey.Win32HotkeyBridge()
    with patch.object(winhotkey.os, "name", "posix"):
        result = bridge.register([("aninda", "f9", lambda: None)])
    assert result == []


def test_register_returns_empty_without_qapplication():
    bridge = winhotkey.Win32HotkeyBridge()
    fake_qtwidgets = MagicMock()
    fake_qtwidgets.QApplication.instance.return_value = None
    with patch.object(winhotkey.os, "name", "nt"), \
         patch.dict("sys.modules", {"PyQt6.QtWidgets": fake_qtwidgets}):
        result = bridge.register([("aninda", "f9", lambda: None)])
    assert result == []


def test_register_skips_unparseable_keys(qapp):
    bridge = winhotkey.Win32HotkeyBridge()
    with patch.object(winhotkey.ctypes, "windll") as fake_windll:
        fake_windll.user32.RegisterHotKey.return_value = 1
        result = bridge.register([("aninda", "not a real key!!!", lambda: None)])
    assert result == []
    bridge.unregister_all()


def test_register_calls_register_hotkey_for_each_valid_entry(qapp):
    bridge = winhotkey.Win32HotkeyBridge()
    with patch.object(winhotkey.ctypes, "windll") as fake_windll:
        fake_windll.user32.RegisterHotKey.return_value = 1
        result = bridge.register([
            ("aninda", "f9", lambda: None),
            ("canli", "f10", lambda: None),
        ])
    assert result == ["aninda=f9", "canli=f10"]
    assert fake_windll.user32.RegisterHotKey.call_count == 2
    bridge.unregister_all()


def test_register_reports_failure_silently_when_already_taken(qapp):
    bridge = winhotkey.Win32HotkeyBridge()
    with patch.object(winhotkey.ctypes, "windll") as fake_windll:
        fake_windll.user32.RegisterHotKey.return_value = 0  # basarisiz
        result = bridge.register([("aninda", "f9", lambda: None)])
    assert result == []
    bridge.unregister_all()


def test_unregister_all_calls_unregister_hotkey_for_each_registered(qapp):
    bridge = winhotkey.Win32HotkeyBridge()
    with patch.object(winhotkey.ctypes, "windll") as fake_windll:
        fake_windll.user32.RegisterHotKey.return_value = 1
        bridge.register([("aninda", "f9", lambda: None), ("canli", "f10", lambda: None)])
        bridge.unregister_all()
    assert fake_windll.user32.UnregisterHotKey.call_count == 2


def test_double_unregister_all_is_safe(qapp):
    bridge = winhotkey.Win32HotkeyBridge()
    bridge.unregister_all()
    bridge.unregister_all()  # istisna firlatmamali


def test_handler_invoked_on_wm_hotkey_message(qapp):
    """nativeEvent'in dogru handler'i WM_HOTKEY mesajindaki wParam'a
    (hotkey id) gore cagirdigini dogrular."""
    handler = MagicMock()
    with patch.object(winhotkey.ctypes, "windll") as fake_windll:
        fake_windll.user32.RegisterHotKey.return_value = 1
        bridge = winhotkey.Win32HotkeyBridge()
        bridge.register([("aninda", "f9", handler)])

    window = bridge._window
    assert window is not None
    hotkey_id = next(iter(window.handlers))

    msg = winhotkey._MSG()
    msg.message = winhotkey.WM_HOTKEY
    msg.wParam = hotkey_id
    address = winhotkey.ctypes.addressof(msg)
    window.nativeEvent(b"windows_generic_MSG", address)

    handler.assert_called_once()
    bridge.unregister_all()
