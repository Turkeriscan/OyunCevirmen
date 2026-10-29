"""
Ceviri modulu testleri: baglam (context) blogu dogru olusturuluyor mu,
onbellek anahtari baglamdan bagimsiz mi, halusinasyon korumasi hala
calisiyor mu. Gercek Ollama/internet gerektirmez (HTTP cagrisi mock'lanir).
"""
from unittest.mock import patch

from app.core import translate


# ------------------------------------------------------- baglam blogu olusturma
def test_build_context_block_empty_for_no_context():
    assert translate._build_context_block(None) == ""
    assert translate._build_context_block([]) == ""


def test_build_context_block_formats_pairs():
    block = translate._build_context_block([("Hello", "Merhaba"), ("Bye", "Güle güle")])
    assert "Hello" in block and "Merhaba" in block
    assert "Bye" in block and "Güle güle" in block
    assert "CONTEXT ONLY" in block
    assert "Do NOT translate" in block


def test_build_context_block_skips_empty_pairs():
    block = translate._build_context_block([("", ""), ("A", "B")])
    assert block.count(" -> ") == 1


# --------------------------------------------------- onbellek baglamdan bagimsiz
def test_cache_key_independent_of_context(tmp_path):
    from app.core import cache as cache_mod

    config = {
        "translate_engine": "ollama", "ollama_host": "http://127.0.0.1:11434",
        "ollama_model": "test-model", "source_lang": "auto", "target_lang": "tr",
        "max_cache_memory_items": 100,
    }
    manager = translate.TranslationManager(config)
    # Gercek uygulama onbellegine/singleton'a dokunmamak icin test'e ozel,
    # gecici bir SQLite onbellegi enjekte ediyoruz.
    manager.cache = cache_mod.TranslationCache(
        max_memory_items=100, db_path=str(tmp_path / "test_cache.sqlite3")
    )

    call_count = {"n": 0}

    def fake_translate(self, text, source_lang="auto", target_lang="tr", model=None, context_lines=None, glossary_block=""):
        call_count["n"] += 1
        return "Merhaba Dünya"

    with patch.object(translate.OllamaTranslator, "translate", fake_translate):
        r1 = manager.translate("Hello World", context_lines=None)
        r2 = manager.translate("Hello World", context_lines=[("A", "B")])

    assert r1 == r2 == "Merhaba Dünya"
    # Ikinci cagri FARKLI baglamla geldi ama AYNI metin -> onbellekten gelmeli,
    # modele ikinci kez gidilmemeli.
    assert call_count["n"] == 1


# --------------------------------------------- canli onbellek siniri guncelleme
def test_translate_applies_live_cache_size_from_config(tmp_path):
    """Kullanici "Bellekte tutulacak çeviri" ayarini calisirken degistirirse,
    onbellek YENIDEN OLUSTURULMADAN (TranslationManager oturum boyunca tek
    bir kere kurulur) hemen uygulanmali - aksi halde ayar sessizce yeniden
    baslatana kadar etkisiz kalirdi."""
    from app.core import cache as cache_mod

    config = {
        "translate_engine": "ollama", "ollama_host": "http://127.0.0.1:11434",
        "ollama_model": "test-model", "source_lang": "auto", "target_lang": "tr",
        "max_cache_memory_items": 5000,
    }
    manager = translate.TranslationManager(config)
    manager.cache = cache_mod.TranslationCache(
        max_memory_items=5000, db_path=str(tmp_path / "test_cache2.sqlite3")
    )

    with patch.object(translate.OllamaTranslator, "translate", lambda *a, **k: "ok"):
        manager.translate("Hello")
        assert manager.cache.max_memory_items == 5000

        config["max_cache_memory_items"] = 7
        manager.translate("World")
        assert manager.cache.max_memory_items == 7


# ------------------------------------------------------------ ollama entegrasyonu
def test_ollama_translator_includes_context_in_system_message():
    translator = translate.OllamaTranslator(host="http://127.0.0.1:11434", model="m")
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "Merhaba"}}

    def fake_post(url, json=None, timeout=None):
        captured["payload"] = json
        return _FakeResponse()

    with patch.object(translator._session, "post", side_effect=fake_post):
        result = translator.translate(
            "Hello", context_lines=[("Hi there", "Merhaba orada")]
        )

    assert result == "Merhaba"
    system_msg = captured["payload"]["messages"][0]["content"]
    assert "Hi there" in system_msg
    assert "Merhaba orada" in system_msg
    assert "CONTEXT ONLY" in system_msg
    # Asil cevrilecek metin hala ayri, kullanici mesaji olarak gidiyor
    assert captured["payload"]["messages"][1]["content"] == "Hello"


