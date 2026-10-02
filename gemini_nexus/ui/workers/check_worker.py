"""Thread-safe background QThread worker for batch Gemini API key validation."""

import random
import time
from typing import Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from gemini_nexus.core.checker import check_api_key


class CheckWorker(QThread):
    """Background worker executing network requests for API key verification."""

    # Qt Signals for thread-safe UI updates
    progress_updated = pyqtSignal(int, int)  # current, total
    stats_updated = pyqtSignal(dict)  # stats summary dictionary
    log_emitted = pyqtSignal(str, str)  # log message, tag
    key_finished = pyqtSignal(int, str, str)  # key_id, status, detail
    all_finished = pyqtSignal()

    def __init__(
        self,
        keys_to_check: list[dict[str, Any]],
        model: str,
        proxy_url: str | None = None,
        delay_min: float = 7.0,
        delay_max: float = 10.0,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.keys = list(keys_to_check)
        self.model = model
        self.proxy_url = proxy_url
        self.delay_min = min(delay_min, delay_max)
        self.delay_max = max(delay_min, delay_max)
        self._is_running = True
        self._is_paused = False

    def pause(self) -> None:
        """Pause worker processing before the next key request."""
        self._is_paused = True

    def resume(self) -> None:
        """Resume paused worker processing."""
        self._is_paused = False

    def stop(self) -> None:
        """Immediately flag worker for interruption and cancellation."""
        self._is_running = False
        self._is_paused = False

    def run(self) -> None:
        """Worker thread main loop."""
        total = len(self.keys)
        stats = {
            "total": total,
            "checked": 0,
            "ok": 0,
            "limits": 0,
            "dead": 0,
            "errors": 0,
        }

        self.log_emitted.emit(
            f"Старт проверки {total} ключей через модель [{self.model}]...",
            "SYS",
        )

        for index, item in enumerate(self.keys):
            # Pause check loop
            while self._is_paused and self._is_running:
                time.sleep(0.1)

            # Cancellation check
            if not self._is_running:
                self.log_emitted.emit(
                    "Проверка принудительно остановлена пользователем.",
                    "WARN",
                )
                break

            if isinstance(item, dict):
                k_id = item.get("id", index + 1)
                k_str = item.get("key_string", item.get("key", ""))
            else:
                k_id = getattr(item, "id", index + 1)
                k_str = getattr(item, "key_string", str(item))

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
            self.stats_updated.emit(dict(stats))

            # Delay between requests (interruptible)
            if index < total - 1 and self._is_running:
                delay = random.uniform(self.delay_min, self.delay_max)
                end_time = time.time() + delay
                while time.time() < end_time and self._is_running:
                    time.sleep(0.05)

        if self._is_running:
            self.log_emitted.emit("Процесс проверки полностью завершен.", "SYS")

        self.all_finished.emit()
