import sqlite3
import urllib.request
import urllib.error
import urllib.parse
import json
import time
import socket
import random
import threading
import os
import re
import hmac
import hashlib
import base64
import secrets
import tkinter as tk
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import customtkinter as ctk
from tkinter import messagebox, filedialog

# Настройки ядра
TIMEOUT = 30
DB_FILE = "gemini_keys.db"
APP_VERSION = "13.9 (Enterprise)"
AUTHOR = "NeuroStarNet"

# Русская локализация статусов для вывода
STATUS_RU = {
    "UNCHECKED": "Не проверен ⏳",
    "OK": "Рабочий (OK) ✅",
    "UNRESTRICTED": "Требует привязки API (Блок от 19 июня) ⚠️",
    "RESOURCE_EXHAUSTED": "Превышен лимит RPM/TPM (Ключ живой, разгрузится) ⏳",
    "SERVICE_UNAVAILABLE": "Сервер перегружен / Сервис недоступен (Разгрузится) ⏳",
    "FAILED_PRECONDITION": "Региональный блок / Нужен биллинг (Fatal) ❌",
    "PERMISSION_DENIED": "Отказано в доступе / Ключ заблокирован (Fatal) ❌",
    "UNAUTHORIZED": "Не существует / Неверный ключ (Fatal) ❌",
    "NOT_FOUND": "Модель не найдена (Проверь ID модели) ❌",
    "INTERNAL_ERROR": "Внутренняя ошибка Google (Разгрузится) ⏳",
    "DEADLINE_EXCEEDED": "Таймаут сервера Google (Попробуй позже) ⏳",
    "TIMEOUT": "Сеть лагает (Таймаут соединения) ⏳",
    "ERROR": "Фатальная ошибка ключа ❌"
}

def connect_db():
    conn = sqlite3.connect(DB_FILE, timeout=30.0)
    c = conn.cursor()
    c.execute("PRAGMA foreign_keys = ON;")
    c.execute("PRAGMA journal_mode=WAL;")
    c.execute("PRAGMA synchronous=NORMAL;")
    c.execute("PRAGMA temp_store=MEMORY;")
    c.close()
    return conn

