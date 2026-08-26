#!/usr/bin/env bash
# ==============================================================================
# Gemini Nexus DB (ping_keys) - Universal Launcher
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
# Защита от read-only кэша шрифтов CustomTkinter в ~/.fonts
chmod 644 "$HOME/.fonts"/Roboto-*.ttf "$HOME/.fonts"/CustomTkinter_shapes_font.otf 2>/dev/null || true


APP_SCRIPT="ping_keys_NeuroStarNet_v13.9.py"

if [ ! -f "$APP_SCRIPT" ]; then
    echo "❌ Ошибка: Файл $APP_SCRIPT не найден в $SCRIPT_DIR" >&2
    exit 1
fi

# 1. Проверяем, работает ли текущий python3 из окружения (например, direnv / nix-shell)
if command -v python3 >/dev/null 2>&1; then
    if python3 -c "import tkinter, customtkinter, socks" >/dev/null 2>&1; then
        exec python3 "$APP_SCRIPT" "$@"
    fi
fi

# 2. Проверяем локальный .venv
if [ -f "$SCRIPT_DIR/.venv/bin/python3" ]; then
    if "$SCRIPT_DIR/.venv/bin/python3" -c "import tkinter, customtkinter, socks" >/dev/null 2>&1; then
        exec "$SCRIPT_DIR/.venv/bin/python3" "$APP_SCRIPT" "$@"
    fi
fi

# 3. Если мы на NixOS / есть nix, используем nix-shell или пересоздаем .venv
if command -v nix-shell >/dev/null 2>&1; then
    echo "⚙️ Запуск через Nix окружение (customtkinter + pysocks + tkinter)..."
    
    # Если .venv нет или он поврежден, создаем его автоматически для быстрого повторного запуска
    if [ ! -d "$SCRIPT_DIR/.venv" ]; then
        echo "📦 Инициализация локального .venv из системного Nix-окружения..."
        nix-shell -p 'python3.withPackages (ps: with ps; [ customtkinter pysocks tkinter ])' \
            --run "python3 -m venv '$SCRIPT_DIR/.venv' --system-site-packages" >/dev/null 2>&1 || true
    fi

    if [ -f "$SCRIPT_DIR/.venv/bin/python3" ] && "$SCRIPT_DIR/.venv/bin/python3" -c "import tkinter, customtkinter, socks" >/dev/null 2>&1; then
        exec "$SCRIPT_DIR/.venv/bin/python3" "$APP_SCRIPT" "$@"
    fi

    exec nix-shell -p 'python3.withPackages (ps: with ps; [ customtkinter pysocks tkinter ])' \
        --run "python3 '$SCRIPT_DIR/$APP_SCRIPT' $*"
fi

# 4. Fallback: обычный venv с pip
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "📦 Создание виртуального окружения .venv..."
    python3 -m venv "$SCRIPT_DIR/.venv"
    "$SCRIPT_DIR/.venv/bin/pip" install --upgrade pip
    "$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

exec "$SCRIPT_DIR/.venv/bin/python3" "$APP_SCRIPT" "$@"
