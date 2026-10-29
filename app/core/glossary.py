"""
Oyun sozlugu: kullanicinin kendi terim listesi (karakter/yer/esya adlari
gibi oyuna ozgu isimler). Her terim ya "kaynak -> hedef" ceviri ciftiyle,
ya da "cevirme" (no_translate) olarak isaretlenebilir.

Ollama'ya sistem talimatinda dogrudan verilir (modelin kendisi okuyup
uygulayabilir). Google Translate kullanilirken ise model talimat
okuyamadigi icin terimler once bir YER TUTUCUYLA (@@G0@@ gibi) korunur,
ceviri bittikten sonra gercek (sozlukteki) hedef terimle geri konur.
"""
import json
import logging
import os
import re
import threading

logger = logging.getLogger("OyunCevirmen.glossary")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GLOSSARY_PATH = os.path.join(BASE_DIR, "glossary.json")

_lock = threading.RLock()
_cached = None

_PLACEHOLDER_FMT = "@@G{idx}@@"


def _validate_entries(data):
    """Bozuk/elle duzenlenmis bir glossary.json'u sessizce temizler;
    kaynak terimi olmayan veya metin olmayan kayitlari atar."""
    if not isinstance(data, list):
        return []
    cleaned = []
    for item in data:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "")).strip()
        if not source:
            continue
        no_translate = bool(item.get("no_translate", False))
        target = "" if no_translate else str(item.get("target", "")).strip()
        cleaned.append({"source": source, "target": target, "no_translate": no_translate})
    return cleaned


def load_glossary():
    global _cached
    with _lock:
        if _cached is not None:
            return _cached
        if not os.path.exists(GLOSSARY_PATH):
            _cached = []
            return _cached
        try:
            with open(GLOSSARY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError, ValueError) as exc:
            logger.warning("glossary.json okunamadi (%s), bos sozluk kullaniliyor.", exc)
            data = []
        _cached = _validate_entries(data)
        return _cached


def save_glossary(entries):
    global _cached
    cleaned = _validate_entries(entries)
    with _lock:
        _cached = cleaned
        try:
            with open(GLOSSARY_PATH, "w", encoding="utf-8") as f:
                json.dump(cleaned, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.warning("glossary.json yazilamadi: %s", exc)
    return cleaned


def reset_cache():
    """Test veya elle dosya degisikliginden sonra yeniden yuklenmesi
    icin bellek onbellegini temizler."""
    global _cached
    with _lock:
        _cached = None


def build_ollama_system_block(entries):
    """Ollama'nin sistem talimatina eklenecek terim listesi blogunu
    uretir. Bos liste icin bos dize doner (talimata hic ekleme yapilmaz)."""
    if not entries:
        return ""
    lines = []
    for e in entries:
        if e["no_translate"]:
            lines.append(f'- "{e["source"]}" -> do NOT translate, keep exactly as-is')
        else:
            lines.append(f'- "{e["source"]}" -> "{e["target"]}"')
    return (
        "\n\nGLOSSARY - the source text may contain these game-specific terms "
        "(character/place/item names). Whenever one appears, ALWAYS use the "
        "exact mapping below instead of your own translation:\n" + "\n".join(lines)
    )


def protect_terms(text, entries):
    """Google Translate'e gondermeden once sozlukteki terimleri bir yer
    tutucuyla (@@G0@@ gibi) degistirir - bu sayede Google bu kelimeleri
    KENDI BASINA cevirmeye calismaz. (korunmus_metin, eslesmeler) dondurur;
    eslesmeler restore_terms() ile geri koymak icin kullanilir."""
    if not entries or not text:
        return text, []
    matches = []
    protected = text
    # Once en UZUN kaynak terimlerden baslanir: kisa bir terim, daha uzun
    # baska bir terimin PARCASI olabilir (orn. "Ldhen" ve "Badu'dan Ldhen'e").
    ordered = sorted(entries, key=lambda e: len(e["source"]), reverse=True)
    for e in ordered:
        source = e["source"]
        if not source:
            continue
        pattern = re.compile(re.escape(source), re.IGNORECASE)
        if pattern.search(protected):
            placeholder = _PLACEHOLDER_FMT.format(idx=len(matches))
            protected = pattern.sub(placeholder, protected, count=1)
            matches.append((placeholder, e))
    return protected, matches


def restore_terms(text, matches):
    """protect_terms ile konan yer tutuculari gercek (sozlukteki) hedef
    terimlerle geri koyar; "cevirme" isaretli terimler KAYNAK haliyle
    geri konur."""
    if not matches or not text:
        return text
    restored = text
    for placeholder, e in matches:
        replacement = e["source"] if e["no_translate"] else (e["target"] or e["source"])
        restored = restored.replace(placeholder, replacement)
    return restored
