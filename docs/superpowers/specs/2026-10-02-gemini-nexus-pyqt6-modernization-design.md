# Архитектурная спецификация: Модернизация Gemini Nexus DB (ping_keys v14.0 Enterprise)

- **Дата:** 2026-10-02
- **Автор:** detkeroot & J.A.R.V.I.S.
- **Проект:** `ping_keys` (Gemini Nexus DB)
- **Статус:** Draft / Design Approval

---

## 1. Контекст и Проблематика

### 1.1. Текущее состояние (v13.9)
`ping_keys` — десктопное приложение для управления, верификации, балансировки и экспорта пула API-ключей Google Gemini / Gemma.
Приложение было разработано в формате диалога с Google AI Studio под ОС Windows и представляет собой монолитный скрипт `ping_keys_NeuroStarNet_v13.9.py` (1752 строки кода), использующий графическую библиотеку **CustomTkinter** поверх стандартного Python `tkinter` (Tcl/Tk 8.6).

### 1.2. Проблемы физики рендеринга на Linux / Wayland (Niri)
На рабочей станции разработчика (Linux Wayland, композитор Niri, 2.8K IPS, 120Hz, дробный масштаб **1.8x**):
1. **Прослойка XWayland:** Tcl/Tk не поддерживает Wayland нативно. Окно запускается через XWayland, подвергаясь принудительному билинейному апскейлингу композитором, что приводит к размытию шрифтов и графики («мыло»).
2. **Отрисовка CustomTkinter на Canvas:** Элементы с закругленными углами рисуются на холсте Tkinter через полигоны без аппаратного ускорения и субпиксельного LCD-сглаживания (лесенки по краям, микрофризы при перерисовке).
3. **Костыли буфера обмена:** События вставки/копирования (`Ctrl+C`, `Ctrl+V`) при русской раскладке клавиатуры в Tkinter перехватываются через 60 строк хаков `apply_context_menu`.
4. **Конфликты шрифтов:** Приложение требует записи в `~/.fonts`, что конфликтует с декларативным read-only стилем NixOS.

### 1.3. Архитектурный долг
- Монолит: UI, прямые SQL-запросы, криптография, сетевые запросы и сплиттер находятся в одном файле и одном классе `GeminiNexus`.
- Отсутствие транзакционной изоляции и пула подключений к SQLite (открытие/закрытие `conn` на каждый клик).
- Устаревший каталог моделей (присутствуют архивные модели, отсутствуют актуальные Gemini 3.x).
- Потоковая модель на примитивных тредах Python без надежной синхронизации через очереди/сигналы.

---

## 2. Архитектура целевой системы (v14.0 Native Wayland)

### 2.1. Технологический стек
- **GUI Engine:** **PyQt6 (Qt 6.11+)** с нативным плагином платформы `qt6.qtwayland`.
  - Полноценная поддержка Wayland протоколов (`xdg-shell`, `xdg-decoration`).
  - Аппаратное ускорение графики через Qt Rendering Hardware Interface (RHI / Vulkan / OpenGL).
  - Нативный векторный HiDPI-рендеринг при масштабе 1.8x с субпиксельным сглаживанием FreeType/HarfBuzz.
  - Нативная работа с системным буфером обмена Wayland в любой раскладке клавиатуры.
- **Темизация:** **`pyqtdarktheme`** (нативно доступен в `nixpkgs`). Глубокая темная тема, идеально гармонирующая с системным окружением Noctalia Shell и темой Adwaita-dark.
- **СУБД:** SQLite в режиме WAL (`journal_mode = WAL`, `synchronous = NORMAL`, `temp_store = MEMORY`).
- **Сетевой стек:** `urllib.request` с поддержкой HTTP(S) и SOCKS4/5 через `PySocks`.
- **Среда сборки:** Декларативный `flake.nix` под NixOS 26.05 с хуком `wrapQtAppsHook`.

---

## 3. Модульная декомпозиция (Service-Repository Pattern)

Проект реорганизуется из монолита в чистую модульную структуру пакета `gemini_nexus`:

