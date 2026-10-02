# Repository Guidelines

## Project Overview

**Gemini Nexus DB** (`ping_keys`, v14.0 Enterprise by NeuroStarNet) is a standalone desktop application and orchestration system designed for managing, verifying, load-balancing, and securely backing up crowd-sourced Google Gemini and Gemma API keys.

The system features a native Wayland PyQt6 graphical interface with HiDPI support, decoupled service-repository architecture (`gemini_nexus/`), pure-Python authenticated stream cryptography, SQLite WAL storage, and a multi-threaded network dispatcher.
---

## Architecture & Data Flow

```
+-------------------------------------------------------------------------------+
|                 PyQt6 Native Wayland GUI (MainWindow Shell)                   |
|  [ ManagerView ]       [ CheckerView ]       [ SplitterView ]     [ InfoView ]|
+------------------------------------+------------------------------------------+
                                     |
              +----------------------+----------------------+
              |                                             |
              v                                             v
   +--------------------+                       +-----------------------+
   | SQLite WAL Repo    |                       | CheckWorker (QThread) |
   | (core/db.py)       |                       | (ui/workers)          |
   +--------------------+                       +-----------+-----------+
              |                                             |
              |                                             v
              |                                 +-----------------------+
              |                                 | Network Dispatcher    |
              |                                 | (core/checker.py)     |
              |                                 +-----------+-----------+
              v                                             |
   +--------------------+                                   v
   | Zero-Dep Crypto    |                       +-----------------------+
   | (core/crypto.py)   |                       | Google Generative API |
   | PBKDF2 + CTR + HMAC|                       | :generateContent      |
   +--------------------+                       +-----------------------+
```

### Core Subsystems

1. **Presentation & UI Layer (`gemini_nexus/ui/`)**:
   - Built on **PyQt6** and **`pyqtdarktheme`** with native Wayland rendering (`qt6.qtwayland`), fractional HiDPI scaling (1.8x on 2.8K displays), and hardware acceleration.
   - Decoupled into `MainWindow`, `ManagerView` (virtualized `QTableView`), `CheckerView`, `SplitterView`, and `InfoView`.
   - Full native Wayland clipboard integration across Latin and Cyrillic keyboard layouts without input hacks.
2. **Database Engine (`sqlite3` with WAL mode)**:
   - High-concurrency SQLite storage using `PRAGMA journal_mode=WAL;`, `PRAGMA synchronous=NORMAL;`, and `PRAGMA temp_store=MEMORY;`.
   - Automatic inline schema migrations on startup (adding notes, ignore flags, migration markers).

3. **Key Checker & Network Dispatcher**:
   - Asynchronous execution using `CheckWorker(QThread)` driving network calls with Qt signal-slot thread safety (`progress_updated`, `stats_updated`, `log_emitted`, `key_finished`).
   - Sends test generation requests (`POST https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}`).
   - HTTP/HTTPS and SOCKS4/SOCKS5 proxy dispatching via `urllib.request` and `PySocks` (`SocksiPyHandler`).
   - Fine-grained HTTP response classifier mapping status codes and Google error JSON payloads to standardized operational statuses.

4. **Zero-Dependency Cryptography Subsystem**:
   - Pure-Python stream encryption/decryption (`encrypt_data` / `decrypt_data`).
   - Key derivation: `hashlib.pbkdf2_hmac('sha256', password, salt, 10000)` with 16-byte CSPRNG salt.
   - Stream cipher: SHA-256 counter mode (`key + iv + counter_bin`) operating in 32-byte chunks.
   - Payload format: `Base64(salt [16B] + IV [16B] + Ciphertext)`.

5. **Stream Splitter & Load Balancer**:
   - Partitions all active (`status='OK' AND is_ignored=0`) keys across $N$ streams using a Round-Robin algorithm (`do_split`).
   - Exports key sets into distinct stream files (`valid_keys_stream_<id>.txt`) for multi-worker parallel execution.

