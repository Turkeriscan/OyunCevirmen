"""
OCR modulu: ekrandan yakalanan goruntudeki yazilari KONUMLARIYLA (kutu)
birlikte bulur. Uc motor desteklenir, config'ten secilir:

 - "windows"  : Windows'un yerlesik OCR motoru (winocr / WinRT). Hizli,
                kurulum gerektirmez, varsayilan motordur.
 - "paddle"   : PaddleOCR (GPU). Kurulu ve bu GPU'da calisabiliyorsa kullanilir.
 - "easyocr"  : EasyOCR (PyTorch/CUDA GPU). PaddleOCR calismiyorsa yedek.

Her motor recognize(frame_bgr, offset) -> list[OCRBoxResult] dondurur.
bbox'lar frame'in sol-ust kosesine offset eklenerek MUTLAK EKRAN
koordinatina cevrilir (overlay'in dogru yere cizebilmesi icin).
"""
import logging
import threading

import cv2
import numpy as np

logger = logging.getLogger("OyunCevirmen.ocr")


class OCRBoxResult:
    __slots__ = ("text", "confidence", "bbox")

    def __init__(self, text, confidence, bbox):
        self.text = text
        self.confidence = confidence
        self.bbox = bbox  # (left, top, right, bottom) mutlak ekran koordinati

    def __repr__(self):
        return f"OCRBoxResult({self.text!r}, conf={self.confidence:.2f}, bbox={self.bbox})"


# --------------------------------------------------------------------------
# Windows OCR (varsayilan)
# --------------------------------------------------------------------------
class WindowsOCREngine:
    name = "windows"

    def __init__(self, lang="en"):
        import winocr

        self._winocr = winocr
        self.lang = lang if lang and lang != "auto" else "en"

    def recognize(self, frame_bgr, offset=(0, 0)):
        from PIL import Image

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        try:
            res = self._winocr.recognize_pil_sync(pil_img, lang=self.lang)
        except AssertionError as exc:
            logger.error(
                "Windows OCR dil paketi kurulu degil (%s). "
                "PowerShell'de yonetici olarak calistirin: %s",
                self.lang, exc,
            )
            return []
        except Exception as exc:
            logger.error("Windows OCR hatasi: %s", exc)
            return []

        ox, oy = offset
        out = []
        for line in res.get("lines", []):
            words = line.get("words", [])
            if not words:
                continue
            text = (line.get("text") or "").strip()
            if not text:
                continue
            xs1, ys1, xs2, ys2 = [], [], [], []
            for w in words:
                br = w.get("bounding_rect", {})
                x, y = br.get("x", 0), br.get("y", 0)
                w_, h_ = br.get("width", 0), br.get("height", 0)
                xs1.append(x)
                ys1.append(y)
                xs2.append(x + w_)
                ys2.append(y + h_)
            if not xs1:
                continue
            l, t, r, b = min(xs1), min(ys1), max(xs2), max(ys2)
            out.append(
                OCRBoxResult(
                    text=text,
                    confidence=0.95,  # Windows OCR skor vermez, varsayilan yuksek guven
                    bbox=(l + ox, t + oy, r + ox, b + oy),
                )
            )
        return out


# --------------------------------------------------------------------------
# EasyOCR (GPU - PyTorch/CUDA)
# --------------------------------------------------------------------------
class EasyOCREngine:
    name = "easyocr"

    def __init__(self, langs=None, gpu=True):
        import easyocr

        self.langs = langs or ["en"]
        self.reader = easyocr.Reader(self.langs, gpu=gpu, verbose=False)
        logger.info("EasyOCR yuklendi (gpu=%s, langs=%s)", gpu, self.langs)

    def recognize(self, frame_bgr, offset=(0, 0)):
        try:
            results = self.reader.readtext(frame_bgr, detail=1)
        except Exception as exc:
            logger.error("EasyOCR tanima hatasi: %s", exc)
            return []

        ox, oy = offset
        out = []
        for bbox_pts, text, conf in results:
            text = (text or "").strip()
            if not text:
                continue
            xs = [p[0] for p in bbox_pts]
            ys = [p[1] for p in bbox_pts]
            l, t, r, b = min(xs), min(ys), max(xs), max(ys)
            out.append(
                OCRBoxResult(text=text, confidence=float(conf), bbox=(l + ox, t + oy, r + ox, b + oy))
            )
        return out