def test_ollama_translator_without_context_has_clean_system_message():
    translator = translate.OllamaTranslator(host="http://127.0.0.1:11434", model="m")
    captured = {}

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "Merhaba"}}

    def fake_post(url, json=None, timeout=None):
        captured["payload"] = json
        return _FakeResponse()

    with patch.object(translator._session, "post", side_effect=fake_post):
        translator.translate("Hello", context_lines=None)

    assert "CONTEXT ONLY" not in captured["payload"]["messages"][0]["content"]


# -------------------------------------------------- halusinasyon korumasi bozulmadi
def test_hallucination_guard_still_works_with_context_param():
    """Baglam eklenmis olsa bile halusinasyon kontrolu (_looks_like_hallucination)
    hala asil kaynak/ceviri ciftine bakarak calismali."""
    long_fake = "Bu çok uzun ve alakasız bir açıklama metni " * 5
    assert translate._looks_like_hallucination("Hi", long_fake)
    assert not translate._looks_like_hallucination("Hi", "Merhaba")


# ------------------------------------------- 1.4: yedek sonucu tekrar bulunabilmeli
def test_google_fallback_result_is_cached_under_primary_engine_key(tmp_path):
    """Ollama basarisiz olup Google yedegine dusuldugunde, sonuc GELECEKTEKI
    aramalarin kullanacagi anahtarla (engine_pref='ollama') kaydedilmeli -
    eskiden 'google' anahtariyla kaydedildigi icin ayni satir HER SEFERINDE
    once basarisiz Ollama'ya gidip tekrar Google'a duserdi."""
    from app.core import cache as cache_mod

    config = {
        "translate_engine": "ollama", "ollama_host": "http://127.0.0.1:11434",
        "ollama_model": "test-model", "source_lang": "auto", "target_lang": "tr",
        "max_cache_memory_items": 100, "allow_google_fallback": True,
    }
    manager = translate.TranslationManager(config)
    manager.cache = cache_mod.TranslationCache(
        max_memory_items=100, db_path=str(tmp_path / "fallback_cache.sqlite3")
    )

    ollama_calls = {"n": 0}
    google_calls = {"n": 0}

    def ollama_fails(self, text, source_lang="auto", target_lang="tr", model=None, context_lines=None, glossary_block=""):
        ollama_calls["n"] += 1
        return None  # Ollama cevap vermiyor

    def google_succeeds(self, text, source_lang="auto", target_lang="tr"):
        google_calls["n"] += 1
        return "Merhaba Dunya"

    with patch.object(translate.OllamaTranslator, "translate", ollama_fails), \
         patch.object(translate.GoogleFallbackTranslator, "translate", google_succeeds):
        first = manager.translate("Hello World")
        second = manager.translate("Hello World")  # AYNI metin tekrar geldi

    assert first == second == "Merhaba Dunya"
    # Ikinci cagri onbellekten gelmeli - Ollama'ya VE Google'a TEKRAR gidilmemeli
    assert ollama_calls["n"] == 1
    assert google_calls["n"] == 1

    # Kayit, kullanicinin SECTIGI motor anahtariyla (ollama) bulunabilir olmali
    cached = manager.cache.get("Hello World", "auto", "tr", "ollama")
    assert cached == "Merhaba Dunya"


def test_fallback_cache_entry_is_marked_and_expires_allowing_ollama_retry(tmp_path):
    """Yedekten gelen kayit suresi dolunca, Ollama duzelmisse YENI (ve bu
    kez Ollama'dan gelen) bir ceviri uretilebilmeli."""
    from app.core import cache as cache_mod

    config = {
        "translate_engine": "ollama", "ollama_host": "http://127.0.0.1:11434",
        "ollama_model": "test-model", "source_lang": "auto", "target_lang": "tr",
        "max_cache_memory_items": 100, "allow_google_fallback": True,
    }
    manager = translate.TranslationManager(config)
    manager.cache = cache_mod.TranslationCache(
        max_memory_items=100, db_path=str(tmp_path / "fallback_cache2.sqlite3")
    )

    with patch.object(translate.OllamaTranslator, "translate", lambda *a, **k: None), \
         patch.object(translate.GoogleFallbackTranslator, "translate", lambda *a, **k: "Google cevirisi"):
        manager.translate("Hello Again")

    key = cache_mod._make_key("Hello Again", "auto", "tr", "ollama")
    text, is_fallback, created, is_manual = manager.cache._mem[key]
    assert is_fallback is True
    # Suresini (hem bellekte hem diskte, gercek yaslanmayla tutarli olacak
    # sekilde) simule olarak doldur.
    manager.cache._mem[key] = (text, is_fallback, created - cache_mod.FALLBACK_TTL_SECONDS - 1, is_manual)
    manager.cache._conn.execute(
        "UPDATE translations SET created_at = ? WHERE key = ?", ("2000-01-01 00:00:00", key)
    )
    manager.cache._conn.commit()

    with patch.object(translate.OllamaTranslator, "translate", lambda *a, **k: "Ollama cevirisi"):
        result = manager.translate("Hello Again")

    assert result == "Ollama cevirisi"  # Ollama duzeldi, yeniden denendi ve kazandi