```
├── gemini_nexus/                     # Main application package
│   ├── __init__.py                   # Package metadata (v14.0.0, NeuroStarNet)
│   ├── main.py                       # Application entrypoint & High DPI init
│   ├── core/                         # Pure Python business logic & services
│   │   ├── config.py                 # Configuration, models catalog (Gemini 3.x), status mappings
│   │   ├── crypto.py                 # PBKDF2-HMAC-SHA256 + CTR Stream Cipher + HMAC
│   │   ├── db.py                     # SQLite WAL repository with cascading foreign keys
│   │   ├── checker.py                # Network dispatcher & Google API error classifier
│   │   └── splitter.py               # Round-Robin stream balancer
│   └── ui/                           # PyQt6 presentation layer
│       ├── main_window.py            # MainWindow shell & sidebar navigation
│       ├── widgets/                  # StatusBadge, LogViewer
│       ├── views/                    # ManagerView, CheckerView, SplitterView, InfoView
│       └── workers/                  # CheckWorker (QThread)
├── tests/                            # Comprehensive Pytest test suite (58 tests)
├── run.sh                            # Universal native launcher script
├── flake.nix                         # Declarative Nix flake (PyQt6 + pyqtdarktheme + qtwayland)
├── pyproject.toml                    # Package metadata and ruff configuration
├── CONTRACT.yaml                     # GRACE 4 + PCAM module contract passport
└── AGENTS.md                         # Repository guidelines & developer documentation
```

---

## Development Commands

### Running the Application

```bash
# Universal one-click launch (handles venv / Nix automatically)
./run.sh

# Direct execution via Python
python3 ping_keys_NeuroStarNet_v13.9.py

# Run via Nix Flake
nix run

# Enter Nix devShell
nix develop
```

### Dependency Installation

```bash
# Pip installation
pip install customtkinter PySocks

# System Tk dependencies (Debian/Ubuntu)
sudo apt-get install python3-tk
```

### Code Quality & Linting

```bash
# Check code with Ruff
ruff check ping_keys_NeuroStarNet_v13.9.py

# Format code with Ruff
ruff format ping_keys_NeuroStarNet_v13.9.py
```

### Database Inspection

```bash
# Query status overview
sqlite3 gemini_keys.db "SELECT status, count(*) FROM api_keys GROUP BY status;"

# Inspect active settings
sqlite3 gemini_keys.db "SELECT key, value FROM settings;"
```

---

## Code Conventions & Common Patterns

### Concurrency & UI Thread Safety

- **Never update GUI widgets directly from worker threads.** All UI updates, progress counter increments, and console log lines must be dispatched to Tkinter's event loop via `self.after(0, callback)`.
- **Atomic Counters**: Use `self.counter_lock = threading.Lock()` when mutating shared metrics (`self.checked_count`).
- **Cooperative Worker Interruption**: Background loops check `self.is_running` and handle pause states via:
  ```python
  while self.is_paused and self.is_running:
      time.sleep(0.5)
  if not self.is_running:
      return
  ```

### Database Access Pattern

- Connections are opened on demand and closed immediately after query execution:
  ```python
  conn = connect_db()
  c = conn.cursor()
  c.execute("SELECT ... WHERE key=?", (param,))
  rows = c.fetchall()
  conn.close()
  ```
- Write operations commit explicitly before closing:
  ```python
  conn = connect_db()
  conn.execute("UPDATE api_keys SET status=?, detail=? WHERE id=?", (status, detail, k_id))
  conn.commit()
  conn.close()
  ```

### Google API Status Classification

When modifying or adding status types, update both `check_key_request` and `STATUS_RU`:

| Status Code / Identifier | Category | Meaning | Recovery / Handling |
|---|---|---|---|
| `OK` | Valid (Green) | Key operates normally | Ready for translation streams |
| `RESOURCE_EXHAUSTED` | Transient (Yellow) | Rate limit exceeded (429 RPM/TPM) | Key is valid; wait for quota reset |
| `UNRESTRICTED` | Policy (Yellow/Red) | Google API policy restriction (June 19) | Key requires API service limitation in Google Console |
| `SERVICE_UNAVAILABLE` | Transient (Yellow) | Google servers overloaded (503) | Temporary; retry later |
| `INTERNAL_ERROR` | Transient (Yellow) | Google internal error (500) | Temporary; retry later |
| `DEADLINE_EXCEEDED` | Transient (Yellow) | Generation timeout (504) | Temporary; retry later |
| `TIMEOUT` | Network (Yellow) | Local network or proxy failure | Automatic 1-time retry after 2s; check proxy |
| `FAILED_PRECONDITION` | Fatal (Red) | Regional block or missing billing (400) | Remove from rotation |
| `PERMISSION_DENIED` | Fatal (Red) | Access denied / key banned (403) | Remove from rotation |
| `UNAUTHORIZED` | Fatal (Red) | Key does not exist / invalid (401) | Remove from rotation |
| `NOT_FOUND` | Config (Red) | Requested model ID does not exist (404) | Verify model name in settings |

