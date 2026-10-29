"""
app/core/activity.py testleri (3.4): canli modun ne zaman duraklatilacagina
karar veren saf fonksiyon (should_pause_live) ve Windows ctypes cagrilarinin
hataya karsi dayanikliligi. Gercek Windows API'lerine ihtiyac duymaz.
"""
from unittest.mock import MagicMock, patch

from app.core import activity


# ------------------------------------------------------- should_pause_live
def test_disabled_never_pauses():
    assert activity.should_pause_live("game.exe", 0.0, "game.exe", "python.exe", False) is False
    assert activity.should_pause_live(None, 9999.0, None, "python.exe", False) is False


def test_pauses_when_idle_past_threshold():
    assert activity.should_pause_live("game.exe", 120.0, "game.exe", "python.exe", True,
                                       idle_threshold_seconds=120) is True


def test_does_not_pause_when_idle_below_threshold():
    assert activity.should_pause_live("game.exe", 10.0, "game.exe", "python.exe", True,
                                       idle_threshold_seconds=120) is False


def test_does_not_pause_when_game_is_foreground():
    assert activity.should_pause_live("game.exe", 0.0, "game.exe", "python.exe", True) is False


def test_does_not_pause_when_own_app_is_foreground():
    """Kullanici ayar penceresine (kendi uygulamasina) gecince canli mod
    yanlislikla 'oyun arka planda' sanilip duraklatilmamali."""
    assert activity.should_pause_live("python.exe", 0.0, "game.exe", "python.exe", True) is False


def test_pauses_when_some_other_app_is_foreground():
    assert activity.should_pause_live("discord.exe", 0.0, "game.exe", "python.exe", True) is True


def test_does_not_pause_when_foreground_unknown():
    """Tespit edilemezse (None) GUVENLI TARAFTA kalinir - yanlis pozitifle
    cevirinin bosu bosuna kesilmemesi icin duraklatilmaz."""
    assert activity.should_pause_live(None, 0.0, "game.exe", "python.exe", True) is False


def test_does_not_pause_when_game_exe_unknown():
    assert activity.should_pause_live("discord.exe", 0.0, None, "python.exe", True) is False


# -------------------------------------------------------- own_exe_name
def test_own_exe_name_returns_lowercase_basename():
    with patch("app.core.activity.sys") as fake_sys:
        fake_sys.executable = "C:\\OyunCevirmen\\venv\\Scripts\\PYTHON.EXE"
        assert activity.own_exe_name() == "python.exe"


def test_own_exe_name_handles_exception_gracefully():
    with patch("app.core.activity.sys") as fake_sys:
        fake_sys.executable = None
        with patch("app.core.activity.os.path.basename", side_effect=RuntimeError("patlat")):
            assert activity.own_exe_name() == ""


class _NoWindll:
    """ctypes.windll'e erisimin patladigi (orn. Windows disi platform) bir
    ortami simule eder."""

    @property
    def windll(self):
        raise AttributeError("windll yok")


# -------------------------------------------------- get_foreground_exe_name
def test_get_foreground_exe_name_handles_missing_ctypes_gracefully():
    """ctypes.windll herhangi bir sebeple patlarsa (orn. Windows disi bir
    ortam) sessizce None donmeli, program cokmemeli."""
    with patch("app.core.activity.ctypes", _NoWindll()):
        assert activity.get_foreground_exe_name() is None


def test_get_foreground_exe_name_returns_none_when_no_window():
    fake_user32 = MagicMock()
    fake_user32.GetForegroundWindow.return_value = 0
    fake_windll = MagicMock(user32=fake_user32, kernel32=MagicMock())
    with patch("app.core.activity.ctypes.windll", fake_windll):
        assert activity.get_foreground_exe_name() is None


# -------------------------------------------------------- get_idle_seconds
def test_get_idle_seconds_handles_missing_ctypes_gracefully():
    with patch("app.core.activity.ctypes", _NoWindll()):
        assert activity.get_idle_seconds() == 0.0


def test_get_idle_seconds_returns_zero_when_api_call_fails():
    fake_user32 = MagicMock()
    fake_user32.GetLastInputInfo.return_value = 0  # basarisiz
    fake_windll = MagicMock(user32=fake_user32, kernel32=MagicMock())

    with patch("app.core.activity.ctypes.windll", fake_windll):
        assert activity.get_idle_seconds() == 0.0


def test_get_idle_seconds_is_never_negative():
    """GetTickCount tasarsal olarak dwTime'dan kucuk donerse (kuramsal uç
    durum) negatif sure yerine 0.0 donmeli."""
    fake_user32 = MagicMock()
    fake_user32.GetLastInputInfo.return_value = 1
    fake_kernel32 = MagicMock()
    fake_kernel32.GetTickCount.return_value = 0
    fake_windll = MagicMock(user32=fake_user32, kernel32=fake_kernel32)

    with patch("app.core.activity.ctypes.windll", fake_windll):
        assert activity.get_idle_seconds() >= 0.0
