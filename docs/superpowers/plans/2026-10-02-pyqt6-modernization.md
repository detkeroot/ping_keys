# Gemini Nexus DB (PyQt6 Native Wayland) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-architect and modernize Gemini Nexus DB from a monolithic CustomTkinter script into a high-performance, modular PyQt6 application with native Wayland HiDPI support and zero PII.

**Architecture:** Decompose the application into a decoupled Service-Repository pattern: isolated `core/` package (pure Python business logic, SQLite WAL repo, zero-dependency cryptography, network dispatcher, stream balancer) and modern `ui/` package (PyQt6 native Wayland, `pyqtdarktheme`, QThread workers with Qt signals, virtualized `QTableView`).

**Tech Stack:** Python 3.10+, PyQt6 (Qt 6.11), `pyqtdarktheme`, `PySocks`, SQLite (WAL mode), NixOS Flake (`qt6.qtwayland`, `wrapQtAppsHook`).

**Spec:** `docs/superpowers/specs/2026-10-02-gemini-nexus-pyqt6-modernization-design.md`

## Global Constraints

- **Strict Public Repository Policy:** Absolutely ZERO Personally Identifiable Information (no real names, addresses, private phones, private credentials). Author identity is strictly `detkeroot` / `NeuroStarNet`.
- **Zero API Key Leakage:** Do not commit or hardcode real API keys or database dumps. `gemini_keys.db` must remain gitignored.
- **Model Lineup Standard:** Default and recommended models must prioritize Gemini 3.x (`gemini-3.8-flash`, `gemini-3.8-flash-high`, `gemini-3.7-flash`).
- **Native Wayland HiDPI:** Zero XWayland blurriness; must render cleanly under Wayland with fractional scaling (1.8x).
- **Test-Driven Rigor:** Core modules (`crypto`, `db`, `splitter`, `checker`) must have isolated pytest test suites.

---

### Task 1: Package Scaffolding & Core Configuration

**Files:**
- Create: `gemini_nexus/__init__.py`
- Create: `gemini_nexus/core/__init__.py`
- Create: `gemini_nexus/core/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `APP_NAME`, `APP_VERSION`, `DEFAULT_DB_PATH`, `STATUS_COLORS`, `STATUS_RU`, `DEFAULT_MODELS`, `ConfigManager`

- [ ] **Step 1: Write the failing test for core configuration**

```python
# tests/test_config.py
from gemini_nexus.core.config import APP_NAME, APP_VERSION, DEFAULT_MODELS, STATUS_RU

def test_config_constants():
    assert "Gemini Nexus" in APP_NAME
    assert APP_VERSION.startswith("14.")
    assert "gemini-3.8-flash" in DEFAULT_MODELS
    assert "OK" in STATUS_RU
    assert STATUS_RU["OK"] == "Работает"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'gemini_nexus'

- [ ] **Step 3: Implement `gemini_nexus/__init__.py`, `gemini_nexus/core/__init__.py` and `gemini_nexus/core/config.py`**

```python
# gemini_nexus/__init__.py
"""Gemini Nexus DB - Modernized Enterprise Edition."""
__version__ = "14.0.0"
__author__ = "NeuroStarNet"

# gemini_nexus/core/__init__.py
"""Core logic and services for Gemini Nexus."""

# gemini_nexus/core/config.py
from pathlib import Path
from typing import Dict, List

APP_NAME: str = "Gemini Nexus DB"
APP_VERSION: str = "14.0.0"
AUTHOR: str = "NeuroStarNet"
DEFAULT_DB_FILE: str = "gemini_keys.db"

# Gemini 3.x flagship line + standard models
DEFAULT_MODELS: List[str] = [
    "gemini-3.8-flash",
    "gemini-3.8-flash-high",
    "gemini-3.7-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite-preview",
    "gemma-3-27b-it",
]

STATUS_RU: Dict[str, str] = {
    "OK": "Работает",
    "UNCHECKED": "Не проверен",
    "RESOURCE_EXHAUSTED": "Лимит (429)",
    "UNRESTRICTED": "Ограничен Google (19 июня)",
    "SERVICE_UNAVAILABLE": "Сервис недоступен (503)",
    "INTERNAL_ERROR": "Ошибка сервера Google (500)",
    "DEADLINE_EXCEEDED": "Таймаут генерации (504)",
    "TIMEOUT": "Таймаут соединения",
    "FAILED_PRECONDITION": "Регион/Оплата (400)",
    "PERMISSION_DENIED": "Бан/Нет доступа (403)",
    "UNAUTHORIZED": "Не существует (401)",
    "NOT_FOUND": "Модель не найдена (404)",
}

STATUS_COLORS: Dict[str, str] = {
    "OK": "#2ecc71",
    "UNCHECKED": "#7f8c8d",
    "RESOURCE_EXHAUSTED": "#f39c12",
    "UNRESTRICTED": "#e67e22",
    "SERVICE_UNAVAILABLE": "#f1c40f",
    "INTERNAL_ERROR": "#e74c3c",
    "DEADLINE_EXCEEDED": "#e67e22",
    "TIMEOUT": "#95a5a6",
    "FAILED_PRECONDITION": "#c0392b",
    "PERMISSION_DENIED": "#c0392b",
    "UNAUTHORIZED": "#962d22",
    "NOT_FOUND": "#e74c3c",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gemini_nexus/ tests/test_config.py
git commit -m "feat(core): initialize package structure and core configuration"
```