```
ping_keys/
├── flake.nix                     # Декларативный Flake (PyQt6 + pyqtdarktheme + qtwayland)
├── run.sh                        # Легковесный чистый лаунчер
├── pyproject.toml                # Метаданные пакета и зависимости
├── gemini_nexus/                 # Основной пакет приложения
│   ├── __init__.py               # Экспорт точки входа и метаданных
│   ├── main.py                   # Точка входа QApplication и запуск окна
│   ├── core/                     # Изолированное ядро бизнес-логики (без UI зависимостей)
│   │   ├── __init__.py
│   │   ├── config.py             # Константы, пути к БД, дефолтные параметры
│   │   ├── db.py                 # SQLite Repository: контекстный менеджер, CRUD, миграции
│   │   ├── crypto.py             # PBKDF2-HMAC-SHA256 + CTR Stream Cipher + HMAC валидация
│   │   ├── checker.py            # Диспетчер сетевых запросов и классификатор статусов Google API
│   │   └── splitter.py           # Round-Robin сплиттер активных ключей по N потокам
│   └── ui/                       # Графический интерфейс PyQt6
│       ├── __init__.py
│       ├── main_window.py        # Главное окно: QMainWindow, Sidebar, QStackedWidget
│       ├── widgets/              # Переиспользуемые компоненты
│       │   ├── status_badge.py   # Цветные чипы статусов (OK, LIMIT, DEAD, IGNORE)
│       │   └── log_viewer.py     # Высокопроизводительный терминал логов на QPlainTextEdit
│       ├── views/                # Экраны приложения
│       │   ├── manager_view.py   # Управление БД: таблица QTableView, добавление, CRUD, заметки
│       │   ├── checker_view.py   # Панель проверки: запуск, пауза, выбор модели, карточки статистики
│       │   ├── splitter_view.py  # Сплиттер: распределение, превью потоков, экспорт файлов
│       │   └── info_view.py      # Справка, FAQ, горячие клавиши, документация
│       └── workers/
│           └── check_worker.py   # QThread / QRunnable воркер с сигналами (pyqtSignal)
└── tests/                        # Модульные автоматические тесты
    ├── test_crypto.py            # Тесты шифрования и восстановления
    ├── test_db.py                # Тесты CRUD-операций и каскадного удаления
    ├── test_splitter.py          # Тесты балансировки Round-Robin
    └── test_classifier.py        # Тесты парсинга ошибок Google API
```

---

## 4. Спецификация компонентов ядра (`gemini_nexus/core/`)

### 4.1. `core/db.py` (Database Repository)
- **Инициализация:** Автоматическое применение PRAGMA (WAL, foreign_keys = ON, busy_timeout = 5000).
- **Миграции:** Идемпотентный запуск структуры таблиц (`owners`, `api_keys`, `models`, `settings`).
- **Справочник моделей:** Дефолтный набор актуальных моделей Gemini 3.x:
  - `gemini-3.8-flash` (по умолчанию)
  - `gemini-3.8-flash-high`
  - `gemini-3.7-flash`
  - `gemini-3.5-flash`
  - `gemini-3.1-flash-lite-preview`
  - `gemma-3-27b-it`
- **Методы:**
  - `get_owners() -> list[tuple[int, str, int]]` (id, nickname, key_count)
  - `add_owner(nickname, notes) -> int`
  - `delete_owner(owner_id) -> None`
  - `add_keys(owner_id, key_strings) -> tuple[int, int]` (добавлено, дубликатов)
  - `get_keys_filtered(status_filter, owner_filter, search_query) -> list[dict]`
  - `update_key_status(key_id, status, detail)`
  - `toggle_key_ignored(key_id) -> bool`
  - `delete_keys_by_status(status_list) -> int`
  - `get_setting(key, default) / set_setting(key, value)`

### 4.2. `core/crypto.py` (Zero-Dependency Cryptography)
- Изолированные функции без обращений к UI:
  - `encrypt_database_payload(data: dict, password: str) -> str`
  - `decrypt_database_payload(payload_b64: str, password: str) -> dict`
- Защита от повреждения данных: проверка HMAC-SHA256 перед расшифровкой тела.

### 4.3. `core/checker.py` (Network Dispatcher)
- Классификатор ошибок Google Generative Language API:
  - 200 OK -> `OK`
  - 429 -> `RESOURCE_EXHAUSTED` (квота/лимит запросов)
  - 400 Bad Request -> `FAILED_PRECONDITION` (региональный блок / биллинг)
  - 403 Forbidden -> `PERMISSION_DENIED` или `UNRESTRICTED` (политика Google от 19 июня)
  - 401 Unauthorized -> `UNAUTHORIZED` (несуществующий/отозванный ключ)
  - 404 Not Found -> `NOT_FOUND` (ошибка в названии модели)
  - 500 / 503 / 504 -> `INTERNAL_ERROR` / `SERVICE_UNAVAILABLE` / `DEADLINE_EXCEEDED`
  - Timeout / Socket Error -> `TIMEOUT` (автоповтор через 2с)

