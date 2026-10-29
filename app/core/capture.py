"""
Ekran yakalama modulu.
Birincil yontem: dxcam (DXGI Desktop Duplication - oyunlarda hizli, borderless
windowed modu destekler). dxcam baslatilamazsa (bazi surucu/GPU kombinasyonlarinda
olabilir) otomatik olarak mss kutuphanesine duser.

Ayrica canli mod icin "degisen bolge" tespiti saglar: ekran bir izgaraya
(grid) bolunur, her hucrenin onceki kareyle farki olculur, sadece degisen
hucreler OCR'a gonderilir. Bu sayede performans artar ve oyunu yavaslatmaz.
"""
import logging
import threading

import numpy as np
import cv2

logger = logging.getLogger("OyunCevirmen.capture")

try:
    import dxcam
    _DXCAM_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    logger.warning("dxcam yuklenemedi, mss'e dusuluyor: %s", exc)
    _DXCAM_AVAILABLE = False

import mss


def to_virtual_desktop(bbox, origin):
    """Yerel (yakalanan monitore gore) bir bbox'i (l,t,r,b) sanal masaustu
    (global, overlay'in kullandigi) koordinatina cevirir.

    Saf bir fonksiyondur (yan etkisi yok) ki farkli monitor dizilimleri
    (ikincil monitor saga/sola, negatif koordinatli monitor vb.) icin
    kolayca test edilebilsin.

    bbox: (left, top, right, bottom) - yakalanan karenin kendi 0,0'ina gore
    origin: (left, top) - o monitorun sanal masaustundeki sol-ust kosesi
    """
    ox, oy = origin
    l, t, r, b = bbox
    return (l + ox, t + oy, r + ox, b + oy)


def _dxcam_output_origin(camera):
    """dxcam kamerasinin baglandigi DXGI ciktisinin sanal masaustundeki
    sol-ust kosesini dondurur (DesktopCoordinates fiziksel piksel
    cinsindendir, DPI olceklemesinden etkilenmez). Basarisiz olursa None."""
    try:
        coords = camera._output.desc.DesktopCoordinates
        return int(coords.left), int(coords.top)
    except Exception as exc:
        logger.warning("dxcam ciktisinin konumu okunamadi: %s", exc)
        return None


def _mss_monitor_origin(monitor_dict):
    """mss'in monitor sozlugunden (left/top) sol-ust koseyi cikarir."""
    return int(monitor_dict.get("left", 0)), int(monitor_dict.get("top", 0))


def _lookup_mss_origin(monitor_index):
    """dxcam'in kendi konum bilgisi alinamadiginda yedek: mss uzerinden
    AYNI numaralandirmayla (list_monitors ile birebir) konum arar."""
    try:
        with mss.mss() as sct:
            physical = sct.monitors[1:]
            idx = monitor_index if monitor_index < len(physical) else 0
            return _mss_monitor_origin(physical[idx])
    except Exception as exc:
        logger.warning("Yedek monitor konumu da alinamadi: %s", exc)
        return (0, 0)


def get_monitor_identity(monitor_index):
    """Secili (mss numaralandirmali) monitorun "kimligini" (konum +
    cozunurluk) dondurur. Bu, salt bir SIRA NUMARASINDAN farkli olarak
    ekranlar yeniden duzenlendiginde (kablo degisikligi, yeni monitor
    eklenmesi vb.) bile AYNI fiziksel ekrani tekrar bulmaya yarar."""
    try:
        with mss.mss() as sct:
            physical = sct.monitors[1:]
            if monitor_index >= len(physical):
                return None
            mon = physical[monitor_index]
            return {
                "left": int(mon.get("left", 0)), "top": int(mon.get("top", 0)),
                "width": int(mon.get("width", 0)), "height": int(mon.get("height", 0)),
            }
    except Exception as exc:
        logger.warning("Monitor kimligi okunamadi: %s", exc)
        return None


def _identity_matches(identity, mon):
    if not identity or not isinstance(identity, dict):
        return False
    return (
        identity.get("left") == int(mon.get("left", 0))
        and identity.get("top") == int(mon.get("top", 0))
        and identity.get("width") == int(mon.get("width", 0))
        and identity.get("height") == int(mon.get("height", 0))
    )