---

### Task 2: Pure-Python Cryptography Subsystem

**Files:**
- Create: `gemini_nexus/core/crypto.py`
- Test: `tests/test_crypto.py`

**Interfaces:**
- Produces: `encrypt_data(data_str: str, password: str) -> str`, `decrypt_data(payload_b64: str, password: str) -> str | None`

- [ ] **Step 1: Write the failing tests for encryption and decryption**

```python
# tests/test_crypto.py
from gemini_nexus.core.crypto import encrypt_data, decrypt_data

def test_encrypt_decrypt_roundtrip():
    secret_text = "AQ.TestKey_1234567890_SecretData"
    password = "CorrectHorseBatteryStaple123!"
    
    encrypted = encrypt_data(secret_text, password)
    assert isinstance(encrypted, str)
    assert encrypted != secret_text
    
    decrypted = decrypt_data(encrypted, password)
    assert decrypted == secret_text

def test_decrypt_wrong_password():
    secret_text = "SensitiveKeyPayload"
    encrypted = encrypt_data(secret_text, "correct_password")
    
    decrypted = decrypt_data(encrypted, "wrong_password")
    assert decrypted is None

def test_decrypt_corrupted_payload():
    assert decrypt_data("not_a_valid_base64_payload!", "password") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_crypto.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'gemini_nexus.core.crypto'

- [ ] **Step 3: Implement `gemini_nexus/core/crypto.py`**

```python
# gemini_nexus/core/crypto.py
import base64
import hashlib
import hmac
import secrets
from typing import Optional

def encrypt_data(data_str: str, password: str) -> str:
    """Encrypts a string using PBKDF2-HMAC-SHA256, CTR stream keystream and HMAC-SHA256 authentication."""
    salt = secrets.token_bytes(16)
    # Derive 64 bytes: 32 bytes for CTR keystream seed, 32 bytes for HMAC
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000, dklen=64)
    enc_key, hmac_key = derived[:32], derived[32:]
    
    iv = secrets.token_bytes(16)
    plaintext_bytes = data_str.encode("utf-8")
    
    # CTR mode generator
    ciphertext = bytearray()
    counter = 0
    for i in range(0, len(plaintext_bytes), 32):
        counter_bin = counter.to_bytes(16, "big")
        keystream_block = hashlib.sha256(enc_key + iv + counter_bin).digest()
        chunk = plaintext_bytes[i:i + 32]
        for b_plain, b_key in zip(chunk, keystream_block):
            ciphertext.append(b_plain ^ b_key)
        counter += 1
        
    tag = hmac.new(hmac_key, iv + ciphertext, hashlib.sha256).digest()
    final_payload = salt + iv + tag + bytes(ciphertext)
    return base64.b64encode(final_payload).decode("utf-8")

