"""
app/core/profiles.py testleri (4.1): oyun bazli profillerin saf karar
fonksiyonlari - hangi profilin uygulanmasi gerektigi, "genel ayarlarin"
ne zaman/nasil yakalanip geri yuklendigi, ve profil olusturma.

Gercek ekran/Windows API/Qt gerektirmez.
"""
from app.core import profiles


# ------------------------------------------------------------- resolve_target_exe
def test_resolve_target_exe_returns_none_when_disabled():
    assert profiles.resolve_target_exe("game.exe", {"game.exe": {}}, enabled=False) is None


def test_resolve_target_exe_returns_none_when_no_foreground():
    assert profiles.resolve_target_exe(None, {"game.exe": {}}, enabled=True) is None


def test_resolve_target_exe_returns_none_when_no_matching_profile():
    assert profiles.resolve_target_exe("discord.exe", {"game.exe": {}}, enabled=True) is None


def test_resolve_target_exe_returns_exe_when_profile_exists():
    assert profiles.resolve_target_exe("game.exe", {"game.exe": {}}, enabled=True) == "game.exe"


# ------------------------------------------------------------ compute_profile_sync
def test_no_change_when_target_equals_current():
    active, base, values = profiles.compute_profile_sync(
        "game.exe", "game.exe", {"game.exe": {}}, {"ocr_engine": "windows"}, {"ocr_engine": "windows"})
    assert active == "game.exe"
    assert values is None


def test_entering_profile_captures_live_values_as_base_and_applies_overrides():
    live = {"ocr_engine": "windows", "source_lang": "auto", "overlay_style": "box",
            "exclude_regions": [], "include_regions": []}
    game_profiles = {"game.exe": {"ocr_engine": "easyocr", "source_lang": "en"}}

    active, base, values = profiles.compute_profile_sync(
        None, "game.exe", game_profiles, None, live)

    assert active == "game.exe"
    assert base == live  # genel ayarlar canli degerlerden yakalandi
    assert values["ocr_engine"] == "easyocr"
    assert values["source_lang"] == "en"
    assert values["overlay_style"] == "box"  # profilde yok -> base'den kalır


def test_leaving_profile_restores_base_values():
    base = {"ocr_engine": "windows", "source_lang": "auto", "overlay_style": "box",
            "exclude_regions": [], "include_regions": []}
    live = {"ocr_engine": "easyocr", "source_lang": "en", "overlay_style": "box",
            "exclude_regions": [], "include_regions": []}

    active, new_base, values = profiles.compute_profile_sync(
        "game.exe", None, {"game.exe": {}}, base, live)

    assert active is None
    assert values == base


def test_switching_between_two_profiles_reuses_original_base_not_previous_profile():
    """A oyunundan B oyununa gecerken, A'nin degerleri degil GERCEK genel
    ayarlar temel alinmali - aksi halde profiller arasinda sizinti olurdu."""
    base = {"ocr_engine": "windows", "source_lang": "auto", "overlay_style": "box",
            "exclude_regions": [], "include_regions": []}
    game_profiles = {
        "a.exe": {"ocr_engine": "easyocr"},
        "b.exe": {"source_lang": "ja"},
    }
    # ONCE a.exe'ye girilmis (base yakalanmis) durumdayken b.exe'ye geciliyor
    active, new_base, values = profiles.compute_profile_sync(
        "a.exe", "b.exe", game_profiles, base,
        {"ocr_engine": "easyocr", "source_lang": "auto", "overlay_style": "box",
         "exclude_regions": [], "include_regions": []})

    assert active == "b.exe"
    assert new_base == base  # ayni (orijinal) temel korunuyor
    assert values["ocr_engine"] == "windows"  # a.exe'nin degeri SIZMADI
    assert values["source_lang"] == "ja"


def test_first_time_no_profile_matches_does_not_touch_base():
    active, base, values = profiles.compute_profile_sync(
        None, None, {}, None, {"ocr_engine": "windows"})
    assert active is None
    assert base is None
    assert values is None


# ------------------------------------------------------- build_profile_from_config
def test_build_profile_from_config_captures_profile_keys_and_glossary():
    config = {
        "ocr_engine": "easyocr", "source_lang": "ja", "overlay_style": "subtitle",
        "exclude_regions": [{"left": 0, "top": 0, "width": 1, "height": 1}],
        "include_regions": [], "unrelated_key": "ignored",
    }
    glossary_entries = [{"source": "Ldhen", "target": "Ldhen", "no_translate": True}]

    profile = profiles.build_profile_from_config(config, glossary_entries)

    assert profile["ocr_engine"] == "easyocr"
    assert profile["source_lang"] == "ja"
    assert profile["overlay_style"] == "subtitle"
    assert profile["exclude_regions"] == config["exclude_regions"]
    assert profile["include_regions"] == []
    assert profile["glossary"] == glossary_entries
    assert "unrelated_key" not in profile


def test_build_profile_from_config_handles_missing_glossary():
    config = {k: None for k in profiles.PROFILE_KEYS}
    profile = profiles.build_profile_from_config(config, None)
    assert profile["glossary"] == []
