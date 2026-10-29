"""
Ceviri onbellegi: once bellekte (hizli, RAM'de dict + OrderedDict LRU),
bulunamazsa diskte (SQLite) arar. SQLite sayesinde program kapatilip
acilsa bile ayni metinler tekrar tekrar modele/Google'a gonderilmez.
"""
import os
import sqlite3
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "cache", "translations.sqlite3")

# Bir satir, kullanicinin SECTIGI motor (engine_pref) yerine YEDEK motordan
# (orn. Ollama cokmusken Google) geldiyse, bu kayit "yedekten geldi"
# isaretlenir ve bu sure sonunda "suresi dolmus" sayilir - boylece tercih
# edilen motor (orn. Ollama) duzelince, aynI satir tekrar geldiginde ona
# bir sans daha verilir; sonsuza dek yedegin cevirisine mahkum kalinmaz.
FALLBACK_TTL_SECONDS = 600  # 10 dakika


def _make_key(text, source_lang, target_lang, engine):
    return f"{engine}|{source_lang}|{target_lang}|{text}"


def _parse_sqlite_timestamp(value):
    """SQLite'in CURRENT_TIMESTAMP'inin yazdigi 'YYYY-MM-DD HH:MM:SS' (UTC)
    bicimini Unix zaman damgasina cevirir. Ayrıstirilamazsa 0.0 doner
    (yedek kaydi guvenli tarafta kalip suresi dolmus sayilir)."""
    try:
        dt = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


class TranslationCache:
    def __init__(self, max_memory_items=5000, db_path=DB_PATH):
        self.max_memory_items = max_memory_items
        self._mem = OrderedDict()  # key -> (translated_text, is_fallback, created_at_unix)
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS translations (
                key TEXT PRIMARY KEY,
                source_text TEXT NOT NULL,
                source_lang TEXT,
                target_lang TEXT,
                engine TEXT,
                translated_text TEXT NOT NULL,
                is_fallback INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._ensure_is_fallback_column()
        self._conn.commit()

    def _ensure_is_fallback_column(self):
        """Eski (bu alan eklenmeden once olusturulmus) bir translations.sqlite3
        dosyasini geriye uyumlu sekilde gunceller."""
        try:
            cols = {row[1] for row in self._conn.execute("PRAGMA table_info(translations)")}
            if "is_fallback" not in cols:
                self._conn.execute(
                    "ALTER TABLE translations ADD COLUMN is_fallback INTEGER DEFAULT 0"
                )
        except Exception:
            pass

    def get(self, text, source_lang, target_lang, engine):
        key = _make_key(text, source_lang, target_lang, engine)
        with self._lock:
            entry = self._mem.get(key)
            if entry is not None:
                translated_text, is_fallback, created_at = entry
                if is_fallback and (time.time() - created_at) > FALLBACK_TTL_SECONDS:
                    del self._mem[key]
                else:
                    self._mem.move_to_end(key)
                    return translated_text
        try:
            row = self._conn.execute(
                "SELECT translated_text, is_fallback, created_at FROM translations WHERE key = ?",
                (key,),
            ).fetchone()
        except Exception:
            return None
        if row:
            translated_text, is_fallback, created_at_str = row
            is_fallback = bool(is_fallback)
            created_at = _parse_sqlite_timestamp(created_at_str)
            if is_fallback and (time.time() - created_at) > FALLBACK_TTL_SECONDS:
                return None  # suresi dolmus yedek ceviri; tercih edilen motora tekrar sans ver
            with self._lock:
                self._mem[key] = (translated_text, is_fallback, created_at)
                self._trim_memory()
            return translated_text
        return None

    def set(self, text, source_lang, target_lang, engine, translated_text, is_fallback=False):
        key = _make_key(text, source_lang, target_lang, engine)
        now = time.time()
        with self._lock:
            self._mem[key] = (translated_text, bool(is_fallback), now)
            self._trim_memory()
        try:
            self._conn.execute(
                """
                INSERT INTO translations
                    (key, source_text, source_lang, target_lang, engine, translated_text, is_fallback)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    translated_text = excluded.translated_text,
                    is_fallback = excluded.is_fallback,
                    created_at = CURRENT_TIMESTAMP
                """,
                (key, text, source_lang, target_lang, engine, translated_text, int(bool(is_fallback))),
            )
            self._conn.commit()
        except Exception:
            pass

    def _trim_memory(self):
        while len(self._mem) > self.max_memory_items:
            self._mem.popitem(last=False)

    def set_max_memory_items(self, n):
        """Kullanici Gelismis sayfasindaki "Bellekte tutulacak çeviri"
        ayarini calisirken degistirebilir; TranslationCache bir kere
        kurulup oturum boyunca tekrar olusturulmadigi icin bu deger
        config'ten canli olarak bu metotla yeniden uygulanmalidir (bkz.
        TranslationManager.translate)."""
        with self._lock:
            self.max_memory_items = max(1, int(n))
            self._trim_memory()

    def count(self):
        """Diskte kayitli toplam ceviri sayisi."""
        try:
            row = self._conn.execute("SELECT COUNT(*) FROM translations").fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0

    def clear(self):
        """Hem bellek hem disk onbellegini bosaltir."""
        with self._lock:
            self._mem.clear()
        try:
            self._conn.execute("DELETE FROM translations")
            self._conn.commit()
        except Exception:
            pass

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


_singleton = None
_singleton_lock = threading.Lock()


def get_cache(max_memory_items=5000):
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = TranslationCache(max_memory_items=max_memory_items)
        return _singleton
