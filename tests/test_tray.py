"""
app/core/tray.py testleri: buyuk altyazi penceresi (4.3) tepsi menusu
girdisinin etiketlenmesi ve tiklaninca dogru callback'i cagirmasi.

Gercek sistem tepsisi simgesi baslatmaz (TrayApp.start() hic cagrilmaz).
"""
from unittest.mock import MagicMock

from app.core.tray import TrayApp


def _make_tray(**status_overrides):
    status = {"ocr_engine": "windows", "translate_engine": "ollama",
              "live_active": False, "mini_visible": False, "big_subtitle_visible": False}
    status.update(status_overrides)
    on_toggle_big_subtitle = MagicMock()
    tray = TrayApp(
        config={}, status_provider=lambda: status,
        on_toggle_live=MagicMock(), on_instant=MagicMock(), on_quit=MagicMock(),
        on_toggle_big_subtitle=on_toggle_big_subtitle,
    )
    return tray, on_toggle_big_subtitle


def test_big_subtitle_label_shows_when_hidden():
    tray, _ = _make_tray(big_subtitle_visible=False)
    assert "göster" in tray._big_subtitle_label(None)


def test_big_subtitle_label_shows_when_visible():
    tray, _ = _make_tray(big_subtitle_visible=True)
    assert "gizle" in tray._big_subtitle_label(None)


def test_toggle_big_subtitle_calls_callback():
    tray, callback = _make_tray()
    tray._toggle_big_subtitle()
    callback.assert_called_once()


def test_toggle_big_subtitle_safe_when_callback_missing():
    tray = TrayApp(
        config={}, status_provider=lambda: {"big_subtitle_visible": False},
        on_toggle_live=MagicMock(), on_instant=MagicMock(), on_quit=MagicMock(),
    )
    tray._toggle_big_subtitle()  # istisna firlatmamali


def test_build_menu_includes_big_subtitle_item():
    tray, _ = _make_tray()
    menu = tray._build_menu()
    labels = [getattr(item, "text", None) for item in menu.items]
    # pystray MenuItem.text ya sabit bir dize ya da cagrilabilir bir fonksiyondur
    resolved = [t(None) if callable(t) else t for t in labels]
    assert any("altyazı" in (r or "").lower() for r in resolved)
