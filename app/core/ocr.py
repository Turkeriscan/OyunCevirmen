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

# UI'daki source_lang kodlarini Windows OCR'in bekledigi BCP-47 dil
# etiketlerine esler. "zh-cn" gibi bolge bazli etiketler Windows OCR icin
# geçerli degildir (Windows "zh-Hans"/"zh-Hant" script etiketlerini kullanir).
LANG_TO_WINDOWS_OCR = {
    "auto": "en-US",
    "en": "en-US",
    "de": "de-DE",
    "fr": "fr-FR",
    "es": "es-ES",
    "it": "it-IT",
    "pt": "pt-PT",
    "ru": "ru-RU",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "zh-cn": "zh-Hans",
    "zh-hans": "zh-Hans",
    "zh-hant": "zh-Hant",
    "tr": "tr-TR",
}


def windows_ocr_tag_for(source_lang):
    """config'teki source_lang kodunu Windows OCR dil etiketine cevirir."""
    if not source_lang or source_lang == "auto":
        return LANG_TO_WINDOWS_OCR["auto"]
    key = source_lang.lower()
    return LANG_TO_WINDOWS_OCR.get(key, source_lang)


def windows_ocr_available_languages():
    """Bu bilgisayarda kurulu Windows OCR dil paketlerinin etiket kumesini
    dondurur (kucuk harfe cevrilmis). Alinamazsa bos kume doner."""
    try:
        from winsdk.windows.media.ocr import OcrEngine
        return {lang.language_tag.lower() for lang in OcrEngine.available_recognizer_languages}
    except Exception as exc:
        logger.warning("Windows OCR dil listesi alinamadi: %s", exc)
        return set()


def is_windows_ocr_language_installed(source_lang):
    """Secili kaynak dilin Windows OCR paketi kurulu mu? Liste hic
    alinamadiysa (beklenmedik durum) engel olmamak icin True doner."""
    installed = windows_ocr_available_languages()
    if not installed:
        return True
    return windows_ocr_tag_for(source_lang).lower() in installed


_ALLOWED_PUNCT = set(".,!?'\"-:;()/%&")


def estimate_windows_ocr_confidence(text, box_height=None):
    """Windows OCR skor dondurmedigi icin, satirin kendisinden ve kutu
    yuksekliginden makul bir guven tahmini uretir:
      - harf/rakam orani yuksekse guven artar
      - beklenmeyen/garip karakter orani yuksekse guven duser
      - kutu cok kucukse (kucuk fontta okuma hatasi riski) guven duser
    Boylece arayuzdeki "Okuma guveni esigi" bu motorda da ise yarar."""
    cleaned = (text or "").strip()
    if not cleaned:
        return 0.0

    total = len(cleaned)
    alnum = sum(1 for c in cleaned if c.isalnum())
    weird = sum(1 for c in cleaned if not (c.isalnum() or c.isspace() or c in _ALLOWED_PUNCT))

    alnum_ratio = alnum / total
    weird_ratio = weird / total

    score = 0.55 + 0.4 * alnum_ratio - 1.3 * weird_ratio

    if total <= 2:
        score -= 0.15

    if box_height is not None and box_height > 0:
        if box_height < 11:
            score -= 0.3
        elif box_height < 16:
            score -= 0.12

    return max(0.05, min(0.99, score))


# ----------------------------------------------------------- kucuk yazi büyütme
UPSCALE_FACTOR = 2.0
# Bundan daha buyuk (genis cekim: tam ekran aninda tarama gibi) kareler
# buyutulmez; aksi halde islem suresi 4 katina cikar ve program yavaslar.
UPSCALE_MAX_PIXELS = 1_000_000


