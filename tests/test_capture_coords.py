"""
Cok monitor koordinat donusumu testleri.

Gercek ekran kartina/monitore ihtiyac duymaz: dxcam/mss nesneleri sahte
(mock) olarak kurulur, sadece saf koordinat matematigi ve ScreenCapturer'in
backend'e gore dogru 'origin' (sanal masaustundeki sol-ust kose) degerini
bulup bulmadigi dogrulanir.
"""
import types
from unittest.mock import MagicMock, patch

import pytest

from app.core import capture


# --------------------------------------------------------------- saf fonksiyon
@pytest.mark.parametrize(
    "bbox, origin, expected",
    [
        # Birincil monitor, origin (0,0): degisiklik olmamali
        ((10, 20, 110, 60), (0, 0), (10, 20, 110, 60)),
        # Ikincil monitor saga konumlanmis (yaygin durum: 1920,0)
        ((10, 20, 110, 60), (1920, 0), (1930, 20, 2030, 60)),
        # Ikincil monitor SOLA konumlanmis -> NEGATIF origin
        ((10, 20, 110, 60), (-1920, 0), (-1910, 20, -1810, 60)),
        # Ikincil monitor USTE konumlanmis -> negatif Y
        ((0, 0, 50, 50), (0, -1080), (0, -1080, 50, -1030)),
        # Hem X hem Y negatif (sol-ust capraz yerlesim)
        ((100, 100, 200, 150), (-1920, -200), (-1820, -100, -1720, -50)),
    ],
)
def test_to_virtual_desktop(bbox, origin, expected):
    assert capture.to_virtual_desktop(bbox, origin) == expected


def test_to_virtual_desktop_is_pure():
    """Ayni girdiyle her zaman ayni sonuc; girdi degistirilmez."""
    bbox = (5, 5, 25, 25)
    origin = (100, 200)
    r1 = capture.to_virtual_desktop(bbox, origin)
    r2 = capture.to_virtual_desktop(bbox, origin)
    assert r1 == r2 == (105, 205, 125, 225)
    assert bbox == (5, 5, 25, 25)  # girdi bozulmadi


# --------------------------------------------------------- dxcam origin okuma
def _fake_dxcam_camera(left, top, right, bottom):
    cam = MagicMock()
    rect = types.SimpleNamespace(left=left, top=top, right=right, bottom=bottom)
    desc = types.SimpleNamespace(DesktopCoordinates=rect)
    output = types.SimpleNamespace(desc=desc)
    cam._output = output
    return cam


def test_dxcam_output_origin_reads_desktop_coordinates():
    cam = _fake_dxcam_camera(1920, 0, 3840, 1080)
    assert capture._dxcam_output_origin(cam) == (1920, 0)


def test_dxcam_output_origin_negative_coordinates():
    cam = _fake_dxcam_camera(-1920, -200, 0, 880)
    assert capture._dxcam_output_origin(cam) == (-1920, -200)


def test_dxcam_output_origin_returns_none_on_failure():
    """Ic API degisirse (ornegin dxcam guncellenirse) sessizce None donup
    cagiran taraf mss'e yedeklenebilsin; cokmemeli."""
    broken_camera = object()  # _output ozniteligi hic yok
    assert capture._dxcam_output_origin(broken_camera) is None


def test_mss_monitor_origin():
    mon = {"left": 1920, "top": 0, "width": 1920, "height": 1080}
    assert capture._mss_monitor_origin(mon) == (1920, 0)


def test_mss_monitor_origin_missing_keys_defaults_zero():
    assert capture._mss_monitor_origin({}) == (0, 0)


# -------------------------------------------------- ScreenCapturer entegrasyonu
class _FakeMssMonitor(dict):
    pass


def _make_fake_mss(monitors):
    """mss.mss() yerine gececek sahte nesne; context manager da destekler."""
    fake = MagicMock()
    fake.monitors = monitors
    fake.__enter__ = MagicMock(return_value=fake)
    fake.__exit__ = MagicMock(return_value=False)
    fake.close = MagicMock()
    return fake


def test_screen_capturer_mss_backend_sets_origin_for_second_monitor():
    """dxcam yokmus gibi davranip mss yoluna dusur; ikinci monitorun
    (saga konumlu) orijininin dogru okundugunu dogrular."""
    monitors = [
        {"left": 0, "top": 0, "width": 3840, "height": 1080},        # 0: birlesik
        {"left": 0, "top": 0, "width": 1920, "height": 1080},        # 1: birincil
        {"left": 1920, "top": 0, "width": 1920, "height": 1080},     # 2: ikincil (sagda)
    ]
    fake_mss_instance = _make_fake_mss(monitors)

    with patch.object(capture, "_DXCAM_AVAILABLE", False), \
         patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        cap = capture.ScreenCapturer(monitor_index=1)  # ikinci fiziksel monitor

    assert cap.backend == "mss"
    assert cap.get_origin() == (1920, 0)


def test_screen_capturer_mss_backend_negative_origin():
    """Ikincil monitor birincilin SOLUNDA duruyorsa negatif X verir."""
    monitors = [
        {"left": -1920, "top": 0, "width": 3840, "height": 1080},
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": -1920, "top": 0, "width": 1920, "height": 1080},
    ]
    fake_mss_instance = _make_fake_mss(monitors)

    with patch.object(capture, "_DXCAM_AVAILABLE", False), \
         patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        cap = capture.ScreenCapturer(monitor_index=1)

    assert cap.get_origin() == (-1920, 0)


def test_screen_capturer_dxcam_backend_uses_dxgi_origin():
    """dxcam kullanilabiliyorsa, konum DXGI DesktopCoordinates'ten gelmeli
    (mss'e hic danisilmamali)."""
    fake_cam = _fake_dxcam_camera(1920, 0, 3840, 1080)
    fake_cam.grab.return_value = object()  # test yakalamasi None donmesin

    fake_dxcam_module = MagicMock()
    fake_dxcam_module.create.return_value = fake_cam

    with patch.object(capture, "_DXCAM_AVAILABLE", True), \
         patch.object(capture, "dxcam", fake_dxcam_module, create=True):
        cap = capture.ScreenCapturer(monitor_index=1)

    assert cap.backend == "dxcam"
    assert cap.get_origin() == (1920, 0)
    fake_dxcam_module.create.assert_called_once()


def test_screen_capturer_dxcam_falls_back_to_mss_origin_when_dxgi_unavailable():
    """dxcam'in ic API'si degisip origin okunamasa bile (None donerse),
    program cokmeden mss uzerinden konumu bulabilmeli."""
    fake_cam = MagicMock()
    fake_cam.grab.return_value = object()
    del fake_cam._output  # DesktopCoordinates okumasi basarisiz olsun

    fake_dxcam_module = MagicMock()
    fake_dxcam_module.create.return_value = fake_cam

    monitors = [
        {"left": 0, "top": 0, "width": 3840, "height": 1080},
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    ]
    fake_mss_instance = _make_fake_mss(monitors)

    with patch.object(capture, "_DXCAM_AVAILABLE", True), \
         patch.object(capture, "dxcam", fake_dxcam_module, create=True), \
         patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        cap = capture.ScreenCapturer(monitor_index=1)

    assert cap.backend == "dxcam"
    assert cap.get_origin() == (1920, 0)
