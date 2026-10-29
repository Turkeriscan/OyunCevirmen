"""
Ceviri modulu.

Birincil motor: Ollama (yerel, GPU hizlandirmali, aya-expanse:8b modeli).
Yedek motor: Google Translate (deep-translator, internet gerektirir).

Her iki motor da once bellek+SQLite onbellegine bakar; aynen daha once
cevrilmis bir metin tekrar modele/Google'a gonderilmez.
"""
import logging
import threading

import requests

from . import cache as cache_mod

logger = logging.getLogger("OyunCevirmen.translate")

SYSTEM_PROMPT_TR = (
    "You are a translation engine, not a chatbot or an assistant. "
    "You will be given a piece of text extracted from a video game's screen "
    "(UI, dialogue, subtitle, item name, quest text, book/sign text, etc.) via OCR. "
    "Your ONLY job is to translate exactly what is given into natural, fluent Turkish, "
    "matching the tone of a well-localized Turkish game. "
    "Preserve numbers, proper nouns and placeholders as-is when appropriate. "
    "\n"
    "STRICT RULES:\n"
    "- Output ONLY the Turkish translation of the given text, nothing else.\n"
    "- The translation's length and structure must closely match the source text. "
    "Never expand a short phrase into a long passage.\n"
    "- NEVER add explanations, definitions, glossaries, examples, lists, notes, "
    "alternatives, questions, or any information that is not literally present in "
    "the source text, even if the source text is incomplete, ambiguous, or looks "
    "like a fragment or garbled OCR output.\n"
    "- If the text is unclear or garbled, translate it as literally as possible "
    "anyway. Do not refuse, do not ask for clarification, do not comment on it.\n"
    "- Do not add quotes, markdown formatting, or the original text."
)


def _build_context_block(context_lines):
    """Son birkac cevrilmis satiri modele BAGLAM OLARAK ekler (zamir/hitap
    tutarliligi icin - orn. bir diyalogda 'o' -> 'sen' tutarli kalsin).
    Modelin bunlari TEKRAR CEVIRMEMESI veya tekrar ETMEMESI acikca
    belirtilir; _looks_like_hallucination kontrolu yalnizca asil 'text'
    parametresiyle calistigi icin bu blok halusinasyon korumasini bozmaz."""
    if not context_lines:
        return ""
    lines = [f'- "{orig}" -> "{trans}"' for orig, trans in context_lines if orig and trans]
    if not lines:
        return ""
    return (
        "\n\nCONTEXT ONLY - previous lines from this same scene, already "
        "translated (for pronoun/tone consistency only). Do NOT translate, "
        "repeat, or reference these in your output; only translate the NEW "
        "line given in the user message below:\n" + "\n".join(lines)
    )