# --------------------------------------------------------------------------
# PaddleOCR (GPU) - kurulabiliyor ve bu GPU'da calisiyorsa kullanilir
# --------------------------------------------------------------------------
class PaddleOCREngine:
    name = "paddle"

    def __init__(self, lang="en", use_gpu=True):
        from paddleocr import PaddleOCR

        self._api_mode = None
        try:
            # Yeni PaddleOCR (3.x) API: device parametresi
            self.ocr = PaddleOCR(use_angle_cls=True, lang=lang, device="gpu" if use_gpu else "cpu")
            self._api_mode = "new"
        except TypeError:
            # Eski PaddleOCR (2.x) API: use_gpu parametresi
            self.ocr = PaddleOCR(use_angle_cls=True, lang=lang, use_gpu=use_gpu, show_log=False)
            self._api_mode = "old"
        logger.info("PaddleOCR yuklendi (api=%s, gpu=%s)", self._api_mode, use_gpu)

    def recognize(self, frame_bgr, offset=(0, 0)):
        ox, oy = offset
        out = []
        try:
            if self._api_mode == "new" and hasattr(self.ocr, "predict"):
                results = self.ocr.predict(frame_bgr)
                for res in results:
                    texts = res.get("rec_texts", []) if hasattr(res, "get") else getattr(res, "rec_texts", [])
                    scores = res.get("rec_scores", []) if hasattr(res, "get") else getattr(res, "rec_scores", [])
                    polys = res.get("dt_polys", []) if hasattr(res, "get") else getattr(res, "dt_polys", [])
                    for text, score, poly in zip(texts, scores, polys):
                        text = (text or "").strip()
                        if not text:
                            continue
                        pts = np.array(poly)
                        l, t = pts[:, 0].min(), pts[:, 1].min()
                        r, b = pts[:, 0].max(), pts[:, 1].max()
                        out.append(OCRBoxResult(text, float(score), (l + ox, t + oy, r + ox, b + oy)))
            else:
                raw = self.ocr.ocr(frame_bgr, cls=True)
                for page in raw or []:
                    for item in page or []:
                        poly, (text, score) = item[0], item[1]
                        text = (text or "").strip()
                        if not text:
                            continue
                        pts = np.array(poly)
                        l, t = pts[:, 0].min(), pts[:, 1].min()
                        r, b = pts[:, 0].max(), pts[:, 1].max()
                        out.append(OCRBoxResult(text, float(score), (l + ox, t + oy, r + ox, b + oy)))
        except Exception as exc:
            logger.error("PaddleOCR tanima hatasi: %s", exc)
            return []
        return out


# --------------------------------------------------------------------------
# Factory / yonetici
# --------------------------------------------------------------------------
class OCRManager:
    """Secili motoru tembel (lazy) yukler, basarisiz olursa Windows OCR'a doner."""

    def __init__(self, config):
        self.config = config
        self._engine = None
        self._engine_name = None
        self._lock = threading.Lock()

    def get_engine(self):
        with self._lock:
            wanted = self.config.get("ocr_engine", "windows")
            if self._engine is not None and self._engine_name == wanted:
                return self._engine

            self._engine = self._build_engine(wanted)
            self._engine_name = wanted
            return self._engine

    def _build_engine(self, wanted):
        source_lang = self.config.get("source_lang", "auto")
        lang = "en" if source_lang in (None, "auto") else source_lang

        try:
            if wanted == "easyocr":
                return EasyOCREngine(langs=[lang])
            if wanted == "paddle":
                return PaddleOCREngine(lang=lang)
            return WindowsOCREngine(lang=lang)
        except Exception as exc:
            logger.error("OCR motoru '%s' yuklenemedi (%s), Windows OCR'a donuluyor.", wanted, exc)
            try:
                return WindowsOCREngine(lang=lang)
            except Exception as exc2:
                logger.critical("Windows OCR da yuklenemedi: %s", exc2)
                raise

    def recognize(self, frame_bgr, offset=(0, 0)):
        engine = self.get_engine()
        return engine.recognize(frame_bgr, offset)


def merge_paragraph_lines(results):
    """OCR motoru uzun bir paragrafi (kitap, tabela, gorev metni vb.) tek tek
    satirlara bolerek dondurur. Her satir baglamindan koparilip AYRI AYRI
    cevrilirse hem anlam kaybolur hem de modelin "bosluklari doldurup"
    alakasiz metin uretmesi (halusinasyon) kolaylasir.

    Bu fonksiyon, DIKEYDE BIRBIRINE YAKIN ve SOL KENARI HIZALI ardisik
    satirlari (gercek bir paragrafin tipik gorunumu) tek bir blokta
    birlestirir; aralarinda belirgin bosluk olan veya hizasiz duran
    satirlar (ayri menu/UI ogeleri olma ihtimali yuksek) birlestirilmez.
    """
    if not results:
        return results

    items = sorted(results, key=lambda r: (r.bbox[1], r.bbox[0]))
    used = [False] * len(items)
    merged = []

    for i, base in enumerate(items):
        if used[i]:
            continue
        group = [base]
        used[i] = True
        cur_left, cur_top, cur_right, cur_bottom = base.bbox
        cur_height = cur_bottom - cur_top

        extended = True
        while extended:
            extended = False
            for j, cand in enumerate(items):
                if used[j]:
                    continue
                cl, ct, cr, cb = cand.bbox
                cand_height = cb - ct
                avg_h = (cur_height + cand_height) / 2.0
                gap = ct - cur_bottom
                horiz_overlap = min(cur_right, cr) - max(cur_left, cl)
                left_aligned = abs(cl - cur_left) <= max(25, avg_h * 0.6)

                # Siki dikey aralik (tipik paragraf satir araligi) + sol
                # kenar hizasi -> ayni paragrafin devami kabul edilir.
                if -5 <= gap <= avg_h * 0.65 and (left_aligned or horiz_overlap > 0):
                    group.append(cand)
                    used[j] = True
                    cur_left = min(cur_left, cl)
                    cur_top = min(cur_top, ct)
                    cur_right = max(cur_right, cr)
                    cur_bottom = max(cur_bottom, cb)
                    cur_height = avg_h
                    extended = True

        if len(group) == 1:
            merged.append(base)
            continue

        group.sort(key=lambda r: r.bbox[1])
        text = " ".join(g.text.strip() for g in group if g.text.strip())
        conf = min(g.confidence for g in group)
        merged.append(OCRBoxResult(text, conf, (cur_left, cur_top, cur_right, cur_bottom)))

    return merged