def resolve_monitor_index(config):
    """config'teki capture_monitor_identity, su anki ekran dizilimindeki
    bir monitorle eslesiyorsa O MONITORUN GUNCEL index'ini dondurur (ekran
    dizilimi degismisse dogru ekranda kalinsin diye); eslesme yoksa
    (ilk kurulum, kimlik hic kaydedilmemis, veya o monitor artik yok)
    config'teki ham capture_monitor_index'e sessizce doner."""
    stored_index = int(config.get("capture_monitor_index", 0) or 0)
    identity = config.get("capture_monitor_identity")
    if not identity:
        return stored_index
    try:
        with mss.mss() as sct:
            physical = sct.monitors[1:]
            for i, mon in enumerate(physical):
                if _identity_matches(identity, mon):
                    return i
    except Exception as exc:
        logger.warning("Monitor kimligi eslestirilemedi: %s", exc)
    return stored_index


def _enum_dxcam_outputs(max_devices=4, max_outputs=8):
    """Butun dxcam (cihaz, cikis) ciftlerini DENEYEREK bulur. Sadece
    PUBLIC dxcam.create()/release() API'si kullanilir (ic DXFactory'ye
    dogrudan erisilmez) ki dxcam surumleri arasinda daha dayanikli olsun.
    Her bulunan cikis icin (device_idx, output_idx, origin, resolution)
    dondurur; origin/resolution okunamayan bir cikis da (None, None)
    degerleriyle listeye eklenir (en azindan deneme sayisi bilinsin)."""
    found = []
    for device_idx in range(max_devices):
        any_output_this_device = False
        for output_idx in range(max_outputs):
            cam = None
            try:
                cam = dxcam.create(device_idx=device_idx, output_idx=output_idx, output_color="BGR")
            except Exception:
                break  # bu cihazda bu ciktidan sonrasi yok
            if cam is None:
                break
            any_output_this_device = True
            origin = _dxcam_output_origin(cam)
            resolution = None
            try:
                resolution = tuple(int(v) for v in cam._output.resolution)
            except Exception:
                pass
            found.append((device_idx, output_idx, origin, resolution))
            try:
                cam.release()
            except Exception:
                pass
        if not any_output_this_device and device_idx > 0:
            break
    return found


def _find_matching_dxcam_output(target, outputs):
    """target: {"left","top","width","height"} (mss'ten, eslestirilmek
    istenen fiziksel monitor). outputs: _enum_dxcam_outputs() ciktisi.
    Konumu (ve biliniyorsa cozunurlugu) eslesen (device_idx, output_idx)
    ciftini dondurur; hicbiri eslesmezse None.

    Saf bir fonksiyondur (dxcam'e hic dokunmaz) ki gercek ekran karti
    olmadan da test edilebilsin."""
    if target is None:
        return None
    tl, tt = target.get("left"), target.get("top")
    tw, th = target.get("width"), target.get("height")
    for device_idx, output_idx, origin, resolution in outputs:
        if origin is None:
            continue
        if origin[0] != tl or origin[1] != tt:
            continue
        if resolution is not None and tw and th and resolution != (tw, th):
            continue  # ayni konum ama cozunurluk uyusmuyor - suphelidir, atla
        return (device_idx, output_idx)
    return None


def list_monitors():
    """Fiziksel monitorlerin kullanici dostu listesini dondurur.

    Donen 'index' degeri, config'teki capture_monitor_index ile AYNI
    numaralandirmayi kullanir (0 = ilk fiziksel monitor, ScreenCapturer'in
    kendisinin kullandigi numaralandirmayla birebir eslesir).
    """
    results = []
    try:
        with mss.mss() as sct:
            physical = sct.monitors[1:]
            for i, mon in enumerate(physical):
                name = mon.get("name") or f"Ekran {i + 1}"
                primary = bool(mon.get("is_primary", i == 0))
                text = f"Ekran {i + 1}: {name} — {mon['width']}×{mon['height']}"
                if primary:
                    text += " (Birincil)"
                results.append({
                    "index": i,
                    "label": text,
                    "width": mon["width"],
                    "height": mon["height"],
                    "primary": primary,
                })
    except Exception as exc:
        logger.warning("Monitor listesi alinamadi: %s", exc)

    if not results:
        results = [{"index": 0, "label": "Ekran 1 (varsayılan)", "width": 0, "height": 0, "primary": True}]
    return results