class OllamaTranslator:
    def __init__(self, host="http://127.0.0.1:11434", model="aya-expanse:8b", timeout=20):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self._session = requests.Session()

    def is_available(self):
        try:
            r = self._session.get(f"{self.host}/api/tags", timeout=3)
            return r.status_code == 200
        except Exception:
            return False

    def translate(self, text, source_lang="auto", target_lang="tr", model=None, context_lines=None):
        # num_predict girdi uzunluguyla orantili: kisa bir oyun ici yazi icin
        # modelin yuzlerce token'lik alakasiz bir metin ("sozluk", "aciklama"
        # vb.) uretip halusinasyon gormesini onler.
        word_count = max(1, len(text.split()))
        num_predict = max(24, min(300, word_count * 5 + 20))

        system_content = SYSTEM_PROMPT_TR + _build_context_block(context_lines)

        payload = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system_content},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "options": {"temperature": 0.2, "num_predict": num_predict},
        }
        try:
            resp = self._session.post(
                f"{self.host}/api/chat", json=payload, timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            out = data.get("message", {}).get("content", "").strip()
            return _clean_model_output(out)
        except Exception as exc:
            logger.warning("Ollama ceviri hatasi: %s", exc)
            return None


_HALLUCINATION_MARKERS = (
    "\n-", "\n•", "- **", "**:",
)


def _looks_like_hallucination(original, translated):
    """Modelin kisa bir metni cevirmek yerine kendi uydurdugu uzun/alakasiz
    bir metin (sozluk, aciklama, liste vb.) uretip uretmedigini tahmin eder."""
    if not translated:
        return False
    orig_len = len(original)
    trans_len = len(translated)

    # Ceviri, kaynaktan cok daha uzunsa (kisa bir ifade icin ozellikle supheli)
    if trans_len > max(80, orig_len * 3.5):
        return True

    # Kaynakta olmayan liste/baslik/sozluk bicimlendirmesi ortaya ciktiysa
    lowered = translated.lower()
    if any(marker in lowered for marker in _HALLUCINATION_MARKERS):
        return True

    # Kaynak tek satirken ceviri birden fazla satira/maddeye yayilmissa
    if original.count("\n") <= 1 and translated.count("\n") >= 2:
        return True

    return False


def _clean_model_output(text):
    if not text:
        return text
    text = text.strip()
    # Bazi modeller ciktisini tirnak icine alabiliyor, temizle.
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        text = text[1:-1].strip()
    if len(text) >= 2 and text[0] == "'" and text[-1] == "'":
        text = text[1:-1].strip()
    return text


class GoogleFallbackTranslator:
    def __init__(self):
        self._lock = threading.Lock()

    def translate(self, text, source_lang="auto", target_lang="tr"):
        try:
            from deep_translator import GoogleTranslator

            src = "auto" if source_lang in (None, "auto") else source_lang
            with self._lock:
                result = GoogleTranslator(source=src, target=target_lang).translate(text)
            return result
        except Exception as exc:
            logger.warning("Google Translate hatasi: %s", exc)
            return None


class TranslationManager:
    """Config'e gore motor secer, onbellek kullanir, basarisizlikta yedek motora gecer."""

    def __init__(self, config):
        self.config = config
        self.cache = cache_mod.get_cache(config.get("max_cache_memory_items", 5000))
        self.ollama = OllamaTranslator(
            host=config.get("ollama_host", "http://127.0.0.1:11434"),
            model=config.get("ollama_model", "aya-expanse:8b"),
        )
        self.google = GoogleFallbackTranslator()
        # Orchestrator bunu baglayip, izin "sorulmadi" (None) durumundayken
        # kullanicidan bir kez izin istenmesini saglar (bkz. main.py
        # _request_google_permission). Arayuzsuz/testte None kalabilir.
        self.on_google_permission_needed = None

    def _google_fallback_allowed(self):
        """Ollama BASARISIZ olup YEDEK olarak Google'a gidilmesi gerektiginde
        bu kontrol edilir (kullanici motor olarak bilerek 'google' secmisse
        bu fonksiyon hic cagrilmaz - o zaman zaten acik riza vardir)."""
        allowed = self.config.get("allow_google_fallback")
        if allowed is None:
            if self.on_google_permission_needed:
                try:
                    self.on_google_permission_needed()
                except Exception as exc:
                    logger.warning("Google izin istemi tetiklenemedi: %s", exc)
            return False
        return bool(allowed)

    def translate(self, text, source_lang=None, target_lang=None, context_lines=None):
        target_lang = target_lang or self.config.get("target_lang", "tr")
        source_lang = source_lang or self.config.get("source_lang", "auto")
        engine_pref = self.config.get("translate_engine", "ollama")
        # Ollama host/model gibi: kullanici "Bellekte tutulacak çeviri"
        # ayarini calisirken degistirirse, zaten kurulu olan onbellege de
        # hemen yansisin (bkz. TranslationCache.set_max_memory_items).
        self.cache.set_max_memory_items(self.config.get("max_cache_memory_items", 5000))

        # Onbellek anahtari baglamdan BAGIMSIZ kalir: ayni metin, baglam
        # degisse de ayni anahtarla aranir/kaydedilir (aksi halde ayni
        # satir sahne ilerledikce tekrar tekrar modele gonderilirdi).
        cached = self.cache.get(text, source_lang, target_lang, engine_pref)
        if cached is not None:
            return cached

        result = None
        used_engine = engine_pref

        self.ollama.host = self.config.get("ollama_host", self.ollama.host).rstrip("/")
        current_model = self.config.get("ollama_model", self.ollama.model)

        if engine_pref == "ollama":
            result = self.ollama.translate(
                text, source_lang, target_lang, model=current_model, context_lines=context_lines
            )
            if result and _looks_like_hallucination(text, result):
                if self._google_fallback_allowed():
                    logger.warning(
                        "Ollama supheli/alakasiz ceviri uretti, Google'a geciliyor. "
                        "Kaynak=%r Model_ciktisi=%r", text[:60], result[:80],
                    )
                    result = self.google.translate(text, source_lang, target_lang)
                    used_engine = "google"
                    if result and _looks_like_hallucination(text, result):
                        result = None  # Google de supheliyse, hicbir sey gosterme
                else:
                    logger.info("Ollama supheli ceviri uretti, Google izni yok: %r", text[:40])
                    result = None
            elif not result:
                if self._google_fallback_allowed():
                    logger.info("Ollama basarisiz, Google'a geciliyor: %r", text[:40])
                    result = self.google.translate(text, source_lang, target_lang)
                    used_engine = "google"
                else:
                    logger.info("Ollama basarisiz, Google izni yok, cevrilemedi: %r", text[:40])
        else:
            result = self.google.translate(text, source_lang, target_lang)
            used_engine = "google"
            if not result:
                result = self.ollama.translate(
                    text, source_lang, target_lang, model=current_model, context_lines=context_lines
                )
                used_engine = "ollama"
                if result and _looks_like_hallucination(text, result):
                    result = None

        if result:
            # ONEMLI: onbellek anahtari HER ZAMAN kullanicinin SECTIGI motor
            # (engine_pref) ile yazilir - sonucu GERCEKTE hangi motorun
            # urettigi (used_engine) degil. Aksi halde yedek motordan gelen
            # bir sonuc "google" anahtariyla kaydedilir, ama her arama hala
            # "ollama" anahtariyla yapildigi icin BIR DAHA HIC BULUNAMAZ -
            # ayni satir her seferinde yeniden (basarisiz) Ollama'ya gidip
            # tekrar Google'a duserdi. used_engine != engine_pref ise bu
            # kayit "yedekten geldi" (is_fallback) isaretlenir ve bir sure
            # sonra suresi dolar: tercih edilen motor (orn. Ollama) duzelince
            # ayni satir tekrar geldiginde ona yeniden bir sans verilir.
            self.cache.set(
                text, source_lang, target_lang, engine_pref, result,
                is_fallback=(used_engine != engine_pref),
            )
        return result