def maybe_upscale(frame_bgr, enabled):
    """enabled ve kare yeterince kucukse goruntuyu UPSCALE_FACTOR kadar
    buyutur (kucuk yazilarin daha net okunmasi icin). (yeni_kare, olcek)
    dondurur; buyutulmediyse olcek 1.0'dir."""
    if not enabled or frame_bgr is None:
        return frame_bgr, 1.0
    h, w = frame_bgr.shape[:2]
    if w <= 0 or h <= 0 or w * h > UPSCALE_MAX_PIXELS:
        return frame_bgr, 1.0
    new_w, new_h = int(round(w * UPSCALE_FACTOR)), int(round(h * UPSCALE_FACTOR))
    try:
        scaled = cv2.resize(frame_bgr, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    except Exception as exc:
        logger.warning("Kucuk yazi buyutme basarisiz, orijinal kare kullanilacak: %s", exc)
        return frame_bgr, 1.0
    return scaled, UPSCALE_FACTOR


def rescale_results(results, factor):
    """OCR sonuclarinin bbox'larini (buyutulmus kareden) orijinal olcege
    geri cevirir. factor == 1.0 ise degisiklik yapmaz."""
    if factor == 1.0 or not results:
        return results
    out = []
    for r in results:
        l, t, right, b = r.bbox
        out.append(OCRBoxResult(
            r.text, r.confidence,
            (l / factor, t / factor, right / factor, b / factor),
        ))
    return out


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
        self.source_lang = lang if lang and lang != "auto" else "en"
        self.lang = windows_ocr_tag_for(self.source_lang)
        if not is_windows_ocr_language_installed(self.source_lang):
            logger.warning(
                "Windows OCR dil paketi kurulu degil: %s (%s). Yonetici olarak "
                "PowerShell'de su komutu calistirin: "
                "DISM /Online /Add-Capability /CapabilityName:Language.OCR~~~%s~0.0.1.0 "
                "veya Ayarlar > Çeviri sayfasindan 'EasyOCR' motorunu secin.",
                self.source_lang, self.lang, self.lang,
            )

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
                    # Windows OCR skor vermez; harf/sembol oranindan ve kutu
                    # yuksekliginden makul bir tahmin uretiyoruz ki arayuzdeki
                    # "Okuma guveni esigi" ayari bu motorda da ise yarasin.
                    confidence=estimate_windows_ocr_confidence(text, box_height=(b - t)),
                    bbox=(l + ox, t + oy, r + ox, b + oy),
                )
            )
        return out