class ScreenCapturer:
    """Tum ekrani (veya tek bir monitoru) yakalayan sinif."""

    def __init__(self, monitor_index: int = 0):
        self.monitor_index = monitor_index
        self.backend = None
        self._dxcam_cam = None
        self._mss_inst = None
        self._mss_monitor = None
        self._lock = threading.Lock()
        # Bu monitorun sanal masaustundeki (overlay'in kullandigi global
        # koordinat sistemi) sol-ust kosesi. Ikincil bir monitor birincilin
        # solunda/ustunde duruyorsa negatif olabilir.
        self.left = 0
        self.top = 0
        self._init_backend()

    def get_origin(self):
        """Bu monitorun sanal masaustundeki sol-ust kosesi: (left, top)."""
        return (self.left, self.top)

    def _init_backend(self):
        if _DXCAM_AVAILABLE:
            # ONEMLI: mss'in monitor sira numarasi ile dxcam'in kendi
            # (device_idx, output_idx) numaralandirmasi AYNI SIRADA OLMAK
            # ZORUNDA DEGIL - ozellikle birden fazla ekran karti (dahili +
            # harici GPU) oldugunda tamamen farkli olabilir. "monitor_index"i
            # dogrudan dxcam output_idx olarak kullanmak YANLIS EKRANIN
            # yakalanmasina yol acabilirdi. Bunun yerine, kullanicinin
            # sectigi mss monitorunun KONUMUNU (ve cozunurlugunu) dxcam'in
            # ciktilari arasinda ARAYIP eslesen ciktiyi kullaniyoruz.
            target = get_monitor_identity(self.monitor_index)
            match = None
            if target is not None:
                try:
                    match = _find_matching_dxcam_output(target, _enum_dxcam_outputs())
                except Exception as exc:
                    logger.warning("dxcam ciktilari taranamadi: %s", exc)
            if match is None:
                logger.warning(
                    "Monitor %s icin eslesen bir dxcam ciktisi bulunamadi (hedef=%s); "
                    "mss'e dusuluyor.", self.monitor_index, target,
                )
            else:
                device_idx, output_idx = match
                try:
                    self._dxcam_cam = dxcam.create(
                        device_idx=device_idx, output_idx=output_idx, output_color="BGR"
                    )
                    if self._dxcam_cam is not None:
                        # Tek seferlik test yakalama (bazi GPU/surucu kombinasyonlarinda
                        # create() basarili olsa da grab() patlar; burada yakalanir)
                        self._dxcam_cam.grab()
                        self.backend = "dxcam"
                        origin = _dxcam_output_origin(self._dxcam_cam)
                        if origin is None:
                            origin = (target["left"], target["top"])
                        self.left, self.top = origin
                        logger.info(
                            "Yakalama motoru: dxcam (monitor %s -> device=%s output=%s, konum=%s)",
                            self.monitor_index, device_idx, output_idx, origin,
                        )
                        return
                except Exception as exc:
                    logger.warning(
                        "Eslesen dxcam ciktisi baslatilamadi (device=%s output=%s): %s, "
                        "mss'e dusuluyor", device_idx, output_idx, exc,
                    )

        self._mss_inst = mss.mss()
        # mss monitors[0] = tum monitorler birlesik; 1,2,... tekil monitorler
        monitors = self._mss_inst.monitors
        idx = self.monitor_index + 1 if self.monitor_index + 1 < len(monitors) else 1
        self._mss_monitor = monitors[idx]
        self.left, self.top = _mss_monitor_origin(self._mss_monitor)
        self.backend = "mss"
        logger.info("Yakalama motoru: mss (monitor %s, konum=%s)", idx, (self.left, self.top))

    def get_resolution(self):
        if self.backend == "dxcam":
            frame = self.grab_full()
            if frame is not None:
                h, w = frame.shape[:2]
                return w, h
            return 1920, 1080
        else:
            return self._mss_monitor["width"], self._mss_monitor["height"]

    def grab_full(self):
        """Tum ekrani BGR numpy array olarak dondurur. Basarisizsa None."""
        with self._lock:
            try:
                if self.backend == "dxcam":
                    frame = self._dxcam_cam.grab()
                    if frame is None:
                        return None
                    return frame  # BGR, HxWx3
                else:
                    shot = self._mss_inst.grab(self._mss_monitor)
                    arr = np.array(shot)  # BGRA
                    return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
            except Exception as exc:
                logger.error("Ekran yakalama hatasi: %s", exc)
                return None

    def grab_region(self, region):
        """region = (left, top, right, bottom) -> BGR numpy array."""
        l, t, r, b = region
        with self._lock:
            try:
                if self.backend == "dxcam":
                    frame = self._dxcam_cam.grab(region=(l, t, r, b))
                    return frame
                else:
                    mon = {"left": l, "top": t, "width": r - l, "height": b - t}
                    shot = self._mss_inst.grab(mon)
                    arr = np.array(shot)
                    return cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
            except Exception as exc:
                logger.error("Bolge yakalama hatasi: %s", exc)
                return None

    def close(self):
        try:
            if self.backend == "dxcam" and self._dxcam_cam is not None:
                # dxcam'in DXGI Desktop Duplication arayuzunu HEMEN serbest
                # birakir. "del" ile cop toplayiciya birakmak CPython'da
                # genelde de ayni ani sonucu verir (DXCamera.__del__ zaten
                # release() cagirir), ama monitor sik degistiriliyorsa
                # (change_monitor) GPU/ekran kopyalama kaynaginin gecikmeden
                # birakilmasi icin acikca cagirmak daha guvenilir.
                try:
                    if not self._dxcam_cam.is_released:
                        self._dxcam_cam.release()
                except Exception as exc:
                    logger.warning("dxcam release() basarisiz: %s", exc)
                self._dxcam_cam = None
            if self._mss_inst is not None:
                self._mss_inst.close()
                self._mss_inst = None
        except Exception as exc:
            logger.warning("Yakalama kaynaklari kapatilirken hata: %s", exc)


