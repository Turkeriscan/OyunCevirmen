"""
Oyun bazli profiller (4.1): on plandaki .exe'ye gore OCR motoru/dili,
overlay stili ve okuma bolgelerini otomatik degistirir. Sozluk (glossary)
de profile dahildir ama config'in disinda (TranslationManager.active_profile_glossary
uzerinden) tasinir - bkz. app/main.py Orchestrator._sync_active_profile.

Bu modul SAF (Qt/threading/IO icermez) - Orchestrator durumu (hangi profil
su an aktif, "genel ayar" anlik goruntusu) kendi tarafinda tutar, kararlari
buradaki fonksiyonlara sorar.
"""

PROFILE_KEYS = ("ocr_engine", "source_lang", "overlay_style", "exclude_regions", "include_regions")

POLL_INTERVAL_SECONDS = 2.0


def resolve_target_exe(fg_exe, game_profiles, enabled):
    """Bu an itibariyle uygulanmasi gereken profilin exe adini (ya da
    profil yoksa/ozellik kapaliysa None) dondurur."""
    if not enabled or not fg_exe:
        return None
    return fg_exe if fg_exe in game_profiles else None


def compute_profile_sync(current_active_exe, target_exe, game_profiles,
                          current_base_snapshot, live_config_snapshot):
    """Profil degisimi icin saf karar fonksiyonu.

    current_active_exe: su an aktif sayilan profilin exe'si (yoksa None).
    target_exe: bu turda uygulanmasi gereken exe (genel ayarlara donulmesi
        gerekiyorsa None).
    current_base_snapshot: ONCEDEN alinmis "genel ayar" anlik goruntusu
        (hic profile girilmediyse None).
    live_config_snapshot: su anki canli config degerleri (PROFILE_KEYS icin) -
        HENUZ bir profile girilmemisse bu degerler "genel ayar" olarak
        yakalanir (kullanicinin en son elle ayarladigi degerler olsun diye).

    (yeni_active_exe, yeni_base_snapshot, uygulanacak_degerler_veya_None) dondurur.
    uygulanacak_degerler_veya_None: config'e YAZILMASI gereken {key: value}
    sozlugu - degisiklik yoksa None (cagiran taraf config'e dokunmamali)."""
    if target_exe == current_active_exe:
        return current_active_exe, current_base_snapshot, None

    base = current_base_snapshot
    if current_active_exe is None:
        base = dict(live_config_snapshot)

    if target_exe is None:
        values = dict(base)
    else:
        profile = game_profiles.get(target_exe, {})
        values = dict(base)
        values.update({k: profile[k] for k in PROFILE_KEYS if k in profile})

    return target_exe, base, values


def build_profile_from_config(config, glossary_entries):
    """Su anki (canli) config degerlerinden YENI bir profil sozlugu olusturur
    (kaydet/guncelle islemlerinde kullanilir)."""
    profile = {k: config.get(k) for k in PROFILE_KEYS}
    profile["glossary"] = list(glossary_entries or [])
    return profile
