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
from . import glossary as glossary_mod

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
    "- The source text comes from OCR, so it may contain obvious character "
    "misreads (e.g. l/I/1, 0/O, rn/m confusion) or missing/extra spaces between "
    "words. Silently interpret and correct these as the most likely intended "
    "word before translating; do not mention or explain the correction.\n"
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

    def translate(self, text, source_lang="auto", target_lang="tr", model=None,
                  context_lines=None, glossary_block=""):
        # num_predict girdi uzunluguyla orantili: kisa bir oyun ici yazi icin
        # modelin yuzlerce token'lik alakasiz bir metin ("sozluk", "aciklama"
        # vb.) uretip halusinasyon gormesini onler.
        word_count = max(1, len(text.split()))
        num_predict = max(24, min(300, word_count * 5 + 20))

        system_content = SYSTEM_PROMPT_TR + _build_context_block(context_lines) + glossary_block

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


class ArgosTranslator:
    """Cevrimdisi (internetsiz) yedek/alternatif motor: Argos Translate.
    "İsteğe bağlı kurulum" oldugu icin requirements.txt'e DAHIL EDILMEDI;
    kurulu degilse is_available() False doner ve bu motor sessizce
    atlanir (hicbir hata gostermez)."""

    def __init__(self):
        self._checked = False
        self._available = False

    def is_available(self):
        if not self._checked:
            self._checked = True
            try:
                import argostranslate.translate  # noqa: F401
                self._available = True
            except Exception:
                self._available = False
        return self._available

    def translate(self, text, source_lang="auto", target_lang="tr"):
        if not self.is_available():
            return None
        try:
            import argostranslate.translate as at
            src = "en" if source_lang in (None, "auto") else source_lang
            return at.translate(text, src, target_lang)
        except Exception as exc:
            logger.warning("Argos Translate hatasi: %s", exc)
            return None


class DeepLTranslator:
    """Isteğe bagli bulut motoru: DeepL (ucretsiz API anahtari gerekir,
    Çeviri sayfasindan girilir). Anahtar bos ise kullanilamaz sayilir -
    ekstra bir "izin" akisina gerek yok, anahtari girmis olmak zaten
    acik riza anlamina gelir."""

    def __init__(self, api_key=""):
        self.api_key = api_key or ""
        self._session = requests.Session()

    def is_configured(self):
        return bool(self.api_key.strip())

    def translate(self, text, source_lang="auto", target_lang="tr"):
        if not self.is_configured():
            return None
        try:
            data = {
                "auth_key": self.api_key.strip(),
                "text": text,
                "target_lang": target_lang.upper(),
            }
            if source_lang not in (None, "auto"):
                data["source_lang"] = source_lang.upper()
            resp = self._session.post(
                "https://api-free.deepl.com/v2/translate", data=data, timeout=10,
            )
            resp.raise_for_status()
            payload = resp.json()
            return payload["translations"][0]["text"]
        except Exception as exc:
            logger.warning("DeepL ceviri hatasi: %s", exc)
            return None