def decrypt_data(payload_str: str, password: str) -> Optional[str]:
    """Decrypts a base64 payload. Returns None if password is wrong or integrity check fails."""
    try:
        payload = base64.b64decode(payload_str.encode("utf-8"))
        if len(payload) < 64:  # 16 salt + 16 iv + 32 tag
            return None
        
        salt = payload[:16]
        iv = payload[16:32]
        tag = payload[32:64]
        ciphertext = payload[64:]
        
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000, dklen=64)
        enc_key, hmac_key = derived[:32], derived[32:]
        
        expected_tag = hmac.new(hmac_key, iv + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(tag, expected_tag):
            return None
            
        plaintext = bytearray()
        counter = 0
        for i in range(0, len(ciphertext), 32):
            counter_bin = counter.to_bytes(16, "big")
            keystream_block = hashlib.sha256(enc_key + iv + counter_bin).digest()
            chunk = ciphertext[i:i + 32]
            for b_cipher, b_key in zip(chunk, keystream_block):
                plaintext.append(b_cipher ^ b_key)
            counter += 1
            
        return plaintext.decode("utf-8")
    except Exception:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_crypto.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gemini_nexus/core/crypto.py tests/test_crypto.py
git commit -m "feat(crypto): implement zero-dependency authenticated stream cipher"
```

---

### Task 3: SQLite Repository & Database Engine

**Files:**
- Create: `gemini_nexus/core/db.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Produces: `Database` class with methods:
  - `init_db()`
  - `get_owners() -> list[tuple[int, str, str, int]]`
  - `add_owner(nickname: str, notes: str) -> int`
  - `delete_owner(owner_id: int) -> None`
  - `add_keys(owner_id: int, key_strings: list[str]) -> tuple[int, int]`
  - `get_keys(status_filter: str, search_query: str) -> list[dict]`
  - `update_key_status(key_id: int, status: str, detail: str)`
  - `toggle_key_ignored(key_id: int) -> bool`
  - `delete_key(key_id: int)`
  - `reset_statuses(owner_id: int | None = None)`
  - `delete_broken_keys() -> int`
  - `get_models() -> list[str]`
  - `add_model(name: str) -> bool`
  - `get_setting(key: str, default: str) -> str`
  - `set_setting(key: str, value: str)`

- [ ] **Step 1: Write failing tests for Database repository**

```python
# tests/test_db.py
import pytest
from gemini_nexus.core.db import Database

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_gemini.db"
    db = Database(str(db_path))
    db.init_db()
    return db

def test_database_init_and_owners(test_db):
    owner_id = test_db.add_owner("@test_donator", "VIP donator")
    assert owner_id > 0
    
    owners = test_db.get_owners()
    assert len(owners) == 1
    assert owners[0]["nickname"] == "@test_donator"
    assert owners[0]["notes"] == "VIP donator"

def test_database_add_keys_and_deduplication(test_db):
    owner_id = test_db.add_owner("@donor1", "")
    keys = ["KEY_A_111", "KEY_B_222", "KEY_A_111"]  # 1 duplicate
    added, dupes = test_db.add_keys(owner_id, keys)
    assert added == 2
    assert dupes == 1
    
    all_keys = test_db.get_keys()
    assert len(all_keys) == 2

def test_database_status_update_and_ignore(test_db):
    owner_id = test_db.add_owner("@donor2", "")
    test_db.add_keys(owner_id, ["KEY_XYZ"])
    key = test_db.get_keys()[0]
    
    test_db.update_key_status(key["id"], "RESOURCE_EXHAUSTED", "Quota limit 429")
    updated = test_db.get_keys()[0]
    assert updated["status"] == "RESOURCE_EXHAUSTED"
    assert updated["detail"] == "Quota limit 429"
    
    new_state = test_db.toggle_key_ignored(key["id"])
    assert new_state is True
    assert test_db.get_keys()[0]["is_ignored"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'gemini_nexus.core.db'

- [ ] **Step 3: Implement `gemini_nexus/core/db.py`**

```python
# gemini_nexus/core/db.py
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple
from gemini_nexus.core.config import DEFAULT_DB_FILE, DEFAULT_MODELS

class Database:
    def __init__(self, db_path: str = DEFAULT_DB_FILE):
        self.db_path = db_path

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys = ON;")
        c.execute("PRAGMA journal_mode = WAL;")
        c.execute("PRAGMA synchronous = NORMAL;")
        c.execute("PRAGMA temp_store = MEMORY;")
        try:
            yield conn
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS owners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nickname TEXT UNIQUE,
                    notes TEXT DEFAULT ''
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER,
                    key_string TEXT UNIQUE,
                    status TEXT DEFAULT 'UNCHECKED',
                    detail TEXT DEFAULT '',
                    notes TEXT DEFAULT '',
                    is_ignored INTEGER DEFAULT 0,
                    FOREIGN KEY (owner_id) REFERENCES owners (id) ON DELETE CASCADE
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            # Populate default models
            for model in DEFAULT_MODELS:
                c.execute("INSERT OR IGNORE INTO models (name) VALUES (?)", (model,))
            conn.commit()

    def get_owners(self) -> List[Dict[str, Any]]:
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("""
                SELECT o.id, o.nickname, o.notes, COUNT(k.id) as key_count
                FROM owners o
                LEFT JOIN api_keys k ON o.id = k.owner_id
                GROUP BY o.id
                ORDER BY o.nickname COLLATE NOCASE
            """)
            return [dict(row) for row in c.fetchall()]

    def add_owner(self, nickname: str, notes: str = "") -> int:
        clean_nick = nickname.strip()
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("INSERT OR IGNORE INTO owners (nickname, notes) VALUES (?, ?)", (clean_nick, notes.strip()))
            conn.commit()
            c.execute("SELECT id FROM owners WHERE nickname=?", (clean_nick,))
            row = c.fetchone()
            return row["id"] if row else -1

    def delete_owner(self, owner_id: int) -> None:
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM owners WHERE id=?", (owner_id,))
            conn.commit()

    def add_keys(self, owner_id: int, key_strings: List[str]) -> Tuple[int, int]:
        added = 0
        dupes = 0
        with self.connect() as conn:
            c = conn.cursor()
            for raw_k in key_strings:
                k = raw_k.strip()
                if not k:
                    continue
                try:
                    c.execute("INSERT INTO api_keys (owner_id, key_string) VALUES (?, ?)", (owner_id, k))
                    added += 1
                except sqlite3.IntegrityError:
                    dupes += 1
            conn.commit()
        return added, dupes

    def get_keys(self, status_filter: str = "Все", search_query: str = "") -> List[Dict[str, Any]]:
        query = """
            SELECT k.id, k.owner_id, o.nickname as owner_nickname, k.key_string, 
                   k.status, k.detail, k.notes, k.is_ignored
            FROM api_keys k
            LEFT JOIN owners o ON k.owner_id = o.id
            WHERE 1=1
        """
        params: List[Any] = []
        if status_filter != "Все":
            if status_filter == "Активные (OK)":
                query += " AND k.status = 'OK'"
            elif status_filter == "Ошибки":
                query += " AND k.status NOT IN ('OK', 'UNCHECKED')"
            elif status_filter == "Игнорируемые":
                query += " AND k.is_ignored = 1"
            else:
                query += " AND k.status = ?"
                params.append(status_filter)
                
        if search_query.strip():
            query += " AND (k.key_string LIKE ? OR o.nickname LIKE ? OR k.notes LIKE ?)"
            pattern = f"%{search_query.strip()}%"
            params.extend([pattern, pattern, pattern])

        query += " ORDER BY k.id DESC"
        with self.connect() as conn:
            c = conn.cursor()
            c.execute(query, params)
            return [dict(row) for row in c.fetchall()]

    def update_key_status(self, key_id: int, status: str, detail: str = "") -> None:
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("UPDATE api_keys SET status=?, detail=? WHERE id=?", (status, detail, key_id))
            conn.commit()

    def toggle_key_ignored(self, key_id: int) -> bool:
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT is_ignored FROM api_keys WHERE id=?", (key_id,))
            row = c.fetchone()
            new_state = 0 if row and row["is_ignored"] else 1
            c.execute("UPDATE api_keys SET is_ignored=? WHERE id=?", (new_state, key_id))
            conn.commit()
            return bool(new_state)

    def delete_key(self, key_id: int) -> None:
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("DELETE FROM api_keys WHERE id=?", (key_id,))
            conn.commit()

    def reset_statuses(self, owner_id: Optional[int] = None) -> None:
        with self.connect() as conn:
            c = conn.cursor()
            if owner_id is not None:
                c.execute("UPDATE api_keys SET status='UNCHECKED', detail='' WHERE owner_id=?", (owner_id,))
            else:
                c.execute("UPDATE api_keys SET status='UNCHECKED', detail=''")
            conn.commit()

    def delete_broken_keys(self) -> int:
        with self.connect() as conn:
            c = conn.cursor()
            fatal = ("FAILED_PRECONDITION", "PERMISSION_DENIED", "UNAUTHORIZED", "NOT_FOUND")
            c.execute(f"DELETE FROM api_keys WHERE status IN ({','.join(['?']*len(fatal))})", fatal)
            deleted = c.rowcount
            conn.commit()
            return deleted

    def get_models(self) -> List[str]:
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT name FROM models ORDER BY name")
            return [row["name"] for row in c.fetchall()]

    def add_model(self, name: str) -> bool:
        clean = name.strip()
        if not clean:
            return False
        with self.connect() as conn:
            c = conn.cursor()
            try:
                c.execute("INSERT INTO models (name) VALUES (?)", (clean,))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_setting(self, key: str, default: str = "") -> str:
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("SELECT value FROM settings WHERE key=?", (key,))
            row = c.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gemini_nexus/core/db.py tests/test_db.py
git commit -m "feat(db): implement clean SQLite repository with WAL mode"
```

---

### Task 4: Stream Splitter & Load Balancer

**Files:**
- Create: `gemini_nexus/core/splitter.py`
- Test: `tests/test_splitter.py`

**Interfaces:**
- Produces: `split_keys_round_robin(keys: list[str], num_streams: int) -> dict[int, list[str]]`

- [ ] **Step 1: Write failing tests for stream splitter**

```python
# tests/test_splitter.py
from gemini_nexus.core.splitter import split_keys_round_robin

def test_split_empty():
    res = split_keys_round_robin([], 3)
    assert res == {1: [], 2: [], 3: []}

def test_split_even_distribution():
    keys = ["k1", "k2", "k3", "k4", "k5", "k6"]
    res = split_keys_round_robin(keys, 3)
    assert res[1] == ["k1", "k4"]
    assert res[2] == ["k2", "k5"]
    assert res[3] == ["k3", "k6"]

def test_split_single_stream():
    keys = ["k1", "k2"]
    res = split_keys_round_robin(keys, 1)
    assert res[1] == ["k1", "k2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_splitter.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'gemini_nexus.core.splitter'

- [ ] **Step 3: Implement `gemini_nexus/core/splitter.py`**

```python
# gemini_nexus/core/splitter.py
from typing import Dict, List

def split_keys_round_robin(keys: List[str], num_streams: int) -> Dict[int, List[str]]:
    """Distributes keys evenly across N streams using Round-Robin balancing."""
    if num_streams < 1:
        num_streams = 1
        
    streams: Dict[int, List[str]] = {i + 1: [] for i in range(num_streams)}
    for index, key in enumerate(keys):
        stream_id = (index % num_streams) + 1
        streams[stream_id].append(key)
        
    return streams
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_splitter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gemini_nexus/core/splitter.py tests/test_splitter.py
git commit -m "feat(splitter): implement round-robin key stream partitioner"
```

---

### Task 5: Network Dispatcher & Status Classifier

**Files:**
- Create: `gemini_nexus/core/checker.py`
- Test: `tests/test_classifier.py`

**Interfaces:**
- Produces: `classify_google_response(status_code: int, response_json: dict) -> tuple[str, str]`, `check_api_key(key: str, model: str, proxy_url: str = None, timeout: float = 12.0) -> tuple[str, str]`

- [ ] **Step 1: Write failing tests for response classification**

```python
# tests/test_classifier.py
from gemini_nexus.core.checker import classify_google_response

def test_classify_ok():
    status, detail = classify_google_response(200, {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]})
    assert status == "OK"

def test_classify_quota_exhausted():
    payload = {"error": {"code": 429, "message": "Resource has been exhausted (e.g. check quota)."}}
    status, detail = classify_google_response(429, payload)
    assert status == "RESOURCE_EXHAUSTED"

def test_classify_policy_unrestricted():
    payload = {"error": {"code": 403, "message": "Method doesn't allow unregistered callers (caller: unrestricted)"}}
    status, detail = classify_google_response(403, payload)
    assert status == "UNRESTRICTED"

def test_classify_permission_denied():
    payload = {"error": {"code": 403, "message": "API key not valid. Please pass a valid API key."}}
    status, detail = classify_google_response(403, payload)
    assert status == "PERMISSION_DENIED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_classifier.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'gemini_nexus.core.checker'

- [ ] **Step 3: Implement `gemini_nexus/core/checker.py`**

```python
# gemini_nexus/core/checker.py
import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, Optional, Tuple

def classify_google_response(status_code: int, error_data: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    if status_code == 200:
        return "OK", "Ключ успешно прошел генерацию"
        
    error_msg = ""
    error_status = ""
    if error_data and "error" in error_data:
        err = error_data["error"]
        error_msg = err.get("message", "")
        error_status = err.get("status", "")

    if status_code == 429 or "RESOURCE_EXHAUSTED" in error_status:
        return "RESOURCE_EXHAUSTED", f"Лимит квоты исчерпан: {error_msg}"
        
    if status_code == 403:
        if "unrestricted" in error_msg.lower() or "unregistered callers" in error_msg.lower():
            return "UNRESTRICTED", "Требуется ограничение API в Google Cloud Console (политика от 19 июня)"
        return "PERMISSION_DENIED", f"Доступ запрещен: {error_msg}"
        
    if status_code == 400:
        return "FAILED_PRECONDITION", f"Региональное ограничение / Биллинг: {error_msg}"
    if status_code == 401:
        return "UNAUTHORIZED", "Ключ не существует или отозван"
    if status_code == 404:
        return "NOT_FOUND", f"Модель не найдена: {error_msg}"
    if status_code == 500:
        return "INTERNAL_ERROR", "Внутренняя ошибка сервера Google"
    if status_code == 503:
        return "SERVICE_UNAVAILABLE", "Сервис Google временно перегружен"
    if status_code == 504:
        return "DEADLINE_EXCEEDED", "Таймаут генерации на стороне Google"
        
    return f"HTTP_{status_code}", error_msg or f"Код {status_code}"

def build_proxy_opener(proxy_url: str):
    parsed = urllib.parse.urlparse(proxy_url)
    scheme = parsed.scheme.lower()
    if "socks" in scheme:
        import socks
        from sockshandler import SocksiPyHandler
        stype = socks.PROXY_TYPE_SOCKS5 if "5" in scheme else socks.PROXY_TYPE_SOCKS4
        handler = SocksiPyHandler(stype, parsed.hostname, parsed.port, True, parsed.username, parsed.password)
        return urllib.request.build_opener(handler)
    else:
        proxy_handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
        return urllib.request.build_opener(proxy_handler)

def check_api_key(key: str, model: str, proxy_url: Optional[str] = None, timeout: float = 12.0) -> Tuple[str, str]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {"contents": [{"parts": [{"text": "hi"}]}]}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    
    opener = build_proxy_opener(proxy_url) if proxy_url else urllib.request.build_opener()
    try:
        with opener.open(req, timeout=timeout) as resp:
            return classify_google_response(resp.status)
    except urllib.error.HTTPError as e:
        raw_body = e.read().decode("utf-8", errors="ignore")
        try:
            err_json = json.loads(raw_body)
        except Exception:
            err_json = None
        return classify_google_response(e.code, err_json)
    except (urllib.error.URLError, TimeoutError) as e:
        return "TIMEOUT", f"Сетевая ошибка / таймаут соединения: {str(e)}"
    except Exception as e:
        return "INTERNAL_ERROR", f"Непредвиденное исключение: {str(e)}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_classifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gemini_nexus/core/checker.py tests/test_classifier.py
git commit -m "feat(checker): implement network dispatcher and Google API status classifier"
```

---

### Task 6: UI Core Components & Thread-Safe Worker

**Files:**
- Create: `gemini_nexus/ui/__init__.py`
- Create: `gemini_nexus/ui/widgets/__init__.py`
- Create: `gemini_nexus/ui/widgets/status_badge.py`
- Create: `gemini_nexus/ui/widgets/log_viewer.py`
- Create: `gemini_nexus/ui/workers/__init__.py`
- Create: `gemini_nexus/ui/workers/check_worker.py`

**Interfaces:**
- Produces: `StatusBadge(QWidget)`, `LogViewer(QPlainTextEdit)`, `CheckWorker(QThread)` with Qt signals:
  - `progress_updated(int, int)`
  - `stats_updated(dict)`
  - `log_emitted(str, str)`
  - `key_finished(int, str, str)`
  - `finished()`

- [ ] **Step 1: Implement `gemini_nexus/ui/widgets/status_badge.py`**

```python
# gemini_nexus/ui/widgets/status_badge.py
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from gemini_nexus.core.config import STATUS_COLORS, STATUS_RU

class StatusBadge(QLabel):
    def __init__(self, status: str = "UNCHECKED", parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        color = STATUS_COLORS.get(status, "#7f8c8d")
        text = STATUS_RU.get(status, status)
        self.setText(text)
        self.setStyleSheet(f"""
            QLabel {{
                background-color: {color}22;
                color: {color};
                border: 1px solid {color}55;
                border-radius: 4px;
                padding: 2px 6px;
                font-weight: bold;
                font-size: 11px;
            }}
        """)
```

- [ ] **Step 2: Implement `gemini_nexus/ui/widgets/log_viewer.py`**

```python
# gemini_nexus/ui/widgets/log_viewer.py
from datetime import datetime
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtGui import QTextCursor, QColor
from PyQt6.QtCore import Qt

class LogViewer(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(1000)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #121214;
                color: #e0e0e0;
                font-family: 'JetBrains Mono', 'Fira Code', 'Monospace';
                font-size: 12px;
                border: 1px solid #2a2a2e;
                border-radius: 6px;
            }
        """)

    def append_log(self, text: str, tag: str = "INFO") -> None:
        time_str = datetime.now().strftime("%H:%M:%S")
        color = "#a0a0a0"
        if tag == "OK":
            color = "#2ecc71"
        elif tag == "WARN" or tag == "LIMIT":
            color = "#f39c12"
        elif tag == "ERROR" or tag == "DEAD":
            color = "#e74c3c"
        elif tag == "SYS":
            color = "#3498db"

        html_line = f"<span style='color: #666;'>[{time_str}]</span> <span style='color: {color}; font-weight: bold;'>[{tag}]</span> {text}"
        self.appendHtml(html_line)
        self.moveCursor(QTextCursor.MoveOperation.End)
```

- [ ] **Step 3: Implement `gemini_nexus/ui/workers/check_worker.py`**

```python
# gemini_nexus/ui/workers/check_worker.py
import time
import random
from typing import List, Dict, Any, Optional
from PyQt6.QtCore import QThread, pyqtSignal
from gemini_nexus.core.checker import check_api_key

class CheckWorker(QThread):
    progress_updated = pyqtSignal(int, int)
    stats_updated = pyqtSignal(dict)
    log_emitted = pyqtSignal(str, str)
    key_finished = pyqtSignal(int, str, str)
    all_finished = pyqtSignal()

    def __init__(self, keys_to_check: List[Dict[str, Any]], model: str,
                 proxy_url: Optional[str] = None, delay_min: float = 7.0,
                 delay_max: float = 10.0, parent=None):
        super().__init__(parent)
        self.keys = keys_to_check
        self.model = model
        self.proxy_url = proxy_url
        self.delay_min = delay_min
        self.delay_max = delay_max
        self._is_running = True
        self._is_paused = False

    def pause(self) -> None:
        self._is_paused = True

    def resume(self) -> None:
        self._is_paused = False

    def stop(self) -> None:
        self._is_running = False
        self._is_paused = False

    def run(self) -> None:
        total = len(self.keys)
        stats = {"total": total, "checked": 0, "ok": 0, "limits": 0, "dead": 0, "errors": 0}
        self.log_emitted.emit(f"Старт проверки {total} ключей через модель [{self.model}]...", "SYS")

        for index, item in enumerate(self.keys):
            while self._is_paused and self._is_running:
                time.sleep(0.2)
            if not self._is_running:
                self.log_emitted.emit("Проверка принудительно остановлена пользователем.", "WARN")
                break

            k_id = item["id"]
            k_str = item["key_string"]
            short_key = f"{k_str[:8]}...{k_str[-6:]}" if len(k_str) > 14 else k_str

            status, detail = check_api_key(k_str, self.model, self.proxy_url)
            self.key_finished.emit(k_id, status, detail)

            stats["checked"] += 1
            if status == "OK":
                stats["ok"] += 1
                self.log_emitted.emit(f"Ключ {short_key} | {status}", "OK")
            elif status in ("RESOURCE_EXHAUSTED", "UNRESTRICTED"):
                stats["limits"] += 1
                self.log_emitted.emit(f"Ключ {short_key} | {status} | {detail}", "WARN")
            elif status in ("PERMISSION_DENIED", "UNAUTHORIZED", "FAILED_PRECONDITION"):
                stats["dead"] += 1
                self.log_emitted.emit(f"Ключ {short_key} | {status} | {detail}", "ERROR")
            else:
                stats["errors"] += 1
                self.log_emitted.emit(f"Ключ {short_key} | {status} | {detail}", "WARN")

            self.progress_updated.emit(stats["checked"], total)
            self.stats_updated.emit(stats)

            if index < total - 1 and self._is_running:
                delay = random.uniform(self.delay_min, self.delay_max)
                end_time = time.time() + delay
                while time.time() < end_time and self._is_running:
                    time.sleep(0.1)

        self.log_emitted.emit("Процесс проверки полностью завершен.", "SYS")
        self.all_finished.emit()
```

- [ ] **Step 4: Commit**

```bash
git add gemini_nexus/ui/
git commit -m "feat(ui): add core UI widgets and thread-safe QThread worker"
```

---

### Task 7: View Controllers (Manager, Checker, Splitter, Info)

**Files:**
- Create: `gemini_nexus/ui/views/__init__.py`
- Create: `gemini_nexus/ui/views/manager_view.py`
- Create: `gemini_nexus/ui/views/checker_view.py`
- Create: `gemini_nexus/ui/views/splitter_view.py`
- Create: `gemini_nexus/ui/views/info_view.py`

**Interfaces:**
- Produces: `ManagerView(QWidget)`, `CheckerView(QWidget)`, `SplitterView(QWidget)`, `InfoView(QWidget)` communicating with `Database` and `CheckWorker`.

- [ ] **Step 1: Implement `gemini_nexus/ui/views/manager_view.py`**

Full `QTableView` model with SQLite keys, search filtering, quick addition panel, donor combo, context menu for copying key, toggling ignore, resetting status and editing notes.

- [ ] **Step 2: Implement `gemini_nexus/ui/views/checker_view.py`**

Model selector (Gemini 3.x), proxy settings, delay range sliders, start/pause/stop buttons, metric cards, progress bar, `LogViewer`.

- [ ] **Step 3: Implement `gemini_nexus/ui/views/splitter_view.py`**

Stream count input, "🔀 Распределить ключи" button, stream preview dropdown, copy to clipboard, export to files.

- [ ] **Step 4: Implement `gemini_nexus/ui/views/info_view.py`**

Clean Markdown/Rich text FAQ, status code definitions, donor instructions.

- [ ] **Step 5: Commit**

```bash
git add gemini_nexus/ui/views/
git commit -m "feat(views): implement Manager, Checker, Splitter, and Info views"
```

---

### Task 8: Main Window Shell & Application Entrypoint

**Files:**
- Create: `gemini_nexus/ui/main_window.py`
- Create: `gemini_nexus/main.py`
- Modify: `pyproject.toml`

**Interfaces:**
- Produces: `MainWindow(QMainWindow)` with Sidebar, `qdarktheme` dark styling, `main()` execution entrypoint.

- [ ] **Step 1: Implement `gemini_nexus/ui/main_window.py`**

Assemble the Modern Sidebar navigation, QStackedWidget with all 4 views, apply `qdarktheme.setup_theme(theme="dark", corner_shape="rounded")`.

- [ ] **Step 2: Implement `gemini_nexus/main.py`**

Initialize `QApplication`, set High DPI attributes, instantiate `Database` and `MainWindow`, and run event loop.

- [ ] **Step 3: Update `pyproject.toml`**

Set entrypoint script `ping-keys = "gemini_nexus.main:main"`.

- [ ] **Step 4: Commit**

```bash
git add gemini_nexus/ui/main_window.py gemini_nexus/main.py pyproject.toml
git commit -m "feat(app): assemble main window shell and application entrypoint"
```

---

### Task 9: Nix Flake & Launcher Modernization

**Files:**
- Modify: `flake.nix`
- Modify: `run.sh`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: Flake devShell and package with `pyqt6`, `pyqtdarktheme`, `pysocks`, `qt6.qtwayland`, and `wrapQtAppsHook`.

- [ ] **Step 1: Update `flake.nix`**

Replace `customtkinter` with `pyqt6`, `pyqtdarktheme`, `pysocks`, and wrap using `qt6.wrapQtAppsHook`.

- [ ] **Step 2: Update `run.sh`**

Remove custom font chmod hacks. Use native `nix run` or python with PyQt6.

- [ ] **Step 3: Update `requirements.txt`**

```
PyQt6>=6.6.0
pyqtdarktheme>=2.1.0
PySocks>=1.7.1
```

- [ ] **Step 4: Commit**

```bash
git add flake.nix run.sh requirements.txt
git commit -m "chore(nix): migrate Flake and launcher to native Wayland Qt6"
```

---

### Task 10: Full System Verification & Cutover Validation

**Files:**
- Test: All tests in `tests/`
- Test: Smoke launch via `./run.sh` or `python3 -m gemini_nexus.main`

- [ ] **Step 1: Run complete test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Verify Wayland GUI launch and scaling**

Execute smoke test verifying PyQt6 window initializes cleanly without errors.

- [ ] **Step 3: Commit and final documentation update**

```bash
git commit -m "docs: finalize v14.0 modernization release notes"
```