def test_non_fallback_result_cached_without_fallback_flag(tmp_path):
    """Ollama DOGRUDAN basarili olursa, kayit yedek isaretli olmamali
    (suresiz gecerli kalmali)."""
    from app.core import cache as cache_mod

    config = {
        "translate_engine": "ollama", "ollama_host": "http://127.0.0.1:11434",
        "ollama_model": "test-model", "source_lang": "auto", "target_lang": "tr",
        "max_cache_memory_items": 100,
    }
    manager = translate.TranslationManager(config)
    manager.cache = cache_mod.TranslationCache(
        max_memory_items=100, db_path=str(tmp_path / "normal_cache.sqlite3")
    )

    with patch.object(translate.OllamaTranslator, "translate", lambda *a, **k: "Merhaba"):
        manager.translate("Hi")

    key = cache_mod._make_key("Hi", "auto", "tr", "ollama")
    _text, is_fallback, _created, _is_manual = manager.cache._mem[key]
    assert is_fallback is False


# ---------------------------------------- 2.3: OCR hatalarini tolere etme
def test_system_prompt_includes_ocr_error_tolerance_rule():
    assert "OCR" in translate.SYSTEM_PROMPT_TR
    assert "misreads" in translate.SYSTEM_PROMPT_TR
    assert "do not mention or explain the correction" in translate.SYSTEM_PROMPT_TR


def test_ocr_tolerance_rule_does_not_weaken_hallucination_guard():
    """Yeni kural, modelin ne yapmasi gerektigini anlatan sistem talimatina
    eklendi - _looks_like_hallucination SADECE ciktinin kendisine
    (uzunluk/bicimleme) bakar, bu kuraldan bagimsiz calismaya devam
    etmeli."""
    long_fake = "Bu çok uzun ve alakasız bir açıklama metni " * 5
    assert translate._looks_like_hallucination("Hi", long_fake)
    assert not translate._looks_like_hallucination("Hi", "Merhaba")


# ------------------------------------------------------ 2.5: cok motorlu zincir
def test_argos_unavailable_when_not_installed():
    """Argos Translate kurulu degilse (gercek ortamda kurulu olmayabilir),
    is_available() False donup sessizce atlanmali - hata firlatmamali."""
    translator = translate.ArgosTranslator()
    # Gercekten kurulu olup olmadigina bakmaksizin, API cokmemeli:
    available = translator.is_available()
    assert isinstance(available, bool)
    if not available:
        assert translator.translate("Hello") is None


def test_argos_unavailable_simulated_via_import_error():
    translator = translate.ArgosTranslator()
    with patch("builtins.__import__", side_effect=ImportError("yok")):
        assert translator.is_available() is False
        assert translator.translate("Hello") is None


def test_deepl_without_api_key_is_not_configured():
    translator = translate.DeepLTranslator(api_key="")
    assert translator.is_configured() is False
    assert translator.translate("Hello") is None


def test_deepl_with_api_key_calls_api():
    translator = translate.DeepLTranslator(api_key="test-key")
    assert translator.is_configured() is True

    class _FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"translations": [{"text": "Merhaba"}]}

    captured = {}

    def fake_post(url, data=None, timeout=None):
        captured["url"] = url
        captured["data"] = data
        return _FakeResponse()

    with patch.object(translator._session, "post", side_effect=fake_post):
        result = translator.translate("Hello", source_lang="en", target_lang="tr")

    assert result == "Merhaba"
    assert captured["data"]["auth_key"] == "test-key"
    assert captured["data"]["target_lang"] == "TR"
    assert captured["data"]["source_lang"] == "EN"


def test_deepl_handles_request_exception_gracefully():
    translator = translate.DeepLTranslator(api_key="test-key")
    with patch.object(translator._session, "post", side_effect=RuntimeError("ag hatasi")):
        assert translator.translate("Hello") is None


def test_engine_order_puts_primary_first_then_fallback_chain():
    config = {"translate_engine": "ollama", "fallback_order": ["ollama", "argos", "google"]}
    manager = translate.TranslationManager(config)
    assert manager._engine_order("ollama") == ["ollama", "argos", "google"]


def test_engine_order_dedupes_primary_from_fallback_chain():
    config = {"fallback_order": ["ollama", "argos", "google"]}
    manager = translate.TranslationManager(config)
    assert manager._engine_order("google") == ["google", "ollama", "argos"]


