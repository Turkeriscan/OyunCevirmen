"""
Donanima gore Ollama model onerisi. Ekran kartinin bellegini (VRAM)
nvidia-smi ile okur; NVIDIA karti yoksa veya bellek azsa daha kucuk
(CPU'da da calisabilen) bir model onerir.
"""
import logging
import subprocess

logger = logging.getLogger("OyunCevirmen.hardware")

CREATE_NO_WINDOW = 0x08000000

# Model adi -> (asgari onerilen VRAM MB, aciklama)
RECOMMENDED_MODEL_LARGE = "aya-expanse:8b"
RECOMMENDED_MODEL_SMALL = "gemma2:2b"


def detect_gpu_vram_mb():
    """NVIDIA ekran kartinin toplam bellegini (MB) dondurur; kart yoksa
    veya nvidia-smi calismiyorsa None doner (NVIDIA olmayan bilgisayarlar
    icin de - orn. AMD/Intel - bu fonksiyon guvenle None doner)."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            creationflags=CREATE_NO_WINDOW, timeout=5,
        ).decode("utf-8", "ignore").strip()
        first_line = out.splitlines()[0].strip()
        return int(float(first_line))
    except Exception as exc:
        logger.info("GPU VRAM bilgisi alinamadi (NVIDIA karti olmayabilir): %s", exc)
        return None


def recommend_ollama_model(vram_mb):
    """VRAM miktarina (MB) gore onerilen Ollama modelini dondurur.
    vram_mb None ise (NVIDIA karti yok/okunamadi) kucuk modeli onerir -
    CPU'da da makul hizda calisabilir."""
    if vram_mb is None or vram_mb < 6000:
        return RECOMMENDED_MODEL_SMALL
    return RECOMMENDED_MODEL_LARGE


def recommend_model_for_this_machine():
    """detect_gpu_vram_mb() + recommend_ollama_model()'i birlestirir;
    (model_adi, vram_mb) dondurur."""
    vram_mb = detect_gpu_vram_mb()
    return recommend_ollama_model(vram_mb), vram_mb
