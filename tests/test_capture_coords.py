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


# ------------------------------------- dxcam<->mss monitor eslestirme (1.6)
def test_find_matching_dxcam_output_matches_by_position():
    target = {"left": 1920, "top": 0, "width": 1920, "height": 1080}
    outputs = [
        (0, 0, (0, 0), (1920, 1080)),
        (0, 1, (1920, 0), (1920, 1080)),
    ]
    assert capture._find_matching_dxcam_output(target, outputs) == (0, 1)


def test_find_matching_dxcam_output_rejects_resolution_mismatch():
    """Ayni konumda ama FARKLI cozunurlukte bir cikis (suphelidir,
    muhtemelen farkli bir ekran) eslesme SAYILMAMALI."""
    target = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    outputs = [(0, 0, (0, 0), (2560, 1440))]
    assert capture._find_matching_dxcam_output(target, outputs) is None


def test_find_matching_dxcam_output_none_when_no_outputs():
    target = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    assert capture._find_matching_dxcam_output(target, []) is None


def test_find_matching_dxcam_output_none_for_none_target():
    assert capture._find_matching_dxcam_output(None, [(0, 0, (0, 0), (1920, 1080))]) is None


def test_find_matching_dxcam_output_skips_unreadable_origin():
    target = {"left": 0, "top": 0, "width": 1920, "height": 1080}
    outputs = [(0, 0, None, None), (0, 1, (0, 0), (1920, 1080))]
    assert capture._find_matching_dxcam_output(target, outputs) == (0, 1)


def test_get_monitor_identity_returns_position_and_resolution():
    monitors = [
        {"left": 0, "top": 0, "width": 3840, "height": 1080},
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    ]
    fake_mss_instance = _make_fake_mss(monitors)
    with patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        identity = capture.get_monitor_identity(1)
    assert identity == {"left": 1920, "top": 0, "width": 1920, "height": 1080}


def test_get_monitor_identity_out_of_range_returns_none():
    monitors = [{"left": 0, "top": 0, "width": 3840, "height": 1080},
                {"left": 0, "top": 0, "width": 1920, "height": 1080}]
    fake_mss_instance = _make_fake_mss(monitors)
    with patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        assert capture.get_monitor_identity(5) is None


def test_resolve_monitor_index_prefers_matching_identity_over_stale_index():
    """Ekran dizilimi degisip monitorler yeniden numaralansa bile, kayitli
    KIMLIK (konum+cozunurluk) eslesen monitorun GUNCEL index'ini dondurmeli -
    salt eski (artik yanlis ekrani isaret eden) sira numarasini degil."""
    monitors = [
        {"left": 0, "top": 0, "width": 3840, "height": 1080},
        {"left": 1920, "top": 0, "width": 1920, "height": 1080},  # simdi index 0
        {"left": 0, "top": 0, "width": 1920, "height": 1080},     # simdi index 1
    ]
    fake_mss_instance = _make_fake_mss(monitors)
    config = {
        "capture_monitor_index": 0,  # ESKI (artik gecersiz) sira numarasi
        "capture_monitor_identity": {"left": 0, "top": 0, "width": 1920, "height": 1080},
    }
    with patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        assert capture.resolve_monitor_index(config) == 1


def test_resolve_monitor_index_falls_back_to_stored_index_when_no_identity():
    config = {"capture_monitor_index": 2}
    assert capture.resolve_monitor_index(config) == 2


def test_resolve_monitor_index_falls_back_when_identity_matches_nothing():
    monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]
    fake_mss_instance = _make_fake_mss(monitors)
    config = {
        "capture_monitor_index": 3,
        "capture_monitor_identity": {"left": 9999, "top": 9999, "width": 100, "height": 100},
    }
    with patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        assert capture.resolve_monitor_index(config) == 3


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