_KNOWN_ENGINES = ("ollama", "google", "argos", "deepl")
DEFAULT_FALLBACK_ORDER = ["ollama", "argos", "google"]


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
        self.argos = ArgosTranslator()
        self.deepl = DeepLTranslator(api_key=config.get("deepl_api_key", ""))
        # Orchestrator bunu baglayip, izin "sorulmadi" (None) durumundayken
        # kullanicidan bir kez izin istenmesini saglar (bkz. main.py
        # _request_google_permission). Arayuzsuz/testte None kalabilir.
        self.on_google_permission_needed = None
        # Su an aktif bir oyun profilinin SOZLUGU (4.1, bkz. main.py
        # Orchestrator._sync_active_profile). None/bos ise genel glossary.json
        # kullanilir - boylece profilsiz oyunlar/testler hic etkilenmez.
        self.active_profile_glossary = None

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

    def _translate_via_google(self, text, source_lang, target_lang, glossary_entries):
        """Google Translate sistem talimati OKUYAMADIGI icin, oyun
        sozlugundeki terimler Google'a gonderilmeden once bir YER
        TUTUCUYLA korunur; Google ceviriyi bitirince sozlukteki hedef
        terimle (veya "cevirme" isaretliyse kaynak terimle) geri konur."""
        protected_text, matches = glossary_mod.protect_terms(text, glossary_entries)
        result = self.google.translate(protected_text, source_lang, target_lang)
        if result:
            result = glossary_mod.restore_terms(result, matches)
        return result

    def _engine_order(self, engine_pref):
        """Birincil motoru basa alip, config'teki yedek sirasini (orn.
        Ollama -> Argos -> Google) tekrarsiz olarak ekler. Boylece
        kullanici motor olarak ne secerse secsin, calismadiginda/suphe
        ciktiginda hangi SIRAYLA diger motorlarin denenecegi ayni mantikla
        belirlenir."""
        fallback_order = self.config.get("fallback_order") or DEFAULT_FALLBACK_ORDER
        fallback_order = [e for e in fallback_order if e in _KNOWN_ENGINES]
        return [engine_pref] + [e for e in fallback_order if e != engine_pref]

    def _engine_translate(self, name, text, source_lang, target_lang, context_lines,
                           glossary_entries, current_model):
        """Tek bir motoru dener; o motor kullanilamiyorsa (kurulu degil,
        anahtar girilmemis vb.) veya basarisiz olursa None doner."""
        if name == "ollama":
            glossary_block = glossary_mod.build_ollama_system_block(glossary_entries)
            return self.ollama.translate(
                text, source_lang, target_lang, model=current_model,
                context_lines=context_lines, glossary_block=glossary_block,
            )
        if name == "google":
            return self._translate_via_google(text, source_lang, target_lang, glossary_entries)
        if name == "argos":
            return self.argos.translate(text, source_lang, target_lang)
        if name == "deepl":
            return self.deepl.translate(text, source_lang, target_lang)
        return None

    def translate(self, text, source_lang=None, target_lang=None, context_lines=None):
        target_lang = target_lang or self.config.get("target_lang", "tr")
        source_lang = source_lang or self.config.get("source_lang", "auto")
        engine_pref = self.config.get("translate_engine", "ollama")
        # Ollama host/model gibi: kullanici "Bellekte tutulacak çeviri"
        # ayarini calisirken degistirirse, zaten kurulu olan onbellege de
        # hemen yansisin (bkz. TranslationCache.set_max_memory_items).
        self.cache.set_max_memory_items(self.config.get("max_cache_memory_items", 5000))
        self.deepl.api_key = self.config.get("deepl_api_key", self.deepl.api_key)

        # Onbellek anahtari baglamdan BAGIMSIZ kalir: ayni metin, baglam
        # degisse de ayni anahtarla aranir/kaydedilir (aksi halde ayni
        # satir sahne ilerledikce tekrar tekrar modele gonderilirdi).
        cached = self.cache.get(text, source_lang, target_lang, engine_pref)
        if cached is not None:
            return cached

        self.ollama.host = self.config.get("ollama_host", self.ollama.host).rstrip("/")
        current_model = self.config.get("ollama_model", self.ollama.model)

        # Oyun sozlugu (karakter/yer/esya adlari): Ollama'ya sistem
        # talimatinda dogrudan verilir; Google'a gonderilirken terimler
        # yer tutucuyla korunup sonra sozlukteki hedef terimle geri konur
        # (bkz. _translate_via_google). Argos/DeepL icin sozluk talimati
        # OKUYAMADIKLARI icin uygulanmaz (ikisi de ayni zamanda nadiren
        # kullanilan, isteğe bagli motorlardir).
        glossary_entries = self.active_profile_glossary or glossary_mod.load_glossary()

        result = None
        used_engine = None
        order = self._engine_order(engine_pref)
        for position, name in enumerate(order):
            if name == "google" and position > 0 and not self._google_fallback_allowed():
                # Google SADECE yedek pozisyonundaysa izin gerekir; birincil
                # motor olarak bilerek secilmisse (position == 0) zaten acik riza vardir.
                logger.info("Google yedek olarak denenecekti ama izin yok: %r", text[:40])
                continue
            candidate = self._engine_translate(
                name, text, source_lang, target_lang, context_lines, glossary_entries, current_model,
            )
            if candidate and _looks_like_hallucination(text, candidate):
                logger.warning(
                    "%s supheli/alakasiz ceviri uretti, atlaniyor. Kaynak=%r Cikti=%r",
                    name, text[:60], candidate[:80],
                )
                candidate = None
            if candidate:
                result = candidate
                used_engine = name
                break

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
