#!/usr/bin/env bash
# ==============================================================================
# Gemini Nexus DB (ping_keys) - Universal Launcher
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

export QT_QPA_PLATFORM="wayland;xcb"

if [ ! -d "$SCRIPT_DIR/gemini_nexus" ]; then
    echo "❌ Ошибка: Пакет gemini_nexus не найден в $SCRIPT_DIR" >&2
    exit 1
fi

# 1. Проверяем, работает ли текущий python3 из окружения (например, direnv / nix-shell)
if command -v python3 >/dev/null 2>&1; then
    if python3 -c "import PyQt6, qdarktheme, socks" >/dev/null 2>&1; then
        exec python3 -m gemini_nexus.main "$@"
    fi
fi

# 2. Проверяем локальный .venv
if [ -f "$SCRIPT_DIR/.venv/bin/python3" ]; then
    if "$SCRIPT_DIR/.venv/bin/python3" -c "import PyQt6, qdarktheme, socks" >/dev/null 2>&1; then
        exec "$SCRIPT_DIR/.venv/bin/python3" -m gemini_nexus.main "$@"
    fi
fi

# 3. Если мы на NixOS / есть nix, используем nix-shell или пересоздаем .venv
if command -v nix-shell >/dev/null 2>&1; then
    echo "⚙️ Запуск через Nix окружение (PyQt6 + pyqtdarktheme + PySocks + Wayland)..."

    # Если .venv нет или он поврежден, создаем его автоматически для быстрого повторного запуска
    if [ ! -d "$SCRIPT_DIR/.venv" ]; then
        echo "📦 Инициализация локального .venv из системного Nix-окружения..."
        nix-shell -p python3Packages.pyqt6 python3Packages.pyqtdarktheme python3Packages.pysocks qt6.qtwayland \
            --run "python3 -m venv '$SCRIPT_DIR/.venv' --system-site-packages" >/dev/null 2>&1 || true
    fi

    if [ -f "$SCRIPT_DIR/.venv/bin/python3" ] && "$SCRIPT_DIR/.venv/bin/python3" -c "import PyQt6, qdarktheme, socks" >/dev/null 2>&1; then
        exec "$SCRIPT_DIR/.venv/bin/python3" -m gemini_nexus.main "$@"
    fi

    exec nix-shell -p python3Packages.pyqt6 python3Packages.pyqtdarktheme python3Packages.pysocks qt6.qtwayland \
        --run "python3 -m gemini_nexus.main $*"
fi

# 4. Fallback: обычный venv с pip
if [ ! -d "$SCRIPT_DIR/.venv" ]; then
    echo "📦 Создание виртуального окружения .venv..."
    python3 -m venv "$SCRIPT_DIR/.venv"
    "$SCRIPT_DIR/.venv/bin/pip" install --upgrade pip
    "$SCRIPT_DIR/.venv/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

exec "$SCRIPT_DIR/.venv/bin/python3" -m gemini_nexus.main "$@"
