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


class ScreenCapturer:
    """Tum ekrani (veya tek bir monitoru) yakalayan sinif."""

    def __init__(self, monitor_index: int = 0):
        self.monitor_index = monitor_index
        self.backend = None
        self._dxcam_cam = None
        self._mss_inst = None
        self._mss_monitor = None
        self._lock = threading.Lock()
        self._init_backend()

    def _init_backend(self):
        if _DXCAM_AVAILABLE:
            try:
                self._dxcam_cam = dxcam.create(
                    output_idx=self.monitor_index, output_color="BGR"
                )
                if self._dxcam_cam is not None:
                    # Tek seferlik test yakalama
                    test = self._dxcam_cam.grab()
                    self.backend = "dxcam"
                    logger.info("Yakalama motoru: dxcam (monitor %s)", self.monitor_index)
                    return
            except Exception as exc:
                logger.warning("dxcam baslatilamadi (%s), mss'e dusuluyor", exc)

        self._mss_inst = mss.mss()
        # mss monitors[0] = tum monitorler birlesik; 1,2,... tekil monitorler
        monitors = self._mss_inst.monitors
        idx = self.monitor_index + 1 if self.monitor_index + 1 < len(monitors) else 1
        self._mss_monitor = monitors[idx]
        self.backend = "mss"
        logger.info("Yakalama motoru: mss (monitor %s)", idx)

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
                del self._dxcam_cam
            if self._mss_inst is not None:
                self._mss_inst.close()
        except Exception:
            pass


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
