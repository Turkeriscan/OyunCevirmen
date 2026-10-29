"""
4.4 "Yönetici olarak yeniden başlat" testleri:
1) app/core/winhotkey.py relaunch_as_admin() - ShellExecuteW cagrisi,
   dondurulmus (.exe) / gelistirme (python -m) ortami farki, basari/hata.
2) Gelismis sayfasindaki buton - basarili olursa programi kapatmasi,
   basarisiz/iptal olursa kullaniciya bilgi vermesi.

Gercek UAC istemi gostermez (ctypes.windll.shell32 mock'lanir).
"""
from unittest.mock import MagicMock, patch

from app.core import capture as capture_mod
from app.core import winhotkey
from app.ui.pages.advanced import AdvancedPage


# ----------------------------------------------------------- relaunch_as_admin
def test_relaunch_returns_false_on_non_windows():
    with patch.object(winhotkey.os, "name", "posix"):
        assert winhotkey.relaunch_as_admin() is False


def test_relaunch_returns_true_on_shell_execute_success():
    with patch.object(winhotkey.os, "name", "nt"), \
         patch.object(winhotkey.ctypes, "windll") as fake_windll:
        fake_windll.shell32.ShellExecuteW.return_value = 42  # > 32 = basari
        assert winhotkey.relaunch_as_admin() is True


def test_relaunch_returns_false_on_shell_execute_failure_code():
    with patch.object(winhotkey.os, "name", "nt"), \
         patch.object(winhotkey.ctypes, "windll") as fake_windll:
        fake_windll.shell32.ShellExecuteW.return_value = 5  # ERROR_ACCESS_DENIED (kullanici reddetti)
        assert winhotkey.relaunch_as_admin() is False


def test_relaunch_returns_false_when_shell_execute_raises():
    with patch.object(winhotkey.os, "name", "nt"), \
         patch.object(winhotkey.ctypes, "windll") as fake_windll:
        fake_windll.shell32.ShellExecuteW.side_effect = RuntimeError("patlat")
        assert winhotkey.relaunch_as_admin() is False


def test_relaunch_includes_script_path_when_not_frozen():
    with patch.object(winhotkey.os, "name", "nt"), \
         patch.object(winhotkey.sys, "argv", ["C:\\OyunCevirmen\\app\\main.py"]), \
         patch.object(winhotkey.sys, "frozen", False, create=True), \
         patch.object(winhotkey.ctypes, "windll") as fake_windll:
        fake_windll.shell32.ShellExecuteW.return_value = 42
        winhotkey.relaunch_as_admin()
    params = fake_windll.shell32.ShellExecuteW.call_args[0][3]
    assert "main.py" in params


def test_relaunch_excludes_own_exe_path_when_frozen():
    """Dondurulmus (.exe) bir surumde sys.argv[0], sys.executable ile
    AYNIDIR - tekrar eklenirse parametre olarak kendi yolunu ikinci kez
    alirdi."""
    with patch.object(winhotkey.os, "name", "nt"), \
         patch.object(winhotkey.sys, "argv", ["C:\\OyunCevirmen.exe", "--foo"]), \
         patch.object(winhotkey.sys, "frozen", True, create=True), \
         patch.object(winhotkey.ctypes, "windll") as fake_windll:
        fake_windll.shell32.ShellExecuteW.return_value = 42
        winhotkey.relaunch_as_admin()
    params = fake_windll.shell32.ShellExecuteW.call_args[0][3]
    assert "OyunCevirmen.exe" not in params
    assert "--foo" in params


# ----------------------------------------------------------------- Advanced sayfasi
class _FakeCtx(MagicMock):
    def is_loading(self):
        return False


def _make_page():
    with patch.object(capture_mod, "list_monitors", return_value=[{"label": "Ekran 1", "index": 0}]):
        return AdvancedPage(_FakeCtx())


def test_relaunch_button_quits_app_on_success(qapp):
    page = _make_page()
    with patch.object(winhotkey, "relaunch_as_admin", return_value=True):
        page.btn_relaunch_admin.click()
    page.ctx.orchestrator.request_quit.assert_called_once()


def test_relaunch_button_flashes_message_on_failure(qapp):
    page = _make_page()
    with patch.object(winhotkey, "relaunch_as_admin", return_value=False):
        page.btn_relaunch_admin.click()
    page.ctx.orchestrator.request_quit.assert_not_called()
    page.ctx.flash.assert_called_once()
