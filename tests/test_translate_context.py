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