def _dxcam_factory(specs):
    """specs: {(device_idx, output_idx): (left, top, right, bottom, resolution)}.
    Her cagrida YENI bir sahte kamera dondurur - boylece "tarama" (probe)
    asamasindaki kameralar ile gercekte KULLANILAN (son) kamera birbirinden
    ayirt edilebilir (orn. close() testlerinde release() sayisini dogru
    saymak icin). Eslesmeyen bir (device_idx, output_idx) icin IndexError
    firlatir - _enum_dxcam_outputs'un tarama dongusunun dogru yerde
    durmasini saglar."""
    created = []

    def factory(device_idx=0, output_idx=None, output_color="RGB", **kw):
        key = (device_idx, output_idx)
        if key not in specs:
            raise IndexError("yok")
        l, t, r, b, resolution = specs[key]
        cam = _fake_dxcam_camera(l, t, r, b)
        cam.grab.return_value = object()
        cam._output.resolution = resolution
        cam.is_released = False
        created.append(cam)
        return cam

    factory.created = created
    return factory


def _make_fake_dxcam_module(specs):
    factory = _dxcam_factory(specs)
    module = MagicMock()
    module.create = MagicMock(side_effect=factory)
    module.created = factory.created
    return module


_THREE_MONITOR_LAYOUT = [
    {"left": 0, "top": 0, "width": 3840, "height": 1080},
    {"left": 0, "top": 0, "width": 1920, "height": 1080},
    {"left": 1920, "top": 0, "width": 1920, "height": 1080},
]


def test_screen_capturer_dxcam_backend_uses_dxgi_origin():
    """dxcam kullanilabiliyorsa VE secilen mss monitorune konumca eslesen
    bir dxcam ciktisi bulunursa, konum DXGI DesktopCoordinates'ten
    gelmeli."""
    fake_dxcam_module = _make_fake_dxcam_module({
        (0, 0): (0, 0, 1920, 1080, (1920, 1080)),
        (0, 1): (1920, 0, 3840, 1080, (1920, 1080)),
    })
    fake_mss_instance = _make_fake_mss(_THREE_MONITOR_LAYOUT)

    with patch.object(capture, "_DXCAM_AVAILABLE", True), \
         patch.object(capture, "dxcam", fake_dxcam_module, create=True), \
         patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        cap = capture.ScreenCapturer(monitor_index=1)  # mss fiziksel 1 -> (1920,0)

    assert cap.backend == "dxcam"
    assert cap.get_origin() == (1920, 0)


def test_screen_capturer_dxcam_falls_back_to_mss_when_no_matching_output():
    """dxcam ciktilarindan HICBIRI secilen monitorun konumuyla eslesmezse
    (orn. dxcam'in numaralandirmasi mss'inkiyle farkli), program cokmeden
    mss'e dusmeli - YANLIS ekrani sessizce yakalamamali."""
    fake_dxcam_module = _make_fake_dxcam_module({
        (0, 0): (0, 0, 1920, 1080, (1920, 1080)),
        # (1920, 0) konumunda bir cikis YOK - kasitli eksik
    })
    fake_mss_instance = _make_fake_mss(_THREE_MONITOR_LAYOUT)

    with patch.object(capture, "_DXCAM_AVAILABLE", True), \
         patch.object(capture, "dxcam", fake_dxcam_module, create=True), \
         patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        cap = capture.ScreenCapturer(monitor_index=1)  # mss fiziksel 1 -> (1920,0)

    assert cap.backend == "mss"
    assert cap.get_origin() == (1920, 0)


# ------------------------------------------------------- close() kaynak temizligi
def test_close_releases_dxcam_camera():
    """close() dxcam kamerasinda acikca release() cagirmali (GC'ye birakmak
    yerine - monitor sik degistiginde kaynagin hemen serbest kalmasi icin)."""
    fake_dxcam_module = _make_fake_dxcam_module({(0, 0): (1920, 0, 3840, 1080, (1920, 1080))})
    fake_mss_instance = _make_fake_mss(_THREE_MONITOR_LAYOUT)

    with patch.object(capture, "_DXCAM_AVAILABLE", True), \
         patch.object(capture, "dxcam", fake_dxcam_module, create=True), \
         patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        cap = capture.ScreenCapturer(monitor_index=1)
        cap.close()

    real_cam = fake_dxcam_module.created[-1]  # probe degil, GERCEKTEN kullanilan kamera
    real_cam.release.assert_called_once()
    assert cap._dxcam_cam is None


