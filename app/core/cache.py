"""
Ceviri onbellegi: once bellekte (hizli, RAM'de dict + OrderedDict LRU),
bulunamazsa diskte (SQLite) arar. SQLite sayesinde program kapatilip
acilsa bile ayni metinler tekrar tekrar modele/Google'a gonderilmez.
"""
import os
import sqlite3
import threading
from collections import OrderedDict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "cache", "translations.sqlite3")


def _make_key(text, source_lang, target_lang, engine):
    return f"{engine}|{source_lang}|{target_lang}|{text}"


class TranslationCache:
    def __init__(self, max_memory_items=5000, db_path=DB_PATH):
        self.max_memory_items = max_memory_items
        self._mem = OrderedDict()  # key -> translated text
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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self._conn.commit()

    def get(self, text, source_lang, target_lang, engine):
        key = _make_key(text, source_lang, target_lang, engine)
        with self._lock:
            if key in self._mem:
                self._mem.move_to_end(key)
                return self._mem[key]
        row = self._conn.execute(
            "SELECT translated_text FROM translations WHERE key = ?", (key,)
        ).fetchone()
        if row:
            with self._lock:
                self._mem[key] = row[0]
                self._trim_memory()
            return row[0]
        return None

    def set(self, text, source_lang, target_lang, engine, translated_text):
        key = _make_key(text, source_lang, target_lang, engine)
        with self._lock:
            self._mem[key] = translated_text
            self._trim_memory()
        try:
            self._conn.execute(
                """
                INSERT INTO translations (key, source_text, source_lang, target_lang, engine, translated_text)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET translated_text = excluded.translated_text
                """,
                (key, text, source_lang, target_lang, engine, translated_text),
            )
            self._conn.commit()
        except Exception:
            pass

    def _trim_memory(self):
        while len(self._mem) > self.max_memory_items:
            self._mem.popitem(last=False)

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