### 4.4. `core/splitter.py` (Load Balancer)
- Функция `split_keys(keys: list[str], streams_count: int) -> dict[int, list[str]]`.
- Равномерное Round-Robin распределение только валидных ключей (`status == 'OK' and not is_ignored`).

---

## 5. Спецификация графического интерфейса (`gemini_nexus/ui/`)

### 5.1. Дизайн-система и компоновка
- **Стиль:** `qdarktheme.setup_theme(theme="dark", corner_shape="rounded")`.
- **Архитектура главного окна (`MainWindow`):**
  - Слева: `Sidebar` с кнопками навигации, логотипом "NEXUS CORE" и системным статусом.
  - По центру: `QStackedWidget` с экранами:
    1. **База данных (`ManagerView`):**
       - Верхняя панель: Быстрое добавление (выбор донатера, текстовое поле для вставки пачки ключей, кнопка сохранения).
       - Центральная область: `QTableView` со списком всех ключей (ID, Владелец, Ключ, Статус, Заметка, Игнорируется).
       - Фильтры: строка поиска в реальном времени, выпадающий список статусов (Все, OK, Лимиты, Мертвые, Игнор).
       - Действия по правому клику мыши (Контекстное меню): Копировать ключ, Переключить игнор, Сбросить статус, Удалить, Изменить заметку.
    2. **Чекер ключей (`CheckerView`):**
       - Панель управления: выбор модели Gemini 3.x, слайдеры/спинбоксы задержки (мин/макс), потоки, переключатель прокси.
       - Кнопки: Запуск полной проверки, Выборочная проверка, Пауза, Стоп.
       - Дашборд статистики: карточки со счетчиками (Всего, Проверено, Валидно, Лимиты, Ошибки, Скорость проверок в сек).
       - Терминал логов: скроллируемый лог с цветовой разметкой ANSI/Rich Text.
    3. **Сплиттер потоков (`SplitterView`):**
       - Ввод числа потоков $N$.
       - Кнопка «Распределить ключи».
       - Селектор потока и превью содержимого.
       - Экспорт в буфер обмена или в текстовые файлы `valid_keys_stream_N.txt`.
    4. **Справка / FAQ (`InfoView`):**
       - Инструкция по получению ключей, регламент донатов и описание статусов Google API.

### 5.2. Потокобезопасность (Worker Protocol)
- Класс `CheckWorker(QThread)`:
  - Сигналы:
    - `progress_updated = pyqtSignal(int, int)` (текущий, всего)
    - `stats_updated = pyqtSignal(dict)` (метрики по статусам)
    - `log_emitted = pyqtSignal(str, str)` (текст, цветовой тег)
    - `key_finished = pyqtSignal(int, str, str)` (id, статус, деталь)
    - `finished = pyqtSignal()`
  - Корректная обработка `pause` и `stop` через `QWaitCondition` и атомарные флаги без утечек ресурсов.

---

## 6. План интеграции с NixOS и Лаунчером

1. **`flake.nix`:**
   - `pythonEnv = pkgs.python3.withPackages (ps: [ ps.pyqt6 ps.pyqtdarktheme ps.pysocks ps.pytest ps.ruff ])`.
   - Подключение `pkgs.qt6.qtwayland` и `pkgs.qt6.wrapQtAppsHook`.
   - Десктоп-интеграция: сборка пакета `gemini-nexus-db` с ярлыком `.desktop` для меню Niri.
2. **`run.sh`:**
   - Чистый запуск через `nix-shell` / `nix run` без костылей с `chmod` шрифтов.

---

## 7. Верификация и План тестирования (TDD / QA)

- **Unit-тесты:**
  - `tests/test_crypto.py`: проверка шифрования/дешифрования с валидным и неверным паролем, проверка HMAC.
  - `tests/test_db.py`: создание тестовой БД `:memory:`, добавление ключей, каскадные удаления, сброс статусов.
  - `tests/test_splitter.py`: проверка сбалансированности Round-Robin на 1, 3, 5, 10 потоков, исключение `is_ignored = 1` и статусов != `OK`.
- **Smoke-тест GUI:**
  - Запуск PyQt6 интерфейса в Wayland-сессии под Niri, проверка масштабирования 1.8x, отсутствия артефактов и мыла.