# --------------------------------------------------------------------------
# RapidOCR (onnxruntime-directml) - ekran karti ureticisinden BAGIMSIZ hizli
# OCR: DirectML sayesinde NVIDIA/AMD/Intel ekran kartlarinda calisir.
# "isteğe bağlı kurulum"dur (requirements.txt'e DAHIL EDILMEDI); kurulu
# degilse OCRManager._build_engine() sessizce Windows OCR'a doner.
# --------------------------------------------------------------------------
class RapidOCREngine:
    name = "rapidocr"

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR

        self._engine = RapidOCR()
        logger.info("RapidOCR yuklendi.")

    def recognize(self, frame_bgr, offset=(0, 0)):
        try:
            results, _elapse = self._engine(frame_bgr)
        except Exception as exc:
            logger.error("RapidOCR tanima hatasi: %s", exc)
            return []
        if not results:
            return []

        ox, oy = offset
        out = []
        for box_points, text, score in results:
            text = (text or "").strip()
            if not text:
                continue
            xs = [p[0] for p in box_points]
            ys = [p[1] for p in box_points]
            l, t, r, b = min(xs), min(ys), max(xs), max(ys)
            out.append(
                OCRBoxResult(text=text, confidence=float(score), bbox=(l + ox, t + oy, r + ox, b + oy))
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
        self._engine_lang = None
        self._lock = threading.Lock()

    def get_engine(self):
        with self._lock:
            wanted = self.config.get("ocr_engine", "windows")
            # Dil degisikligi de motorun yeniden kurulmasini gerektirir:
            # WindowsOCREngine/EasyOCREngine/PaddleOCREngine dili SADECE
            # kurulurken sabitler (bkz. __init__'leri); aksi halde "Oyunun
            # dili" ayari degistirildiginde (motor turu ayni kalirsa) eski
            # dil sessizce kullanilmaya devam ederdi.
            wanted_lang = self.config.get("source_lang", "auto")
            if (self._engine is not None and self._engine_name == wanted
                    and self._engine_lang == wanted_lang):
                return self._engine

            old_engine = self._engine
            self._engine = self._build_engine(wanted)
            self._engine_name = wanted
            self._engine_lang = wanted_lang
            self._release_engine(old_engine)
            return self._engine

    @staticmethod
    def _release_engine(engine):
        """Birakilan motor GPU'da bellek tutuyorsa (EasyOCR/PyTorch) onu
        serbest birakir - kullanici OCR motorunu degistirince oyunun
        kullanabilecegi ekran karti bellegi hemen geri verilsin diye."""
        if engine is None or engine.name != "easyocr":
            return
        try:
            del engine.reader
        except Exception:
            pass
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                logger.info("EasyOCR birakildi, GPU bellegi serbest birakildi.")
        except Exception:
            pass

    def _build_engine(self, wanted):
        source_lang = self.config.get("source_lang", "auto")
        lang = "en" if source_lang in (None, "auto") else source_lang

        try:
            if wanted == "easyocr":
                return EasyOCREngine(langs=[lang])
            if wanted == "paddle":
                return PaddleOCREngine(lang=lang)
            if wanted == "rapidocr":
                return RapidOCREngine()
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
        upscale_enabled = self.config.get("ocr_upscale_small_text", True)
        processed, factor = maybe_upscale(frame_bgr, upscale_enabled)
        # Motora offset=(0,0) veririz: once buyutulmus kare uzerindeki
        # koordinatlari gercek olcege geri ceviririz, GERCEK offset'i ancak
        # ondan sonra ekleriz (aksi halde offset de yanlislikla olceklenirdi).
        results = engine.recognize(processed, offset=(0, 0))
        results = rescale_results(results, factor)

        if upscale_enabled and factor == 1.0:
            # Kare COK BUYUK oldugu icin (orn. F9 aninda tarama - tam ekran)
            # toptan buyutulemedi (bkz. UPSCALE_MAX_PIXELS). Onun yerine
            # SADECE ilk gecisin bulduğu kucuk yazili bolgeleri tek tek
            # kirpip buyutup yeniden okuyoruz - boylece kucuk yazi
            # buyutmesi aninda taramada da ise yarar.
            results = self._refine_small_text_regions(engine, frame_bgr, results)

        ox, oy = offset
        if ox or oy:
            results = [
                OCRBoxResult(
                    r.text, r.confidence,
                    (r.bbox[0] + ox, r.bbox[1] + oy, r.bbox[2] + ox, r.bbox[3] + oy),
                )
                for r in results
            ]
        return results

    @staticmethod
    def _refine_small_text_regions(engine, frame_bgr, results, max_regions=20,
                                    height_threshold=20, padding=12):
        """Ilk gecisin bulduğu, yazi yuksekligi kucuk olan (okuma hatasina
        daha acik) sonuclari kirpip 2 kat buyutup o KUCUK bolgeyi tekrar
        okur; daha iyi bir sonuc bulunursa onu kullanir, bulunamazsa ilk
        sonucu korur. max_regions, cok sayida kucuk yazi oldugunda aninda
        taramanin asiri uzamasini onler."""
        frame_h, frame_w = frame_bgr.shape[:2]
        refined = []
        refined_count = 0
        for r in results:
            l, t, right, b = r.bbox
            height = b - t
            if refined_count >= max_regions or height <= 0 or height >= height_threshold:
                refined.append(r)
                continue
            crop_l = max(0, int(l - padding))
            crop_t = max(0, int(t - padding))
            crop_r = min(frame_w, int(right + padding))
            crop_b = min(frame_h, int(b + padding))
            crop = frame_bgr[crop_t:crop_b, crop_l:crop_r]
            if crop.size == 0:
                refined.append(r)
                continue
            # Sayac burada (GERCEK bir yeniden-okuma DENEMESI yapilmadan
            # once) artirilir - basarili/basarisiz olmasina bakmaksizin,
            # aksi halde cok sayida OKUNAMAYAN kucuk bolge (hepsi bos
            # sonuc dondurur) max_regions sinirini hic tetiklemeden
            # taramayi yavaslatabilirdi.
            refined_count += 1
            upscaled_crop, crop_factor = maybe_upscale(crop, True)
            try:
                crop_results = engine.recognize(upscaled_crop, offset=(0, 0))
            except Exception as exc:
                logger.warning("Kucuk yazi bolgesi yeniden okunamadi: %s", exc)
                crop_results = []
            crop_results = rescale_results(crop_results, crop_factor)
            if crop_results:
                best = max(crop_results, key=lambda cr: cr.confidence)
                refined.append(OCRBoxResult(
                    best.text, best.confidence,
                    (best.bbox[0] + crop_l, best.bbox[1] + crop_t,
                     best.bbox[2] + crop_l, best.bbox[3] + crop_t),
                ))
            else:
                refined.append(r)
        return refined


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