def build_grid(width, height, cols, rows):
    """Ekrani cols x rows hucreye bolen (l,t,r,b) listesini dondurur."""
    cell_w = width / cols
    cell_h = height / rows
    cells = []
    for row in range(rows):
        for col in range(cols):
            l = int(col * cell_w)
            t = int(row * cell_h)
            r = int((col + 1) * cell_w) if col < cols - 1 else width
            b = int((row + 1) * cell_h) if row < rows - 1 else height
            cells.append((l, t, r, b))
    return cells


def cell_signature(frame, cell):
    """Bir hucrenin kucuk gri-tonlamali ozetini (hizli karsilastirma icin) cikarir."""
    l, t, r, b = cell
    sub = frame[t:b, l:r]
    if sub.size == 0:
        return None
    small = cv2.resize(sub, (16, 16), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    return gray


def signature_changed(sig_a, sig_b, threshold=8.0):
    """Iki hucre ozetinin ortalama farki esigin ustundeyse True (degismis) doner."""
    if sig_a is None or sig_b is None:
        return True
    if sig_a.shape != sig_b.shape:
        return True
    diff = cv2.absdiff(sig_a, sig_b)
    return float(np.mean(diff)) > threshold


def frames_identical(frame_a, frame_b, threshold=1.5):
    """Iki tam kareyi hizlica karsilastirir (kucultup gri yaparak)."""
    if frame_a is None or frame_b is None:
        return False
    try:
        small_a = cv2.resize(frame_a, (160, 90), interpolation=cv2.INTER_AREA)
        small_b = cv2.resize(frame_b, (160, 90), interpolation=cv2.INTER_AREA)
        ga = cv2.cvtColor(small_a, cv2.COLOR_BGR2GRAY)
        gb = cv2.cvtColor(small_b, cv2.COLOR_BGR2GRAY)
        return float(np.mean(cv2.absdiff(ga, gb))) <= threshold
    except Exception:
        return False