def init_db():
    conn = connect_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS owners (
                 id INTEGER PRIMARY KEY, nickname TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS api_keys (
                 id INTEGER PRIMARY KEY, 
                 owner_id INTEGER, 
                 key_string TEXT UNIQUE, 
                 status TEXT DEFAULT 'UNCHECKED', 
                 detail TEXT DEFAULT '',
                 FOREIGN KEY(owner_id) REFERENCES owners(id) ON DELETE CASCADE)''')
    
    # Автоматические миграции СУБД под новые фичи
    try: c.execute("ALTER TABLE owners ADD COLUMN notes TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE api_keys ADD COLUMN notes TEXT DEFAULT ''")
    except sqlite3.OperationalError: pass
    try: c.execute("ALTER TABLE api_keys ADD COLUMN is_ignored INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass

    c.execute('''CREATE TABLE IF NOT EXISTS models (name TEXT UNIQUE)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT UNIQUE, value TEXT)''')
    
    actual_models = [
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-robotics-er-1.5-preview",
        "gemini-robotics-er-1.6-preview",
        "gemma-3-27b-it",
        "gemma-4-26b-a4b-it",
        "gemma-4-31b-it",
        "gemini-3.1-flash-tts-preview",
        "gemini-2.5-flash-preview-tts",
        "gemini-2.5-pro-preview-tts"
    ]
    for m in actual_models: 
        c.execute("INSERT OR IGNORE INTO models (name) VALUES (?)", (m,))
            
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('delay_min', '7')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('delay_max', '10')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('current_model', 'gemini-3.5-flash')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('proxy_use', '0')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('proxy_url', 'socks5://127.0.0.1:1080')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('checker_threads', '1')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('splitter_streams', '3')")
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('ui_scaling', '140%')")
    
    c.execute("SELECT COUNT(*) FROM settings WHERE key='v13_2_migrated'")
    if c.fetchone()[0] == 0:
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('splitter_streams', '3')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('v13_2_migrated', '1')")
    
    conn.commit()
    conn.close()

init_db()

def get_setting(key):
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else ""

def save_setting(key, value):
    conn = connect_db()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_models_list():
    conn = connect_db()
    c = conn.cursor()
    c.execute("SELECT name FROM models ORDER BY name")
    models = [row[0] for row in c.fetchall()]
    conn.close()
    return models

class GeminiNexus(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"Gemini Nexus DB v{APP_VERSION} | by {AUTHOR}")
        self.geometry("1150x820")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.is_running = False
        self.is_paused = False
        self.ping_selective = False
        self.split_results = {}
        self.counter_lock = threading.Lock()
        self.checked_count = 0
        self.guide_win = None
        
        self.setup_ui()
        self.show_frame("manager")
        
        saved_scaling = get_setting("ui_scaling")
        if not saved_scaling:
            saved_scaling = "140%"
        self.scaling_optionemenu.set(saved_scaling)
        self.change_scaling(saved_scaling)

    def change_scaling(self, new_scaling: str):
        try:
            new_scaling_float = int(new_scaling.replace("%", "")) / 100
            ctk.set_widget_scaling(new_scaling_float)
            save_setting("ui_scaling", new_scaling)
        except Exception:
            pass

    def safe_after(self, delay_ms, callback):
        try:
            if self.winfo_exists():
                self.after(delay_ms, callback)
        except (tk.TclError, RuntimeError):
            pass

    # --- СИСТЕМНЫЙ ФИКС БУФЕРА ОБМЕНА И КОНТЕКСТНОГО МЕНЮ ---
    def apply_context_menu(self, widget):
        is_textbox = isinstance(widget, ctk.CTkTextbox)
        inner = widget._textbox if is_textbox else widget._entry

        def get_state():
            try: return widget.cget("state")
            except ValueError: return inner.cget("state")

        def do_copy():
            try: inner.event_generate("<<Copy>>")
            except: pass
            
        def do_paste():
            if get_state() == "normal":
                try: inner.event_generate("<<Paste>>")
                except: pass

        def do_cut():
            if get_state() == "normal":
                try: inner.event_generate("<<Cut>>")
                except: pass

        def select_all(event=None):
            if is_textbox: widget.tag_add("sel", "1.0", "end")
            else: widget.select_range(0, "end")
            return "break"

        menu = tk.Menu(self, tearoff=0, font=("Consolas", 14), bg="#2b2b2b", fg="white", activebackground="#1f538d")
        menu.add_command(label="Копировать (Ctrl+C)", command=do_copy)
        menu.add_command(label="Вставить (Ctrl+V)", command=do_paste)
        menu.add_command(label="Вырезать (Ctrl+X)", command=do_cut)
        menu.add_separator()
        menu.add_command(label="Выделить всё (Ctrl+A)", command=select_all)

        menu_disabled = tk.Menu(self, tearoff=0, font=("Consolas", 14), bg="#2b2b2b", fg="white", activebackground="#1f538d")
        menu_disabled.add_command(label="Копировать (Ctrl+C)", command=do_copy)
        menu_disabled.add_separator()
        menu_disabled.add_command(label="Выделить всё (Ctrl+A)", command=select_all)
        
        # Защита от Garbage Collector
        widget._ctx_menu = menu
        widget._ctx_menu_disabled = menu_disabled

        def show_menu(event):
            inner.focus_set()
            try:
                m = widget._ctx_menu_disabled if get_state() == "disabled" else widget._ctx_menu
                m.tk_popup(event.x_root, event.y_root)
            except Exception:
                pass

        inner.bind("<Button-3>", show_menu)
        
        def handle_ctrl(event):
            kc = event.keycode
            c = event.char
            sym = event.keysym.lower()
            
            # Windows keycodes: V=86, C=67, X=88, A=65
            # Linux X11/Wayland keycodes: V=55, C=54, X=53, A=38
            is_paste = kc in (86, 55) or c == '\x16' or sym in ('v', 'м', 'cyrillic_em', 'cyrillic_ve')
            is_copy = kc in (67, 54) or c == '\x03' or sym in ('c', 'с', 'cyrillic_es')
            is_cut = kc in (88, 53) or c == '\x18' or sym in ('x', 'ч', 'cyrillic_che')
            is_select = kc in (65, 38) or c == '\x01' or sym in ('a', 'ф', 'cyrillic_ef')

            if is_paste:
                do_paste()
                return "break"
            elif is_copy:
                do_copy()
                return "break"
            elif is_cut:
                do_cut()
                return "break"
            elif is_select:
                select_all()
                return "break"

        inner.bind("<Control-Key>", handle_ctrl)

    # Очистка имени донатера от суффикса счетчика вида " (N шт.)"
    def get_clean_nickname(self, raw_str):
        if not raw_str or raw_str == "Нет донатеров": 
            return ""
        return re.sub(r'\s*\(\d+\s*шт\.\)$', '', raw_str).strip()

    def setup_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # --- БОКОВОЕ МЕНЮ ---
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.logo = ctk.CTkLabel(self.sidebar, text="NEXUS CORE", font=ctk.CTkFont(size=22, weight="bold"))
        self.logo.grid(row=0, column=0, padx=20, pady=(20, 30))
        self.btn_nav_manager = ctk.CTkButton(self.sidebar, text="🗄️ База данных", command=lambda: self.show_frame("manager"))
        self.btn_nav_manager.grid(row=1, column=0, padx=20, pady=10)
        self.btn_nav_checker = ctk.CTkButton(self.sidebar, text="📡 Чекер ключей", command=lambda: self.show_frame("checker"))
        self.btn_nav_checker.grid(row=2, column=0, padx=20, pady=10)
        self.btn_nav_splitter = ctk.CTkButton(self.sidebar, text="🔀 Сплиттер (Кастомный)", command=lambda: self.show_frame("splitter"))
        self.btn_nav_splitter.grid(row=3, column=0, padx=20, pady=10)
        self.btn_nav_guide = ctk.CTkButton(self.sidebar, text="📖 ИНСТРУКЦИЯ", fg_color="#b85c00", hover_color="#8f4700", command=self.show_instruction_window)
        self.btn_nav_guide.grid(row=4, column=0, padx=20, pady=10)
        self.btn_nav_info = ctk.CTkButton(self.sidebar, text="ℹ️ О программе / FAQ", fg_color="#444", hover_color="#555", command=lambda: self.show_frame("info"))
        self.btn_nav_info.grid(row=5, column=0, padx=20, pady=(20, 10))
        
        self.sidebar.grid_rowconfigure(6, weight=1)
        self.scaling_label = ctk.CTkLabel(self.sidebar, text="🔍 Масштаб UI:", anchor="w", font=ctk.CTkFont(size=12, weight="bold"))
        self.scaling_label.grid(row=7, column=0, padx=20, pady=(10, 0), sticky="w")
        self.scaling_optionemenu = ctk.CTkOptionMenu(
            self.sidebar,
            values=["100%", "110%", "120%", "130%", "140%", "150%", "160%", "170%", "180%", "200%"],
            command=self.change_scaling
        )
        self.scaling_optionemenu.grid(row=8, column=0, padx=20, pady=(5, 20), sticky="ew")
        
        self.frames = {}
        
        # === 1. Фрейм Менеджера БД ===
        self.frames["manager"] = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frames["manager"].grid_columnconfigure(0, weight=1)
        self.frames["manager"].grid_rowconfigure(1, weight=1)
        
        self.mgr_tabs = ctk.CTkTabview(self.frames["manager"])
        self.mgr_tabs.grid(row=0, column=0, sticky="ew", padx=10, pady=0)
        self.mgr_tabs.add("Добавление")
        self.mgr_tabs.add("Заметки (Редактор)")
        self.mgr_tabs.add("Управление (CRUD)")
        self.mgr_tabs.add("Импорт / Экспорт")
        
        tab_add = self.mgr_tabs.tab("Добавление")
        self.owner_var = ctk.StringVar()
        self.owner_cb = ctk.CTkComboBox(tab_add, variable=self.owner_var, values=self.get_owners(), width=180)
        self.owner_cb.pack(side="left", padx=10, pady=10)
        btn_add_owner = ctk.CTkButton(tab_add, text="➕ Новый донатер", width=120, command=self.add_owner)
        btn_add_owner.pack(side="left", padx=5, pady=10)
        
        self.keys_input = ctk.CTkTextbox(tab_add, height=45, width=280)
        self.keys_input.pack(side="left", padx=10, pady=10)
        self.keys_input.insert("0.0", "Вставь ключи (столбиком)...")
        self.keys_input.bind("<FocusIn>", lambda e: self.keys_input.delete("0.0", "end") if self.keys_input.get("0.0", "end").strip() == "Вставь ключи (столбиком)..." else None)
        self.apply_context_menu(self.keys_input)

        btn_save_keys = ctk.CTkButton(tab_add, text="💾 Сохранить ключи", width=140, command=self.add_keys)
        btn_save_keys.pack(side="left", padx=5, pady=10)
        
        # Вкладка 2: Заметки
        tab_notes = self.mgr_tabs.tab("Заметки (Редактор)")
        self.note_owner_var = ctk.StringVar()
        self.note_owner_cb = ctk.CTkComboBox(tab_notes, variable=self.note_owner_var, values=self.get_owners(), width=160, command=self.load_owner_data)
        self.note_owner_cb.pack(side="left", padx=5, pady=10)
        
        self.owner_note_input = ctk.CTkEntry(tab_notes, placeholder_text="Заметка донатера...", width=160)
        self.owner_note_input.pack(side="left", padx=5, pady=10)
        self.apply_context_menu(self.owner_note_input)
        
        btn_save_o_note = ctk.CTkButton(tab_notes, text="💾 Донатер", width=80, command=self.save_owner_note)
        btn_save_o_note.pack(side="left", padx=5, pady=10)
        
        self.note_key_var = ctk.StringVar()
        self.note_key_cb = ctk.CTkComboBox(tab_notes, variable=self.note_key_var, values=["Нет ключей"], width=160, command=self.load_key_note)
        self.note_key_cb.pack(side="left", padx=5, pady=10)
        
        self.key_note_input = ctk.CTkEntry(tab_notes, placeholder_text="Заметка ключа...", width=160)
        self.key_note_input.pack(side="left", padx=5, pady=10)
        self.apply_context_menu(self.key_note_input)
        
        btn_save_k_note = ctk.CTkButton(tab_notes, text="💾 Ключ", width=70, command=self.save_key_note)
        btn_save_k_note.pack(side="left", padx=5, pady=10)
        
        # Вкладка 3: Управление (CRUD)
        tab_crud = self.mgr_tabs.tab("Управление (CRUD)")
        crud_left = ctk.CTkFrame(tab_crud, fg_color="transparent")
        crud_left.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(crud_left, text="Управление Донатерами", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        self.crud_owner_var = ctk.StringVar()
        self.crud_owner_cb = ctk.CTkComboBox(crud_left, variable=self.crud_owner_var, values=self.get_owners(), width=180, command=self.on_crud_owner_select)
        self.crud_owner_cb.pack(pady=5)
        
        btn_del_owner = ctk.CTkButton(crud_left, text="🗑️ Удалить донатера", fg_color="#802020", hover_color="#601515", command=self.delete_owner)
        btn_del_owner.pack(pady=5)
        btn_reset_owner = ctk.CTkButton(crud_left, text="🔄 Сбросить ключи", fg_color="#a86000", hover_color="#7a4600", command=self.reset_owner_statuses)
        btn_reset_owner.pack(pady=5)

        crud_right = ctk.CTkFrame(tab_crud, fg_color="transparent")
        crud_right.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(crud_right, text="Управление Ключами", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        self.crud_key_var = ctk.StringVar()
        self.crud_key_cb = ctk.CTkComboBox(crud_right, variable=self.crud_key_var, values=["Выберите донатера"], width=180, command=self.load_crud_key_status)
        self.crud_key_cb.pack(pady=5)
        
        self.crud_full_key_entry = ctk.CTkEntry(crud_right, placeholder_text="Полный ключ...", width=200)
        self.crud_full_key_entry.pack(pady=5)
        self.apply_context_menu(self.crud_full_key_entry)

        self.crud_key_ignore_var = ctk.BooleanVar(value=False)
        self.crud_key_ignore_cb = ctk.CTkCheckBox(crud_right, text="Исключить из Сплиттера", variable=self.crud_key_ignore_var, command=self.toggle_ignore_key, font=ctk.CTkFont(size=11))
        self.crud_key_ignore_cb.pack(pady=5)

        btn_del_key = ctk.CTkButton(crud_right, text="🗑️ Удалить ключ", fg_color="#802020", hover_color="#601515", command=self.delete_key)
        btn_del_key.pack(pady=5)
        btn_reset_key = ctk.CTkButton(crud_right, text="🔄 Сбросить статус", fg_color="#a86000", hover_color="#7a4600", command=self.reset_key_status)
        btn_reset_key.pack(pady=5)
        
        crud_mass = ctk.CTkFrame(tab_crud, fg_color="transparent")
        crud_mass.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(crud_mass, text="Общие Операции (База)", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        btn_reset_all = ctk.CTkButton(crud_mass, text="💥 Сбросить ВСЕ статусы", fg_color="#c25900", hover_color="#914300", command=self.reset_all_statuses)
        btn_reset_all.pack(pady=5)
        btn_del_broken = ctk.CTkButton(crud_mass, text="❌ Удалить все мертвые", fg_color="#a80000", hover_color="#800000", command=self.delete_broken_keys)
        btn_del_broken.pack(pady=5)

        # Вкладка 4: Импорт/Экспорт
        tab_io = self.mgr_tabs.tab("Импорт / Экспорт")
        exp_frame = ctk.CTkFrame(tab_io, fg_color="transparent")
        exp_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(exp_frame, text="Выгрузка данных (Экспорт)", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        self.exp_fmt_var = ctk.StringVar(value="Чистый JSON (.json)")
        self.exp_fmt_cb = ctk.CTkComboBox(exp_frame, variable=self.exp_fmt_var, values=["Чистый JSON (.json)", "Зашифрованный JSON (.enc.json)", "Список ключей в столбик (.txt)", "Obsidian Markdown (.md)"], width=220)
        self.exp_fmt_cb.pack(pady=5)
        self.exp_pwd_entry = ctk.CTkEntry(exp_frame, placeholder_text="Пароль для шифрования...", show="*", width=220)
        self.exp_pwd_entry.pack(pady=5)
        self.apply_context_menu(self.exp_pwd_entry)
        btn_export = ctk.CTkButton(exp_frame, text="📤 Экспорт базы", command=self.export_db)
        btn_export.pack(pady=5)

        imp_frame = ctk.CTkFrame(tab_io, fg_color="transparent")
        imp_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(imp_frame, text="Загрузка данных (Импорт)", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        self.imp_fmt_var = ctk.StringVar(value="Чистый JSON (.json)")
        self.imp_fmt_cb = ctk.CTkComboBox(imp_frame, variable=self.imp_fmt_var, values=["Чистый JSON (.json)", "Зашифрованный JSON (.enc.json)"], width=220)
        self.imp_fmt_cb.pack(pady=5)
        self.imp_pwd_entry = ctk.CTkEntry(imp_frame, placeholder_text="Пароль расшифровки...", show="*", width=220)
        self.imp_pwd_entry.pack(pady=5)
        self.apply_context_menu(self.imp_pwd_entry)
        btn_import = ctk.CTkButton(imp_frame, text="📥 Импорт бэкапа", command=self.import_db)
        btn_import.pack(pady=5)

        self.db_view = ctk.CTkTextbox(self.frames["manager"], font=("Consolas", 13), wrap="none")
        self.db_view.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.db_view.tag_config("green", foreground="#2db92d")
        self.db_view.tag_config("yellow", foreground="#e5a93c")
        self.db_view.tag_config("red", foreground="#ff4d4d")
        self.apply_context_menu(self.db_view)

        db_controls = ctk.CTkFrame(self.frames["manager"], fg_color="transparent")
        db_controls.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        ctk.CTkLabel(db_controls, text="Фильтр базы:").pack(side="left", padx=5)
        self.active_db_status_cb = ctk.CTkComboBox(db_controls, values=["Все ключи", "Рабочие (OK)", "Временные лимиты (Yellow)", "Нерабочие (Red)", "Не проверенные (Grey)"], width=200, command=lambda e: self.refresh_db_view())
        self.active_db_status_cb.set("Все ключи")
        self.active_db_status_cb.pack(side="left", padx=5)

        btn_refresh = ctk.CTkButton(db_controls, text="🔄 Обновить", width=100, command=self.refresh_db_view)
        btn_refresh.pack(side="left", padx=5)
        
        # === 2. Фрейм Чекера Ключей ===
        self.frames["checker"] = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frames["checker"].grid_columnconfigure(0, weight=1)
        self.frames["checker"].grid_rowconfigure(2, weight=1)
        
        chk_settings = ctk.CTkFrame(self.frames["checker"])
        chk_settings.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        # 1-й ряд: Модель и потоки
        row1 = ctk.CTkFrame(chk_settings, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(row1, text="Модель Google:").pack(side="left", padx=5)
        self.model_var = ctk.StringVar(value=get_setting("current_model") or "gemini-3.5-flash")
        self.model_cb = ctk.CTkComboBox(row1, variable=self.model_var, values=get_models_list(), width=220)
        self.model_cb.pack(side="left", padx=5)
        
        btn_custom_model = ctk.CTkButton(row1, text="➕ Кастомная модель", width=140, fg_color="#333", hover_color="#444", command=self.add_custom_model)
        btn_custom_model.pack(side="left", padx=5)
        
        ctk.CTkLabel(row1, text="Потоков (Threads):").pack(side="left", padx=(20, 5))
        self.threads_var = ctk.StringVar(value=get_setting("checker_threads") or "1")
        self.threads_entry = ctk.CTkEntry(row1, textvariable=self.threads_var, width=50)
        self.threads_entry.pack(side="left", padx=5)
        self.apply_context_menu(self.threads_entry)

        # 2-й ряд: Паузы
        row2 = ctk.CTkFrame(chk_settings, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(row2, text="Пауза Min (сек):").pack(side="left", padx=5)
        self.delay_min_var = ctk.StringVar(value=get_setting("delay_min") or "7")
        self.delay_min_entry = ctk.CTkEntry(row2, textvariable=self.delay_min_var, width=60)
        self.delay_min_entry.pack(side="left", padx=5)
        self.apply_context_menu(self.delay_min_entry)
        
        ctk.CTkLabel(row2, text="Пауза Max (сек):").pack(side="left", padx=5)
        self.delay_max_var = ctk.StringVar(value=get_setting("delay_max") or "10")
        self.delay_max_entry = ctk.CTkEntry(row2, textvariable=self.delay_max_var, width=60)
        self.delay_max_entry.pack(side="left", padx=5)
        self.apply_context_menu(self.delay_max_entry)

        # 3-й ряд: Прокси
        row3 = ctk.CTkFrame(chk_settings, fg_color="transparent")
        row3.pack(fill="x", padx=10, pady=5)

        self.proxy_use_var = ctk.BooleanVar(value=(get_setting("proxy_use") == "1"))
        self.proxy_cb = ctk.CTkCheckBox(row3, text="Использовать Прокси (SOCKS4/5, HTTP)", variable=self.proxy_use_var)
        self.proxy_cb.pack(side="left", padx=5)

        self.proxy_url_var = ctk.StringVar(value=get_setting("proxy_url") or "socks5://127.0.0.1:1080")
        self.proxy_entry = ctk.CTkEntry(row3, textvariable=self.proxy_url_var, width=320)
        self.proxy_entry.pack(side="left", padx=10)
        self.apply_context_menu(self.proxy_entry)
        
        # Кнопки управления чекером
        chk_controls = ctk.CTkFrame(self.frames["checker"], fg_color="transparent")
        chk_controls.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.btn_start = ctk.CTkButton(chk_controls, text="▶ Полный Пинг", fg_color="#2b7a2b", hover_color="#1e5c1e", width=120, command=lambda: self.start_checking(selective=False))
        self.btn_start.pack(side="left", padx=5, pady=10)

        ctk.CTkLabel(chk_controls, text="Выборочно:").pack(side="left", padx=(10, 2), pady=10)
        self.ping_select_var = ctk.StringVar(value="Только Серые (Не проверенные)")
        self.ping_select_cb = ctk.CTkComboBox(
            chk_controls, 
            variable=self.ping_select_var, 
            values=["Только Серые (Не проверенные)", "Только Желтые (Временные)", "Только Красные (Мертвые)", "Желтые + Серые", "Все нерабочие (!= OK)"], 
            width=210
        )
        self.ping_select_cb.pack(side="left", padx=5, pady=10)

        self.btn_ping_selective = ctk.CTkButton(chk_controls, text="🎯 Запустить выбор", fg_color="#b8860b", hover_color="#8b6508", width=120, command=lambda: self.start_checking(selective=True))
        self.btn_ping_selective.pack(side="left", padx=5, pady=10)

        self.btn_pause = ctk.CTkButton(chk_controls, text="⏸️ Пауза", fg_color="#1f538d", hover_color="#143e68", width=80, state="disabled", command=self.toggle_pause)
        self.btn_pause.pack(side="left", padx=5, pady=10)

        self.btn_stop = ctk.CTkButton(chk_controls, text="⏹️ Стоп", fg_color="#802020", hover_color="#601515", width=80, state="disabled", command=self.stop_checking)
        self.btn_stop.pack(side="left", padx=5, pady=10)

        self.chk_stats = ctk.CTkLabel(chk_controls, text="Проверено: 0/0", font=ctk.CTkFont(weight="bold"))
        self.chk_stats.pack(side="right", padx=10)

        self.log_box = ctk.CTkTextbox(self.frames["checker"], font=("Consolas", 12))
        self.log_box.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        self.log_box.tag_config("green", foreground="#2db92d")
        self.log_box.tag_config("yellow", foreground="#e5a93c")
        self.log_box.tag_config("red", foreground="#ff4d4d")
        self.apply_context_menu(self.log_box)
        
        # === 3. Фрейм Кастомного Сплиттера ===
        self.frames["splitter"] = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frames["splitter"].grid_columnconfigure(0, weight=1)
        self.frames["splitter"].grid_rowconfigure(1, weight=1)

        spl_top = ctk.CTkFrame(self.frames["splitter"])
        spl_top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(spl_top, text="Количество потоков (Streams):").pack(side="left", padx=10, pady=10)
        self.streams_count_var = ctk.StringVar(value=get_setting("splitter_streams") or "3")
        self.streams_entry = ctk.CTkEntry(spl_top, textvariable=self.streams_count_var, width=50)
        self.streams_entry.pack(side="left", padx=5, pady=10)
        self.apply_context_menu(self.streams_entry)

        btn_run_split = ctk.CTkButton(spl_top, text="🔀 Распределить ключи", command=self.do_split)
        btn_run_split.pack(side="left", padx=10, pady=10)

        btn_export_streams = ctk.CTkButton(spl_top, text="💾 Экспорт всех потоков (.txt)", fg_color="#2b7a2b", hover_color="#1e5c1e", command=self.export_all_streams)
        btn_export_streams.pack(side="left", padx=10, pady=10)

        spl_main = ctk.CTkFrame(self.frames["splitter"])
        spl_main.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        spl_main.grid_columnconfigure(1, weight=1)
        spl_main.grid_rowconfigure(0, weight=1)

        spl_left = ctk.CTkFrame(spl_main, width=220)
        spl_left.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        ctk.CTkLabel(spl_left, text="Выбор потока:", font=ctk.CTkFont(weight="bold")).pack(padx=10, pady=10)
        self.active_stream_var = ctk.StringVar(value="Нет потоков")
        self.active_stream_cb = ctk.CTkComboBox(spl_left, variable=self.active_stream_var, values=["Нет потоков"], width=180, command=self.show_stream_preview)
        self.active_stream_cb.pack(padx=10, pady=10)

        btn_copy_stream = ctk.CTkButton(spl_left, text="📋 Скопировать поток", command=self.copy_selected_stream)
        btn_copy_stream.pack(padx=10, pady=10)

        self.stream_preview_box = ctk.CTkTextbox(spl_main, font=("Consolas", 13))
        self.stream_preview_box.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        self.stream_preview_box.insert("0.0", "Распредели ключи, чтобы сгенерировать потоки перевода...")
        self.stream_preview_box.configure(state="disabled")
        self.apply_context_menu(self.stream_preview_box)
        
        # === 4. Фрейм О Программе / FAQ ===
        self.frames["info"] = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.frames["info"].grid_columnconfigure(0, weight=1)
        self.frames["info"].grid_rowconfigure(0, weight=1)

        info_text = f"""
========================================================================================
🚀 GEMINI NEXUS CORE DB — Версия {APP_VERSION} (by {AUTHOR})
========================================================================================

📌 ОПИСАНИЕ СИСТЕМЫ:
Gemini Nexus — комплекс управления и балансировки пула API ключей Google Gemini / Gemma.
Автоматизирует многопоточную проверку ключей, работу с прокси, шифрование базы и экспорт потоков.

🔍 РАЗБОР СТАТУСОВ И ОШИБОК GOOGLE API:
----------------------------------------------------------------------------------------
🟢 Рабочий (OK) ✅
   Ключ полностью валиден и готов к работе в переводчиках.

⚠️ Требует привязки API (Блок от 19 июня) [UNRESTRICTED]
   Google ввел политику безопасности: ключ не привязан к конкретному сервису Generative Language.
   Лечится в Google AI Studio/Cloud Console установкой API Restrictions.

🟡 Превышен лимит RPM/TPM [RESOURCE_EXHAUSTED] ⏳
   Лимит запросов в минуту/день исчерпан. Ключ ЖИВОЙ, разгрузится со временем.

🟡 Сервер перегружен / Таймаут [SERVICE_UNAVAILABLE, TIMEOUT] ⏳
   Временный сбой на стороне Google или сетевая задержка.

❌ Региональный блок / Нужен биллинг [FAILED_PRECONDITION] ❌
   Фатальная ошибка: аккаунт/страна заблокированы или требуется привязка карты.

❌ Отказано в доступе / Ключ удален [PERMISSION_DENIED, UNAUTHORIZED] ❌
   Ключ деактивирован, удален или заблокирован Google.
========================================================================================
        """
        info_box = ctk.CTkTextbox(self.frames["info"], font=("Consolas", 14), wrap="word")
        info_box.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        info_box.insert("0.0", info_text.strip())
        info_box.configure(state="disabled")
        self.apply_context_menu(info_box)

    def show_instruction_window(self):
        if self.guide_win is not None and self.guide_win.winfo_exists():
            self.guide_win.focus()
            return
            
        self.guide_win = ctk.CTkToplevel(self)
        self.guide_win.title("📖 Руководство пользователя (NEXUS)")
        self.guide_win.geometry("900x700")
        self.guide_win.attributes("-topmost", True)
        
        guide_text = """
========================================================================================
📖 ИНСТРУКЦИЯ ПО РАБОТЕ С NEXUS CORE
========================================================================================

1. 🗄️ БАЗА ДАННЫХ И ДОБАВЛЕНИЕ:
   • Выбери донатера или создай нового через «➕ Новый донатер».
   • Вставь ключи в поле ввода (каждый ключ с новой строки) и нажми «💾 Сохранить ключи».
   • Вкладка «Заметки»: добавь описание донатеру или конкретному ключу.
   • Вкладка «Управление (CRUD)»: удаление, сброс статусов или исключение ключа из сплиттера.

2. 📡 ЧЕКЕР КЛЮЧЕЙ:
   • Выбери модель Google (по умолчанию gemini-3.5-flash).
   • Настрой паузы (7-10 сек рекомендуется для защиты от мгновенных 429).
   • При необходимости укажи SOCKS5/HTTP прокси.
   • «▶ Полный Пинг» проверяет все ключи базы.
   • «🎯 Запустить выбор» проверяет только выбранную категорию (Серые, Желтые, Красные).
   • Кнопки «Пауза» и «Стоп» реагируют мгновенно.

3. 🔀 КАСТОМНЫЙ СПЛИТТЕР:
   • Укажи количество потоков перевода (например, 3 или 5).
   • Нажми «🔀 Распределить ключи» — рабочие ключи распределятся Round-Robin.
   • Скопируй нужный поток в буфер или нажми «💾 Экспорт всех потоков (.txt)».
========================================================================================
        """
        textbox = ctk.CTkTextbox(self.guide_win, font=("Consolas", 14), wrap="word")
        textbox.pack(fill="both", expand=True, padx=15, pady=15)
        textbox.insert("0.0", guide_text.strip())
        textbox.configure(state="disabled")
        self.apply_context_menu(textbox)

    def show_frame(self, frame_name):
        for frame in self.frames.values(): 
            frame.grid_remove()
        self.frames[frame_name].grid(row=0, column=1, sticky="nsew")
        if frame_name == "manager":
            self.refresh_db_view()
            self.update_owner_dropdowns()

    # --- ЛОГИКА СУБД И СПИСКОВ ---
    def get_owners(self):
        conn = connect_db()
        c = conn.cursor()
        c.execute('''SELECT owners.nickname, COUNT(api_keys.id) 
                     FROM owners LEFT JOIN api_keys ON owners.id = api_keys.owner_id 
                     GROUP BY owners.id, owners.nickname
                     ORDER BY owners.nickname''')
        rows = c.fetchall()
        conn.close()
        return [f"{nick} ({cnt} шт.)" for nick, cnt in rows] if rows else ["Нет донатеров"]

    def update_owner_dropdowns(self):
        owners = self.get_owners()
        self.owner_cb.configure(values=owners)
        self.note_owner_cb.configure(values=owners)
        self.crud_owner_cb.configure(values=owners)
        self.imp_fmt_cb.configure(values=["Чистый JSON (.json)", "Зашифрованный JSON (.enc.json)"])
        if owners and owners[0] != "Нет донатеров":
            self.owner_var.set(owners[0])
            self.note_owner_var.set(owners[0])
            self.crud_owner_var.set(owners[0])
            self.load_owner_data(owners[0])
            self.on_crud_owner_select(owners[0])

    def add_owner(self):
        dialog = ctk.CTkInputDialog(text="Введи ник/тег донатера:", title="Новый владелец")
        name = dialog.get_input()
        if name and name.strip():
            conn = connect_db()
            try:
                conn.execute("INSERT INTO owners (nickname, notes) VALUES (?, ?)", (name.strip(), ""))
                conn.commit()
            except sqlite3.IntegrityError:
                pass
            finally:
                conn.close()
            self.update_owner_dropdowns()

    def add_keys(self):
        owner_raw = self.owner_var.get()
        owner = self.get_clean_nickname(owner_raw)
        if owner == "Нет донатеров" or not owner: 
            return
        raw_keys = self.keys_input.get("0.0", "end").strip().split('\n')
        self.keys_input.delete("0.0", "end")
        
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("SELECT id FROM owners WHERE nickname=?", (owner,))
            row = c.fetchone()
            if not row:
                return
            owner_id = row[0]
            
            for k in raw_keys:
                k = k.strip()
                if k:
                    try: 
                        c.execute("INSERT INTO api_keys (owner_id, key_string) VALUES (?, ?)", (owner_id, k))
                    except sqlite3.IntegrityError: 
                        pass
            conn.commit()
        finally:
            conn.close()
            
        self.update_owner_dropdowns()
        self.refresh_db_view()
        self.on_crud_owner_select(owner)

    def load_owner_data(self, choice_raw):
        choice = self.get_clean_nickname(choice_raw)
        if not choice: 
            return
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("SELECT notes FROM owners WHERE nickname=?", (choice,))
            res = c.fetchone()
            self.owner_note_input.delete(0, "end")
            self.owner_note_input.insert(0, res[0] if res and res[0] else "")
            
            c.execute("SELECT key_string FROM api_keys JOIN owners ON api_keys.owner_id = owners.id WHERE owners.nickname=?", (choice,))
            keys = [row[0] for row in c.fetchall()]
        finally:
            conn.close()
        
        if keys:
            formatted_keys = [f"{k[:10]}...{k[-4:]}" if len(k) > 15 else k for k in keys]
            self.note_key_cb.configure(values=formatted_keys)
            self.note_key_var.set(formatted_keys[0])
            self.load_key_note(formatted_keys[0])
        else:
            self.note_key_cb.configure(values=["Нет ключей"])
            self.note_key_var.set("Нет ключей")
            self.key_note_input.delete(0, "end")

    def load_key_note(self, short_key):
        if short_key in ("Нет ключей", "Выберите донатера") or not short_key:
            self.key_note_input.delete(0, "end")
            return
            
        owner_raw = self.note_owner_var.get()
        owner = self.get_clean_nickname(owner_raw)
        if not owner: 
            return
        
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT key_string, notes 
                FROM api_keys 
                WHERE owner_id = (SELECT id FROM owners WHERE nickname=?)
            """, (owner,))
            rows = c.fetchall()
        finally:
            conn.close()
        
        full_key = None
        key_note = ""
        for k_str, note in rows:
            masked = f"{k_str[:10]}...{k_str[-4:]}" if len(k_str) > 15 else k_str
            if masked == short_key or k_str == short_key:
                full_key = k_str
                key_note = note
                break
                
        if not full_key: 
            return
        self.key_note_input.delete(0, "end")
        self.key_note_input.insert(0, key_note if key_note else "")

    def save_owner_note(self):
        owner_raw = self.note_owner_var.get()
        owner = self.get_clean_nickname(owner_raw)
        note = self.owner_note_input.get()
        if owner and owner != "Нет донатеров":
            conn = connect_db()
            try:
                conn.execute("UPDATE owners SET notes=? WHERE nickname=?", (note, owner))
                conn.commit()
            finally:
                conn.close()
            self.refresh_db_view()

    def save_key_note(self):
        short_key = self.note_key_var.get()
        note = self.key_note_input.get()
        if short_key in ("Нет ключей", "Выберите донатера") or not short_key: 
            return
        
        owner_raw = self.note_owner_var.get()
        owner = self.get_clean_nickname(owner_raw)
        if not owner: 
            return
        
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT key_string 
                FROM api_keys 
                WHERE owner_id = (SELECT id FROM owners WHERE nickname=?)
            """, (owner,))
            rows = c.fetchall()
            
            full_key = None
            for k_str, in rows:
                masked = f"{k_str[:10]}...{k_str[-4:]}" if len(k_str) > 15 else k_str
                if masked == short_key or k_str == short_key:
                    full_key = k_str
                    break
                    
            if not full_key:
                return
                
            c.execute("UPDATE api_keys SET notes=? WHERE key_string=?", (note, full_key))
            conn.commit()
        finally:
            conn.close()
            
        self.refresh_db_view()

    # --- УПРАВЛЕНИЕ (CRUD) НА ПРЯМЫХ ЗАПРОСАХ ---
    def on_crud_owner_select(self, choice_raw):
        choice = self.get_clean_nickname(choice_raw)
        if not choice:
            self.crud_key_cb.configure(values=["Нет ключей"])
            self.crud_key_var.set("Нет ключей")
            self.load_crud_key_status("Нет ключей")
            return
            
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("SELECT key_string FROM api_keys JOIN owners ON api_keys.owner_id = owners.id WHERE owners.nickname=?", (choice,))
            keys = [row[0] for row in c.fetchall()]
        finally:
            conn.close()
        
        if keys:
            formatted_keys = [f"{k[:10]}...{k[-4:]}" if len(k) > 15 else k for k in keys]
            self.crud_key_cb.configure(values=formatted_keys)
            self.crud_key_var.set(formatted_keys[0])
            self.load_crud_key_status(formatted_keys[0])
        else:
            self.crud_key_cb.configure(values=["Нет ключей"])
            self.crud_key_var.set("Нет ключей")
            self.load_crud_key_status("Нет ключей")

    def delete_owner(self):
        owner_raw = self.crud_owner_var.get()
        owner = self.get_clean_nickname(owner_raw)
        if owner == "Нет донатеров" or not owner: 
            return
        if not messagebox.askyesno("Удаление донатера", f"ВНИМАНИЕ:\nЭто каскадно удалит донатера {owner} и ВСЕ его ключи из базы данных!\n\nПродолжить?"): 
            return
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("DELETE FROM api_keys WHERE owner_id = (SELECT id FROM owners WHERE nickname=?)", (owner,))
            c.execute("DELETE FROM owners WHERE nickname=?", (owner,))
            conn.commit()
        finally:
            conn.close()
        self.update_owner_dropdowns()
        self.refresh_db_view()

    def reset_owner_statuses(self):
        owner_raw = self.crud_owner_var.get()
        owner = self.get_clean_nickname(owner_raw)
        if owner == "Нет донатеров" or not owner: 
            return
        if not messagebox.askyesno("Сброс донатера", f"Сбросить статус 'Не проверен' для всех ключей донатера {owner}?"): 
            return
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("UPDATE api_keys SET status='UNCHECKED', detail='' WHERE owner_id = (SELECT id FROM owners WHERE nickname=?)", (owner,))
            conn.commit()
        finally:
            conn.close()
        self.refresh_db_view()

    def delete_key(self):
        short_key = self.crud_key_var.get()
        if short_key in ("Нет ключей", "Выберите донатера") or not short_key: 
            return
        
        owner_raw = self.crud_owner_var.get()
        owner = self.get_clean_nickname(owner_raw)
        if not owner: 
            return
        
        conn = connect_db()
        full_key = None
        try:
            c = conn.cursor()
            c.execute("""
                SELECT key_string 
                FROM api_keys 
                WHERE owner_id = (SELECT id FROM owners WHERE nickname=?)
            """, (owner,))
            rows = c.fetchall()
            for k_str, in rows:
                masked = f"{k_str[:10]}...{k_str[-4:]}" if len(k_str) > 15 else k_str
                if masked == short_key or k_str == short_key:
                    full_key = k_str
                    break
        finally:
            conn.close()
            
        if not full_key:
            return
            
        if not messagebox.askyesno("Удаление ключа", f"Удалить выбранный ключ {short_key} из базы данных?"):
            return
            
        conn = connect_db()
        try:
            conn.execute("DELETE FROM api_keys WHERE key_string=?", (full_key,))
            conn.commit()
        finally:
            conn.close()
            
        self.update_owner_dropdowns()
        self.refresh_db_view()

    def reset_key_status(self):
        short_key = self.crud_key_var.get()
        if short_key in ("Нет ключей", "Выберите донатера") or not short_key: 
            return
        
        owner_raw = self.crud_owner_var.get()
        owner = self.get_clean_nickname(owner_raw)
        if not owner: 
            return
        
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT key_string 
                FROM api_keys 
                WHERE owner_id = (SELECT id FROM owners WHERE nickname=?)
            """, (owner,))
            rows = c.fetchall()
            
            full_key = None
            for k_str, in rows:
                masked = f"{k_str[:10]}...{k_str[-4:]}" if len(k_str) > 15 else k_str
                if masked == short_key or k_str == short_key:
                    full_key = k_str
                    break
                    
            if not full_key:
                return
                
            c.execute("UPDATE api_keys SET status='UNCHECKED', detail='' WHERE key_string=?", (full_key,))
            conn.commit()
        finally:
            conn.close()
            
        self.refresh_db_view()

    def reset_all_statuses(self):
        if not messagebox.askyesno("Глобальный сброс", "Сбросить статусы для ВСЕХ ключей?"): 
            return
        conn = connect_db()
        try:
            conn.execute("UPDATE api_keys SET status='UNCHECKED', detail=''")
            conn.commit()
        finally:
            conn.close()
        self.refresh_db_view()

    def delete_broken_keys(self):
        if not messagebox.askyesno("Очистка мертвых", "Удалить все ключи с фатальными ошибками?"): 
            return
        conn = connect_db()
        try:
            conn.execute("DELETE FROM api_keys WHERE status IN ('FAILED_PRECONDITION', 'PERMISSION_DENIED', 'UNAUTHORIZED', 'NOT_FOUND', 'ERROR')")
            conn.commit()
        finally:
            conn.close()
        self.update_owner_dropdowns()
        self.refresh_db_view()

    # --- СВОДКА ПО ДОНАТЕРАМ И ОБНОВЛЕННАЯ ТАБЛИЦА БАЗЫ ДАННЫХ ---
    def refresh_db_view(self):
        filter_val = self.active_db_status_cb.get()
        
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT owners.nickname, 
                       COUNT(api_keys.id) as total,
                       SUM(CASE WHEN api_keys.status = 'OK' THEN 1 ELSE 0 END) as ok_cnt,
                       SUM(CASE WHEN api_keys.status IN ('RESOURCE_EXHAUSTED', 'SERVICE_UNAVAILABLE', 'INTERNAL_ERROR', 'DEADLINE_EXCEEDED', 'TIMEOUT') THEN 1 ELSE 0 END) as yellow_cnt,
                       SUM(CASE WHEN api_keys.status NOT IN ('OK', 'UNCHECKED', 'RESOURCE_EXHAUSTED', 'SERVICE_UNAVAILABLE', 'INTERNAL_ERROR', 'DEADLINE_EXCEEDED', 'TIMEOUT') THEN 1 ELSE 0 END) as red_cnt,
                       SUM(CASE WHEN api_keys.status = 'UNCHECKED' THEN 1 ELSE 0 END) as grey_cnt
                FROM owners 
                LEFT JOIN api_keys ON owners.id = api_keys.owner_id 
                GROUP BY owners.id, owners.nickname
                ORDER BY owners.nickname
            """)
            owner_stats = c.fetchall()
            
            query = '''SELECT owners.nickname, owners.notes, api_keys.key_string, api_keys.status, api_keys.detail, api_keys.notes, api_keys.is_ignored 
                       FROM api_keys JOIN owners ON api_keys.owner_id = owners.id '''
            if "Рабочие" in filter_val: 
                query += "WHERE api_keys.status = 'OK' "
            elif "Временные" in filter_val: 
                query += "WHERE api_keys.status IN ('RESOURCE_EXHAUSTED', 'SERVICE_UNAVAILABLE', 'INTERNAL_ERROR', 'DEADLINE_EXCEEDED', 'TIMEOUT') "
            elif "Нерабочие" in filter_val: 
                query += "WHERE api_keys.status NOT IN ('OK', 'UNCHECKED', 'RESOURCE_EXHAUSTED', 'SERVICE_UNAVAILABLE', 'INTERNAL_ERROR', 'DEADLINE_EXCEEDED', 'TIMEOUT') "
            elif "Не проверенные" in filter_val: 
                query += "WHERE api_keys.status = 'UNCHECKED' "
            query += "ORDER BY owners.nickname, api_keys.status"
            
            c.execute(query)
            rows = c.fetchall()
        finally:
            conn.close()
        
        self.db_view.configure(state="normal")
        self.db_view.delete("0.0", "end")
        
        # 1. Сводная таблица по донатерам
        self.db_view.insert("end", "📊 СВОДКА ПО ДОНАТЕРАМ:\n")
        self.db_view.insert("end", "-"*110 + "\n")
        if owner_stats:
            for nick, total, ok, yellow, red, grey in owner_stats:
                ok = ok or 0; yellow = yellow or 0; red = red or 0; grey = grey or 0
                self.db_view.insert("end", f"👤 {nick:20} | Всего ключей: {total:<3} [ 🟢 {ok:<2} | 🟡 {yellow:<2} | 🔴 {red:<2} | ⏳ {grey:<2} ]\n")
        else:
            self.db_view.insert("end", "Нет зарегистрированных донатеров.\n")
        self.db_view.insert("end", "="*110 + "\n\n")
        
        # 2. Вывод списка ключей
        self.db_view.insert("end", f"📋 СПИСОК КЛЮЧЕЙ ({filter_val}) - Показано: {len(rows)}\n")
        self.db_view.insert("end", "="*110 + "\n")
        
        current_owner = None
        counts = {row[0]: row[1] for row in owner_stats}
        
        for owner, owner_note, key, status, detail, key_note, is_ignored in rows:
            if owner != current_owner:
                current_owner = owner
                owner_keys_cnt = counts.get(owner, 0)
                o_note_str = f" (Заметка: {owner_note})" if owner_note else ""
                self.db_view.insert("end", f"\n👤 {owner}{o_note_str} [Всего ключей: {owner_keys_cnt}]:\n")
                self.db_view.insert("end", "-"*110 + "\n")
                
            status_desc = STATUS_RU.get(status, status)
            masked = f"{key[:10]}...{key[-4:]}" if len(key) > 15 else key
            k_note_str = f" [Заметка к ключу: {key_note}]" if key_note else ""
            detail_str = f" ({detail})" if detail else ""
            ignore_str = " 🚫 [ИГНОРИРУЕТСЯ В СПЛИТТЕРЕ]" if is_ignored == 1 else ""
            line = f"  • {masked} -> {status_desc}{detail_str}{k_note_str}{ignore_str}\n"
            
            tag = "green" if status == "OK" else "yellow" if status in ("RESOURCE_EXHAUSTED", "SERVICE_UNAVAILABLE", "INTERNAL_ERROR", "DEADLINE_EXCEEDED", "TIMEOUT") else None if status == "UNCHECKED" else "red"
            self.db_view.insert("end", line, tag)
            
        self.db_view.configure(state="disabled")

    # --- КРИПТОГРАФИЯ (PBKDF2-HMAC-SHA256 + CTR Keystream + HMAC Tag) ---
    def encrypt_data(self, data_str, password):
        salt = secrets.token_bytes(16)
        derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000, dklen=64)
        enc_key, hmac_key = derived[:32], derived[32:]
        iv = secrets.token_bytes(16)
        data_bytes = data_str.encode('utf-8')
        encrypted_bytes = bytearray()
        
        for block_idx, i in enumerate(range(0, len(data_bytes), 32)):
            counter_bin = block_idx.to_bytes(8, 'big')
            keystream = hashlib.sha256(enc_key + iv + counter_bin).digest()
            chunk = data_bytes[i:i+32]
            for b, k in zip(chunk, keystream): 
                encrypted_bytes.append(b ^ k)
                
        payload_raw = salt + iv + bytes(encrypted_bytes)
        tag = hmac.new(hmac_key, payload_raw, hashlib.sha256).digest()
        return base64.b64encode(payload_raw + tag).decode('utf-8')

    def decrypt_data(self, payload_str, password):
        try:
            payload = base64.b64decode(payload_str.encode('utf-8'))
            if len(payload) < 32: 
                return None
            
            # Попытка расшифровки нового формата с HMAC-тегом (минимум 16+16+32 = 64 байт)
            if len(payload) >= 64:
                tag = payload[-32:]
                payload_raw = payload[:-32]
                salt = payload_raw[:16]
                iv = payload_raw[16:32]
                encrypted_bytes = payload_raw[32:]
                derived = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000, dklen=64)
                enc_key, hmac_key = derived[:32], derived[32:]
                computed_tag = hmac.new(hmac_key, payload_raw, hashlib.sha256).digest()
                
                if hmac.compare_digest(tag, computed_tag):
                    decrypted_bytes = bytearray()
                    for block_idx, i in enumerate(range(0, len(encrypted_bytes), 32)):
                        counter_bin = block_idx.to_bytes(8, 'big')
                        keystream = hashlib.sha256(enc_key + iv + counter_bin).digest()
                        chunk = encrypted_bytes[i:i+32]
                        for b, k in zip(chunk, keystream): 
                            decrypted_bytes.append(b ^ k)
                    return decrypted_bytes.decode('utf-8')
            
            # Обратная совместимость с легаси бэкапами (10k итераций без HMAC)
            salt = payload[:16]
            iv = payload[16:32]
            encrypted_bytes = payload[32:]
            key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 10000)
            decrypted_bytes = bytearray()
            for i in range(0, len(encrypted_bytes), 32):
                counter_bin = i.to_bytes(4, 'big')
                keystream = hashlib.sha256(key + iv + counter_bin).digest()
                chunk = encrypted_bytes[i:i+32]
                for b, k in zip(chunk, keystream): 
                    decrypted_bytes.append(b ^ k)
            return decrypted_bytes.decode('utf-8')
        except Exception: 
            return None

    def export_db(self):
        fmt = self.exp_fmt_var.get()
        pwd = self.exp_pwd_entry.get().strip()
        if "Зашифрованный" in fmt and not pwd:
            messagebox.showerror("Ошибка", "Для зашифрованного экспорта необходимо указать пароль!")
            return
            
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("SELECT id, nickname, notes FROM owners")
            owners_rows = c.fetchall()
            export_data = {"owners": []}
            for o_id, nick, o_notes in owners_rows:
                owner_entry = {"nickname": nick, "notes": o_notes, "keys": []}
                c.execute("SELECT key_string, status, detail, notes, is_ignored FROM api_keys WHERE owner_id=?", (o_id,))
                for k_str, k_status, k_detail, k_notes, k_ign in c.fetchall():
                    owner_entry["keys"].append({
                        "key_string": k_str, 
                        "status": k_status, 
                        "detail": k_detail, 
                        "notes": k_notes,
                        "is_ignored": k_ign
                    })
                export_data["owners"].append(owner_entry)
        finally:
            conn.close()
        
        if "Зашифрованный" in fmt: def_ext = ".enc.json"; file_types = [("Encrypted JSON", "*.enc.json")]
        elif "JSON" in fmt: def_ext = ".json"; file_types = [("JSON File", "*.json")]
        elif "TXT" in fmt: def_ext = ".txt"; file_types = [("Text File", "*.txt")]
        else: def_ext = ".md"; file_types = [("Markdown File", "*.md")]
            
        filename = filedialog.asksaveasfilename(title="Экспортировать базу", defaultextension=def_ext, filetypes=file_types)
        if not filename: 
            return
        
        try:
            if "Зашифрованный" in fmt:
                plain_json = json.dumps(export_data, ensure_ascii=False)
                encrypted = self.encrypt_data(plain_json, pwd)
                with open(filename, "w", encoding="utf-8") as f: 
                    f.write(encrypted)
            elif "JSON" in fmt:
                with open(filename, "w", encoding="utf-8") as f: 
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            elif "TXT" in fmt:
                all_keys = [k["key_string"] for o in export_data["owners"] for k in o["keys"]]
                with open(filename, "w", encoding="utf-8") as f: 
                    f.write("\n".join(all_keys))
            else:
                now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
                md_lines = [f"# База API ключей Gemini (Выгрузка {now_str})\n"]
                for owner in export_data["owners"]:
                    md_lines.append(f"## {owner['nickname']}")
                    if owner['notes']: md_lines.append(f"> Заметка донатера: {owner['notes']}\n")
                    md_lines.append("")
                    for key in owner["keys"]:
                        masked = f"{key['key_string'][:10]}...{key['key_string'][-4:]}"
                        status_str = STATUS_RU.get(key['status'], key['status'])
                        k_note = f" (Заметка: {key['notes']})" if key['notes'] else ""
                        md_lines.append(f"- `{masked}` -> Статус: **{status_str}**{k_note}")
                        md_lines.append(f"  %% {key['key_string']} %%") 
                    md_lines.append("")
                with open(filename, "w", encoding="utf-8") as f: 
                    f.write("\n".join(md_lines))
            messagebox.showinfo("Успех", f"База экспортирована в файл:\n{os.path.basename(filename)}")
        except Exception as e: 
            messagebox.showerror("Ошибка", f"Не удалось выполнить экспорт: {str(e)}")

    def import_db(self):
        fmt = self.imp_fmt_var.get()
        pwd = self.imp_pwd_entry.get().strip()
        if "Зашифрованный" in fmt and not pwd:
            messagebox.showerror("Ошибка", "Для импорта зашифрованного бэкапа укажи пароль!")
            return
        file_types = [("Encrypted JSON", "*.enc.json")] if "Зашифрованный" in fmt else [("JSON File", "*.json")]
        filename = filedialog.askopenfilename(title="Выбрать файл импорта", filetypes=file_types)
        if not filename: 
            return
        try:
            with open(filename, "r", encoding="utf-8") as f: 
                content = f.read().strip()
            if "Зашифрованный" in fmt:
                decrypted = self.decrypt_data(content, pwd)
                if not decrypted:
                    messagebox.showerror("Ошибка", "Неверный пароль или поврежденная структура бэкапа!")
                    return
                import_data = json.loads(decrypted)
            else: 
                import_data = json.loads(content)
                
            if not isinstance(import_data, dict) or "owners" not in import_data or not isinstance(import_data["owners"], list):
                messagebox.showerror("Ошибка", "Некорректная структура файла бэкапа!")
                return
                
            conn = connect_db()
            owners_cnt, keys_cnt = 0, 0
            try:
                c = conn.cursor()
                for owner in import_data.get("owners", []):
                    if not isinstance(owner, dict): 
                        continue
                    nick = owner.get("nickname")
                    notes = owner.get("notes", "")
                    if not nick: 
                        continue
                    try: 
                        c.execute("INSERT INTO owners (nickname, notes) VALUES (?, ?)", (nick, notes))
                        owners_cnt += 1
                    except sqlite3.IntegrityError: 
                        c.execute("UPDATE owners SET notes=? WHERE nickname=?", (notes, nick))
                    
                    c.execute("SELECT id FROM owners WHERE nickname=?", (nick,))
                    row = c.fetchone()
                    if not row: 
                        continue
                    owner_id = row[0]
                    
                    for key in owner.get("keys", []):
                        if not isinstance(key, dict): 
                            continue
                        k_str = key.get("key_string")
                        k_status = key.get("status", "UNCHECKED")
                        k_detail = key.get("detail", "")
                        k_notes = key.get("notes", "")
                        k_ign = key.get("is_ignored", 0)
                        if not k_str: 
                            continue
                        try:
                            c.execute('''INSERT INTO api_keys (owner_id, key_string, status, detail, notes, is_ignored) 
                                         VALUES (?, ?, ?, ?, ?, ?)''', (owner_id, k_str, k_status, k_detail, k_notes, k_ign))
                            keys_cnt += 1
                        except sqlite3.IntegrityError:
                            c.execute('''UPDATE api_keys SET owner_id=?, status=?, detail=?, notes=?, is_ignored=? 
                                         WHERE key_string=?''', (owner_id, k_status, k_detail, k_notes, k_ign, k_str))
                conn.commit()
            finally:
                conn.close()
                
            self.update_owner_dropdowns()
            self.refresh_db_view()
            messagebox.showinfo("Успех", f"Импорт выполнен!\nДобавлено/обновлено донатеров: {owners_cnt}\nИмпортировано ключей: {keys_cnt}")
        except Exception as e: 
            messagebox.showerror("Ошибка", f"Не удалось выполнить импорт: {str(e)}")

    def get_proxy_opener(self, proxy_url):
        parsed = urllib.parse.urlparse(proxy_url)
        scheme = parsed.scheme.lower()
        if "socks" in scheme:
            try:
                import socks
                from sockshandler import SocksiPyHandler
            except ImportError: 
                raise ImportError("Для работы SOCKS прокси требуется библиотека PySocks. Установи её: pip install PySocks")
            socks_type = socks.SOCKS5 if "5" in scheme else socks.SOCKS4
            handler = SocksiPyHandler(socks_type, parsed.hostname, parsed.port, True, parsed.username, parsed.password)
            return urllib.request.build_opener(handler)
        else:
            handler = urllib.request.ProxyHandler({'http': proxy_url, 'https': proxy_url})
            return urllib.request.build_opener(handler)

    def add_custom_model(self):
        dialog = ctk.CTkInputDialog(text="Введи точное название модели (id):", title="Добавить модель")
        new_model = dialog.get_input()
        if new_model and new_model.strip():
            new_model = new_model.strip()
            conn = connect_db()
            try: 
                conn.execute("INSERT INTO models (name) VALUES (?)", (new_model,))
                conn.commit()
            except sqlite3.IntegrityError: 
                pass
            finally:
                conn.close()
            models = get_models_list()
            self.model_cb.configure(values=models)
            self.model_var.set(new_model)

    def check_key_request(self, key, model_name, use_proxy, proxy_url, attempt=1):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        payload = {"contents": [{"parts": [{"text": "hi"}]}]}
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}

        try:
            if use_proxy and proxy_url: 
                opener = self.get_proxy_opener(proxy_url)
            else: 
                opener = urllib.request.build_opener()
        except ImportError as ie: 
            return "ERROR", str(ie)
        except Exception as e: 
            return "ERROR", f"Ошибка прокси-парсера: {str(e)}"

        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with opener.open(req, timeout=TIMEOUT) as response:
                if response.status == 200: 
                    return "OK", ""
        except urllib.error.HTTPError as e:
            try:
                error_body = e.read().decode('utf-8', errors='replace')
            except Exception:
                error_body = ""
                
            try: 
                err_json = json.loads(error_body)
                reason = err_json.get('error', {}).get('message', error_body)
                g_status = err_json.get('error', {}).get('status', '')
            except Exception: 
                reason = error_body
                g_status = ""
            
            if e.code == 400:
                if "failed_precondition" in g_status.lower() or "precondition" in reason.lower():
                    return "FAILED_PRECONDITION", f"Региональный блок. Код Google: {reason}"
                return "ERROR", f"Неверный запрос. Код Google: {reason}"
            elif e.code == 401: 
                return "UNAUTHORIZED", f"Ключ не существует. Код Google: {reason}"
            elif e.code == 403:
                if "unrestricted" in reason.lower(): 
                    return "UNRESTRICTED", f"Блок безопасности от 19 июня. Код Google: {reason}"
                return "PERMISSION_DENIED", f"Отказано в доступе. Код Google: {reason}"
            elif e.code == 404: 
                return "NOT_FOUND", f"Модель не найдена. Код Google: {reason}"
            elif e.code == 429: 
                return "RESOURCE_EXHAUSTED", f"Лимит RPM/TPM исчерпан. Код Google: {reason}"
            elif e.code == 500: 
                return "INTERNAL_ERROR", f"Сбой серверов Google (500). Код Google: {reason}"
            elif e.code in (502, 503): 
                return "SERVICE_UNAVAILABLE", f"Перегрузка мощностей Google ({e.code}). Код Google: {reason}"
            elif e.code == 504: 
                return "DEADLINE_EXCEEDED", f"Таймаут генерации (504). Код Google: {reason}"
            return "ERROR", f"HTTP {e.code}: {reason}"
        except (socket.timeout, urllib.error.URLError):
            if attempt < 2 and self.is_running:
                time.sleep(2)
                return self.check_key_request(key, model_name, use_proxy, proxy_url, attempt + 1)
            err_msg = "Сеть лагает" if not use_proxy else "Прокси не отвечает/лежит"
            return "TIMEOUT", err_msg
        except Exception as e: 
            return "ERROR", str(e)

    def toggle_pause(self):
        if not self.is_running: 
            return
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.btn_pause.configure(text="▶️ Продолжить", fg_color="#c25900", hover_color="#914300")
            self._append_log("⏸️ Проверка приостановлена...")
        else:
            self.btn_pause.configure(text="⏸️ Пауза", fg_color="#1f538d", hover_color="#143e68")
            self._append_log("▶️ Проверка возобновлена.")

    def stop_checking(self):
        if self.is_running:
            self.is_running = False
            self.is_paused = False
            self.btn_pause.configure(text="⏸️ Пауза", fg_color="#1f538d", hover_color="#143e68")
            self._append_log("🛑 Запрос на остановку отправлен. Ожидаем завершения активных потоков...")

    def interruptible_sleep(self, duration):
        end_time = time.time() + duration
        while time.time() < end_time:
            if not self.is_running:
                return
            while self.is_paused and self.is_running:
                time.sleep(0.1)
            time.sleep(0.1)

    def start_checking(self, selective=False):
        if self.is_running: 
            return
        self.is_running = True
        self.is_paused = False
        self.ping_selective = selective
        
        # Считываем все переменные GUI на основном потоке
        model_name = self.model_var.get().strip()
        delay_min_raw = self.delay_min_var.get()
        delay_max_raw = self.delay_max_var.get()
        use_proxy = self.proxy_use_var.get()
        proxy_url = self.proxy_url_var.get().strip()
        threads_raw = self.threads_var.get().strip()
        select_val = self.ping_select_var.get()
        
        save_setting("current_model", model_name)
        save_setting("delay_min", delay_min_raw)
        save_setting("delay_max", delay_max_raw)
        save_setting("proxy_use", "1" if use_proxy else "0")
        save_setting("proxy_url", proxy_url)
        save_setting("checker_threads", threads_raw)
        
        self.btn_start.configure(state="disabled")
        self.btn_ping_selective.configure(state="disabled")
        self.log_box.configure(state="normal")
        self.log_box.delete("0.0", "end")
        self.log_box.configure(state="disabled")
        
        threading.Thread(
            target=self.worker_thread, 
            args=(model_name, use_proxy, proxy_url, delay_min_raw, delay_max_raw, threads_raw, selective, select_val),
            daemon=True
        ).start()

    def check_single_key_task(self, k_id, key_str, model_name, use_proxy, proxy_url, d_min, d_max, total_keys):
        while self.is_paused and self.is_running: 
            time.sleep(0.1)
        if not self.is_running: 
            return
        
        status, detail = self.check_key_request(key_str, model_name, use_proxy, proxy_url)
        
        while self.is_paused and self.is_running: 
            time.sleep(0.1)
        if not self.is_running: 
            return
        
        conn = connect_db()
        try:
            conn.execute("UPDATE api_keys SET status=?, detail=? WHERE id=?", (status, detail, k_id))
            conn.commit()
        finally:
            conn.close()
        
        tag = "green" if status == "OK" else "yellow" if status in ("RESOURCE_EXHAUSTED", "SERVICE_UNAVAILABLE", "INTERNAL_ERROR", "DEADLINE_EXCEEDED", "TIMEOUT") else "red"
        status_desc = STATUS_RU.get(status, status)
        masked = f"{key_str[:10]}...{key_str[-4:]}" if len(key_str) > 15 else key_str
        
        with self.counter_lock:
            self.checked_count += 1
            curr_idx = self.checked_count
            
        self.safe_after(0, lambda t=f"[{curr_idx}/{total_keys}] {masked} -> {status_desc}", tg=tag: self._append_log(t, tg))
        self.safe_after(0, lambda idx=curr_idx, t=total_keys: self.chk_stats.configure(text=f"Проверено: {idx}/{t}"))
        
        sleep_dur = random.uniform(d_min, d_max)
        self.interruptible_sleep(sleep_dur)

    def worker_thread(self, model_name, use_proxy, proxy_url, delay_min_raw, delay_max_raw, threads_raw, is_selective, select_val):
        try: 
            d_min = float(delay_min_raw)
            d_max = float(delay_max_raw)
        except ValueError: 
            d_min, d_max = 7.0, 10.0
            self.safe_after(0, lambda: self._append_log("⚠️ Ошибка таймингов. Используется дефолт 7-10 сек."))

        try: 
            num_threads = int(threads_raw)
        except ValueError: 
            num_threads = 1
            self.safe_after(0, lambda: self._append_log("⚠️ Ошибка потоков. Используется дефолт: 1 поток."))
        if num_threads < 1: 
            num_threads = 1

        conn = connect_db()
        try:
            c = conn.cursor()
            if is_selective:
                self.safe_after(0, lambda s=select_val: self._append_log(f"🎯 Запуск ВЫБОРОЧНОЙ проверки: {s}"))
                if "Только Серые" in select_val: 
                    c.execute("SELECT id, key_string FROM api_keys WHERE status = 'UNCHECKED'")
                elif "Только Желтые" in select_val: 
                    c.execute("SELECT id, key_string FROM api_keys WHERE status IN ('RESOURCE_EXHAUSTED', 'SERVICE_UNAVAILABLE', 'INTERNAL_ERROR', 'DEADLINE_EXCEEDED', 'TIMEOUT')")
                elif "Только Красные" in select_val: 
                    c.execute("SELECT id, key_string FROM api_keys WHERE status NOT IN ('OK', 'UNCHECKED', 'RESOURCE_EXHAUSTED', 'SERVICE_UNAVAILABLE', 'INTERNAL_ERROR', 'DEADLINE_EXCEEDED', 'TIMEOUT')")
                elif "Желтые + Серые" in select_val: 
                    c.execute("SELECT id, key_string FROM api_keys WHERE status = 'UNCHECKED' OR status IN ('RESOURCE_EXHAUSTED', 'SERVICE_UNAVAILABLE', 'INTERNAL_ERROR', 'DEADLINE_EXCEEDED', 'TIMEOUT')")
                elif "Все нерабочие" in select_val: 
                    c.execute("SELECT id, key_string FROM api_keys WHERE status != 'OK'")
                else: 
                    c.execute("SELECT id, key_string FROM api_keys")
            else:
                self.safe_after(0, lambda: self._append_log("🚀 Запуск ПОЛНОЙ проверки всех ключей..."))
                c.execute("SELECT id, key_string FROM api_keys")
                
            keys = c.fetchall()
        finally:
            conn.close()
        
        total = len(keys)
        self.checked_count = 0
        
        if total == 0:
            self.safe_after(0, lambda: self._append_log("База пуста или в ней нет подходящих ключей под выбранный фильтр! Пинг отменен."))
            self.is_running = False
            self.safe_after(0, lambda: self.btn_start.configure(state="normal"))
            self.safe_after(0, lambda: self.btn_ping_selective.configure(state="normal"))
            self.safe_after(0, lambda: self.btn_pause.configure(state="disabled", text="⏸️ Пауза", fg_color="#1f538d", hover_color="#143e68"))
            self.safe_after(0, lambda: self.btn_stop.configure(state="disabled"))
            return

        self.safe_after(0, lambda: self.btn_pause.configure(state="normal"))
        self.safe_after(0, lambda: self.btn_stop.configure(state="normal"))

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            for k_id, key_str in keys:
                if not self.is_running: 
                    break
                futures.append(executor.submit(self.check_single_key_task, k_id, key_str, model_name, use_proxy, proxy_url, d_min, d_max, total))
            for future in futures:
                if not self.is_running:
                    for f in futures: 
                        f.cancel()
                    break
                try: 
                    future.result()
                except Exception as e: 
                    self.safe_after(0, lambda err=str(e): self._append_log(f"❌ Ошибка в потоке: {err}"))

        self.is_running = False
        self.safe_after(0, lambda: self.btn_start.configure(state="normal"))
        self.safe_after(0, lambda: self.btn_ping_selective.configure(state="normal"))
        self.safe_after(0, lambda: self.btn_pause.configure(state="disabled", text="⏸️ Пауза", fg_color="#1f538d", hover_color="#143e68"))
        self.safe_after(0, lambda: self.btn_stop.configure(state="disabled"))
        self.safe_after(0, lambda: self._append_log("\n🏁 Проверка завершена! База данных обновлена."))

    def _append_log(self, text, tag=None):
        try:
            self.log_box.configure(state="normal")
            if tag: 
                self.log_box.insert("end", text + "\n", tag)
            else: 
                self.log_box.insert("end", text + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        except Exception:
            pass

    # --- ЛОГИКА ДИНАМИЧЕСКОГО СПЛИТТЕРА ---
    def do_split(self):
        try:
            num_streams = int(self.streams_count_var.get())
            if num_streams < 1: 
                num_streams = 3
        except ValueError:
            num_streams = 3

        save_setting("splitter_streams", str(num_streams))
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("SELECT key_string FROM api_keys WHERE status='OK' AND is_ignored=0")
            valid_keys = [row[0] for row in c.fetchall()]
        finally:
            conn.close()

        self.stream_preview_box.configure(state="normal")
        self.stream_preview_box.delete("0.0", "end")

        if not valid_keys:
            self.split_results = {}
            self.stream_preview_box.insert("end", "В базе нет свободных рабочих ключей (OK)! Либо все ключи игнорируются.")
            self.stream_preview_box.configure(state="disabled")
            self.active_stream_cb.configure(values=["Нет потоков"])
            self.active_stream_var.set("Нет потоков")
            return

        self.split_results = {i: [] for i in range(1, num_streams + 1)}
        for idx, key in enumerate(valid_keys):
            stream_id = (idx % num_streams) + 1
            self.split_results[stream_id].append(key)

        stream_options = [f"Поток {i} ({len(self.split_results[i])} шт.)" for i in range(1, num_streams + 1)]
        self.active_stream_cb.configure(values=stream_options)
        self.active_stream_var.set(stream_options[0])
        self.show_stream_preview(stream_options[0])

    def show_stream_preview(self, choice):
        if choice == "Нет потоков" or not choice: 
            return
        m = re.search(r'\d+', choice)
        if not m:
            return
        stream_idx = int(m.group(0))
        keys = self.split_results.get(stream_idx, [])
        self.stream_preview_box.configure(state="normal")
        self.stream_preview_box.delete("0.0", "end")
        self.stream_preview_box.insert("end", "\n".join(keys))
        self.stream_preview_box.configure(state="disabled")

    def copy_selected_stream(self):
        choice = self.active_stream_var.get()
        if choice == "Нет потоков" or not choice: 
            return
        m = re.search(r'\d+', choice)
        if not m:
            return
        stream_idx = int(m.group(0))
        keys = self.split_results.get(stream_idx, [])
        if keys:
            self.clipboard_clear()
            self.clipboard_append("\n".join(keys))
            self.update()

    def export_all_streams(self):
        if not self.split_results: 
            messagebox.showinfo("Информация", "Сначала выполни распределение ключей (кнопка '🔀 Распределить ключи')!")
            return
        exported_files = 0
        for stream_idx, keys in self.split_results.items():
            if not keys:
                continue
            filename = f"valid_keys_stream_{stream_idx}.txt"
            with open(filename, "w", encoding="utf-8") as f: 
                f.write("\n".join(keys))
            exported_files += 1
            
        self.show_frame("checker")
        self._append_log(f"💾 Экспорт завершен! Сгенерировано {exported_files} файлов в директорию скрипта.")

    # --- ПРЯМАЯ SQL-ЛОГИКА ПРОСМОТРА И ИГНОРИРОВАНИЯ КЛЮЧЕЙ ---
    def load_crud_key_status(self, short_key):
        if short_key in ("Нет ключей", "Выберите донатера") or not short_key:
            self.crud_full_key_entry.configure(state="normal")
            self.crud_full_key_entry.delete(0, "end")
            self.crud_key_ignore_var.set(False)
            return
            
        owner_raw = self.crud_owner_var.get()
        owner = self.get_clean_nickname(owner_raw)
        if not owner: 
            return
        
        conn = connect_db()
        full_key = None
        is_ignored = 0
        try:
            c = conn.cursor()
            c.execute("""
                SELECT key_string, is_ignored 
                FROM api_keys 
                WHERE owner_id = (SELECT id FROM owners WHERE nickname=?)
            """, (owner,))
            rows = c.fetchall()
            for k_str, ignored in rows:
                masked = f"{k_str[:10]}...{k_str[-4:]}" if len(k_str) > 15 else k_str
                if masked == short_key or k_str == short_key:
                    full_key = k_str
                    is_ignored = ignored
                    break
        finally:
            conn.close()
                
        if not full_key: 
            return
        
        self.crud_full_key_entry.configure(state="normal")
        self.crud_full_key_entry.delete(0, "end")
        self.crud_full_key_entry.insert(0, full_key)
        self.crud_key_ignore_var.set(is_ignored == 1)

    def toggle_ignore_key(self):
        short_key = self.crud_key_var.get()
        if short_key in ("Нет ключей", "Выберите донатера") or not short_key: 
            return
        
        owner_raw = self.crud_owner_var.get()
        owner = self.get_clean_nickname(owner_raw)
        if not owner: 
            return
        
        conn = connect_db()
        try:
            c = conn.cursor()
            c.execute("""
                SELECT key_string 
                FROM api_keys 
                WHERE owner_id = (SELECT id FROM owners WHERE nickname=?)
            """, (owner,))
            rows = c.fetchall()
            
            full_key = None
            for k_str, in rows:
                masked = f"{k_str[:10]}...{k_str[-4:]}" if len(k_str) > 15 else k_str
                if masked == short_key or k_str == short_key:
                    full_key = k_str
                    break
                    
            if not full_key:
                return
                
            ignored_state = 1 if self.crud_key_ignore_var.get() else 0
            c.execute("UPDATE api_keys SET is_ignored=? WHERE key_string=?", (ignored_state, full_key))
            conn.commit()
        finally:
            conn.close()
            
        self.refresh_db_view()

    def on_closing(self):
        self.is_running = False
        self.is_paused = False
        try:
            if self.guide_win is not None and self.guide_win.winfo_exists():
                self.guide_win.destroy()
        except Exception:
            pass
        self.destroy()

if __name__ == "__main__":
    app = GeminiNexus()
    app.mainloop()