def test_engine_order_falls_back_to_default_when_unset():
    manager = translate.TranslationManager({})
    assert manager._engine_order("ollama") == translate.DEFAULT_FALLBACK_ORDER


def test_engine_order_ignores_unknown_engine_names():
    config = {"fallback_order": ["ollama", "bilinmeyen_motor", "google"]}
    manager = translate.TranslationManager(config)
    assert manager._engine_order("ollama") == ["ollama", "google"]


def test_chain_tries_argos_before_google_when_ollama_fails(tmp_path):
    """Ollama basarisiz olunca, fallback_order'da Google'dan ONCE gelen
    Argos (kuruluysa) denenmeli."""
    from app.core import cache as cache_mod
    import os

    config = {
        "translate_engine": "ollama", "ollama_host": "http://127.0.0.1:11434",
        "ollama_model": "m", "source_lang": "auto", "target_lang": "tr",
        "max_cache_memory_items": 100, "allow_google_fallback": True,
        "fallback_order": ["ollama", "argos", "google"],
    }
    manager = translate.TranslationManager(config)
    manager.cache = cache_mod.TranslationCache(
        max_memory_items=100, db_path=os.path.join(str(tmp_path), "chain.sqlite3")
    )

    google_calls = {"n": 0}

    def google_translate(self, text, source_lang="auto", target_lang="tr"):
        google_calls["n"] += 1
        return "Google'dan"

    with patch.object(translate.OllamaTranslator, "translate", lambda *a, **k: None), \
         patch.object(translate.ArgosTranslator, "is_available", return_value=True), \
         patch.object(translate.ArgosTranslator, "translate", return_value="Argos'tan"), \
         patch.object(translate.GoogleFallbackTranslator, "translate", google_translate):
        result = manager.translate("Hello")

    assert result == "Argos'tan"
    assert google_calls["n"] == 0  # Argos basarili oldu, Google'a hic gidilmedi


def test_argos_skipped_silently_when_unavailable(tmp_path):
    from app.core import cache as cache_mod
    import os

    config = {
        "translate_engine": "ollama", "source_lang": "auto", "target_lang": "tr",
        "max_cache_memory_items": 100, "allow_google_fallback": True,
        "fallback_order": ["ollama", "argos", "google"],
    }
    manager = translate.TranslationManager(config)
    manager.cache = cache_mod.TranslationCache(
        max_memory_items=100, db_path=os.path.join(str(tmp_path), "chain2.sqlite3")
    )

    with patch.object(translate.OllamaTranslator, "translate", lambda *a, **k: None), \
         patch.object(translate.ArgosTranslator, "is_available", return_value=False), \
         patch.object(translate.GoogleFallbackTranslator, "translate", lambda *a, **k: "Google'dan"):
        result = manager.translate("Hello")

    assert result == "Google'dan"


def test_google_as_primary_does_not_require_permission(tmp_path):
    """Google BIRINCIL motor olarak secilmisse (position 0), izin
    kontrolu hic yapilmamali."""
    from app.core import cache as cache_mod
    import os

    config = {
        "translate_engine": "google", "source_lang": "auto", "target_lang": "tr",
        "max_cache_memory_items": 100, "allow_google_fallback": None,  # izin SORULMADI
        "fallback_order": [],
    }
    manager = translate.TranslationManager(config)
    manager.cache = cache_mod.TranslationCache(
        max_memory_items=100, db_path=os.path.join(str(tmp_path), "chain3.sqlite3")
    )

    with patch.object(translate.GoogleFallbackTranslator, "translate", lambda *a, **k: "Merhaba"):
        result = manager.translate("Hello")

    assert result == "Merhaba"


def test_hallucination_check_applies_uniformly_to_fallback_engines(tmp_path):
    """Eskiden Google, Ollama DOGRUDAN basarisiz oldugunda (hallucinate
    degil) kontrolsuz kullanilirdi; artik HER motorun sonucu
    halusinasyon kontrolunden gecer."""
    from app.core import cache as cache_mod
    import os

    long_fake = "Bu çok uzun ve alakasız bir açıklama metni " * 5
    config = {
        "translate_engine": "ollama", "source_lang": "auto", "target_lang": "tr",
        "max_cache_memory_items": 100, "allow_google_fallback": True,
        "fallback_order": ["ollama", "google"],
    }
    manager = translate.TranslationManager(config)
    manager.cache = cache_mod.TranslationCache(
        max_memory_items=100, db_path=os.path.join(str(tmp_path), "chain4.sqlite3")
    )

    with patch.object(translate.OllamaTranslator, "translate", lambda *a, **k: None), \
         patch.object(translate.GoogleFallbackTranslator, "translate", lambda *a, **k: long_fake):
        result = manager.translate("Hi")

    assert result is None