def test_close_skips_release_if_already_released():
    """Kamera zaten release edilmisse tekrar cagirmamali (dxcam bunu hata
    sayabilir)."""
    fake_dxcam_module = _make_fake_dxcam_module({(0, 0): (1920, 0, 3840, 1080, (1920, 1080))})
    fake_mss_instance = _make_fake_mss(_THREE_MONITOR_LAYOUT)

    with patch.object(capture, "_DXCAM_AVAILABLE", True), \
         patch.object(capture, "dxcam", fake_dxcam_module, create=True), \
         patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        cap = capture.ScreenCapturer(monitor_index=1)
        fake_dxcam_module.created[-1].is_released = True
        cap.close()

    fake_dxcam_module.created[-1].release.assert_not_called()


def test_close_handles_release_exception_gracefully():
    """release() patlarsa bile close() disariya istisna sizdirmamali."""
    fake_dxcam_module = _make_fake_dxcam_module({(0, 0): (1920, 0, 3840, 1080, (1920, 1080))})
    fake_mss_instance = _make_fake_mss(_THREE_MONITOR_LAYOUT)

    with patch.object(capture, "_DXCAM_AVAILABLE", True), \
         patch.object(capture, "dxcam", fake_dxcam_module, create=True), \
         patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        cap = capture.ScreenCapturer(monitor_index=1)
        fake_dxcam_module.created[-1].release.side_effect = RuntimeError("patlat")
        cap.close()  # istisna firlatmamali


def test_close_closes_mss_instance():
    monitors = [
        {"left": 0, "top": 0, "width": 3840, "height": 1080},
        {"left": 0, "top": 0, "width": 1920, "height": 1080},
        {"left": 1920, "top": 0, "width": 1920, "height": 1080},
    ]
    fake_mss_instance = _make_fake_mss(monitors)

    with patch.object(capture, "_DXCAM_AVAILABLE", False), \
         patch.object(capture.mss, "mss", return_value=fake_mss_instance):
        cap = capture.ScreenCapturer(monitor_index=1)
        cap.close()

    fake_mss_instance.close.assert_called_once()
    assert cap._mss_inst is None


# --------------------------------------------------------- dxcam cikis tarama
def test_enum_dxcam_outputs_finds_all_outputs_on_one_device():
    fake_dxcam_module = _make_fake_dxcam_module({
        (0, 0): (0, 0, 1920, 1080, (1920, 1080)),
        (0, 1): (1920, 0, 3840, 1080, (1920, 1080)),
    })
    with patch.object(capture, "dxcam", fake_dxcam_module, create=True):
        outputs = capture._enum_dxcam_outputs()
    assert (0, 0, (0, 0), (1920, 1080)) in outputs
    assert (0, 1, (1920, 0), (1920, 1080)) in outputs
    assert len(outputs) == 2


def test_enum_dxcam_outputs_scans_multiple_devices():
    """Birden fazla ekran karti (orn. dahili + harici GPU) oldugunda,
    her ikisinin de ciktilari taranmali."""
    fake_dxcam_module = _make_fake_dxcam_module({
        (0, 0): (0, 0, 1920, 1080, (1920, 1080)),
        (1, 0): (1920, 0, 3840, 1080, (2560, 1440)),
    })
    with patch.object(capture, "dxcam", fake_dxcam_module, create=True):
        outputs = capture._enum_dxcam_outputs()
    device_indices = {o[0] for o in outputs}
    assert device_indices == {0, 1}


def test_enum_dxcam_outputs_releases_each_probed_camera():
    fake_dxcam_module = _make_fake_dxcam_module({
        (0, 0): (0, 0, 1920, 1080, (1920, 1080)),
    })
    with patch.object(capture, "dxcam", fake_dxcam_module, create=True):
        capture._enum_dxcam_outputs()
    fake_dxcam_module.created[0].release.assert_called_once()


def test_enum_dxcam_outputs_empty_when_nothing_available():
    fake_dxcam_module = _make_fake_dxcam_module({})
    with patch.object(capture, "dxcam", fake_dxcam_module, create=True):
        outputs = capture._enum_dxcam_outputs()
    assert outputs == []
