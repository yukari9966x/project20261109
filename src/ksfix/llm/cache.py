"""LLM 응답 캐시(SQLite, 키 = 모델·프롬프트 버전·입력 해시) → 재현성과 비용 절감."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


def cache_key(model: str, prompt_version: str, system: str, user: str, temperature: float) -> str:
    raw = json.dumps([model, prompt_version, system, user, temperature], ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class LLMCache:
    def __init__(self, path: str | Path | None = None):
        self._mem: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._db = None
        if path is not None:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(p), check_same_thread=False)
            self._db.execute("CREATE TABLE IF NOT EXISTS llm (k TEXT PRIMARY KEY, v TEXT NOT NULL)")
            self._db.commit()

    def get(self, key: str) -> Any:
        with self._lock:
            if key in self._mem:
                return self._mem[key]
            if self._db is not None:
                row = self._db.execute("SELECT v FROM llm WHERE k = ?", (key,)).fetchone()
                if row:
                    val = json.loads(row[0])
                    self._mem[key] = val
                    return val
        return None

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._mem[key] = value
            if self._db is not None:
                self._db.execute(
                    "INSERT OR REPLACE INTO llm (k, v) VALUES (?, ?)",
                    (key, json.dumps(value, ensure_ascii=False)),
                )
                self._db.commit()