### Naming Conventions

- **Constants**: `UPPER_SNAKE_CASE` (e.g., `APP_VERSION`, `STATUS_RU`, `TIMEOUT`, `DB_FILE`).
- **Functions & Methods**: `snake_case` (e.g., `check_key_request`, `get_proxy_opener`, `apply_context_menu`).
- **Classes**: `PascalCase` (e.g., `GeminiNexus`).
- **Tkinter Variable Bindings**: Suffix with `_var` (e.g., `model_var`, `delay_min_var`, `streams_count_var`).

---

## Important Files

- **`ping_keys_NeuroStarNet_v13.9.py`**: Monolithic entry point and implementation containing:
  - `init_db`, `connect_db`, `get_setting`, `save_setting`: SQLite schema setup and CRUD helpers.
  - `encrypt_data`, `decrypt_data`: PBKDF2 + SHA-256 CTR stream cipher.
  - `check_key_request`, `get_proxy_opener`: Network request dispatcher and status classifier.
  - `GeminiNexus`: Main CustomTkinter application window, tab managers, and worker threads.
- **`gemini_keys.db`**: Local SQLite database storing:
  - `owners`: Donators / source entities (`id`, `nickname`, `notes`).
  - `api_keys`: Keys with verification statuses (`id`, `owner_id`, `key_string`, `status`, `detail`, `notes`, `is_ignored`).
  - `models`: Supported Gemini/Gemma models catalog (`name`).
  - `settings`: Persistent configuration key-values (`delay_min`, `delay_max`, `checker_threads`, `proxy_use`, `proxy_url`, `splitter_streams`).

---

## Runtime/Tooling Preferences

- **Python Runtime**: Python 3.10+ (CPython).
- **GUI Engine**: CustomTkinter (`customtkinter`) requiring OS-level Tk/Tcl support (`python3-tk` / `_tkinter`).
- **Dependencies**:
  - `customtkinter`: Modern UI widgets and dark-theme support.
  - `PySocks`: Required for SOCKS4/SOCKS5 proxy routing (optional at launch, checked dynamically).
- **Formatting & Linting**: Ruff (`ruff check`, `ruff format`).

---

## Testing & QA

### Current Verification Model

The repository currently relies on live integration verification through the GUI:
- Direct API verification runs against `https://generativelanguage.googleapis.com/v1beta/`.
- Manual DB checks via SQLite CLI or built-in CRUD inspection tabs.

### Recommended Automated Testing Architecture

When adding automated test suites (`pytest`), structure tests around decoupled modules:

1. **Cryptography Suite (`test_crypto.py`)**:
   - Validate encryption/decryption round-trip with ASCII, UTF-8, and binary strings.
   - Verify salt and IV uniqueness across multiple encryptions of identical plaintexts.
   - Test corrupted payload and incorrect password handling (expect `None`).

2. **Database Migration & CRUD Suite (`test_db.py`)**:
   - Execute `init_db()` against an in-memory database (`:memory:`).
   - Test cascading deletions (removing an owner and linked keys).
   - Test status resetting and ignore flags (`is_ignored`).

3. **Status Classifier Mock Suite (`test_classifier.py`)**:
   - Mock HTTP 200, 400 (`FAILED_PRECONDITION`), 401, 403 (`UNRESTRICTED` vs `PERMISSION_DENIED`), 429, 500, 503, and socket timeouts.
   - Ensure accurate mapping to `STATUS_RU` and domain status strings.

4. **Splitter Logic Suite (`test_splitter.py`)**:
   - Verify Round-Robin distribution balances keys evenly across $N$ streams.
   - Ensure keys with `is_ignored=1` or `status != 'OK'` are excluded from stream partitions.
